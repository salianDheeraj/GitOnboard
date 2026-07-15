from typing import List
from ..rim.repository import RepositoryModel
from .registry import PatternRegistry
from .matcher import GraphMatcher

class PatternRecognitionEngine:
    def __init__(self, registry: PatternRegistry):
        self.registry = registry

    def run(self, model: RepositoryModel) -> RepositoryModel:
        """
        Runs all registered pattern detection rules against the given RepositoryModel.
        Mutates the `patterns` dictionary of the model.
        """
        if not hasattr(model, "patterns"):
            model.patterns = {}
            
        matcher = GraphMatcher(model)
        
        for rule in self.registry.get_all_rules():
            # For each rule, attempt to match it against the graph
            detected_patterns = matcher.match_rule(rule)
            
            # Store in the RIM
            for pattern in detected_patterns:
                model.patterns[pattern.id] = pattern
                
        return model
