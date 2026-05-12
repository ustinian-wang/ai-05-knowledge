from __future__ import annotations

import os

import uvicorn

from api.app import app
from app.config import load_settings, settings

__all__ = ["app"]


if __name__ == "__main__":
    load_settings()
    port = int(os.getenv("PORT", os.getenv("BACKEND_PORT", str(settings.backend_port))))
    host = os.getenv("BACKEND_HOST", settings.backend_host).strip() or "127.0.0.1"
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
