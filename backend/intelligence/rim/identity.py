from .enums import EntityType, RelationshipType

def generate_entity_id(entity_type: EntityType, repository_path: str, qualified_name: str) -> str:
    """
    Generate a stable ID for an entity.
    Format: urn:<type>:<repository_path>#<qualified_name>
    """
    type_str = entity_type.value.lower()
    return f"urn:{type_str}:{repository_path}#{qualified_name}"

def generate_relationship_id(relationship_type: RelationshipType, source_id: str, target_id: str) -> str:
    """
    Generate a stable ID for a relationship.
    Format: rel:<type>:<source_id>-><target_id>
    """
    type_str = relationship_type.value.lower()
    return f"rel:{type_str}:{source_id}->{target_id}"
