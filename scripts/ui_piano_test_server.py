"""Browser QA only: real API backed by an isolated, disposable in-memory DB."""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "isolated-browser-qa-not-production"
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models import StaffUser, Patient, Baseline
from app.db.session import get_db
from app.core.security import hash_password
from app.main import app
import json

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
maker = sessionmaker(bind=engine)
with maker() as db:
    db.add(StaffUser(username="browserqa", password_hash=hash_password("browser-qa-only"), display_name="界面验收", role="DOCTOR", is_active=True))
    for identifier, name in [("browser-qa", "验收患者（虚拟）"), ("browser-second", "第二患者（虚拟）")]:
        db.add(Patient(id=identifier, hospital_number=identifier, name=name, sex="FEMALE", dominant_hand="RIGHT", affected_side="LEFT", medication_state="ON", is_deleted=False))
    db.commit()
    # A fixture baseline skips the 45-second capability task. It exists only in
    # this process; all browser-generated sessions declare SYNTHETIC_SELFTEST.
    for identifier in ["browser-qa", "browser-second"]:
        snapshot = {"baseline_accuracy": .8, "baseline_response_latency": 280, "baseline_response_latency_cv": .2,
                    "baseline_timing_mae": 100, "baseline_left_accuracy": .8, "baseline_right_accuracy": .8,
                    "baseline_left_latency": 280, "baseline_right_latency": 280, "baseline_spontaneous_bpm": 60}
        db.add(Baseline(patient_id=identifier, baseline_type="PIANO_CALIBRATION", snapshot_json=json.dumps(snapshot), is_active=True, algorithm_version="qa-fixture"))
    db.commit()

def qa_db():
    with maker() as db:
        yield db

@asynccontextmanager
async def qa_lifespan(_app):
    # Deliberately bypass production startup, directories, bootstrap and models.
    if os.environ.get('MICRO_EXPRESSION_ENTRY') == 'microflow_da':
        from app.ml.micro_expression.adapter import analyzer
        from app.ml.registry import registry
        registry.set(analyzer.load())
    yield
    engine.dispose()

app.dependency_overrides[get_db] = qa_db
app.router.lifespan_context = qa_lifespan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8013, log_level="warning")
