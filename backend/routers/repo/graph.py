import logging
from collections import Counter
from typing import Optional, List, Dict, Any, Set
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.database import get_db
from backend.models.user import User
from backend.dependencies.auth import get_current_user
from backend.routers.repo.schemas import GraphQueryRequest
from backend.routers.repo.services.hash_resolution import get_latest_analysis_by_hash
from backend.routers.repo.services.analysis import get_latest_analysis
from backend.intelligence.graphs.graph_query_service import GraphQueryService
from backend.intelligence.rim.serialization import deserialize_rim
from backend.models.repository import AnalysisArtifact
from backend.models.fact_store import (
    FactFile,
    FactSymbol,
    FactRelationship,
    FactRoute,
    FactDatabaseObject,
    FactCapability,
    FactCapabilityMember,
)

logger = logging.getLogger(__name__)

graph_router = APIRouter(tags=["graph"])


@graph_router.get("/{repo_name}/knowledge-graph")
def get_knowledge_graph(
    repo_name: str,
    view: str = Query("all", description="View mode: all, calls, imports, routes, capabilities, structure"),
    search: Optional[str] = Query(None, description="Search term to highlight/filter nodes"),
    limit: int = Query(400, ge=10, le=1500, description="Max nodes to return"),
    rel_types: Optional[str] = Query(None, description="Comma-separated relationship types to include"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the comprehensive Knowledge Graph constructed from the Layer 4 Fact Store.
    Supports filtering by architectural view, relationship types, node types, and text search.
    """
    try:
        repo, analysis = get_latest_analysis(repo_name, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[KNOWLEDGE_GRAPH] Failed to resolve repository {repo_name}: {e}")
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    analysis_id = analysis.id
    logger.info(f"[KNOWLEDGE_GRAPH] Loading graph for repo='{repo_name}', analysis_id={analysis_id}, view='{view}'")

    # 1. Fetch Fact Store tables for this analysis
    files = db.query(FactFile).filter(FactFile.analysis_id == analysis_id).all()
    symbols = db.query(FactSymbol).filter(FactSymbol.analysis_id == analysis_id).all()
    rels = db.query(FactRelationship).filter(FactRelationship.analysis_id == analysis_id).all()
    routes = db.query(FactRoute).filter(FactRoute.analysis_id == analysis_id).all()
    db_objects = db.query(FactDatabaseObject).filter(FactDatabaseObject.analysis_id == analysis_id).all()
    capabilities = db.query(FactCapability).filter(FactCapability.analysis_id == analysis_id).all()
    cap_members = (
        db.query(FactCapabilityMember)
        .filter(FactCapabilityMember.capability_id.in_([c.id for c in capabilities]))
        .all()
        if capabilities
        else []
    )

    file_map: Dict[str, FactFile] = {f.id: f for f in files}
    sym_map: Dict[str, FactSymbol] = {s.id: s for s in symbols}

    view_str = view if isinstance(view, str) else "all"
    limit_val = limit if isinstance(limit, int) else 400
    search_str = search if isinstance(search, str) else None

    # Summary statistics
    rel_type_counter = Counter(r.rel_type for r in rels)
    sym_type_counter = Counter(s.symbol_type.upper() for s in symbols)

    # 2. Determine allowed relationship types based on view or filter
    allowed_rel_types: Optional[Set[str]] = None
    if isinstance(rel_types, str) and rel_types.strip():
        allowed_rel_types = {t.strip().upper() for t in rel_types.split(",") if t.strip()}
    elif view_str == "calls":
        allowed_rel_types = {"CALLS"}
    elif view_str == "imports":
        allowed_rel_types = {"IMPORTS"}
    elif view_str == "structure":
        allowed_rel_types = {"DECLARES", "CONTAINS", "INHERITS"}
    elif view_str == "routes":
        allowed_rel_types = {"ROUTE_HANDLER", "CALLS", "EXPOSES"}
    elif view_str == "capabilities":
        allowed_rel_types = {"CAPABILITY_MEMBER", "CALLS", "DATABASE_ACCESS"}

    # 3. Collect active edges
    raw_edges: List[Dict[str, Any]] = []
    for r in rels:
        rtype = (r.rel_type or "GENERIC").upper()
        if allowed_rel_types and rtype not in allowed_rel_types:
            continue
        raw_edges.append({
            "id": r.id,
            "source": r.from_symbol_id,
            "target": r.to_symbol_id,
            "type": rtype,
            "evidence_line": r.evidence_line,
            "status": r.status or "CONFIRMED",
        })

    # Add synthetic route handler edges
    for route in routes:
        handler_id = route.handler_symbol_id or route.symbol_id
        if handler_id and (not allowed_rel_types or "ROUTE_HANDLER" in allowed_rel_types):
            route_node_id = f"route:{route.id}"
            raw_edges.append({
                "id": f"e-route-{route.id}",
                "source": route_node_id,
                "target": handler_id,
                "type": "ROUTE_HANDLER",
                "evidence_line": None,
                "status": "CONFIRMED",
            })

    # Add synthetic capability member edges
    for m in cap_members:
        if not allowed_rel_types or "CAPABILITY_MEMBER" in allowed_rel_types:
            cap_node_id = f"cap:{m.capability_id}"
            raw_edges.append({
                "id": f"e-cap-{m.id}",
                "source": cap_node_id,
                "target": m.symbol_id,
                "type": "CAPABILITY_MEMBER",
                "label": m.role or "member",
                "evidence_line": None,
                "status": "CONFIRMED",
            })

    # 4. Filter allowed node types if specified
    allowed_node_types: Optional[Set[str]] = None
    if isinstance(node_types, str) and node_types.strip():
        allowed_node_types = {t.strip().upper() for t in node_types.split(",") if t.strip()}

    # 5. Build full node registry
    all_nodes: Dict[str, Dict[str, Any]] = {}

    for s in symbols:
        stype = (s.symbol_type or "symbol").upper()
        if allowed_node_types and stype not in allowed_node_types:
            continue
        fpath = s.file.path if s.file else (file_map.get(s.file_id).path if s.file_id in file_map else "")
        all_nodes[s.id] = {
            "id": s.id,
            "name": s.name,
            "label": s.name,
            "full_name": s.qualified_name or s.name,
            "type": stype,
            "file": fpath,
            "line_start": s.line_start,
            "line_end": s.line_end,
            "metadata": {"signature_hash": s.signature_hash},
        }

    for f in files:
        if allowed_node_types and "FILE" not in allowed_node_types:
            continue
        basename = f.path.split("/")[-1] if "/" in f.path else f.path
        all_nodes[f.id] = {
            "id": f.id,
            "name": basename,
            "label": basename,
            "full_name": f.path,
            "type": "FILE",
            "file": f.path,
            "language": f.language,
            "size": f.size,
            "metadata": {"is_test": f.is_test, "is_doc": f.is_documentation},
        }

    for route in routes:
        if allowed_node_types and "ROUTE" not in allowed_node_types:
            continue
        route_node_id = f"route:{route.id}"
        all_nodes[route_node_id] = {
            "id": route_node_id,
            "name": f"{route.method} {route.path}",
            "label": f"{route.method} {route.path}",
            "full_name": f"{route.method} {route.path}",
            "type": "ROUTE",
            "method": route.method,
            "path": route.path,
            "metadata": {"handler_symbol_id": route.handler_symbol_id},
        }

    for db_obj in db_objects:
        if allowed_node_types and "DATABASE_OBJECT" not in allowed_node_types:
            continue
        db_id = db_obj.id or f"db:{db_obj.name}"
        all_nodes[db_id] = {
            "id": db_id,
            "name": db_obj.name,
            "label": db_obj.name,
            "full_name": db_obj.name,
            "type": "DATABASE_OBJECT",
            "object_type": db_obj.object_type,
            "metadata": {},
        }

    for cap in capabilities:
        if allowed_node_types and "CAPABILITY" not in allowed_node_types:
            continue
        cap_node_id = f"cap:{cap.id}"
        all_nodes[cap_node_id] = {
            "id": cap_node_id,
            "name": cap.name,
            "label": cap.name,
            "full_name": cap.name,
            "type": "CAPABILITY",
            "capability_type": cap.capability_type,
            "summary": cap.evidence_summary,
            "metadata": {"status": cap.status},
        }

    # 6. Filter edges: both endpoints must exist in all_nodes
    valid_edges: List[Dict[str, Any]] = []
    in_degrees: Counter = Counter()
    out_degrees: Counter = Counter()

    for e in raw_edges:
        src = e["source"]
        tgt = e["target"]
        if src in all_nodes and tgt in all_nodes:
            valid_edges.append(e)
            out_degrees[src] += 1
            in_degrees[tgt] += 1

    # 7. Apply search / focus filter if provided
    selected_node_ids: Set[str] = set()
    if search_str and search_str.strip():
        q = search_str.strip().lower()
        matching_seed_ids = {
            nid for nid, n in all_nodes.items()
            if q in n["name"].lower() or q in n.get("file", "").lower() or q in n.get("full_name", "").lower()
        }
        # Include seed matches + their 1-hop connected neighbors
        selected_node_ids = set(matching_seed_ids)
        for e in valid_edges:
            if e["source"] in matching_seed_ids:
                selected_node_ids.add(e["target"])
            elif e["target"] in matching_seed_ids:
                selected_node_ids.add(e["source"])
    else:
        # If no search, include nodes connected by valid edges first
        for e in valid_edges:
            selected_node_ids.add(e["source"])
            selected_node_ids.add(e["target"])

        # If graph is still small, fill with standalone files or classes up to limit
        if len(selected_node_ids) < limit_val:
            for nid, n in all_nodes.items():
                if n["type"] in ("CLASS", "FILE", "ROUTE", "CAPABILITY"):
                    selected_node_ids.add(nid)
                if len(selected_node_ids) >= limit_val:
                    break

    # 8. Sort nodes by connectivity (highest degree first) if over limit
    node_degrees = {nid: in_degrees[nid] + out_degrees[nid] for nid in selected_node_ids}
    sorted_node_ids = sorted(selected_node_ids, key=lambda nid: node_degrees.get(nid, 0), reverse=True)
    capped_node_ids = set(sorted_node_ids[:limit_val])

    # Filter edges to only those connecting capped nodes
    final_edges: List[Dict[str, Any]] = [
        e for e in valid_edges
        if e["source"] in capped_node_ids and e["target"] in capped_node_ids
    ]

    # Format final nodes
    final_nodes: List[Dict[str, Any]] = []
    final_node_type_counter: Counter = Counter()

    for nid in capped_node_ids:
        n = all_nodes[nid]
        n_copy = dict(n)
        n_copy["in_degree"] = in_degrees.get(nid, 0)
        n_copy["out_degree"] = out_degrees.get(nid, 0)
        n_copy["total_degree"] = in_degrees.get(nid, 0) + out_degrees.get(nid, 0)
        final_nodes.append(n_copy)
        final_node_type_counter[n["type"]] += 1

    # Top connected hub nodes for quick overview
    top_hubs = [
        {
            "id": nid,
            "name": all_nodes[nid]["name"],
            "type": all_nodes[nid]["type"],
            "file": all_nodes[nid].get("file", ""),
            "degree": node_degrees.get(nid, 0),
        }
        for nid in sorted_node_ids[:10]
        if nid in all_nodes
    ]

    # Final relationship counter on returned edges
    final_rel_counter = Counter(e["type"] for e in final_edges)

    return {
        "repo_name": repo.name if hasattr(repo, "name") and repo.name else repo.url.split("/")[-1].replace(".git", ""),
        "repo_hash": repo.repository_hash,
        "analysis_id": analysis_id,
        "view": view,
        "stats": {
            "returned_nodes": len(final_nodes),
            "returned_edges": len(final_edges),
            "raw_total_files": len(files),
            "raw_total_symbols": len(symbols),
            "raw_total_relationships": len(rels),
            "raw_total_routes": len(routes),
            "raw_total_capabilities": len(capabilities),
            "raw_total_database_objects": len(db_objects),
            "relationship_counts": dict(final_rel_counter),
            "total_relationship_counts": dict(rel_type_counter),
            "node_type_counts": dict(final_node_type_counter),
            "top_hubs": top_hubs,
        },
        "nodes": final_nodes,
        "edges": final_edges,
    }


@graph_router.get("/{repo_name}/knowledge-graph/node/{node_id:path}")
def get_knowledge_graph_node(
    repo_name: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve comprehensive details for an individual Knowledge Graph node,
    including its declaration, location, incoming callers/importers, and outgoing callees/imports.
    """
    repo, analysis = get_latest_analysis(repo_name, db, current_user)
    analysis_id = analysis.id

    # Try FactSymbol
    symbol = db.query(FactSymbol).filter(
        FactSymbol.analysis_id == analysis_id,
        FactSymbol.id == node_id,
    ).first()

    # Try FactFile
    file_obj = None
    if not symbol:
        file_obj = db.query(FactFile).filter(
            FactFile.analysis_id == analysis_id,
            FactFile.id == node_id,
        ).first()

    # Try FactRoute
    route_obj = None
    if not symbol and not file_obj and node_id.startswith("route:"):
        r_id = node_id.split("route:", 1)[1]
        route_obj = db.query(FactRoute).filter(
            FactRoute.analysis_id == analysis_id,
            FactRoute.id == r_id,
        ).first()

    # Try FactCapability
    cap_obj = None
    if not symbol and not file_obj and not route_obj and node_id.startswith("cap:"):
        c_id = node_id.split("cap:", 1)[1]
        cap_obj = db.query(FactCapability).filter(
            FactCapability.analysis_id == analysis_id,
            FactCapability.id == c_id,
        ).first()

    if not symbol and not file_obj and not route_obj and not cap_obj:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in repository graph")

    # Format primary node info
    if symbol:
        fpath = symbol.file.path if symbol.file else ""
        node_info = {
            "id": symbol.id,
            "name": symbol.name,
            "full_name": symbol.qualified_name or symbol.name,
            "type": symbol.symbol_type.upper(),
            "file": fpath,
            "line_start": symbol.line_start,
            "line_end": symbol.line_end,
            "signature_hash": symbol.signature_hash,
        }
    elif file_obj:
        node_info = {
            "id": file_obj.id,
            "name": file_obj.path.split("/")[-1],
            "full_name": file_obj.path,
            "type": "FILE",
            "file": file_obj.path,
            "language": file_obj.language,
            "size": file_obj.size,
        }
    elif route_obj:
        node_info = {
            "id": f"route:{route_obj.id}",
            "name": f"{route_obj.method} {route_obj.path}",
            "full_name": f"{route_obj.method} {route_obj.path}",
            "type": "ROUTE",
            "method": route_obj.method,
            "path": route_obj.path,
        }
    else:
        node_info = {
            "id": f"cap:{cap_obj.id}",
            "name": cap_obj.name,
            "full_name": cap_obj.name,
            "type": "CAPABILITY",
            "capability_type": cap_obj.capability_type,
            "summary": cap_obj.evidence_summary,
        }

    # Fetch incoming relationships (who points to this node)
    incoming_rels = db.query(FactRelationship).filter(
        FactRelationship.analysis_id == analysis_id,
        FactRelationship.to_symbol_id == node_id,
    ).all()

    # Fetch outgoing relationships (what this node points to)
    outgoing_rels = db.query(FactRelationship).filter(
        FactRelationship.analysis_id == analysis_id,
        FactRelationship.from_symbol_id == node_id,
    ).all()

    # Resolve names for related nodes
    all_sym_ids = {r.from_symbol_id for r in incoming_rels} | {r.to_symbol_id for r in outgoing_rels}
    all_syms = db.query(FactSymbol).filter(
        FactSymbol.analysis_id == analysis_id,
        FactSymbol.id.in_(all_sym_ids),
    ).all() if all_sym_ids else []
    sym_lookup = {s.id: s for s in all_syms}

    all_files = db.query(FactFile).filter(
        FactFile.analysis_id == analysis_id,
        FactFile.id.in_(all_sym_ids),
    ).all() if all_sym_ids else []
    file_lookup = {f.id: f for f in all_files}

    def resolve_ref(nid: str):
        if nid in sym_lookup:
            s = sym_lookup[nid]
            return {"id": s.id, "name": s.name, "type": s.symbol_type.upper(), "file": s.file.path if s.file else ""}
        elif nid in file_lookup:
            f = file_lookup[nid]
            return {"id": f.id, "name": f.path.split("/")[-1], "type": "FILE", "file": f.path}
        return {"id": nid, "name": nid.split("#")[-1] if "#" in nid else nid, "type": "UNKNOWN"}

    incoming_list = [
        {
            "id": r.id,
            "rel_type": r.rel_type,
            "evidence_line": r.evidence_line,
            "source": resolve_ref(r.from_symbol_id),
        }
        for r in incoming_rels
    ]

    outgoing_list = [
        {
            "id": r.id,
            "rel_type": r.rel_type,
            "evidence_line": r.evidence_line,
            "target": resolve_ref(r.to_symbol_id),
        }
        for r in outgoing_rels
    ]

    # Check capability memberships
    member_caps = (
        db.query(FactCapability)
        .join(FactCapabilityMember, FactCapabilityMember.capability_id == FactCapability.id)
        .filter(
            FactCapability.analysis_id == analysis_id,
            FactCapabilityMember.symbol_id == node_id,
        )
        .all()
    )
    cap_list = [{"id": c.id, "name": c.name, "summary": c.evidence_summary} for c in member_caps]

    return {
        "node": node_info,
        "incoming": incoming_list,
        "outgoing": outgoing_list,
        "capabilities": cap_list,
    }


# ──────────────────────────────────────────────────────────────────────────
# PROGRESSIVE EXPLORATION ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────

def _get_top_level_dir(path: str) -> str:
    """Extract the first directory segment from a file path."""
    parts = path.replace("\\", "/").strip("/").split("/")
    return parts[0] if len(parts) > 1 else "__root__"


def _get_path_segments(path: str) -> List[str]:
    """Return all directory segments of a path (excludes filename)."""
    parts = path.replace("\\", "/").strip("/").split("/")
    return parts[:-1]  # all except the filename


@graph_router.get("/{repo_name}/knowledge-graph/overview")
def get_knowledge_graph_overview(
    repo_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a lightweight high-level overview graph for progressive exploration.

    The initial view shows:
    - Synthetic top-level directory nodes (e.g. 'backend/', 'frontend/', 'tests/')
    - Capability nodes (cross-cutting features detected by Layer 6)
    - Route count summary nodes (API surface)

    Each directory node is marked expandable=True. Clicking one calls /expand/{node_id}.
    This allows large repositories (50k+ nodes) to be explored progressively without
    loading the entire graph into the browser at once.
    """
    try:
        repo, analysis = get_latest_analysis(repo_name, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GRAPH_OVERVIEW] Failed to resolve repository {repo_name}: {e}")
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    analysis_id = analysis.id
    logger.info(f"[GRAPH_OVERVIEW] Loading overview for repo='{repo_name}', analysis_id={analysis_id}")

    # Fetch only what we need for the overview
    files = db.query(FactFile).filter(FactFile.analysis_id == analysis_id).all()
    capabilities = db.query(FactCapability).filter(FactCapability.analysis_id == analysis_id).all()
    routes = db.query(FactRoute).filter(FactRoute.analysis_id == analysis_id).all()
    symbols = db.query(FactSymbol).filter(FactSymbol.analysis_id == analysis_id).all()

    # Group files by their first directory segment to create synthetic folder nodes
    folder_file_counts: Dict[str, int] = {}
    folder_symbol_counts: Dict[str, int] = {}

    # Track which files/symbols belong to each top-level folder
    file_to_folder: Dict[str, str] = {}
    for f in files:
        folder = _get_top_level_dir(f.path)
        folder_file_counts[folder] = folder_file_counts.get(folder, 0) + 1
        file_to_folder[f.id] = folder

    for s in symbols:
        fid = s.file_id
        if fid and fid in file_to_folder:
            folder = file_to_folder[fid]
            folder_symbol_counts[folder] = folder_symbol_counts.get(folder, 0) + 1

    overview_nodes: List[Dict[str, Any]] = []
    overview_edges: List[Dict[str, Any]] = []

    # 1. Folder nodes (one per top-level directory)
    folder_names = sorted(folder_file_counts.keys())
    for folder in folder_names:
        node_id = f"dir:{folder}"
        file_count = folder_file_counts.get(folder, 0)
        sym_count = folder_symbol_counts.get(folder, 0)
        overview_nodes.append({
            "id": node_id,
            "name": folder if folder != "__root__" else "(root files)",
            "label": folder if folder != "__root__" else "(root)",
            "full_name": folder,
            "type": "DIRECTORY",
            "file_count": file_count,
            "symbol_count": sym_count,
            "expandable": True,
            "expanded": False,
            "metadata": {"folder": folder},
        })

    # 2. Capability nodes (always show - they are high-value cross-cutting nodes)
    for cap in capabilities:
        cap_node_id = f"cap:{cap.id}"
        overview_nodes.append({
            "id": cap_node_id,
            "name": cap.name,
            "label": cap.name,
            "full_name": cap.name,
            "type": "CAPABILITY",
            "capability_type": cap.capability_type,
            "summary": cap.evidence_summary,
            "expandable": False,
            "expanded": False,
            "metadata": {"status": cap.status},
        })

    # 3. Add edges: if a capability member belongs to a file in a folder,
    #    connect that folder -> capability
    cap_members = (
        db.query(FactCapabilityMember)
        .filter(FactCapabilityMember.capability_id.in_([c.id for c in capabilities]))
        .all()
        if capabilities else []
    )
    sym_map: Dict[str, str] = {s.id: s.file_id for s in symbols if s.file_id}
    cap_folder_edges_seen: Set[str] = set()
    for m in cap_members:
        file_id = sym_map.get(m.symbol_id)
        if file_id and file_id in file_to_folder:
            folder = file_to_folder[file_id]
            folder_node_id = f"dir:{folder}"
            cap_node_id = f"cap:{m.capability_id}"
            edge_key = f"{folder_node_id}->{cap_node_id}"
            if edge_key not in cap_folder_edges_seen:
                cap_folder_edges_seen.add(edge_key)
                overview_edges.append({
                    "id": f"e-overview-{edge_key}",
                    "source": folder_node_id,
                    "target": cap_node_id,
                    "type": "CAPABILITY_MEMBER",
                    "status": "CONFIRMED",
                })

    repo_name_str = repo.name if hasattr(repo, "name") and repo.name else repo.url.split("/")[-1].replace(".git", "")
    return {
        "repo_name": repo_name_str,
        "analysis_id": analysis_id,
        "mode": "overview",
        "stats": {
            "total_files": len(files),
            "total_symbols": len(symbols),
            "total_capabilities": len(capabilities),
            "total_routes": len(routes),
            "top_level_folders": len(folder_file_counts),
        },
        "nodes": overview_nodes,
        "edges": overview_edges,
    }


@graph_router.get("/{repo_name}/knowledge-graph/expand/{node_id:path}")
def get_knowledge_graph_expand(
    repo_name: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Expand a directory or file node to reveal its direct children.

    - Expanding a directory node (id starts with 'dir:') returns:
      - Subdirectory nodes one level deeper
      - File nodes directly inside that directory (not deeper)
      - Relationships between the returned files (IMPORTS, etc.)

    - Expanding a file node (id starts with a fact-store file ID) returns:
      - All symbols declared in that file
      - Relationships originating from those symbols (CALLS, IMPORTS, INHERITS, etc.)
      - Neighboring file nodes if referenced

    The caller appends the returned nodes/edges to the existing graph without
    replacing it, preserving the current layout and camera position.
    """
    try:
        repo, analysis = get_latest_analysis(repo_name, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GRAPH_EXPAND] Failed to resolve repository {repo_name}: {e}")
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    analysis_id = analysis.id
    logger.info(f"[GRAPH_EXPAND] Expanding node_id='{node_id}' for repo='{repo_name}', analysis_id={analysis_id}")

    new_nodes: List[Dict[str, Any]] = []
    new_edges: List[Dict[str, Any]] = []

    if node_id.startswith("dir:"):
        # ── DIRECTORY EXPANSION ──────────────────────────────────────────────
        folder_path = node_id[4:]  # strip "dir:" prefix

        # All files in this analysis
        all_files = db.query(FactFile).filter(FactFile.analysis_id == analysis_id).all()

        # Find files whose path starts with this folder
        prefix = (folder_path + "/") if folder_path != "__root__" else ""
        matched_files = [
            f for f in all_files
            if (f.path.replace("\\", "/").startswith(prefix) if prefix else "/" not in f.path.replace("\\", "/").strip("/"))
        ]

        # Group into direct children: immediate sub-folders or files at exactly one level deeper
        direct_children_folders: Dict[str, int] = {}  # subfolder_name -> file count
        direct_files: List[Any] = []

        for f in matched_files:
            relative = f.path.replace("\\", "/").strip("/")
            if prefix:
                relative = relative[len(prefix):]
            parts = relative.split("/")
            if len(parts) == 1:
                # File directly in this folder
                direct_files.append(f)
            elif len(parts) > 1:
                # Goes deeper — add immediate sub-folder
                sub = parts[0]
                direct_children_folders[sub] = direct_children_folders.get(sub, 0) + 1

        # Emit sub-folder nodes
        for sub_folder, count in sorted(direct_children_folders.items()):
            child_path = f"{folder_path}/{sub_folder}" if folder_path != "__root__" else sub_folder
            child_id = f"dir:{child_path}"
            new_nodes.append({
                "id": child_id,
                "name": sub_folder,
                "label": sub_folder,
                "full_name": child_path,
                "type": "DIRECTORY",
                "file_count": count,
                "expandable": True,
                "expanded": False,
                "metadata": {"folder": child_path},
            })
            new_edges.append({
                "id": f"e-dir-{node_id}->{child_id}",
                "source": node_id,
                "target": child_id,
                "type": "CONTAINS",
                "status": "CONFIRMED",
            })

        # Emit direct file nodes (cap at 80 to stay performant)
        for f in direct_files[:80]:
            basename = f.path.split("/")[-1] if "/" in f.path else f.path
            new_nodes.append({
                "id": f.id,
                "name": basename,
                "label": basename,
                "full_name": f.path,
                "type": "FILE",
                "file": f.path,
                "language": f.language,
                "size": f.size,
                "expandable": True,
                "expanded": False,
                "metadata": {"is_test": f.is_test, "is_doc": f.is_documentation},
            })
            new_edges.append({
                "id": f"e-dir-file-{node_id}->{f.id}",
                "source": node_id,
                "target": f.id,
                "type": "CONTAINS",
                "status": "CONFIRMED",
            })

        # Add import-level edges between the returned files (IMPORTS between them)
        file_ids = {f.id for f in direct_files[:80]}
        if file_ids:
            import_rels = (
                db.query(FactRelationship)
                .filter(
                    FactRelationship.analysis_id == analysis_id,
                    FactRelationship.rel_type == "IMPORTS",
                    FactRelationship.from_symbol_id.in_(file_ids),
                    FactRelationship.to_symbol_id.in_(file_ids),
                )
                .limit(200)
                .all()
            )
            for r in import_rels:
                new_edges.append({
                    "id": r.id,
                    "source": r.from_symbol_id,
                    "target": r.to_symbol_id,
                    "type": "IMPORTS",
                    "evidence_line": r.evidence_line,
                    "status": r.status or "CONFIRMED",
                })

    elif node_id.startswith("cap:"):
        # ── CAPABILITY EXPANSION ─────────────────────────────────────────────
        cap_id = node_id[4:]
        cap_members = (
            db.query(FactCapabilityMember)
            .filter(FactCapabilityMember.capability_id == cap_id)
            .all()
        )
        sym_ids = [m.symbol_id for m in cap_members]
        symbols = db.query(FactSymbol).filter(
            FactSymbol.analysis_id == analysis_id,
            FactSymbol.id.in_(sym_ids),
        ).all()
        sym_file_ids = {s.file_id for s in symbols if s.file_id}
        files_map = {}
        if sym_file_ids:
            for f in db.query(FactFile).filter(FactFile.id.in_(sym_file_ids)).all():
                files_map[f.id] = f

        for s in symbols:
            stype = (s.symbol_type or "symbol").upper()
            fpath = files_map[s.file_id].path if s.file_id and s.file_id in files_map else ""
            new_nodes.append({
                "id": s.id,
                "name": s.name,
                "label": s.name,
                "full_name": s.qualified_name or s.name,
                "type": stype,
                "file": fpath,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "expandable": False,
                "expanded": False,
                "metadata": {},
            })
            new_edges.append({
                "id": f"e-cap-member-{node_id}->{s.id}",
                "source": node_id,
                "target": s.id,
                "type": "CAPABILITY_MEMBER",
                "status": "CONFIRMED",
            })

    else:
        # ── FILE EXPANSION ───────────────────────────────────────────────────
        # node_id is a FactFile id
        file_obj = db.query(FactFile).filter(
            FactFile.analysis_id == analysis_id,
            FactFile.id == node_id,
        ).first()

        if not file_obj:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

        # Get symbols in this file
        symbols = db.query(FactSymbol).filter(
            FactSymbol.analysis_id == analysis_id,
            FactSymbol.file_id == node_id,
        ).all()

        sym_ids = {s.id for s in symbols}

        for s in symbols:
            stype = (s.symbol_type or "symbol").upper()
            new_nodes.append({
                "id": s.id,
                "name": s.name,
                "label": s.name,
                "full_name": s.qualified_name or s.name,
                "type": stype,
                "file": file_obj.path,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "expandable": False,
                "expanded": False,
                "metadata": {},
            })
            new_edges.append({
                "id": f"e-file-sym-{node_id}->{s.id}",
                "source": node_id,
                "target": s.id,
                "type": "DECLARES",
                "status": "CONFIRMED",
            })

        # Relationships between symbols in this file
        if sym_ids:
            internal_rels = (
                db.query(FactRelationship)
                .filter(
                    FactRelationship.analysis_id == analysis_id,
                    FactRelationship.from_symbol_id.in_(sym_ids),
                    FactRelationship.to_symbol_id.in_(sym_ids),
                )
                .limit(300)
                .all()
            )
            for r in internal_rels:
                new_edges.append({
                    "id": r.id,
                    "source": r.from_symbol_id,
                    "target": r.to_symbol_id,
                    "type": (r.rel_type or "GENERIC").upper(),
                    "evidence_line": r.evidence_line,
                    "status": r.status or "CONFIRMED",
                })

            # Outgoing relationships from this file's symbols to other files (CALLS/IMPORTS limit 50)
            outgoing_rels = (
                db.query(FactRelationship)
                .filter(
                    FactRelationship.analysis_id == analysis_id,
                    FactRelationship.from_symbol_id.in_(sym_ids),
                    ~FactRelationship.to_symbol_id.in_(sym_ids),
                    FactRelationship.rel_type.in_(["CALLS", "IMPORTS", "INHERITS"]),
                )
                .limit(50)
                .all()
            )
            # Resolve the target symbols so we can add them as nodes too
            out_target_ids = {r.to_symbol_id for r in outgoing_rels}
            out_targets = db.query(FactSymbol).filter(
                FactSymbol.analysis_id == analysis_id,
                FactSymbol.id.in_(out_target_ids),
            ).all() if out_target_ids else []
            out_target_map = {s.id: s for s in out_targets}
            out_file_ids = {s.file_id for s in out_targets if s.file_id}
            out_files = {}
            if out_file_ids:
                for f in db.query(FactFile).filter(FactFile.id.in_(out_file_ids)).all():
                    out_files[f.id] = f

            for s in out_targets:
                if s.id not in sym_ids:
                    stype = (s.symbol_type or "symbol").upper()
                    fpath = out_files[s.file_id].path if s.file_id and s.file_id in out_files else ""
                    new_nodes.append({
                        "id": s.id,
                        "name": s.name,
                        "label": s.name,
                        "full_name": s.qualified_name or s.name,
                        "type": stype,
                        "file": fpath,
                        "line_start": s.line_start,
                        "line_end": s.line_end,
                        "expandable": False,
                        "expanded": False,
                        "metadata": {},
                    })

            for r in outgoing_rels:
                if r.to_symbol_id in out_target_map:
                    new_edges.append({
                        "id": r.id,
                        "source": r.from_symbol_id,
                        "target": r.to_symbol_id,
                        "type": (r.rel_type or "GENERIC").upper(),
                        "evidence_line": r.evidence_line,
                        "status": r.status or "CONFIRMED",
                    })

    return {
        "expanded_node_id": node_id,
        "new_nodes": new_nodes,
        "new_edges": new_edges,
    }


# ──────────────────────────────────────────────────────────────────────────
# LEGACY / HASH-BASED ENDPOINTS (PRESERVED FOR BACKWARD COMPATIBILITY)
# ──────────────────────────────────────────────────────────────────────────

@graph_router.get("/{repo_hash}/graph/search")
def graph_search(repo_hash: str, q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    try:
        repo, analysis = get_latest_analysis_by_hash(repo_hash, db, current_user)
    except HTTPException:
        raise

    artifact = db.query(AnalysisArtifact).filter(
        AnalysisArtifact.analysis_id == analysis.id,
        AnalysisArtifact.type == "rim_model"
    ).first()

    if not artifact or not artifact.data:
        raise HTTPException(status_code=404, detail=f"No model found for analysis {analysis.id}")

    model = deserialize_rim(artifact.data)
    service = GraphQueryService(model)
    results = service.search(q)

    logger.info(f"[GRAPH_SEARCH] repo_hash={repo_hash}, query={q}, results={len(results)}")
    return {"results": results}


@graph_router.post("/{repo_hash}/graph/query")
def graph_query(repo_hash: str, req: GraphQueryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    logger.info(f"[GRAPH_QUERY] repo_hash={repo_hash}, node_id={req.node_id}, direction={req.direction}, depth={req.depth}")

    if not req.node_id or not req.node_id.strip():
        raise HTTPException(status_code=400, detail="node_id cannot be empty")

    node_id = req.node_id.strip()

    valid_directions = ["incoming", "outgoing", "both"]
    if req.direction not in valid_directions:
        raise HTTPException(
            status_code=400,
            detail=f"direction must be one of {valid_directions} (got '{req.direction}')"
        )

    if req.depth < 1 or req.depth > 10:
        raise HTTPException(status_code=400, detail=f"depth must be between 1 and 10 (got {req.depth})")

    if req.max_nodes < 1 or req.max_nodes > 1000:
        raise HTTPException(status_code=400, detail=f"max_nodes must be between 1 and 1000 (got {req.max_nodes})")

    valid_rel_types = ["calls", "imports", "depends_on", "inherits", "renders"]
    if req.relationship_type not in valid_rel_types:
        raise HTTPException(
            status_code=400,
            detail=f"relationship_type must be one of {valid_rel_types} (got '{req.relationship_type}')"
        )

    try:
        repo, analysis = get_latest_analysis_by_hash(repo_hash, db, current_user)
    except HTTPException:
        raise

    artifact = db.query(AnalysisArtifact).filter(
        AnalysisArtifact.analysis_id == analysis.id,
        AnalysisArtifact.type == "rim_model"
    ).first()

    if not artifact or not artifact.data:
        raise HTTPException(status_code=404, detail=f"No model found for analysis {analysis.id}")

    model = deserialize_rim(artifact.data)
    service = GraphQueryService(model)

    if node_id not in service.model.entities:
        logger.warning(f"[GRAPH_QUERY] Node not found: {node_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found in repository graph"
        )

    entity = service.model.entities[node_id]
    logger.info(f"[GRAPH_QUERY] Node found: {entity.name} (type={entity.type})")

    result = service.traverse(
        node_id=node_id,
        direction=req.direction,
        depth=req.depth,
        max_nodes=req.max_nodes,
        relationship_type=req.relationship_type
    )

    logger.info(f"[GRAPH_QUERY] Result: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
    return result
