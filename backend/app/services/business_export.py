"""Credential-free, patient-authorized structured exports. No binary patient files."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.errors import APIError, ErrorCode, forbidden
from app.db import models
from app.db.base import utcnow
from app.services import integration_access

# Explicit snapshot: adding a database column never silently publishes it.
EXPORT_FIELDS = {
    models.AssessmentSession: ('id', 'patient_id', 'session_type', 'medication_state', 'status', 'created_by', 'started_at', 'completed_at', 'notes', 'created_at', 'updated_at'),
    models.MediaFile: ('id', 'patient_id', 'assessment_session_id', 'type', 'mime_type', 'size_bytes', 'sha256', 'created_at'),
    models.MicroExpressionResult: ('id', 'assessment_session_id', 'media_file_id', 'model_name', 'model_version', 'feature_schema_version', 'predicted_class', 'pd_probability', 'dominant_tag', 'tag_distribution_json', 'raw_output_json', 'inference_time_ms', 'quality_json', 'created_at'),
    models.FingerTappingResult: ('id', 'assessment_session_id', 'media_file_id', 'hand', 'input_source', 'tapping_frequency', 'avg_amplitude', 'avg_speed', 'avg_cycle_duration', 'amplitude_cv', 'speed_cv', 'cycle_cv', 'amplitude_slope', 'speed_slope', 'cycle_slope', 'interruptions', 'valid_frame_ratio', 'avg_landmark_confidence', 'severity_score', 'severity_label', 'analyzer_version', 'feature_schema_version', 'quality_json', 'raw_features_json', 'created_at'),
    models.FunctionalAssessment: ('id', 'patient_id', 'assessment_session_id', 'test_type', 'hand', 'value_primary', 'value_secondary', 'unit', 'medication_state', 'notes', 'performed_at', 'created_by', 'created_at'),
    models.Baseline: ('id', 'patient_id', 'baseline_type', 'source_id', 'snapshot_json', 'algorithm_version', 'is_active', 'created_at'),
    models.FaceRecording: ('id', 'patient_id', 'operator_id', 'device_id', 'local_profile_id', 'client_capture_id', 'external_record_id', 'status', 'manifest_sha256', 'data_json', 'created_at', 'updated_at'),
    models.GuidedSongSession: ('id', 'patient_id', 'owner_id', 'client_request_id', 'status', 'config', 'events', 'result', 'audio_metadata', 'created_at', 'completed_at'),
    models.DevicePatientLink: ('id', 'device_id', 'local_profile_id', 'patient_id', 'active', 'bound_by', 'created_at', 'updated_at'),
    models.ExternalPracticeRecord: ('id', 'patient_id', 'operator_id', 'device_id', 'local_profile_id', 'source_record_id', 'record_type', 'schema_version', 'task_version', 'metric_version', 'origin', 'payload_sha256', 'payload_json', 'captured_at_ms', 'created_at'),
    models.MobileFaceJob: ('id', 'patient_id', 'operator_id', 'status', 'result_id', 'assessment_session_id', 'error_code', 'device_id', 'local_profile_id', 'indices_json', 'candidates_json', 'size_bytes', 'created_at', 'updated_at'),
    models.ExpertChatTurn: ('id', 'operator_id', 'patient_id', 'question', 'answer', 'model', 'created_at'),
    models.PatientAccessGrant: ('id', 'patient_id', 'staff_user_id', 'active', 'created_at', 'updated_at'),
    models.MobileAccount: ('user_id', 'patient_id', 'sync_consent_version', 'created_at', 'updated_at'),
    models.MobileSession: ('id', 'user_id', 'expires_at', 'revoked', 'created_at', 'updated_at'),
    models.MobileIdentity: ('id', 'user_id', 'provider', 'app_id', 'subject', 'created_at', 'updated_at'),
    models.Patient: ('id', 'hospital_number', 'name', 'sex', 'birthday', 'phone', 'address', 'emergency_contact', 'emergency_phone', 'dominant_hand', 'affected_side', 'diagnosis_date', 'disease_duration_years', 'current_stage', 'current_medications', 'last_medication_time', 'medication_state', 'medical_history', 'comorbidities', 'allergies', 'surgery_history', 'rehab_history', 'doctor_notes', 'is_deleted', 'created_at', 'updated_at'),
    models.PatientNumberAllocation: ('id',),
    models.StaffUser: ('id', 'username', 'display_name', 'role', 'is_active', 'created_at', 'updated_at'),
    models.StaffApplication: ('id', 'username', 'display_name', 'phone', 'requested_role', 'status', 'reason', 'reviewed_by', 'user_id', 'reviewed_at', 'created_at', 'updated_at'),
    models.TrainingPlan: ('id', 'patient_id', 'name', 'status', 'start_date', 'end_date', 'created_by', 'config_json', 'created_at'),
    models.PianoSession: ('id', 'patient_id', 'training_plan_id', 'mode', 'round_number', 'recipe_id', 'input_source', 'bpm', 'judgement_window_ms', 'sequence_length', 'note_density', 'hand_mode', 'weak_side_ratio', 'finger_complexity', 'session_duration_sec', 'accuracy', 'miss_rate', 'mean_response_latency_ms', 'median_response_latency_ms', 'response_latency_cv', 'mean_timing_error_ms', 'median_timing_error_ms', 'timing_mae_ms', 'timing_error_cv', 'early_press_rate', 'late_press_rate', 'left_mean_latency', 'right_mean_latency', 'left_right_latency_difference', 'left_accuracy', 'right_accuracy', 'weak_finger_error_rate', 'sequence_completion_rate', 'session_completion_rate', 'difficulty_before_json', 'difficulty_after_json', 'adaptation_reason_json', 'difficulty_engine_version', 'metrics_version', 'started_at', 'completed_at'),
    models.PianoEvent: ('id', 'session_id', 'event_index', 'cue_onset_time_ms', 'target_time_ms', 'actual_time_ms', 'response_latency_ms', 'timing_error_ms', 'key_code', 'note', 'hand', 'finger_hint', 'key_down_time_ms', 'key_up_time_ms', 'hold_duration_ms', 'is_correct', 'is_missed', 'created_at'),
    models.PoseSession: ('id', 'patient_id', 'exercise_type', 'difficulty_json', 'execution_mode', 'input_source', 'completion_score', 'range_of_motion', 'symmetry_score', 'stability_score', 'hold_time_sec', 'repetition_count', 'movement_speed', 'valid_pose_frame_ratio', 'raw_metrics_json', 'quality_json', 'algorithm_version', 'exercise_definition_version', 'media_file_id', 'started_at', 'completed_at'),
}

_SECRET = re.compile(r"password|passwd|token|secret|credential|recovery|encrypt.*key|private.*key|api.*key|authorization|cookie|stored.?path|timeseries.?path|server.?config|analysis.?config|(?:^|_)key$|nonce|(?:^|_)iv$|(?:^|_)path$", re.I)
LOCAL_TZ = timezone(timedelta(hours=8))


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def safe_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat() + ('Z' if isinstance(value, datetime) and value.tzinfo is None else '')
    if isinstance(value, dict):
        return {str(k): safe_value(v) for k, v in value.items() if not _SECRET.search(str(k))}
    if isinstance(value, list):
        return [safe_value(item) for item in value]
    if isinstance(value, str) and value.lstrip().startswith(('{', '[')):
        try:
            return safe_value(json.loads(value))
        except (ValueError, TypeError):
            # Malformed structured content must not evade the recursive scrub.
            return None
    return value


def row_data(row):
    result = {field: safe_value(getattr(row, field)) for field in EXPORT_FIELDS[type(row)]}
    if isinstance(row, models.FaceRecording) and isinstance(result.get('data_json'), dict):
        data = result['data_json']
        if data.get('media_deleted'):
            data.pop('manifest', None)
    return result


def date_bounds(start_date, end_date):
    if (start_date and start_date.year < 2) or (end_date and end_date.year >= 9999):
        raise APIError(400, ErrorCode.VALIDATION_ERROR, 'Date is outside supported range.')
    if start_date and end_date and start_date > end_date:
        raise APIError(400, ErrorCode.VALIDATION_ERROR, '开始日期不能晚于结束日期。')
    def midnight(day):
        return datetime.combine(day, time.min, LOCAL_TZ).astimezone(timezone.utc).replace(tzinfo=None)
    return (midnight(start_date) if start_date else None,
            midnight(end_date + timedelta(days=1)) if end_date and end_date < date.max else None)


def _within(row, lower, upper):
    # Captured time is the source event time for immutable App synchronization.
    if isinstance(row, models.ExternalPracticeRecord) and row.captured_at_ms is not None:
        stamp = datetime.fromtimestamp(row.captured_at_ms / 1000, timezone.utc).replace(tzinfo=None)
    else:
        stamp = next((getattr(row, key, None) for key in ('performed_at','started_at','completed_at','created_at') if getattr(row, key, None) is not None), None)
    if stamp is None:
        return lower is None and upper is None
    if stamp.tzinfo:
        stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    return (lower is None or stamp >= lower) and (upper is None or stamp < upper)


def _attachment(raw_path, *, kind, identifier, metadata_hash=None, base_path=None):
    if not raw_path:
        return None
    base = (base_path or settings.upload_path).resolve()
    path = (base / raw_path).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for part in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(part)
    sha = digest.hexdigest()
    return {'kind':kind, 'id':identifier, 'size_bytes':path.stat().st_size, 'sha256':sha,
            'metadata_sha256_matches':sha == metadata_hash if metadata_hash else None,
            'backup_reference':kind + ':' + identifier}


def build_patient_export(db, patient_id: str, actor, start_date: date | None = None, end_date: date | None = None, *, include_attachments: bool = True) -> dict:
    if actor.role not in ('ADMIN','DOCTOR','NURSE') or not actor.is_active:
        raise forbidden('仅授权工作人员可以导出患者业务数据。')
    patient = integration_access.patient(db, patient_id, actor)
    lower, upper = date_bounds(start_date, end_date)
    records, attachments = {}, []
    # A delayed cleanup worker must never extend training video retention.
    recordings = db.scalars(select(models.FaceRecording).where(models.FaceRecording.patient_id == patient_id)).all()
    blocked_recordings = set()
    blocked_jobs = set()
    terminal = {'SUCCESS','PARTIAL_SUCCESS','NO_VALID_SEGMENTS','FAILED','CANCELLED','DELETED'}
    now = utcnow()
    for recording in recordings:
        data = safe_value(recording.data_json) or {}
        expiry = min(recording.created_at + timedelta(days=7), recording.updated_at + timedelta(hours=24)) if recording.status in terminal else recording.created_at + timedelta(hours=24 if recording.status == 'UPLOADING' else 168)
        if recording.status in ('CANCELLED','DELETED') or data.get('media_deleted') or now >= expiry:
            blocked_recordings.add(recording.id)
            blocked_jobs.update(segment.get('job_id') for segment in data.get('segments',[]) if isinstance(segment,dict))
    blocked_sessions = set(db.scalars(select(models.MobileFaceJob.assessment_session_id).where(models.MobileFaceJob.patient_id == patient_id, models.MobileFaceJob.id.in_(blocked_jobs), models.MobileFaceJob.assessment_session_id.is_not(None)))) if blocked_jobs else set()

    # Identity/permission metadata is current state; it is included regardless of event-date filter.
    metadata_models = (models.MobileAccount, models.DevicePatientLink, models.PatientAccessGrant)
    parent_models = (models.AssessmentSession, models.PianoSession)
    selected_assessments, selected_piano = set(), set()
    for model in parent_models:
        rows = [r for r in db.scalars(select(model).where(model.patient_id == patient_id).order_by(model.id)) if _within(r, lower, upper)]
        records[model.__tablename__] = [row_data(r) for r in rows]
        (selected_assessments if model is models.AssessmentSession else selected_piano).update(r.id for r in rows)
    for model in EXPORT_FIELDS:
        if model is models.Patient or model in parent_models:
            continue
        if hasattr(model, 'patient_id'):
            condition = model.patient_id == patient_id
        elif model in (models.MicroExpressionResult, models.FingerTappingResult):
            condition = model.assessment_session_id.in_(selected_assessments)
        elif model is models.PianoEvent:
            condition = model.session_id.in_(selected_piano)
        else:
            continue  # staff/session authentication data belongs only in the admin export.
        if model is models.ExpertChatTurn and actor.role != 'ADMIN':
            condition = condition & (model.operator_id == actor.id)
        if model is models.GuidedSongSession and actor.role != 'ADMIN':
            condition = condition & (model.owner_id == actor.id)
        rows = db.scalars(select(model).where(condition).order_by(*model.__table__.primary_key)).all()
        if model is models.TrainingPlan:
            rows = [r for r in rows if (not start_date or not r.end_date or r.end_date >= start_date)
                    and (not end_date or not r.start_date or r.start_date <= end_date)]
        else:
            rows = [r for r in rows if model in metadata_models or model in (models.PianoEvent, models.MicroExpressionResult, models.FingerTappingResult) or _within(r, lower, upper)]
        if model is models.FaceRecording:
            rows = [r for r in rows if r.status != 'DELETED']
        records[model.__tablename__] = [row_data(r) for r in rows]
        if not include_attachments:
            continue
        if model is models.MediaFile:
            for row in rows:
                if row.assessment_session_id in blocked_sessions:
                    continue
                item = _attachment(row.stored_path, kind='media_file', identifier=row.id, metadata_hash=row.sha256)
                if item: attachments.append(item)
        elif model is models.MobileFaceJob:
            for row in rows:
                raw_parts = Path(row.stored_path).parts if row.stored_path else ()
                expired = row.status in ('REVIEW_REQUIRED','PENDING') and row.created_at < now - timedelta(hours=24)
                blocked = len(raw_parts) > 1 and raw_parts[0] == 'training-face' and raw_parts[1] in blocked_recordings
                if row.status not in ('DELETED', 'CANCELLED') and row.id not in blocked_jobs and not blocked and not expired:
                    item = _attachment(row.stored_path, kind='mobile_face_job', identifier=row.id)
                    if item: attachments.append(item)
        elif model is models.GuidedSongSession:
            for row in rows:
                # Audio is a DB BLOB, backed up with the database, never exported inline.
                audio = row.audio
                if audio is not None:
                    attachments.append({'kind':'database_audio', 'id':row.id, 'size_bytes':len(audio), 'sha256':hashlib.sha256(audio).hexdigest(), 'metadata':safe_value(row.audio_metadata), 'backup_reference':'guided_song_sessions.audio:' + row.id})
        elif model is models.FingerTappingResult:
            for row in rows:
                item = _attachment(row.raw_timeseries_path, kind='tapping_timeseries', identifier=row.id, base_path=settings.output_path)
                if item: attachments.append(item)
        elif model is models.FaceRecording:
            for row in rows:
                data = json.loads(row.data_json)
                if row.id in blocked_recordings or not data.get('upload_complete'):
                    continue
                # Resolve paths only from validated server/file UUIDs.
                from uuid import UUID
                try:
                    recording_id = str(UUID(row.id))
                    for file in data.get('manifest', {}).get('files', []):
                        file_id = str(UUID(file['file_id']))
                        item = _attachment(str(Path('training-face') / recording_id / file_id / 'video.mp4'), kind='training_video', identifier=row.id + ':' + file_id, metadata_hash=file.get('sha256'))
                        if item: attachments.append(item)
                except (ValueError, KeyError, TypeError):
                    continue
    from app.jobs.manager import job_manager
    records['jobs'] = []
    for job in job_manager.list():
        if job.patient_id == patient_id and _within(job, lower, upper):
            snapshot = job.to_dict()
            # Error details can contain server paths; status/code is sufficient for reconciliation.
            error = snapshot.get('error') or {}
            snapshot['error'] = {'code':error.get('error',{}).get('code')} if error else None
            records['jobs'].append(safe_value(snapshot))
            item = _attachment(job.job_id + '.json', kind='job_metadata', identifier=job.job_id, base_path=job_manager.storage_dir)
            if item: attachments.append(item)
    result = {'schema_version':'1', 'generated_at':safe_value(utcnow()), 'patient':row_data(patient),
              'date_range':{'start_date':start_date.isoformat() if start_date else None, 'end_date':end_date.isoformat() if end_date else None, 'timezone':'Asia/Shanghai'},
              'records':records, 'attachments':attachments}
    result['integrity'] = {'sha256':hashlib.sha256(canonical_bytes(result)).hexdigest(), 'counts':{k:len(v) for k,v in records.items()}}
    return result


def csv_bytes(payload):
    # Long form preserves heterogeneous schemas and nested data without lossy joins.
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('category','record_id','field','value'))
    groups = {'export_metadata':[{k:payload[k] for k in ('schema_version','generated_at') if k in payload}], 'patient':[payload['patient']] if 'patient' in payload else [], **payload['records'], 'attachments':payload.get('attachments',[]), 'date_range':[payload['date_range']] if 'date_range' in payload else [], 'integrity':[payload['integrity']]}
    for category, rows in groups.items():
        for row in rows:
            for field, value in row.items():
                text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value,(dict,list)) else ('' if value is None else str(value))
                if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                    text = "'" + text
                writer.writerow((category, row.get('id', row.get('user_id',row.get('job_id',''))), field, text))
    return ('\ufeff' + output.getvalue()).encode('utf-8')


def build_administration_export(db, actor):
    """Safe account/permission metadata; auth credentials stay in controlled DB backups."""
    if actor.role != 'ADMIN' or not actor.is_active:
        raise forbidden('仅管理员可以导出账号管理数据。')
    records = {}
    for model in (models.StaffUser, models.StaffApplication, models.MobileAccount, models.MobileIdentity,
                  models.MobileSession, models.DevicePatientLink, models.PatientAccessGrant, models.PatientNumberAllocation):
        rows = db.scalars(select(model).order_by(*model.__table__.primary_key)).all()
        records[model.__tablename__] = [row_data(row) for row in rows]
    # Patient-linked conversations are in each patient export. Account-only chats
    # have no patient FK and otherwise cannot be recovered in a business export.
    chats = db.scalars(select(models.ExpertChatTurn).where(models.ExpertChatTurn.patient_id.is_(None)).order_by(models.ExpertChatTurn.id))
    records['expert_chat_turns_unlinked'] = [row_data(row) for row in chats]
    # Audit details can contain arbitrary request information: export identity and action only.
    logs = db.scalars(select(models.AuditLog).order_by(models.AuditLog.id))
    records['audit_logs'] = [{k:safe_value(getattr(row,k)) for k in ('id','staff_user_id','action','entity_type','entity_id','created_at')} for row in logs]
    result = {'schema_version':'1', 'generated_at':safe_value(utcnow()), 'records':records, 'attachments':[]}
    result['integrity'] = {'sha256':hashlib.sha256(canonical_bytes(result)).hexdigest(), 'counts':{k:len(v) for k,v in records.items()}}
    return result
