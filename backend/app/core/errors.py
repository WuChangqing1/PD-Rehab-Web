"""Unified API error contract.

Every error returned by the API has the shape:

    {"error": {"code": "...", "message": "...", "detail": {...}|null}}

(code, message) is stable and machine-readable; detail is optional context.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class ErrorCode:
    """Stable error codes. Keep in sync with docs/model_integration.md."""

    # generic
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # auth
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    INACTIVE_USER = "INACTIVE_USER"

    # models
    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    CUDA_OUT_OF_MEMORY = "CUDA_OUT_OF_MEMORY"

    # media / video
    VIDEO_UNREADABLE = "VIDEO_UNREADABLE"
    VIDEO_FPS_INVALID = "VIDEO_FPS_INVALID"
    VIDEO_TOO_SHORT = "VIDEO_TOO_SHORT"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"

    # finger tapping QC
    HAND_NOT_DETECTED = "HAND_NOT_DETECTED"
    LOW_VALID_FRAME_RATIO = "LOW_VALID_FRAME_RATIO"
    LANDMARK_DISCONTINUOUS = "LANDMARK_DISCONTINUOUS"
    INSUFFICIENT_CYCLES = "INSUFFICIENT_CYCLES"

    # not yet built
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


def error_body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "detail": detail}}


class APIError(HTTPException):
    """HTTPException that renders the unified error contract."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail=error_body(code, message, detail),
            headers=headers,
        )
        self.code = code
        self.message = message
        self.detail_payload = detail


def not_found(message: str, detail: Any = None) -> APIError:
    return APIError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, message, detail)


def conflict(message: str, detail: Any = None) -> APIError:
    return APIError(status.HTTP_409_CONFLICT, ErrorCode.CONFLICT, message, detail)


def bad_request(code: str, message: str, detail: Any = None) -> APIError:
    return APIError(status.HTTP_400_BAD_REQUEST, code, message, detail)


def unauthorized(
    message: str = "登录状态无效或已过期，请重新登录。",
    code: str = ErrorCode.NOT_AUTHENTICATED,
    detail: Any = None,
    headers: dict[str, str] | None = None,
) -> APIError:
    return APIError(
        status.HTTP_401_UNAUTHORIZED, code, message, detail, headers=headers
    )


def forbidden(message: str = "当前账号无权执行该操作。", detail: Any = None) -> APIError:
    return APIError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN, message, detail)


def model_not_configured(detail: Any = None) -> APIError:
    """503 used whenever a real model is required but not configured.

    The system must never silently fall back to mock/fabricated output.
    """
    return APIError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        ErrorCode.MODEL_NOT_CONFIGURED,
        "微表情 / AI 模型尚未配置，无法进行分析。请联系管理员配置模型目录。",
        detail,
    )


def not_implemented(what: str, phase: str = "") -> APIError:
    """501 for endpoints whose implementation belongs to a later phase."""
    suffix = f"（计划于 {phase} 实现）" if phase else ""
    return APIError(
        status.HTTP_501_NOT_IMPLEMENTED,
        ErrorCode.NOT_IMPLEMENTED,
        f"{what} 尚未实现{suffix}。",
        {"feature": what, "phase": phase or None},
    )
