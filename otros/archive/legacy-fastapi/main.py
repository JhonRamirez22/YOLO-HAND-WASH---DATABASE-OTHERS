"""
Hand Wash Compliance System - FastAPI Backend
Main application with WebSocket endpoints
Based on AGENTS.md architecture
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from schemas.models import (
    StartSessionRequest, ProtocolType,
    HandWashStatusResponse, HandWashSessionSummary
)
from agents.receptor import receptor
from services.inference import pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hand Wash Compliance System",
    description="Real-time hand wash verification based on WHO protocol",
    version="1.0.0"
)

# CORS - Allow iOS client and web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the web dashboard"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "message": "Hand Wash Compliance System API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "test": "/test",
            "create_session": "POST /api/session",
            "websocket": "ws://localhost:8000/ws/{session_id}"
        }
    }


@app.get("/test")
async def test_page():
    """Serve the iPhone camera test page"""
    test_path = FRONTEND_DIR / "test.html"
    if test_path.exists():
        return FileResponse(str(test_path))
    return {"error": "test.html not found"}


@app.post("/api/session")
async def crear_sesion(request: StartSessionRequest):
    """Create a new hand wash session"""
    session_id = receptor.crear_sesion(request.protocolo)
    return {
        "sessionId": session_id,
        "protocolo": request.protocolo.value,
        "mensaje": "Sesion creada. Conecta via WebSocket para recibir actualizaciones."
    }


@app.get("/api/session/{session_id}")
async def obtener_sesion(session_id: str):
    """Get session status"""
    session = receptor.obtener_sesion(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "sessionId": session.session_id,
        "protocolo": session.protocolo.value,
        "estado": session.evaluador.estado_sesion.value,
        "pasoActual": session.evaluador.get_estado_actual(),
        "progreso": session.evaluador.get_progreso().model_dump(),
        "duracionMs": session.get_duracion_ms(),
        "detallesPasos": [d.model_dump() for d in session.evaluador.get_detalles_pasos()]
    }


@app.get("/api/protocols")
async def obtener_protocolos():
    """Get available validation protocols"""
    from agents.validador_reglas import RulesValidator
    protocols = {}
    for proto in ProtocolType:
        v = RulesValidator(proto)
        protocols[proto.value] = v.get_resumen_protocolo()
    return protocols


@app.delete("/api/session/{session_id}")
async def eliminar_sesion(session_id: str):
    """Delete a session"""
    receptor.eliminar_sesion(session_id)
    return {"message": f"Session {session_id} deleted"}


@app.post("/api/infer")
async def inferir_imagen(
    file: UploadFile = File(...),
    session_id: str = None
):
    """
    2-stage inference pipeline:
      1. hand_yolov8s → detects if a hand is present
      2. yolo26n (7-class) → classifies which hand wash step

    If session_id is provided, also processes through sequence validation.
    """
    image_bytes = await file.read()
    result = pipeline.infer_from_bytes(image_bytes)

    # If session provided, also process through agent pipeline
    if session_id and result["claseBackend"]:
        from schemas.models import DetectionEventRequest
        from datetime import datetime

        evento = DetectionEventRequest(
            sessionId=session_id,
            claseDetectada=result["claseBackend"],
            confianza=result["pasoConfianza"],
            timestamp=datetime.utcnow()
        )
        agent_result = await receptor.procesar_deteccion(evento)
        result["validacionSecuencia"] = agent_result

    return result


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time hand wash monitoring.
    Client sends DeteccionEvento JSON, server responds with EstadoLavadoResponse.
    """
    await websocket.accept()
    receptor.notificador.registrar_conexion(session_id, websocket)
    logger.info(f"WebSocket connected for session {session_id}")

    try:
        while True:
            # Receive detection event from client
            data = await websocket.receive_text()
            try:
                evento_dict = json.loads(data)

                # Create DeteccionEvento
                from schemas.models import DetectionEventRequest
                evento = DetectionEventRequest(
                    sessionId=session_id,
                    claseDetectada=evento_dict.get("claseDetectada", ""),
                    confianza=evento_dict.get("confianza", 0.0),
                    timestamp=datetime.utcnow()
                )

                # Process through agent pipeline
                response = await receptor.procesar_deteccion(evento)

                # Send response back (already sent via observer, but also direct)
                if not receptor.notificador.tiene_conexiones(session_id):
                    await websocket.send_text(json.dumps(response, default=str))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "error": "INVALID_JSON",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error processing detection: {e}")
                await websocket.send_text(json.dumps({
                    "error": "PROCESSING_ERROR",
                    "message": str(e)
                }))

    except WebSocketDisconnect:
        receptor.notificador.eliminar_conexion(session_id, websocket)
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        receptor.notificador.eliminar_conexion(session_id, websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
