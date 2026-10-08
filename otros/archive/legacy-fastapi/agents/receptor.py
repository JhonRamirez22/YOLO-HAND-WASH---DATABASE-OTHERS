"""
Agente Receptor - WebSocket Endpoint
Point of entry for detection events from iPhone
Based on AGENTS.md specification
"""
import uuid
import logging
from datetime import datetime
from typing import Optional

from schemas.models import (
    DeteccionEvento, IniciarSesionRequest, TipoProtocolo
)
from agents.evaluador_secuencia import SesionLavadoContext
from agents.validador_reglas import ValidadorReglas
from agents.notificaciones import EventoDeteccion, NotificadorWebSocket

logger = logging.getLogger(__name__)


class SesionActiva:
    """Represents an active hand wash session"""

    def __init__(self, session_id: str, protocolo: TipoProtocolo):
        self.session_id = session_id
        self.protocolo = protocolo
        self.evaluador = SesionLavadoContext(session_id)
        self.validador = ValidadorReglas(protocolo)
        self.fecha_inicio = datetime.utcnow()
        self.evaluador.iniciar()

    def get_duracion_ms(self) -> int:
        return int((datetime.utcnow() - self.fecha_inicio).total_seconds() * 1000)


class AgenteReceptor:
    """
    Main reception agent (Observer Subject).
    Ingests detection events and publishes to observers.
    """

    def __init__(self):
        self._sesiones: dict[str, SesionActiva] = {}
        self.evento_deteccion = EventoDeteccion()
        self.notificador = NotificadorWebSocket()
        self.evento_deteccion.agregar_observador(self.notificador)

    def crear_sesion(self, protocolo: TipoProtocolo = TipoProtocolo.CLINICO_QUIRURGICO) -> str:
        """Create a new hand wash session"""
        session_id = str(uuid.uuid4())
        self._sesiones[session_id] = SesionActiva(session_id, protocolo)
        logger.info(f"Session created: {session_id} with protocol {protocolo.value}")
        return session_id

    def obtener_sesion(self, session_id: str) -> Optional[SesionActiva]:
        """Get an active session by ID"""
        return self._sesiones.get(session_id)

    def eliminar_sesion(self, session_id: str):
        """Remove a session"""
        if session_id in self._sesiones:
            del self._sesiones[session_id]
            logger.info(f"Session deleted: {session_id}")

    async def procesar_deteccion(self, evento: DeteccionEvento) -> dict:
        """
        Process a detection event (validates, processes, and notifies).
        Returns the response to send back to client.
        """
        session = self._sesiones.get(evento.sessionId)
        if not session:
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Session {evento.sessionId} not found"
            }

        # Validate confidence threshold
        if evento.confianza < 0.6:
            return {
                "sessionId": evento.sessionId,
                "estadoActual": session.evaluador.get_estado_actual(),
                "estadoSesion": session.evaluador.estado_sesion.value,
                "tiempoAcumuladoMs": 0,
                "infraccion": None,
                "progreso": session.evaluador.get_progreso().model_dump(),
                "detallesPasos": [d.model_dump() for d in session.evaluador.get_detalles_pasos()],
                "filtered": True
            }

        # Process through evaluador de secuencia
        infraccion, paso_completado = session.evaluador.procesar_deteccion(
            evento.claseDetectada,
            evento.confianza,
            evento.timestamp
        )

        # Build response
        from schemas.models import EstadoLavadoResponse
        response = EstadoLavadoResponse(
            sessionId=session.session_id,
            estadoActual=session.evaluador.get_estado_actual(),
            estadoSesion=session.evaluador.estado_sesion,
            tiempoAcumuladoMs=session.evaluador.tiempos_por_paso[session.evaluador.estado_actual.paso],
            infraccion=infraccion,
            progreso=session.evaluador.get_progreso(),
            detallesPasos=session.evaluador.get_detalles_pasos()
        )

        # Notify observers
        await self.evento_deteccion.notificar(session.session_id, response.model_dump())

        # If session completed, send summary
        if session.evaluador.estado_sesion.value == "COMPLETADA":
            await self._enviar_resumen(session)

        return response.model_dump()

    async def _enviar_resumen(self, session: SesionActiva):
        """Send final session summary"""
        from schemas.models import ResumenSesionLavado

        validacion = session.validador.validar_sesion(session.evaluador.tiempos_por_paso)

        if validacion["cumple"] and not session.evaluador.infracciones:
            resultado = "APROBADO"
        elif session.evaluador.infracciones:
            resultado = "NO_APROBADO"
        else:
            resultado = "APROBADO_CON_OBSERVACIONES"

        resumen = ResumenSesionLavado(
            sessionId=session.session_id,
            resultado=resultado,
            protocolo=session.protocolo,
            duracionTotalMs=session.get_duracion_ms(),
            pasosCompletados=session.evaluador.pasos_completados,
            pasosTotales=7,
            infracciones=session.evaluador.infracciones,
            detallesPasos=session.evaluador.get_detalles_pasos()
        )

        await self.notificador.enviar_resumen(session.session_id, resumen)
        logger.info(f"Session {session.session_id} completed: {resultado}")


# Global instance
receptor = AgenteReceptor()
