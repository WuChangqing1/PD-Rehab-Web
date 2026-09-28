"""Phase 1 end-to-end honesty check against a running backend.

Proves that the two not-yet-available analysis paths refuse truthfully instead
of returning invented data, and that no result rows are written.
"""

from __future__ import annotations

import httpx

BASE = "http://127.0.0.1:8000/api"
USERNAME = "admin"
PASSWORD = "pd-demo-2026"


def main() -> int:
    # trust_env=False: this talks to 127.0.0.1 only, and the machine's NO_PROXY
    # contains a bracketed IPv6 literal that httpx cannot parse.
    with httpx.Client(timeout=30, trust_env=False) as client:
        token = client.post(
            f"{BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        patient = client.get(
            f"{BASE}/patients", params={"page_size": 1}, headers=headers
        ).json()["items"][0]
        session = client.post(
            f"{BASE}/patients/{patient['id']}/assessment-sessions",
            json={"session_type": "MICRO_EXPRESSION_ONLY"},
            headers=headers,
        ).json()
        session_id = session["id"]
        print(f"patient {patient['hospital_number']}  session {session_id[:8]}")

        print("\n--- micro-expression upload (model NOT configured) ---")
        response = client.post(
            f"{BASE}/assessment-sessions/{session_id}/micro-expression",
            files={"video": ("face.mp4", b"not-a-real-video", "video/mp4")},
            data={"medication_state": "ON"},
            headers=headers,
        )
        print(f"status: {response.status_code}")
        print(f"body  : {response.text[:300]}")

        print("\n--- finger tapping upload (pipeline NOT implemented) ---")
        response = client.post(
            f"{BASE}/assessment-sessions/{session_id}/finger-tapping",
            files={"video": ("tap.mp4", b"not-a-real-video", "video/mp4")},
            data={"hand": "RIGHT"},
            headers=headers,
        )
        print(f"status: {response.status_code}")
        print(f"body  : {response.text[:340]}")

        print("\n--- unsupported extension must be rejected ---")
        response = client.post(
            f"{BASE}/assessment-sessions/{session_id}/finger-tapping",
            files={"video": ("notes.txt", b"hello", "text/plain")},
            data={"hand": "LEFT"},
            headers=headers,
        )
        print(f"status: {response.status_code}  code: {response.json()['error']['code']}")

        print("\n--- no result rows may have been created ---")
        info = client.get(f"{BASE}/system/info", headers=headers).json()
        counts = info["counts"]
        print(f"micro_expression_results: {counts['micro_expression_results']}")
        print(f"finger_tapping_results  : {counts['finger_tapping_results']}")
        print(f"mock_mode               : {info['mock_mode']}")

        print("\n--- model states reported by the API ---")
        models = client.get(f"{BASE}/system/models").json()
        for name, status in models["models"].items():
            print(f"  {name:32s} {status['state']:22s} ready={status['is_ready']}")

        ok = (
            counts["micro_expression_results"] == 0
            and counts["finger_tapping_results"] == 0
            and info["mock_mode"] is False
        )
        print("\nHONESTY CHECK:", "PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
