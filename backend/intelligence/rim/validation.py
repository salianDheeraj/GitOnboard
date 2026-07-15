from .repository import RepositoryModel
from typing import List

class RIMValidator:
    def __init__(self, model: RepositoryModel):
        self.model = model
        self.errors: List[str] = []

    def validate(self) -> bool:
        self.errors.clear()
        self._validate_entities()
        self._validate_relationships()
        return len(self.errors) == 0

    def _validate_entities(self):
        for entity_id, entity in self.model.entities.items():
            if entity.id != entity_id:
                self.errors.append(f"Entity ID mismatch: key={entity_id}, entity.id={entity.id}")
            if not entity.id.startswith("urn:"):
                self.errors.append(f"Entity ID invalid format: {entity.id}")

    def _validate_relationships(self):
        for rel_id, rel in self.model.relationships.items():
            if rel.id != rel_id:
                self.errors.append(f"Relationship ID mismatch: key={rel_id}, rel.id={rel.id}")
            if rel.source_id not in self.model.entities:
                self.errors.append(f"Relationship {rel.id} source_id {rel.source_id} not found in entities")
            if rel.target_id not in self.model.entities:
                self.errors.append(f"Relationship {rel.id} target_id {rel.target_id} not found in entities")
            if rel.source_id == rel.target_id:
                self.errors.append(f"Relationship {rel.id} is a self-loop, which is currently disallowed")
