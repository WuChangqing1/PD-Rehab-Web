"""Unauthenticated, read-only approved Android distribution entry points."""
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from app.services.android_distribution import verified_release

router = APIRouter(prefix="/android", tags=["Android distribution"])


@router.get("/latest")
def latest(response: Response):
    response.headers["Cache-Control"] = "no-store"
    verified = verified_release()
    if verified is None:
        return {"available": False, "message": "正式安装包准备中，请稍后再试。"}
    release, _, facts = verified
    public = release.model_dump()
    return {"available": True, "app_name": "琴伴", "download_url": release.apkUrl, **public, **facts}


@router.get("/download")
def download():
    verified = verified_release()
    if verified is None:
        raise HTTPException(404, "当前暂无已批准的正式安装包。")
    release, apk, _ = verified
    return FileResponse(apk, media_type="application/vnd.android.package-archive",
                        filename=apk.name,
                        headers={"Cache-Control": "private, no-store",
                                 "X-Content-Type-Options": "nosniff"})
