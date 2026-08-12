from .enums import EntityType, RelationshipType
import hashlib

def generate_stable_id(repo_id: str, file_path: str, qualified_name: str, signature_hash: str = "") -> str:
    """
    Generates a deterministic stable ID for a code symbol or entity.
    Formula: sha256(repo_id:file_path:qualified_name:signature_hash)[:32]
    Ensures symbol identity remains consistent across line number changes.
    """
    raw_key = f"{repo_id}:{file_path}:{qualified_name}:{signature_hash}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]

def generate_entity_id(
    entity_type: EntityType,
    repository_path: str,
    qualified_name: str,
    repo_id: str = "",
    signature_hash: str = ""
) -> str:
    """
    Generate a stable ID for an entity, using the canonical hash-based stable ID formula.
    """
    return generate_stable_id(repo_id, repository_path, qualified_name, signature_hash)

def generate_relationship_id(relationship_type: RelationshipType, source_id: str, target_id: str) -> str:
    """
    Generate a stable ID for a relationship.
    Format: rel:<type>:<source_id>-><target_id>
    """
    type_str = relationship_type.value.lower() if hasattr(relationship_type, "value") else str(relationship_type).lower()
    return f"rel:{type_str}:{source_id}->{target_id}"

