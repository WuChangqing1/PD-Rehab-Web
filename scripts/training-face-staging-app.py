"""Loopback staging UI/API entry point; never used by the production unit."""
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.main import app

dist = (Path(__file__).resolve().parents[1] / 'frontend' / 'dist').resolve()


@app.get('/{path:path}', include_in_schema=False)
def frontend(path: str):
    if path == 'api' or path.startswith('api/'):
        raise HTTPException(404)
    target = (dist / path).resolve()
    if not target.is_relative_to(dist):
        raise HTTPException(404)
    if target.is_file():
        return FileResponse(target)
    if Path(path).suffix:
        raise HTTPException(404)
    return FileResponse(dist / 'index.html')
