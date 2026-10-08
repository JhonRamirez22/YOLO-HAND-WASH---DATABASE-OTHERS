"""
Pydantic models for Hand Wash Compliance System
Based on AGENTS.md specification
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime
import uuid


class PasoLavado(str, Enum):
    """7 hand wash steps per WHO protocol"""
    PASO1_PALMAS = "PASO_1_PALMAS"
    PASO2_DORSOS = "PASO_2_DORSOS"
    PASO3_INTERDIGITALES = "PASO_3_INTERDIGITALES"
    PASO4_NUDILLOS = "PASO_4_NUDILLOS"
    PASO5_PULGAR = "PASO_5_PULGAR"
    PASO6_PUNTA_DE_DEDOS = "PASO_6_PUNTA_DE_DEDOS"
    PASO7_CIRCULARES = "PASO_7_CIRCULARES"


class TipoProtocolo(str, Enum):
    """Validation protocol types"""
    CLINICO_QUIRURGICO = "CLINICO_QUIRURGICO"
    DOMESTICO = "DOMESTICO"


class TipoInfraccion(str, Enum):
    """Violation types"""
    PASO_OMITIDO = "PASO_OMITIDO"
    PASO_INVALIDO = "PASO_INVALIDO"
    TIEMPO_INSUFICIENTE = "TIEMPO_INSUFICIENTE"


class EstadoSesion(str, Enum):
    """Session states"""
    ESPERANDO_INICIO = "ESPERANDO_INICIO"
    EN_PROGRESO = "EN_PROGRESO"
    COMPLETADA = "COMPLETADA"
    EXPIRADA = "EXPIRADA"


# === INPUT MODELS ===

class DeteccionEvento(BaseModel):
    """Payload from iPhone (YOLO inference results)"""
    sessionId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claseDetectada: str
    confianza: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IniciarSesionRequest(BaseModel):
    """Request to start a new hand wash session"""
    protocolo: TipoProtocolo = TipoProtocolo.CLINICO_QUIRURGICO
    usuarioId: Optional[str] = None


# === OUTPUT MODELS ===

class Progreso(BaseModel):
    """Progress tracking"""
    pasosCompletados: int = 0
    pasosTotales: int = 7


class Infraccion(BaseModel):
    """Violation detail"""
    tipo: TipoInfraccion
    detalle: str
    pasoDetectado: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DetallePaso(BaseModel):
    """Detail for each step"""
    paso: PasoLavado
    tiempoRequeridoMs: int
    tiempoAcumuladoMs: int = 0
    completado: bool = False
    cumpleTiempo: bool = False


class EstadoLavadoResponse(BaseModel):
    """Response sent back to iPhone per frame"""
    sessionId: str
    estadoActual: str
    estadoSesion: EstadoSesion
    tiempoAcumuladoMs: int = 0
    infraccion: Optional[Infraccion] = None
    progreso: Progreso = Progreso()
    detallesPasos: List[DetallePaso] = []
    manoDetectada: Optional[bool] = None
    manoConfianza: Optional[float] = None


class ResumenSesionLavado(BaseModel):
    """Final session summary"""
    sessionId: str
    resultado: str  # "APROBADO" | "APROBADO_CON_OBSERVACIONES" | "NO_APROBADO"
    protocolo: TipoProtocolo
    duracionTotalMs: int
    pasosCompletados: int
    pasosTotales: int
    infracciones: List[Infraccion] = []
    detallesPasos: List[DetallePaso] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
