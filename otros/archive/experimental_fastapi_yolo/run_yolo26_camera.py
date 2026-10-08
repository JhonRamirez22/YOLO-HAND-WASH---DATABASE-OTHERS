#!/usr/bin/env python3
"""Start the native YOLO26 camera gateway on the local computer."""

import os
import sys
from pathlib import Path
import uvicorn


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    uvicorn.run(
        "archive.experimental_fastapi_yolo.yolo26_camera_service:app",
        # Historical experiment only; the supported station does not launch it.
        host=os.getenv("HANDWASH_YOLO_HOST", "127.0.0.1"),
        port=int(os.getenv("HANDWASH_YOLO_PORT", "8090")),
        reload=False,
    )
