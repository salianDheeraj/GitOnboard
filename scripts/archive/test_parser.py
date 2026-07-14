import sys
import os

# Add current dir to python path
sys.path.append(os.getcwd())

from backend.intelligence.parser import LanguageParser

p = LanguageParser()
with open('data/repos/GitPulse1/backend/src/modules/commits/commits.controller.js') as f:
    src = f.read()
    
tree, _ = p.parse_source(src, '.js')
entities = p.extract_entities(tree, src, 'file_id', 'mod_id')

print("IMPORTS:", entities["imports"])
print("CLASSES:", entities["classes"])
print("FUNCTIONS:", entities["functions"])
