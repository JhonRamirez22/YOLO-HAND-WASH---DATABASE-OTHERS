"""
Pydantic models for Hand Wash Compliance System
Based on AGENTS.md specification
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime
import uuid


class HandWashStep(str, Enum):
    """7 hand wash steps per WHO protocol"""
    PASO1_PALMAS = "PASO_1_PALMAS"
    PASO2_DORSOS = "PASO_2_DORSOS"
    PASO3_INTERDIGITALES = "PASO_3_INTERDIGITALES"
    PASO4_NUDILLOS = "PASO_4_NUDILLOS"
    PASO5_PULGAR = "PASO_5_PULGAR"
    PASO6_PUNTA_DE_DEDOS = "PASO_6_PUNTA_DE_DEDOS"
    PASO7_CIRCULARES = "PASO_7_CIRCULARES"


class ProtocolType(str, Enum):
    """Validation protocol types"""
    CLINICO_QUIRURGICO = "CLINICO_QUIRURGICO"
    DOMESTICO = "DOMESTICO"


class ViolationType(str, Enum):
    """Violation types"""
    PASO_OMITIDO = "PASO_OMITIDO"
    PASO_INVALIDO = "PASO_INVALIDO"
    TIEMPO_INSUFICIENTE = "TIEMPO_INSUFICIENTE"


class SessionStatus(str, Enum):
    """Session states"""
    ESPERANDO_INICIO = "ESPERANDO_INICIO"
    EN_PROGRESO = "EN_PROGRESO"
    COMPLETADA = "COMPLETADA"
    EXPIRADA = "EXPIRADA"


# === INPUT MODELS ===

class DetectionEventRequest(BaseModel):
    """Payload from iPhone (YOLO inference results)"""
    sessionId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claseDetectada: str
    confianza: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StartSessionRequest(BaseModel):
    """Request to start a new hand wash session"""
    protocolo: ProtocolType = ProtocolType.CLINICO_QUIRURGICO
    usuarioId: Optional[str] = None


# === OUTPUT MODELS ===

class Progress(BaseModel):
    """Progress tracking"""
    pasosCompletados: int = 0
    pasosTotales: int = 7


class Violation(BaseModel):
    """Violation detail"""
    tipo: ViolationType
    detalle: str
    pasoDetectado: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StepDetail(BaseModel):
    """Detail for each step"""
    paso: HandWashStep
    tiempoRequeridoMs: int
    tiempoAcumuladoMs: int = 0
    completado: bool = False
    cumpleTiempo: bool = False


class HandWashStatusResponse(BaseModel):
    """Response sent back to iPhone per frame"""
    sessionId: str
    estadoActual: str
    estadoSesion: SessionStatus
    tiempoAcumuladoMs: int = 0
    infraccion: Optional[Violation] = None
    progreso: Progress = Progress()
    detallesPasos: List[StepDetail] = []
    manoDetectada: Optional[bool] = None
    manoConfianza: Optional[float] = None


class HandWashSessionSummary(BaseModel):
    """Final session summary"""
    sessionId: str
    resultado: str  # "APROBADO" | "APROBADO_CON_OBSERVACIONES" | "NO_APROBADO"
    protocolo: ProtocolType
    duracionTotalMs: int
    pasosCompletados: int
    pasosTotales: int
    infracciones: List[Violation] = []
    detallesPasos: List[StepDetail] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
