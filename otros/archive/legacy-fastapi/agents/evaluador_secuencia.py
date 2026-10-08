"""
Agente Evaluador de Secuencia - State Pattern
Ensures hand wash steps are executed in correct order (WHO protocol)
Based on AGENTS.md specification
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
from datetime import datetime
import uuid

from schemas.models import (
    PasoLavado, TipoInfraccion, EstadoSesion,
    Infraccion, DetallePaso, Progreso
)


class PasoLavadoState(ABC):
    """Interface for each hand wash step state"""

    @property
    @abstractmethod
    def paso(self) -> PasoLavado:
        pass

    @property
    @abstractmethod
    def paso_siguiente(self) -> Optional[PasoLavado]:
        pass

    @abstractmethod
    def procesar_deteccion(self, clase_detectada: str, confianza: float) -> tuple:
        """
        Process a detection for this step.
        Returns: (next_state_or_self, infraccion_or_none)
        """
        pass


class PalmasState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO1_PALMAS

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return PasoLavado.PASO2_DORSOS

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada == "PASO_1_PALMAS" or clase_detectada == "Paso1_Palmas":
            return self, None
        if clase_detectada in ["PASO_2_DORSOS", "Paso2_Dorsos"]:
            return DorsosState(), None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 1 (Palmas)",
            pasoDetectado=clase_detectada
        )


class DorsosState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO2_DORSOS

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return PasoLavado.PASO3_INTERDIGITALES

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada in ["PASO_2_DORSOS", "Paso2_Dorsos"]:
            return self, None
        if clase_detectada in ["PASO_3_INTERDIGITALES", "Paso3_Interdigitales"]:
            return InterdigitalesState(), None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 2 (Dorsos)",
            pasoDetectado=clase_detectada
        )


class InterdigitalesState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO3_INTERDIGITALES

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return PasoLavado.PASO4_NUDILLOS

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada in ["PASO_3_INTERDIGITALES", "Paso3_Interdigitales"]:
            return self, None
        if clase_detectada in ["PASO_4_NUDILLOS", "Paso4_Nudillos"]:
            return NudillosState(), None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 3 (Interdigitales)",
            pasoDetectado=clase_detectada
        )


class NudillosState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO4_NUDILLOS

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return PasoLavado.PASO5_PULGAR

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada in ["PASO_4_NUDILLOS", "Paso4_Nudillos"]:
            return self, None
        if clase_detectada in ["PASO_5_PULGAR", "Paso5_Pulgar"]:
            return PulgarState(), None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 4 (Nudillos)",
            pasoDetectado=clase_detectada
        )


class PulgarState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO5_PULGAR

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return PasoLavado.PASO6_PUNTA_DE_DEDOS

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada in ["PASO_5_PULGAR", "Paso5_Pulgar"]:
            return self, None
        if clase_detectada in ["PASO_6_PUNTA_DE_DEDOS", "Paso6_PuntaDeDedos"]:
            return PuntaDedosState(), None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 5 (Pulgar)",
            pasoDetectado=clase_detectada
        )


class PuntaDedosState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO6_PUNTA_DE_DEDOS

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return PasoLavado.PASO7_CIRCULARES

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada in ["PASO_6_PUNTA_DE_DEDOS", "Paso6_PuntaDeDedos"]:
            return self, None
        if clase_detectada in ["PASO_7_CIRCULARES", "Paso7_Circulares"]:
            return CircularesState(), None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 6 (Punta de Dedos)",
            pasoDetectado=clase_detectada
        )


class CircularesState(PasoLavadoState):
    @property
    def paso(self) -> PasoLavado:
        return PasoLavado.PASO7_CIRCULARES

    @property
    def paso_siguiente(self) -> Optional[PasoLavado]:
        return None  # Last step

    def procesar_deteccion(self, clase_detectada: str, confianza: float):
        if clase_detectada in ["PASO_7_CIRCULARES", "Paso7_Circulares"]:
            return self, None
        return self, Infraccion(
            tipo=TipoInfraccion.PASO_INVALIDO,
            detalle=f"Se detectó {clase_detectada} durante Paso 7 (Circulares)",
            pasoDetectado=clase_detectada
        )


class SesionLavadoContext:
    """
    State pattern context for hand wash session.
    Manages step progression and tracks violations.
    """

    # Map step to its required minimum duration (ms)
    TIEMPOS_REQUERIDOS = {
        PasoLavado.PASO1_PALMAS: 5000,
        PasoLavado.PASO2_DORSOS: 5000,
        PasoLavado.PASO3_INTERDIGITALES: 5000,
        PasoLavado.PASO4_NUDILLOS: 5000,
        PasoLavado.PASO5_PULGAR: 5000,
        PasoLavado.PASO6_PUNTA_DE_DEDOS: 5000,
        PasoLavado.PASO7_CIRCULARES: 5000,
    }

    PASOS_EN_ORDEN = [
        PasoLavado.PASO1_PALMAS,
        PasoLavado.PASO2_DORSOS,
        PasoLavado.PASO3_INTERDIGITALES,
        PasoLavado.PASO4_NUDILLOS,
        PasoLavado.PASO5_PULGAR,
        PasoLavado.PASO6_PUNTA_DE_DEDOS,
        PasoLavado.PASO7_CIRCULARES,
    ]

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.estado_actual: PasoLavadoState = PalmasState()
        self.estado_sesion: EstadoSesion = EstadoSesion.ESPERANDO_INICIO
        self.pasos_completados: int = 0
        self.infracciones: list[Infraccion] = []
        self.tiempos_por_paso: Dict[PasoLavado, int] = {p: 0 for p in self.PASOS_EN_ORDEN}
        self._ultimo_timestamp: Optional[datetime] = None
        self._paso_inicio: Optional[datetime] = None
        self._paso_actual_detectado = False

    def iniciar(self):
        """Start the hand wash session"""
        self.estado_sesion = EstadoSesion.EN_PROGRESO
        self._paso_inicio = datetime.utcnow()
        self._ultimo_timestamp = datetime.utcnow()

    def procesar_deteccion(self, clase_detectada: str, confianza: float,
                          timestamp: Optional[datetime] = None) -> tuple:
        """
        Process a detection event.
        Returns: (infraccion_or_None, paso_completado_or_None)
        """
        if self.estado_sesion != EstadoSesion.EN_PROGRESO:
            return None, None

        now = timestamp or datetime.utcnow()
        if self._ultimo_timestamp:
            delta_ms = int((now - self._ultimo_timestamp).total_seconds() * 1000)
            # Cap delta to 500ms to avoid accumulating time during pauses
            delta_ms = min(delta_ms, 500)
            self.tiempos_por_paso[self.estado_actual.paso] += delta_ms
        self._ultimo_timestamp = now

        new_state, infraccion = self.estado_actual.procesar_deteccion(clase_detectada, confianza)

        paso_completado = None
        if new_state is not self.estado_actual:
            # Step transition = previous step completed
            paso_completado = self.estado_actual.paso
            self.pasos_completados += 1
            self._paso_inicio = now

            # Check if all steps done
            if new_state.paso_siguiente is None:
                self.estado_sesion = EstadoSesion.COMPLETADA

        self.estado_actual = new_state
        return infraccion, paso_completado

    def get_estado_actual(self) -> str:
        return self.estado_actual.paso.value

    def get_progreso(self) -> Progreso:
        return Progreso(
            pasosCompletados=self.pasos_completados,
            pasosTotales=7
        )

    def get_detalles_pasos(self) -> list[DetallePaso]:
        detalles = []
        for paso in self.PASOS_EN_ORDEN:
            tiempo_requerido = self.TIEMPOS_REQUERIDOS[paso]
            tiempo_acumulado = self.tiempos_por_paso[paso]
            completado = tiempo_acumulado >= tiempo_requerido
            detalles.append(DetallePaso(
                paso=paso,
                tiempoRequeridoMs=tiempo_requerido,
                tiempoAcumuladoMs=tiempo_acumulado,
                completado=completado,
                cumpleTiempo=completado
            ))
        return detalles
