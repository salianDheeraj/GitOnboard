from backend.database import SessionLocal
from backend.models.repository import AnalysisArtifact
db = SessionLocal()
arts = db.query(AnalysisArtifact).filter(AnalysisArtifact.type == "enriched_metadata").all()
for a in arts:
    print(a.analysis_id)
    if isinstance(a.data, dict):
        print(a.data.keys())
        print("languages:", a.data.get("languages"))
    else:
        print(a.data)
