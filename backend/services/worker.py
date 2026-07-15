import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.repository import Repository, Analysis, AnalysisJob, AnalysisArtifact
from backend.services.queue import WorkerInterface
from backend.services.github import download_repo_zipball
from backend.intelligence import RepositoryBuilder, RelationshipBuilder, AnalysisPipeline
from backend.intelligence.stages.metrics_stage import MetricsStage

logger = logging.getLogger(__name__)

def _serialize_dataclass(obj):
    import dataclasses
    from enum import Enum
    if dataclasses.is_dataclass(obj):
        return {k: _serialize_dataclass(v) for k, v in dataclasses.asdict(obj).items()}
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: _serialize_dataclass(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_dataclass(v) for v in obj]
    return obj

class AnalysisWorker(WorkerInterface):
    async def process(self, job_id: int):
        db: Session = SessionLocal()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            analysis = db.query(Analysis).filter(Analysis.id == job.analysis_id).first()
            repo = db.query(Repository).filter(Repository.id == analysis.repository_id).first()

            job.status = "Downloading"
            job.started_at = datetime.now(timezone.utc)
            db.commit()

            # Parse owner/repo from url
            # e.g., https://github.com/owner/repo
            parts = repo.url.rstrip('/').split('/')
            owner = parts[-2]
            repo_name = parts[-1]
            
            # TODO: get user token
            from backend.models.user import User
            user = db.query(User).filter(User.id == repo.user_id).first()
            token = user.github_access_token if user else None

            # Create temp dir
            base_tmp = Path("/tmp/repo-analysis")
            base_tmp.mkdir(parents=True, exist_ok=True)
            target_dir = base_tmp / f"job_{job_id}_{repo_name}"

            try:
                # 1. Download
                try:
                    await asyncio.wait_for(
                        download_repo_zipball(owner, repo_name, repo.default_branch, str(target_dir), token),
                        timeout=120.0
                    )
                except asyncio.TimeoutError:
                    raise Exception("Download timed out after 120 seconds")

                job.status = "Analyzing"
                db.commit()

                # 2. Analyze
                def run_analysis():
                    builder = RepositoryBuilder(repo_name, target_dir)
                    rel_builder = RelationshipBuilder(target_dir)
                    pipeline = AnalysisPipeline(builder, rel_builder)
                    pipeline.add_stage(MetricsStage(str(target_dir)))
                    
                    from backend.intelligence.stages.metadata_stage import RepositoryMetadataStage
                    pipeline.add_stage(RepositoryMetadataStage(str(target_dir)))
                    
                    model = pipeline.run()
                    
                    import pickle
                    try:
                        model_blob = pickle.dumps(model)
                        model_artifact = AnalysisArtifact(
                            analysis_id=analysis.id,
                            type="core_model",
                            data={},
                            blob_data=model_blob
                        )
                        db.add(model_artifact)
                    except Exception as e:
                        logger.error(f"Failed to pickle core_model: {e}")
                        
                    from analysis.registry import AnalyzerRegistry
                    from analysis.runner import AnalysisRunner
                    import sys
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
                    
                    registry = AnalyzerRegistry()
                    registry.discover("analysis.plugins")
                    runner = AnalysisRunner(registry)
                    report = runner.run(model)
                    model.analyses.findings = report.overall_findings
                    
                    import pickle
                    try:
                        model_blob = pickle.dumps(model)
                        model_artifact = AnalysisArtifact(
                            analysis_id=analysis.id,
                            type="core_model",
                            data={},
                            blob_data=model_blob
                        )
                        db.add(model_artifact)
                    except Exception as e:
                        logger.error(f"Failed to pickle core_model: {e}")
                    
                    from backend.intelligence import QueryLayer
                    query = QueryLayer(model)
                    
                    # Pre-calculate API responses
                    from backend.intelligence.graphs.dependency_graph import DependencyGraphView
                    from backend.intelligence.graphs.call_graph import CallGraphView
                    
                    dep_graph = DependencyGraphView(model)
                    call_graph = CallGraphView(model)
                    
                    # Symbols
                    symbols = []
                    for c in query.model.entities.classes.values():
                        symbols.append({"id": c.id, "type": "Class", "name": c.name, "file_path": c.file_id, "line_number": c.line_number, "docstring": c.docstring})
                    for f in query.model.entities.functions.values():
                        symbols.append({"id": f.id, "type": "Function", "name": f.name, "file_path": f.file_id, "line_number": f.line_number, "docstring": f.docstring})
                    for m in query.model.entities.methods.values():
                        symbols.append({"id": m.id, "type": "Method", "name": m.name, "file_path": m.file_id, "line_number": m.line_number, "docstring": m.docstring})
                        
                    # Dependency Edges/Nodes
                    from backend.intelligence.parser import LanguageParser
                    parser = LanguageParser()
                    lang_map = {
                        ".py": "Python", 
                        ".js": "JavaScript", 
                        ".ts": "TypeScript", 
                        ".jsx": "JavaScript", 
                        ".tsx": "TypeScript", 
                        ".java": "Java"
                    }
                    dep_nodes = []
                    for f in query.get_files():
                        ext = f.extension.lower()
                        if parser.supports_extension(ext):
                            dep_nodes.append({
                                "id": f.path, 
                                "label": f.name, 
                                "full_path": f.path,
                                "language": lang_map.get(ext, "Unknown")
                            })
                    dep_edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, targets in dep_graph.get_edges().items() for t in targets]
                    
                    # Call graph edges
                    cg_nodes = [{"id": n, "label": n.split('::')[-1], "full_name": n} for n in call_graph.get_nodes()]
                    cg_edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, targets in call_graph.get_edges().items() for t in targets]
                    # Build Semantic Index
                    import chromadb
                    import uuid
                    chroma_dir = target_dir / "chroma"
                    chroma_dir.mkdir(parents=True, exist_ok=True)
                    client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
                    collection = client.get_or_create_collection(name="semantic_index")
                    
                    documents = []
                    metadatas = []
                    ids = []
                    for f_node in query.get_files():
                        pf = target_dir / f_node.path
                        ext = pf.suffix.lower()
                        if not parser.supports_extension(ext):
                            continue
                            
                        try:
                            with open(pf, "r", encoding="utf-8") as f:
                                source = f.read()
                            tree, _ = parser.parse_source(source, ext)
                            parsed_entities = parser.extract_entities(tree, source, f_node.path, "")
                            
                            for cls in parsed_entities.get("classes", []):
                                if cls.get("source_segment"):
                                    documents.append(cls["source_segment"])
                                    metadatas.append({"file_path": f_node.path, "type": "class", "name": cls["name"]})
                                    ids.append(str(uuid.uuid4()))
                                    
                            for fn in parsed_entities.get("functions", []):
                                if fn.get("source_segment"):
                                    documents.append(fn["source_segment"])
                                    metadatas.append({"file_path": f_node.path, "type": "function", "name": fn["name"]})
                                    ids.append(str(uuid.uuid4()))
                                    
                            for md in parsed_entities.get("methods", []):
                                if md.get("source_segment"):
                                    documents.append(md["source_segment"])
                                    metadatas.append({"file_path": f_node.path, "type": "method", "name": md["name"]})
                                    ids.append(str(uuid.uuid4()))
                        except Exception:
                            pass
                            
                    if documents:
                        batch_size = 2000
                        for i in range(0, len(documents), batch_size):
                            collection.upsert(
                                documents=documents[i:i+batch_size],
                                metadatas=metadatas[i:i+batch_size],
                                ids=ids[i:i+batch_size]
                            )
                            
                    import shutil
                    zip_path = shutil.make_archive(str(target_dir / "chroma_zip"), 'zip', str(chroma_dir))
                    with open(zip_path, "rb") as f:
                        chroma_blob = f.read()

                    return {
                        "metrics": getattr(model.analyses, "metrics", {}),
                        "findings": getattr(model.analyses, "findings", []),
                        "cycles": getattr(model.analyses, "cycles", []),
                        "symbols": symbols,
                        "dependencies": {"nodes": dep_nodes, "edges": dep_edges},
                        "call_graph": {"nodes": cg_nodes, "edges": cg_edges},
                        "enriched_metadata": getattr(model.analyses, "enriched_metadata", {}),
                        "semantic_index_db": chroma_blob
                    }

                logger.info(f"Analyzing {repo_name}...")
                results = await asyncio.wait_for(
                    asyncio.to_thread(run_analysis),
                    timeout=600.0 # 10 min
                )

                job.status = "Saving"
                db.commit()

                # 3. Save artifacts
                logger.info("Saving artifacts...")
                
                for art_type, data in results.items():
                    if isinstance(data, bytes):
                        art = AnalysisArtifact(
                            analysis_id=analysis.id,
                            type=art_type,
                            data={},
                            blob_data=data
                        )
                    else:
                        art = AnalysisArtifact(
                            analysis_id=analysis.id,
                            type=art_type,
                            data=_serialize_dataclass(data)
                        )
                    db.add(art)

                # Update Analysis
                analysis.status = "Completed"
                
                job.status = "Completed"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Job {job_id} completed successfully.")

            except Exception as e:
                import traceback
                logger.error(f"Job {job_id} failed: {traceback.format_exc()}")
                job.status = "Failed"
                job.error = str(e)
                job.completed_at = datetime.now(timezone.utc)
                analysis.status = "Failed"
                db.commit()
            finally:
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Critical worker error on job {job_id}: {e}")
        finally:
            db.close()
