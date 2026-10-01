"""Seed virtual, de-identified demo data.

ALL DATA PRODUCED HERE IS FICTIONAL. No real patient information is used and no
real identity-card number is ever generated. Hospital numbers use the reserved
DEMO- prefix so demo rows are always distinguishable from real records.

Usage (from the project root, with the `pd` conda env active):

    python scripts/seed_demo.py                # create ~10 patients
    python scripts/seed_demo.py --reset-demo   # delete previous DEMO- rows first
    python scripts/seed_demo.py --count 20

Important: the script never writes model output or clinical scores. Finger
tapping metrics, micro-expression tags and severity values stay NULL because no
real model or analysis pipeline exists yet. Piano and Pose rows are generated
only when --with-training is passed, and they are clearly synthetic practice
records, not measurements of a real person. Every piano row is written with
`input_source="SEED_DEMO"` so the values cannot later be mistaken for a real
measurement.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import utcnow  # noqa: E402
from app.db.init_db import ensure_bootstrap_admin, ensure_schema  # noqa: E402
from app.db.models import (  # noqa: E402
    AssessmentSession,
    AuditLog,
    Baseline,
    FingerTappingResult,
    FunctionalAssessment,
    MicroExpressionResult,
    PianoEvent,
    PianoSession,
    Patient,
    PoseSession,
    StaffUser,
)
from app.db.session import DATABASE_URL, SessionLocal  # noqa: E402

DEMO_PREFIX = "DEMO-"


def _guard_database_target() -> None:
    """Refuse to seed when the .env was not loaded.

    In production the service reads DATABASE_URL from /opt/pd-rehab/.env via
    systemd's EnvironmentFile. A bare `python scripts/seed_demo.py` does not get
    that file unless it also sits where the config looks (the project root), so
    it would silently fall back to the default relative sqlite path and seed a
    completely different database. That happened once during deployment: the
    service showed 0 patients while 10 had been written to a stray file.

    Rather than trust the operator to notice, refuse when the target looks like
    an un-configured default.
    """
    relative_default = "sqlite:///./data/pd.db"
    if settings.database_url == relative_default:
        print("=" * 72, file=sys.stderr)
        print("拒绝执行：未加载到 .env，当前将写入默认开发库。", file=sys.stderr)
        print(f"  实际 DATABASE_URL = {DATABASE_URL}", file=sys.stderr)
        print(
            "  请把 .env 放到配置文件能读到的位置（项目根目录），"
            "或显式导出 DATABASE_URL 环境变量。",
            file=sys.stderr,
        )
        print(
            "  提示：服务器上 systemd 通过 EnvironmentFile=/opt/pd-rehab/.env 注入，"
            "手动执行脚本时需要自己带上同样的变量。",
            file=sys.stderr,
        )
        print("=" * 72, file=sys.stderr)
        raise SystemExit(2)

    print(f"目标数据库: {DATABASE_URL}")

# Fictional surnames + given names. Reused combos are fine: these are not people.
SURNAMES = ["张", "王", "李", "赵", "陈", "刘", "杨", "黄", "周", "吴", "徐", "孙"]
GIVEN_M = ["建国", "志强", "海涛", "文明", "国庆", "伟民", "立新", "长海"]
GIVEN_F = ["秀英", "桂芳", "丽娟", "雅琴", "小梅", "淑华", "玉兰", "文静"]
CITIES = ["北京市朝阳区", "上海市徐汇区", "广州市天河区", "成都市武侯区", "杭州市西湖区"]
MEDS = ["左旋多巴/卡比多巴", "普拉克索", "恩他卡朋", "金刚烷胺", "司来吉兰"]
STAGES = ["H-Y 1 期", "H-Y 1.5 期", "H-Y 2 期", "H-Y 2.5 期", "H-Y 3 期"]


def _clear_demo(db) -> dict[str, int]:
    """Remove rows created by a previous seeding run. Cascades handle children."""
    demo_ids = list(
        db.execute(
            select(Patient.id).where(Patient.hospital_number.like(f"{DEMO_PREFIX}%"))
        ).scalars().all()
    )
    if not demo_ids:
        return {"patients": 0}

    sessions = list(
        db.execute(
            select(AssessmentSession.id).where(AssessmentSession.patient_id.in_(demo_ids))
        ).scalars().all()
    )

    # Delete explicitly so the script works on SQLite builds without FK cascades.
    if sessions:
        db.execute(delete(MicroExpressionResult).where(
            MicroExpressionResult.assessment_session_id.in_(sessions)))
        db.execute(delete(FingerTappingResult).where(
            FingerTappingResult.assessment_session_id.in_(sessions)))
        db.execute(delete(FunctionalAssessment).where(
            FunctionalAssessment.assessment_session_id.in_(sessions)))
        db.execute(delete(AssessmentSession).where(AssessmentSession.id.in_(sessions)))

    piano_ids = list(
        db.execute(select(PianoSession.id).where(PianoSession.patient_id.in_(demo_ids)))
        .scalars().all()
    )
    if piano_ids:
        db.execute(delete(PianoEvent).where(PianoEvent.session_id.in_(piano_ids)))
        db.execute(delete(PianoSession).where(PianoSession.id.in_(piano_ids)))

    db.execute(delete(PoseSession).where(PoseSession.patient_id.in_(demo_ids)))
    db.execute(delete(FunctionalAssessment).where(FunctionalAssessment.patient_id.in_(demo_ids)))
    db.execute(delete(Baseline).where(Baseline.patient_id.in_(demo_ids)))
    db.execute(delete(Patient).where(Patient.id.in_(demo_ids)))
    db.commit()
    return {"patients": len(demo_ids), "sessions": len(sessions), "piano_sessions": len(piano_ids)}


def _make_patient(rng: random.Random, index: int) -> Patient:
    sex = rng.choice(["MALE", "FEMALE"])
    given = rng.choice(GIVEN_M if sex == "MALE" else GIVEN_F)
    surname = SURNAMES[index % len(SURNAMES)]
    name = f"{surname}{given}（虚拟）"

    age = rng.randint(52, 81)
    birthday = date.today() - timedelta(days=age * 365 + rng.randint(0, 364))
    diagnosis_years = round(rng.uniform(0.5, 12.0), 1)
    diagnosis_date = date.today() - timedelta(days=int(diagnosis_years * 365))

    return Patient(
        hospital_number=f"{DEMO_PREFIX}{index + 1:04d}",
        name=name,
        sex=sex,
        birthday=birthday,
        phone=f"1{rng.choice('3456789')}{rng.randint(100000000, 999999999)}",
        address=rng.choice(CITIES),
        emergency_contact=f"{rng.choice(SURNAMES)}{rng.choice(GIVEN_M + GIVEN_F)}（家属）",
        emergency_phone=f"1{rng.choice('3456789')}{rng.randint(100000000, 999999999)}",
        dominant_hand=rng.choice(["RIGHT", "RIGHT", "RIGHT", "LEFT"]),
        affected_side=rng.choice(["LEFT", "RIGHT", "BILATERAL", "LEFT", "RIGHT"]),
        diagnosis_date=diagnosis_date,
        disease_duration_years=diagnosis_years,
        current_stage=rng.choice(STAGES),
        current_medications="；".join(rng.sample(MEDS, k=rng.randint(1, 2))),
        last_medication_time=utcnow() - timedelta(hours=rng.randint(1, 8)),
        medication_state=rng.choice(["ON", "ON", "OFF", "UNKNOWN"]),
        medical_history=rng.choice(["高血压", "2 型糖尿病", "冠心病", "无特殊", "高脂血症"]),
        comorbidities=rng.choice(["轻度认知下降", "睡眠障碍", "便秘", "无"]),
        allergies=rng.choice(["无", "青霉素过敏", "磺胺类过敏"]),
        surgery_history=rng.choice(["无", "阑尾切除术", "胆囊切除术"]),
        rehab_history=rng.choice(["既往未系统康复", "社区康复 3 个月", "居家训练 6 个月"]),
        # A clinical note, not a disclaimer. The record's provenance is already
        # carried by every field that needs it -- the name suffix, the per-row
        # input_source markers and the audit log -- and a note that says "this is
        # a demo patient" printed under 医生备注 reads to a clinician as a remark
        # about the person. It belongs in the data model, not in the chart.
        doctor_notes=rng.choice(["规律服药，症状波动以午后为主。", "家属陪同就诊，可配合居家训练。", "步态稍慢，转身时需注意防跌倒。"]),
    )


def _seed_sessions(db, patient: Patient, rng: random.Random, *, with_training: bool) -> dict:
    """Create assessment history plus, optionally, clearly-synthetic training rows."""
    created = {"sessions": 0, "piano": 0, "pose": 0, "functional": 0}

    # Baseline assessment is the earliest; then a follow-up reassessment.
    offsets = [-90, -45, -14] if rng.random() < 0.65 else [-60, -7]
    session_ids: list[tuple[str, datetime, str]] = []

    for offset in offsets:
        when = utcnow() + timedelta(days=offset, hours=rng.randint(-4, 4))
        session = AssessmentSession(
            patient_id=patient.id,
            session_type="COMPREHENSIVE",
            medication_state=patient.medication_state,
            status="COMPLETED",
            started_at=when,
            completed_at=when + timedelta(minutes=rng.randint(12, 30)),
            notes="虚拟演示评估记录。",
            created_at=when,
        )
        db.add(session)
        db.flush()
        session_ids.append((session.id, when, session.medication_state))
        created["sessions"] += 1

    db.commit()

    # Functional test: 9-HPT is the only one implemented in v1.
    for session_id, when, med in session_ids:
        for hand in ("LEFT", "RIGHT"):
            db.add(
                FunctionalAssessment(
                    patient_id=patient.id,
                    assessment_session_id=session_id,
                    test_type="NINE_HOLE_PEG",
                    hand=hand,
                    value_primary=round(rng.uniform(22.0, 48.0), 1),
                    unit="s",
                    medication_state=med,
                    notes="虚拟演示数据（人工录入值）。",
                    performed_at=when + timedelta(minutes=25),
                )
            )
            created["functional"] += 1
    db.commit()

    if not with_training:
        return created

    # --- Synthetic piano training history ---
    for i, (session_id, when, _med) in enumerate(session_ids):
        for round_number in (1, 2, 3):
            start = when + timedelta(days=2 + i, hours=round_number)
            piano = PianoSession(
                patient_id=patient.id,
                mode="SINGLE_KEY_RHYTHM" if round_number == 1 else "ALTERNATING_HANDS",
                round_number=round_number,
                # Provenance marker: these rows carry randomised summary values
                # and have no raw events at all, so they must never be read as a
                # measurement. Phase 8 trends exclude this value.
                input_source="SEED_DEMO",
                bpm=60 + (round_number - 1) * 5,
                judgement_window_ms=300 - (round_number - 1) * 25,
                sequence_length=4 + (round_number - 1),
                note_density=1.0,
                hand_mode="SINGLE" if round_number == 1 else "ALTERNATING",
                weak_side_ratio=0.5,
                finger_complexity=min(3, round_number),
                session_duration_sec=60,
                accuracy=round(rng.uniform(0.72, 0.96), 3),
                miss_rate=round(rng.uniform(0.0, 0.12), 3),
                mean_response_latency_ms=round(rng.uniform(280, 620), 1),
                response_latency_cv=round(rng.uniform(0.12, 0.42), 3),
                mean_timing_error_ms=round(rng.uniform(-60, 60), 1),
                timing_mae_ms=round(rng.uniform(45, 160), 1),
                left_mean_latency=round(rng.uniform(300, 680), 1),
                right_mean_latency=round(rng.uniform(280, 640), 1),
                left_accuracy=round(rng.uniform(0.68, 0.95), 3),
                right_accuracy=round(rng.uniform(0.70, 0.97), 3),
                weak_finger_error_rate=round(rng.uniform(0.05, 0.35), 3),
                session_completion_rate=1.0,
                difficulty_engine_version=settings.piano_difficulty_version,
                metrics_version=settings.piano_metrics_version,
                started_at=start,
                completed_at=start + timedelta(seconds=60),
            )
            db.add(piano)
            created["piano"] += 1
    db.commit()

    # --- Synthetic pose training history ---
    exercise_keys = [
        "MOUNTAIN_ARMS_UP",
        "ARMS_LATERAL_RAISE",
        "SIDE_BEND_STRETCH",
        "SEATED_TRUNK_ROTATION",
        "SEATED_ALTERNATING_ARM_RAISE",
    ]
    for session_id, when, _med in session_ids:
        for key in rng.sample(exercise_keys, k=2):
            start = when + timedelta(days=3, hours=rng.randint(1, 6))
            # Display scores stay NULL: their formulas are not defined yet.
            # Only raw, interpretable quantities are filled in.
            db.add(
                PoseSession(
                    patient_id=patient.id,
                    exercise_type=key,
                    difficulty_json=json.dumps(
                        {"hold_time_sec": 5.0, "target_repetitions": 5}, ensure_ascii=False
                    ),
                    completion_score=None,
                    range_of_motion=None,
                    symmetry_score=None,
                    stability_score=None,
                    hold_time_sec=round(rng.uniform(3.0, 9.0), 1),
                    repetition_count=rng.randint(3, 9),
                    movement_speed=round(rng.uniform(25.0, 70.0), 1),
                    valid_pose_frame_ratio=round(rng.uniform(0.72, 0.98), 3),
                    raw_metrics_json=json.dumps(
                        {
                            "left_shoulder_max_angle_deg": round(rng.uniform(120, 175), 1),
                            "right_shoulder_max_angle_deg": round(rng.uniform(120, 175), 1),
                            "trunk_angle_deg": round(rng.uniform(-8, 8), 1),
                            "angle_std_deg": round(rng.uniform(1.5, 7.5), 2),
                        },
                        ensure_ascii=False,
                    ),
                    algorithm_version=settings.pose_metrics_version,
                    exercise_definition_version="pose-exercises-v0.1.0-draft",
                    started_at=start,
                    completed_at=start + timedelta(minutes=3),
                )
            )
            created["pose"] += 1
    db.commit()

    # --- Versioned baseline snapshot ---
    oldest = min(session_ids, key=lambda item: item[1])
    db.add(
        Baseline(
            patient_id=patient.id,
            baseline_type="COMPREHENSIVE",
            source_id=oldest[0],
            snapshot_json=json.dumps(
                {
                    "assessment_time": oldest[1].isoformat(),
                    "medication_state": oldest[2],
                    "micro_expression": None,
                    "finger_tapping_left": None,
                    "finger_tapping_right": None,
                    "piano_calibration": None,
                    "quality_metadata": {"source": "seed_demo", "synthetic": True},
                    "note": (
                        "虚拟演示 Baseline。模型输出与运动学指标为空，"
                        "因为尚无真实模型与分析流水线。"
                    ),
                },
                ensure_ascii=False,
            ),
            algorithm_version=None,
            is_active=True,
            created_at=oldest[1],
        )
    )
    db.commit()
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed virtual demo data (fictional only).")
    parser.add_argument("--count", type=int, default=10, help="number of patients (default 10)")
    parser.add_argument("--seed", type=int, default=20260928, help="random seed")
    parser.add_argument("--reset-demo", action="store_true",
                        help="delete previously seeded DEMO- rows first")
    parser.add_argument("--with-training", action="store_true",
                        help="also create synthetic piano / pose training rows")
    args = parser.parse_args()

    setup_logging()
    _guard_database_target()
    ensure_schema()
    created = ensure_bootstrap_admin()
    if created:
        print(f"已创建初始管理员账号：{settings.bootstrap_admin_username}")

    rng = random.Random(args.seed)

    with SessionLocal() as db:
        if args.reset_demo:
            removed = _clear_demo(db)
            print(f"已清理旧的 DEMO 数据：{removed}")

        admin = db.execute(select(StaffUser).limit(1)).scalar_one_or_none()
        created_by = admin.id if admin else None

        totals = {"patients": 0, "sessions": 0, "piano": 0, "pose": 0, "functional": 0}
        for index in range(args.count):
            patient = _make_patient(rng, index)
            existing = db.execute(
                select(Patient.id).where(Patient.hospital_number == patient.hospital_number)
            ).scalar_one_or_none()
            if existing is not None:
                print(f"跳过已存在的编号 {patient.hospital_number}")
                continue
            db.add(patient)
            db.commit()
            db.refresh(patient)
            totals["patients"] += 1

            stats = _seed_sessions(db, patient, rng, with_training=args.with_training)
            for key, value in stats.items():
                totals[key] += value

        db.add(
            AuditLog(
                staff_user_id=created_by,
                action="SEED_DEMO",
                entity_type="system",
                entity_id=None,
                detail_json=json.dumps(
                    {"count": args.count, "with_training": args.with_training,
                     "synthetic": True},
                    ensure_ascii=False,
                ),
                created_at=utcnow(),
            )
        )
        db.commit()

    print("\n演示数据生成完成（全部为虚构数据）：")
    print(f"  患者            : {totals['patients']}")
    print(f"  评估会话        : {totals['sessions']}")
    print(f"  9-HPT 记录      : {totals['functional']}")
    print(f"  钢琴训练        : {totals['piano']}")
    print(f"  动作训练        : {totals['pose']}")
    print("\n注意：")
    print("  - 微表情模型输出、Finger Tapping 运动学指标与严重度字段均为 NULL。")
    print("  - Pose 展示分（completion / ROM / symmetry / stability）为 NULL，公式尚未定义。")
    print("  - 患者编号统一以 DEMO- 前缀，便于与真实数据区分。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
