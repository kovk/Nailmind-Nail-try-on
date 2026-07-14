from __future__ import annotations

import uvicorn

from app.config import get_settings
from app.server import app


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.inference_host, port=settings.inference_port)
