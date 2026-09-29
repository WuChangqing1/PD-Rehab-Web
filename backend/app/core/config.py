"""Application configuration loaded from environment / .env file.

All values have safe development defaults so the app starts with no .env present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = .../PD-Rehab-Web  (this file is backend/app/core/config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- application ----------
    app_name: str = "PD-Rehab-Web"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # ---------- database ----------
    database_url: str = "sqlite:///./data/pd.db"
    db_echo: bool = False

    # ---------- auth ----------
    jwt_secret: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # ---------- storage ----------
    upload_dir: str = "./data/uploads"
    output_dir: str = "./data/outputs"
    report_dir: str = "./data/reports"
    max_upload_size_mb: int = 500
    allowed_video_extensions: str = ".mp4,.mov,.avi"

    # ---------- micro expression model ----------
    micro_expression_model_dir: str = ""
    micro_expression_entry: str = ""
    micro_expression_checkpoint: str = ""
    micro_expression_device: str = ""

    # ---------- finger tapping ----------
    finger_tapping_repo_dir: str = r"D:/CodingData/Github/VideoBased-PD-Biomarkers"
    hand_landmarker_path: str = ""
    # Expected hash of the MediaPipe Hand Landmarker shipped with the external
    # repository; recorded in raw_features so an analysis can be tied to the
    # exact model bytes used.
    hand_landmarker_sha256: str = (
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
    )

    # ---------- inference ----------
    use_gpu: bool = True
    gpu_inference_concurrency: int = 1
    torch_num_threads: int = 4

    # ---------- demo ----------
    demo_mock_mode: bool = False

    # ---------- algorithm versions ----------
    ft_feature_algorithm_version: str = "ft-features-v1.0.0"
    ft_qc_algorithm_version: str = "ft-qc-v1.0.0"
    ft_compare_algorithm_version: str = "ft-compare-v1.0.0"
    piano_metrics_version: str = "piano-metrics-v1.0.0"
    piano_difficulty_version: str = "piano-difficulty-v1.1.0"
    pose_metrics_version: str = "pose-metrics-v1.0.0"
    feature_schema_version: str = "1.0"

    # ---------- bootstrap admin ----------
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "CHANGE_ME_admin"
    bootstrap_admin_display_name: str = "系统管理员"

    @field_validator("log_level")
    @classmethod
    def _upper_level(cls, v: str) -> str:
        return (v or "INFO").upper()

    # ---------- derived helpers ----------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_video_suffixes(self) -> set[str]:
        return {
            s.strip().lower()
            for s in self.allowed_video_extensions.split(",")
            if s.strip()
        }

    def _resolve(self, raw: str) -> Path:
        p = Path(raw)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    @property
    def upload_path(self) -> Path:
        return self._resolve(self.upload_dir)

    @property
    def output_path(self) -> Path:
        return self._resolve(self.output_dir)

    @property
    def report_path(self) -> Path:
        return self._resolve(self.report_dir)

    @property
    def model_base_path(self) -> Path:
        return PROJECT_ROOT / "models"

    @property
    def mediapipe_model_path(self) -> Path:
        """Resolve the MediaPipe hand landmarker, or the first existing fallback."""
        if self.hand_landmarker_path.strip():
            return self._resolve(self.hand_landmarker_path)
        candidates = [
            self.model_base_path / "mediapipe" / "hand_landmarker.task",
            Path(self.finger_tapping_repo_dir) / "src" / "demo" / "hand_landmarker.task",
        ]
        for c in candidates:
            if c.is_file():
                return c
        return candidates[0]

    @property
    def micro_expression_path(self) -> Path | None:
        raw = self.micro_expression_model_dir.strip()
        if not raw:
            return None
        p = self._resolve(raw)
        return p if p.is_dir() else None

    def ensure_directories(self) -> None:
        for p in (self.upload_path, self.output_path, self.report_path):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
