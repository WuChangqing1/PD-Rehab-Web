"""Job state survives restart; fixtures stay in a private temporary directory."""
from pathlib import Path

from app.jobs.manager import JobManager


def test_completed_job_restores_and_is_scoped(tmp_path):
    manager = JobManager(storage_dir=tmp_path)
    row = manager.run_sync('FINGER_TAPPING_ANALYSIS', lambda: {'result_id':'synthetic'}, patient_id='patient-1')
    restored = JobManager(storage_dir=tmp_path).get(row.job_id)
    assert restored.status == 'SUCCESS'
    assert restored.patient_id == 'patient-1'
    assert restored.result_ref == {'result_id':'synthetic'}
    assert not list(tmp_path.glob('*.tmp'))


def test_interrupted_jobs_fail_explicitly_on_restart(tmp_path):
    manager = JobManager(storage_dir=tmp_path)
    row = manager.create('FINGER_TAPPING_ANALYSIS', patient_id='patient-1')
    manager._update(row.job_id,status='RUNNING')
    restored = JobManager(storage_dir=tmp_path).get(row.job_id)
    assert restored.status == 'FAILED'
    assert restored.error['error']['code'] == 'TASK_INTERRUPTED'
    assert restored.finished_at is not None
    assert JobManager(storage_dir=tmp_path).get(row.job_id).status == 'FAILED'


def test_invalid_foreign_files_untouched_and_retention_scoped(tmp_path,monkeypatch):
    import app.jobs.manager as module
    monkeypatch.setattr(module,'_MAX_JOBS',2)
    foreign = tmp_path/'operator-notes.json'; foreign.write_text('{keep}')
    corrupt = tmp_path/'00000000-0000-0000-0000-000000000001.json'; corrupt.write_text('not-json')
    manager = JobManager(storage_dir=tmp_path)
    ids = [manager.run_sync('REPORT_EXPORT', lambda: {}).job_id for _ in range(4)]
    loaded = JobManager(storage_dir=tmp_path)
    assert len(loaded.list()) == 2
    assert loaded.get(ids[0]) is None
    assert foreign.read_text() == '{keep}' and corrupt.read_text() == 'not-json'


def test_restored_job_does_not_bypass_patient_authorization(tmp_path,db,staff_user):
    import pytest
    from app.api.jobs import get_job
    from app.core.errors import APIError
    from app.db.models import Patient, PatientAccessGrant
    import app.api.jobs as api
    person = Patient(name='Synthetic',hospital_number='JOB-TEST')
    db.add(person); db.commit()
    manager=JobManager(storage_dir=tmp_path)
    row=manager.run_sync('REPORT_EXPORT',lambda:{},patient_id=person.id)
    restored=JobManager(storage_dir=tmp_path)
    original=api.job_manager
    api.job_manager=restored
    try:
        assert get_job(row.job_id,staff_user,db)['patient_id'] == person.id
        db.add(PatientAccessGrant(patient_id=person.id,staff_user_id=staff_user.id,active=False));db.commit()
        with pytest.raises(APIError) as error:get_job(row.job_id,staff_user,db)
        assert error.value.status_code == 403
    finally:
        api.job_manager=original

def test_dataclass_outcome_keeps_live_pipeline_contract(tmp_path):
    from app.ml.finger_tapping.pipeline import AnalysisOutcome
    outcome = AnalysisOutcome(hand='LEFT',features={'frequency':2.0},quality={},analysis_config={},raw_features={},timeseries={'x':[1.0]})
    manager=JobManager(storage_dir=tmp_path)
    row=manager.run_sync('FINGER_TAPPING_ANALYSIS',lambda:{'outcome':outcome},patient_id='patient-1')
    assert row.result_ref['outcome'] is outcome
    restored=JobManager(storage_dir=tmp_path).get(row.job_id)
    assert restored.result_ref['outcome']['hand'] == 'LEFT'


def test_atomic_write_failure_preserves_previous_snapshot(tmp_path,monkeypatch):
    import os
    import pytest
    manager=JobManager(storage_dir=tmp_path)
    row=manager.create('REPORT_EXPORT')
    before=(tmp_path/(row.job_id+'.json')).read_bytes()
    def fail(*args): raise OSError('simulated disk failure')
    monkeypatch.setattr(os,'replace',fail)
    with pytest.raises(OSError):manager._update(row.job_id,status='RUNNING')
    assert (tmp_path/(row.job_id+'.json')).read_bytes() == before
    assert manager.get(row.job_id).status == 'PENDING'
    assert not list(tmp_path.glob('*.tmp'))


def test_concurrent_writes_are_complete_snapshots(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    manager=JobManager(storage_dir=tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda n:manager.run_sync('REPORT_EXPORT',lambda:{'index':n},patient_id='p'),range(16)))
    restored=JobManager(storage_dir=tmp_path)
    assert len(restored.list()) == 16
    assert {restored.get(row.job_id).result_ref['index'] for row in rows} == set(range(16))
