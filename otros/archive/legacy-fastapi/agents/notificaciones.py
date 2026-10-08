"""
Agente de Notificaciones - Observer Pattern
Translates internal results into client-facing WebSocket events
Based on AGENTS.md specification
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Set
from datetime import datetime
import json
import logging

from schemas.models import (
    HandWashStatusResponse, HandWashSessionSummary,
    Violation, SessionStatus, Progress, StepDetail
)

logger = logging.getLogger(__name__)


class DetectionObserver(ABC):
    """Observer interface for detection events"""

    @abstractmethod
    async def on_deteccion(self, session_id: str, evento: dict):
        pass


class WebSocketNotifier(DetectionObserver):
    """
    WebSocket-based notification agent.
    Sends real-time updates to connected clients.
    """

    def __init__(self):
        self._conexiones: dict[str, Set] = {}  # session_id -> set of websocket connections

    def registrar_conexion(self, session_id: str, websocket):
        """Register a WebSocket connection for a session"""
        if session_id not in self._conexiones:
            self._conexiones[session_id] = set()
        self._conexiones[session_id].add(websocket)
        logger.info(f"WebSocket connected for session {session_id}")

    def eliminar_conexion(self, session_id: str, websocket):
        """Remove a WebSocket connection"""
        if session_id in self._conexiones:
            self._conexiones[session_id].discard(websocket)
            if not self._conexiones[session_id]:
                del self._conexiones[session_id]
        logger.info(f"WebSocket disconnected for session {session_id}")

    async def on_deteccion(self, session_id: str, evento: dict):
        """Handle detection event and notify connected clients"""
        if session_id not in self._conexiones:
            return

        message = json.dumps(evento, default=str)
        disconnected = set()

        for ws in self._conexiones[session_id]:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(ws)

        # Clean up disconnected clients
        for ws in disconnected:
            self._conexiones[session_id].discard(ws)

    async def enviar_estado(self, session_id: str, estado: HandWashStatusResponse):
        """Send state update to client"""
        await self.on_deteccion(session_id, estado.model_dump())

    async def enviar_resumen(self, session_id: str, resumen: HandWashSessionSummary):
        """Send final session summary to client"""
        await self.on_deteccion(session_id, resumen.model_dump())

    def tiene_conexiones(self, session_id: str) -> bool:
        """Check if session has active connections"""
        return session_id in self._conexiones and len(self._conexiones[session_id]) > 0


class DetectionEventPublisher:
    """Subject that publishes detection events to observers"""

    def __init__(self):
        self._observadores: List[DetectionObserver] = []

    def agregar_observador(self, observer: DetectionObserver):
        """Subscribe an observer to detection events"""
        if observer not in self._observadores:
            self._observadores.append(observer)

    def eliminar_observador(self, observer: DetectionObserver):
        """Unsubscribe an observer"""
        if observer in self._observadores:
            self._observadores.remove(observer)

    async def notificar(self, session_id: str, evento: dict):
        """Notify all observers of a detection event"""
        for observer in self._observadores:
            try:
                await observer.on_deteccion(session_id, evento)
            except Exception as e:
                logger.error(f"Observer notification failed: {e}")
