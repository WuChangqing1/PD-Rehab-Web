"""Hidden-input ASR setup. Run locally; never pass the key as a CLI argument."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings
from app.services.asr_stream import open_provider, command, valid_endpoint


async def probe():
    import uuid
    task_id = str(uuid.uuid4())
    async with open_provider() as provider:
        await provider.send(command("run-task", task_id))
        result = json.loads(await asyncio.wait_for(provider.recv(), 10))
        if result.get("header", {}).get("event") != "task-started":
            raise ValueError("startup failed")
        # A zero-audio task can have no transcription result. Startup ACK proves
        # authorization/protocol readiness; closing cancels the empty task.


def main():
    parser = argparse.ArgumentParser(description="Configure Fun-ASR without echoing the API Key")
    parser.add_argument("--output", type=Path, default=ROOT / "backend" / ".asr.env")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("请在自己的交互式终端运行，以便隐藏输入密钥。")
    endpoint = input("百炼北京地域 WebSocket 地址（回车使用 dashscope.aliyuncs.com）：").strip()
    endpoint = endpoint or "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    if not valid_endpoint(endpoint):
        raise SystemExit("地址不符合百炼北京地域 WebSocket 白名单，未保存。")
    key = getpass.getpass("百炼 API Key（输入隐藏，回车取消）：").strip()
    if not key:
        raise SystemExit("已取消，未修改配置。")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{10,512}", key):
        raise SystemExit("密钥格式无效，未保存。")
    settings.asr_enabled, settings.asr_api_key, settings.asr_ws_url = True, key, endpoint
    settings.asr_model = "fun-asr-realtime"
    try:
        asyncio.run(probe())
    except Exception:
        raise SystemExit("服务连接验证失败，未修改配置。请检查地域、开通状态、网络和密钥权限。") from None
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".asr.env.", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            # Restrict access before writing any secret bytes, including Windows ACLs.
            if os.name == "nt":
                identity = subprocess.check_output(["whoami"], text=True).strip()
                try:
                    subprocess.run(["icacls", temporary, "/inheritance:r", "/grant:r", identity+":(F)"],
                                   capture_output=True, check=True)
                except subprocess.CalledProcessError:
                    raise SystemExit("无法限制密钥文件权限，未保存配置。") from None
            os.chmod(temporary, 0o600)
            f.write(f"ASR_ENABLED=true\nASR_API_KEY={key}\nASR_WS_URL={endpoint}\nASR_MODEL=fun-asr-realtime\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("配置已保存：", output)
    print("已验证服务连接；尚未验证语音识别效果。重启本地后端后可试用。未操作线上服务。")


if __name__ == "__main__":
    main()
