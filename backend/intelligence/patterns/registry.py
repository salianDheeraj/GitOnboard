import yaml
import os
from pathlib import Path
from typing import Dict, Any, List

class PatternRegistry:
    """
    Loads and serves YAML declarative pattern rules.
    """
    def __init__(self, rules_dir: str = None):
        if not rules_dir:
            rules_dir = str(Path(__file__).parent / "rules")
        self.rules_dir = Path(rules_dir)
        self.rules: Dict[str, dict] = {}
        self._load_rules()

    def _load_rules(self):
        if not self.rules_dir.exists():
            return
            
        for file in self.rules_dir.glob("*.yaml"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    rule = yaml.safe_load(f)
                    if "name" in rule and "type" in rule:
                        self.rules[rule["name"]] = rule
            except Exception as e:
                print(f"Failed to load rule {file}: {e}")

    def get_all_rules(self) -> List[dict]:
        return list(self.rules.values())

    def get_rule(self, name: str) -> dict:
        return self.rules.get(name)
