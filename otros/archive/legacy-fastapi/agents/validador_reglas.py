"""
Agente Validador de Reglas - Strategy Pattern
Validates time duration per step against protocol requirements
Based on AGENTS.md specification
"""
from abc import ABC, abstractmethod
from typing import Dict
from schemas.models import PasoLavado, TipoProtocolo


class ReglaValidacionStrategy(ABC):
    """Interface for validation strategies"""

    @property
    @abstractmethod
    def nombre(self) -> str:
        pass

    @property
    @abstractmethod
    def duracion_total_requerida_ms(self) -> int:
        pass

    @abstractmethod
    def get_tiempos_minimos_por_paso(self) -> Dict[PasoLavado, int]:
        """Return minimum time required for each step in ms"""
        pass

    def validar_duracion(self, paso: PasoLavado, tiempo_acumulado_ms: int) -> bool:
        """Check if accumulated time meets minimum requirement for a step"""
        tiempos = self.get_tiempos_minimos_por_paso()
        tiempo_minimo = tiempos.get(paso, 5000)
        return tiempo_acumulado_ms >= tiempo_minimo

    def validar_sesion_completa(self, tiempos_por_paso: Dict[PasoLavado, int]) -> dict:
        """
        Validate entire session.
        Returns: {cumple: bool, pasos_conforme: list, pasos_incumple: list}
        """
        tiempos = self.get_tiempos_minimos_por_paso()
        conformes = []
        incumplidos = []

        for paso, tiempo_requerido in tiempos.items():
            tiempo_real = tiempos_por_paso.get(paso, 0)
            if tiempo_real >= tiempo_requerido:
                conformes.append(paso)
            else:
                incumplidos.append(paso)

        return {
            "cumple": len(incumplidos) == 0,
            "pasos_conforme": conformes,
            "pasos_incumple": incumplidos
        }


class LavadoClinicoStrategy(ReglaValidacionStrategy):
    """
    Clinical/Surgical hand wash protocol (WHO).
    Total duration: 60 seconds minimum.
    Stricter time requirements per step.
    """

    @property
    def nombre(self) -> str:
        return "Lavado Clínico/Quirúrgico"

    @property
    def duracion_total_requerida_ms(self) -> int:
        return 60000  # 60 seconds

    def get_tiempos_minimos_por_paso(self) -> Dict[PasoLavado, int]:
        return {
            PasoLavado.PASO1_PALMAS: 8000,
            PasoLavado.PASO2_DORSOS: 8000,
            PasoLavado.PASO3_INTERDIGITALES: 8000,
            PasoLavado.PASO4_NUDILLOS: 8000,
            PasoLavado.PASO5_PULGAR: 8000,
            PasoLavado.PASO6_PUNTA_DE_DEDOS: 8000,
            PasoLavado.PASO7_CIRCULARES: 12000,
        }


class LavadoDomesticoStrategy(ReglaValidacionStrategy):
    """
    Domestic/General hand wash protocol.
    Total duration: 20 seconds minimum.
    Less strict time requirements.
    """

    @property
    def nombre(self) -> str:
        return "Lavado Doméstico"

    @property
    def duracion_total_requerida_ms(self) -> int:
        return 20000  # 20 seconds

    def get_tiempos_minimos_por_paso(self) -> Dict[PasoLavado, int]:
        return {
            PasoLavado.PASO1_PALMAS: 3000,
            PasoLavado.PASO2_DORSOS: 3000,
            PasoLavado.PASO3_INTERDIGITALES: 3000,
            PasoLavado.PASO4_NUDILLOS: 3000,
            PasoLavado.PASO5_PULGAR: 2000,
            PasoLavado.PASO6_PUNTA_DE_DEDOS: 2000,
            PasoLavado.PASO7_CIRCULARES: 4000,
        }


class ValidadorReglas:
    """
    Strategy executor for time validation.
    Selects and applies the appropriate validation strategy.
    """

    def __init__(self, protocolo: TipoProtocolo = TipoProtocolo.CLINICO_QUIRURGICO):
        self._protocolo = protocolo
        self._estrategia = self._seleccionar_estrategia(protocolo)

    def _seleccionar_estrategia(self, protocolo: TipoProtocolo) -> ReglaValidacionStrategy:
        estrategias = {
            TipoProtocolo.CLINICO_QUIRURGICO: LavadoClinicoStrategy,
            TipoProtocolo.DOMESTICO: LavadoDomesticoStrategy,
        }
        clase = estrategias.get(protocolo, LavadoClinicoStrategy)
        return clase()

    @property
    def protocolo(self) -> TipoProtocolo:
        return self._protocolo

    @property
    def estrategia(self) -> ReglaValidacionStrategy:
        return self._estrategia

    def validar_paso(self, paso: PasoLavado, tiempo_acumulado_ms: int) -> bool:
        """Check if a specific step meets time requirement"""
        return self._estrategia.validar_duracion(paso, tiempo_acumulado_ms)

    def validar_sesion(self, tiempos_por_paso: Dict[PasoLavado, int]) -> dict:
        """Validate entire session against current strategy"""
        return self._estrategia.validar_sesion_completa(tiempos_por_paso)

    def get_tiempos_requeridos(self) -> Dict[PasoLavado, int]:
        """Get minimum times for current protocol"""
        return self._estrategia.get_tiempos_minimos_por_paso()

    def get_resumen_protocolo(self) -> dict:
        """Get protocol summary"""
        return {
            "nombre": self._estrategia.nombre,
            "protocolo": self._protocolo.value,
            "duracion_total_ms": self._estrategia.duracion_total_requerida_ms,
            "tiempos_por_paso": {
                paso.value: tiempo
                for paso, tiempo in self._estrategia.get_tiempos_minimos_por_paso().items()
            }
        }
