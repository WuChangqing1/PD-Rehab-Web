"""Phase 0 environment & model presence probe.

Read-only diagnostic tool. It NEVER fabricates model output: it only reports
whether the real components exist on this machine.

Usage (from the project root, with the `pd` conda env active):

    python scripts/check_models.py
    python scripts/check_models.py --video path/to/video.mp4

Exit code is always 0 unless an unexpected internal error occurs; the report
itself carries the status of every component.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Candidate locations for the teacher's micro-expression / PD model.
# The model source directory has NOT been provided yet, so these are only
# *probes*: finding nothing here means MODEL_NOT_CONFIGURED, not "no model".
MICRO_EXPRESSION_CANDIDATES = [
    os.environ.get("MICRO_EXPRESSION_MODEL_DIR", ""),
    str(PROJECT_ROOT / "models" / "micro_expression"),
    r"D:\CodingData\Github\micro-expression",
    r"D:\CodingData\Github\micro_expression",
    r"D:\CodingData\Github\MicroExpression",
    r"D:\CodingData\Github\PD-MicroExpression",
]

FINGER_TAPPING_REPO_DEFAULT = r"D:\CodingData\Github\VideoBased-PD-Biomarkers"

# Model weight suffixes that must never be committed to the public repository.
WEIGHT_SUFFIXES = {".pt", ".pth", ".ckpt", ".onnx", ".engine", ".h5", ".bin", ".safetensors", ".joblib", ".pkl"}


def hr(title: str) -> None:
    print()
    print("=" * 74)
    print(title)
    print("=" * 74)


def sha256_of(path: Path, limit_mb: int | None = None) -> str:
    h = hashlib.sha256()
    read = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            read += len(chunk)
            if limit_mb and read >= limit_mb * 1024 * 1024:
                break
    return h.hexdigest()


def module_status(name: str) -> dict[str, Any]:
    """Return import status + version for a module without hard-failing."""
    try:
        mod = importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001 - we want the real reason
        return {"installed": False, "version": None, "error": f"{type(exc).__name__}: {exc}"}
    version = getattr(mod, "__version__", None)
    if version is None:
        version = getattr(mod, "version", None)
    return {"installed": True, "version": str(version) if version else "unknown", "error": None}


def check_python() -> dict[str, Any]:
    hr("1. PYTHON / PLATFORM")
    info = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "sys_prefix": sys.prefix,
        "conda_default_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cwd": os.getcwd(),
        "project_root": str(PROJECT_ROOT),
    }
    for k, v in info.items():
        print(f"  {k:24s}: {v}")
    in_pd_env = "envs\\pd" in sys.executable.lower() or "envs/pd" in sys.executable.lower()
    print(f"  {'is pd env':24s}: {in_pd_env}")
    info["is_pd_env"] = in_pd_env
    return info


def check_gpu_torch() -> dict[str, Any]:
    hr("2. GPU / NVIDIA DRIVER")
    info: dict[str, Any] = {}
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free,compute_cap",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            print(out.stdout.strip() or "(empty)")
            info["nvidia_smi_query"] = out.stdout.strip()
            full = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=30, check=False)
            for line in full.stdout.splitlines():
                if "CUDA UMD Version" in line or "NVIDIA-SMI" in line:
                    print("  " + line.strip())
                    info.setdefault("nvidia_smi_header", []).append(line.strip())
        except Exception as exc:  # noqa: BLE001
            print(f"  nvidia-smi failed: {exc}")
            info["nvidia_smi_error"] = str(exc)
    else:
        print("  nvidia-smi: NOT FOUND on PATH")
        info["nvidia_smi_query"] = None

    hr("3. PYTORCH")
    torch_status = module_status("torch")
    print(f"  torch installed : {torch_status['installed']}")
    print(f"  torch version   : {torch_status['version']}")
    if torch_status["error"]:
        print(f"  import error    : {torch_status['error']}")
    info["torch"] = torch_status

    if torch_status["installed"]:
        try:
            import torch  # noqa: PLC0415

            info["torch_cuda_is_available"] = bool(torch.cuda.is_available())
            info["torch_version_cuda"] = torch.version.cuda
            info["torch_cudnn_version"] = torch.backends.cudnn.version()
            if torch.cuda.is_available():
                info["torch_device_name"] = torch.cuda.get_device_name(0)
                info["torch_device_capability"] = torch.cuda.get_device_capability(0)
            else:
                info["torch_device_name"] = "CPU"
                info["torch_device_capability"] = None
            print(f"  torch.version.cuda        : {info['torch_version_cuda']}")
            print(f"  torch.backends.cudnn      : {info['torch_cudnn_version']}")
            print(f"  torch.cuda.is_available() : {info['torch_cuda_is_available']}")
            print(f"  device                    : {info['torch_device_name']}")
            print(f"  capability                : {info['torch_device_capability']}")
        except Exception as exc:  # noqa: BLE001
            print(f"  torch runtime probe failed: {type(exc).__name__}: {exc}")
            info["torch_runtime_error"] = str(exc)
    else:
        print("  -> PyTorch NOT INSTALLED in this environment (expected for Phase 0).")
        info["torch_cuda_is_available"] = None
    return info


def check_libs() -> dict[str, Any]:
    hr("4. BACKEND LIBRARIES")
    libs = [
        "numpy", "scipy", "pandas", "sklearn", "cv2", "mediapipe",
        "fastapi", "uvicorn", "sqlalchemy", "alembic", "pydantic",
        "pydantic_settings", "multipart", "aiofiles", "jose", "passlib",
        "pymysql", "lightgbm", "optuna", "matplotlib", "PIL",
    ]
    result: dict[str, Any] = {}
    for name in libs:
        st = module_status(name)
        result[name] = st
        mark = "OK " if st["installed"] else "-- "
        print(f"  {mark}{name:18s} {st['version'] or ''}")
    return result


def check_micro_expression() -> dict[str, Any]:
    hr("5. TEACHER MICRO-EXPRESSION / PD MODEL")
    print("  Probed candidate directories:")
    found: list[str] = []
    for cand in MICRO_EXPRESSION_CANDIDATES:
        if not cand:
            print("    (env MICRO_EXPRESSION_MODEL_DIR is empty)")
            continue
        p = Path(cand)
        exists = p.is_dir()
        print(f"    [{'FOUND' if exists else '  -  '}] {cand}")
        if exists:
            found.append(str(p))
            for child in sorted(p.iterdir())[:30]:
                print(f"            {child.name}")

    print()
    if found:
        print("  STATUS: MODEL_DIRECTORY_PRESENT (still requires source inspection before use)")
    else:
        print("  STATUS: MODEL_NOT_CONFIGURED")
        print("  The adapter must report MODEL_NOT_CONFIGURED and MUST NOT fabricate")
        print("  tags, probabilities or any other model output.")
    return {"candidates": MICRO_EXPRESSION_CANDIDATES, "found": found,
            "status": "MODEL_DIRECTORY_PRESENT" if found else "MODEL_NOT_CONFIGURED"}


def check_finger_tapping_repo(repo: str) -> dict[str, Any]:
    hr("6. FINGER TAPPING EXTERNAL REPOSITORY")
    p = Path(repo)
    info: dict[str, Any] = {"path": repo, "exists": p.is_dir()}
    print(f"  path   : {repo}")
    print(f"  exists : {p.is_dir()}")
    if not p.is_dir():
        print("  STATUS: REPO_NOT_FOUND")
        return info

    expected = [
        Path("src/preprocessing/keypoint_extraction.py"),
        Path("src/feature extraction/feature_extraction.py"),
        Path("src/training/optimization_training.py"),
        Path("src/demo/ft_video_analysis.py"),
        Path("src/demo/la_video_analysis.py"),
        Path("environment.yml"),
        Path("README.md"),
    ]
    print("\n  Key files:")
    for rel in expected:
        f = p / rel
        if f.is_file():
            print(f"    OK  {rel}  ({f.stat().st_size} bytes)")
            info.setdefault("key_files", {})[str(rel)] = f.stat().st_size
        else:
            print(f"    --  {rel}  MISSING")

    print("\n  MediaPipe hand landmarker model assets found:")
    task_files = list(p.rglob("*.task"))
    if task_files:
        for tf in task_files:
            digest = sha256_of(tf)
            print(f"    {tf.relative_to(p)}  {tf.stat().st_size} bytes  sha256={digest}")
            info.setdefault("landmarker_assets", []).append(
                {"rel": str(tf.relative_to(p)), "size": tf.stat().st_size, "sha256": digest}
            )
    else:
        print("    (none found - the repo downloads it on first run)")
        info["landmarker_assets"] = []

    print("\n  Trained severity / classification model weights found:")
    weights = [f for f in p.rglob("*") if f.is_file()
               and f.suffix.lower() in WEIGHT_SUFFIXES
               and ".git" not in f.parts]
    if weights:
        for w in weights:
            print(f"    {w.relative_to(p)}  {w.stat().st_size} bytes")
    else:
        print("    NONE -> no pretrained MCI/severity classifier ships with this repository.")
        print("    => severity_score / severity_label must stay NULL (NEEDS_IMPLEMENTATION).")
    info["trained_weights"] = [str(w.relative_to(p)) for w in weights]

    print("\n  Git state (read-only):")
    for args in (["rev-parse", "HEAD"], ["status", "--porcelain"], ["remote", "-v"]):
        try:
            out = subprocess.run(["git", "-C", str(p), *args],
                                 capture_output=True, text=True, timeout=30, check=False)
            print(f"    git {' '.join(args)}: {out.stdout.strip() or '(clean/empty)'}")
        except Exception as exc:  # noqa: BLE001
            print(f"    git {' '.join(args)} failed: {exc}")
    return info


def probe_video(path: str) -> dict[str, Any]:
    hr("7. VIDEO PROBE")
    p = Path(path)
    info: dict[str, Any] = {"path": str(p), "exists": p.is_file()}
    if not p.is_file():
        print(f"  NOT FOUND: {path}")
        return info
    info["size_bytes"] = p.stat().st_size
    print(f"  size: {info['size_bytes']} bytes")

    st = module_status("cv2")
    if not st["installed"]:
        print("  OpenCV not installed -> cannot read frame metadata yet.")
        print("  (MediaInfo/ffprobe fallback not attempted)")
        info["note"] = "opencv-not-installed"
        return info

    import cv2  # noqa: PLC0415

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        print("  OpenCV could NOT open the file (codec/container unsupported?).")
        info["readable"] = False
        return info
    info["readable"] = True
    info["fps"] = cap.get(cv2.CAP_PROP_FPS)
    info["frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    info["fourcc"] = int(cap.get(cv2.CAP_PROP_FOURCC))
    cc = "".join(chr((info["fourcc"] >> (8 * i)) & 0xFF) for i in range(4))
    info["fourcc_str"] = cc
    if info["fps"] and info["fps"] > 0:
        info["duration_sec"] = info["frame_count"] / info["fps"]
    cap.release()
    for k in ("fps", "frame_count", "width", "height", "fourcc_str", "duration_sec"):
        print(f"  {k:14s}: {info.get(k)}")
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 environment / model presence probe (read-only).")
    parser.add_argument("--video", action="append", default=[],
                        help="Optional video path(s) to probe. May be repeated.")
    parser.add_argument("--repo", default=os.environ.get("FINGER_TAPPING_REPO_DIR", FINGER_TAPPING_REPO_DEFAULT),
                        help="Path to the VideoBased-PD-Biomarkers repository.")
    parser.add_argument("--json", dest="json_out", default=None,
                        help="Write the full report as JSON to this path.")
    args = parser.parse_args()

    report: dict[str, Any] = {}
    report["python"] = check_python()
    report["gpu_torch"] = check_gpu_torch()
    report["libraries"] = check_libs()
    report["micro_expression"] = check_micro_expression()
    report["finger_tapping_repo"] = check_finger_tapping_repo(args.repo)
    if args.video:
        report["videos"] = [probe_video(v) for v in args.video]

    hr("SUMMARY")
    gpu = report["gpu_torch"]
    print(f"  Python            : {report['python']['python_version'].split()[0]}")
    print(f"  is pd env         : {report['python']['is_pd_env']}")
    print(f"  torch installed   : {gpu['torch']['installed']}")
    print(f"  cuda available    : {gpu.get('torch_cuda_is_available')}")
    print(f"  micro-expression  : {report['micro_expression']['status']}")
    print(f"  FT repo present   : {report['finger_tapping_repo']['exists']}")
    print(f"  FT pretrained clf : {'YES' if report['finger_tapping_repo'].get('trained_weights') else 'NO'}")

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  JSON report written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
