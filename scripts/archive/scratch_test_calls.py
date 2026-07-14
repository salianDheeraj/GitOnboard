import requests
import json

try:
    r = requests.get("http://127.0.0.1:8000/api/repos/fastapi/call-graph")
    data = r.json()
    print(f"Nodes: {len(data['nodes'])}, Edges: {len(data['edges'])}")
except Exception as e:
    print(e)
