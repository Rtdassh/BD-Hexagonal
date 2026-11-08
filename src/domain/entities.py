"""
Domain Entities and Value Objects for the Unified Clinical Records System.
Hexagonal Architecture Core Domain.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any


class InstitutionType(str, Enum):
    HOSPITAL_GENERAL = "hospital"
    CENTRO_PEDIATRICO = "pediatrico"
    LABORATORIO_CLINICO = "laboratorio"
    CLINICA_ODONTOLOGICA = "odontologia"


class DatabaseEngine(str, Enum):
    POSTGRESQL = "PostgreSQL"
    MYSQL = "MySQL"
    MONGODB = "MongoDB"
    FIREBASE = "Firebase Cloud Firestore"


class UserRole(str, Enum):
    MEDICO = "medico"
    PEDIATRA = "pediatra"
    LABORATORISTA = "laboratorista"
    ODONTOLOGO = "odontologo"
    SECRETARIA = "secretaria"
    ADMIN = "administrador"


class RecordStatus(str, Enum):
    ACTIVO = "activo"
    ARCHIVADO = "archivado"
    TRASLADADO = "trasladado"
    DADO_DE_BAJA = "dado_de_baja"


class InfoClassification(str, Enum):
    PUBLIC = "publica"
    CONFIDENTIAL = "confidencial"
    RESTRICTED = "restringida"


@dataclass
class User:
    username: str
    nombre_completo: str
    institucion: InstitutionType
    rol: UserRole
    motor_asignado: DatabaseEngine
    numero_colegiado: Optional[str] = None
    token: Optional[str] = None
    id_profesional: Optional[int] = None


@dataclass
class Professional:
    """Profesional de salud de una institución (médico, pediatra, laboratorista, odontólogo).
    No inicia sesión: el administrador lo registra y lo asigna a citas y consultas."""
    id_profesional: int
    nombre_completo: str
    numero_colegiado: str
    especialidad: str = ""
    telefono: str = ""
    correo_electronico: str = ""
    estado: str = "activo"


@dataclass
class Surgery:
    """Cirugía del Hospital General: programada -> en_curso -> realizada | cancelada."""
    id_cirugia: int
    id_paciente: int
    paciente_nombre: str
    id_medico: int
    cirujano_nombre: str
    procedimiento: str
    codigo_quirofano: str
    tipo: str
    fecha_hora_programada: str
    duracion_estimada_min: int
    estado: str
    fecha_hora_inicio: Optional[str] = None
    fecha_hora_fin: Optional[str] = None
    id_hospitalizacion: Optional[int] = None
    notas_operatorias: Optional[str] = None
    motivo_cancelacion: Optional[str] = None


@dataclass
class ShiftAssignment:
    """Enfermero asignado a un paciente hospitalizado en un turno."""
    id_asignacion: int
    id_enfermero: int
    enfermero_nombre: str
    id_hospitalizacion: int
    id_paciente: int
    paciente_nombre: str
    numero_habitacion: str
    fecha: str
    turno: str
    observaciones: Optional[str] = None
    estado: str = "activa"


@dataclass
class Patient:
    id_paciente: int
    nombres: str
    apellidos: str
    fecha_nacimiento: str
    sexo: str
    dpi: str
    direccion: str
    telefono: str
    correo_electronico: str
    contacto_emergencia_nombre: str
    contacto_emergencia_telefono: str
    fecha_registro: str
    estado: str = "activo"
    tipo_sangre: Optional[str] = None
    # Atributos específicos pediátricos
    nombre_tutor: Optional[str] = None
    parentesco_tutor: Optional[str] = None
    dpi_tutor: Optional[str] = None
    telefono_tutor: Optional[str] = None
    semanas_gestacion: Optional[int] = None
    peso_nacer_kg: Optional[float] = None
    talla_nacer_cm: Optional[float] = None
    # Entidades normalizadas 3FN (opcionales para compatibilidad)
    tutor: Optional["LegalGuardian"] = None
    perinatal: Optional["PerinatalRecord"] = None

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()


@dataclass
class Prescription:
    id_receta: Optional[int]
    medicamento: str
    dosis: str
    frecuencia: str
    duracion_dias: int
    via_administracion: Optional[str] = "Oral"
    indicaciones: Optional[str] = None
    fecha_emision: Optional[str] = None
    # Pediátrico
    dosis_mg_kg: Optional[float] = None
    dosis_calculada_ml: Optional[float] = None
    presentacion: Optional[str] = None


@dataclass
class Treatment:
    id_tratamiento: Optional[int]
    descripcion: str
    fecha_inicio: str
    fecha_fin: Optional[str]
    estado: str
    indicaciones: Optional[str]
    recetas: List[Prescription] = field(default_factory=list)


@dataclass
class Diagnosis:
    id_diagnostico: Optional[int]
    codigo_cie10: str
    descripcion: str
    tipo: str = "principal"
    fecha_diagnostico: Optional[str] = None
    tratamientos: List[Treatment] = field(default_factory=list)


@dataclass
class HospitalizationRecord:
    id_hospitalizacion: int
    id_consulta: int
    fecha_ingreso: str
    fecha_egreso: Optional[str]
    numero_habitacion: str
    motivo_ingreso: str
    estado: str = "ingresado"


@dataclass
class SomatometryRecord:
    peso_kg: float
    talla_cm: float
    perimetro_cefalico_cm: Optional[float] = None
    percentil_crecimiento: Optional[float] = None


@dataclass
class VaccinationRecord:
    id_vacunacion: int
    nombre_vacuna: str
    dosis: str
    lote: str
    fecha_aplicacion: str
    proxima_fecha_refuerzo: Optional[str] = None


@dataclass
class LabParameter:
    nombre_parametro: str
    valor_resultado: Any
    unidad_medida: str
    rango_referencia_min: Optional[float] = None
    rango_referencia_max: Optional[float] = None
    valor_referencia_cualitativo: Optional[str] = None
    interpretacion_alerta: str = "NORMAL"


@dataclass
class LabExamResult:
    id_resultado: int
    id_orden: int
    codigo_examen: str
    nombre_examen: str
    fecha_hora_analisis: str
    fecha_hora_validacion: Optional[str]
    estado: str
    alertas_criticas: bool
    observaciones_tecnicas: str
    conclusiones_diagnosticas: str
    parametros: List[LabParameter] = field(default_factory=list)


@dataclass
class DentalProcedureRecord:
    id_consulta_procedimiento: int
    id_cita: int
    nombre_procedimiento: str
    pieza_dental: str
    observaciones: str
    fecha_realizacion: str
    costo: float
    estado: str = "completado"


@dataclass
class LegalGuardian:
    id_tutor: int
    dpi: str
    nombres: str
    apellidos: str
    telefono_principal: str
    direccion: str
    telefono_secundario: Optional[str] = None
    correo: Optional[str] = None
    parentesco: str = "Tutor Legal"


@dataclass
class PerinatalRecord:
    id_antecedente: int
    id_paciente: int
    semanas_gestacion: int
    peso_nacer_kg: float
    talla_nacer_cm: float
    perimetro_cefalico_nacer_cm: float = 34.5
    tipo_parto: str = "Eutócico vaginal"
    apgar_1min: int = 9
    apgar_5min: int = 10
    complicaciones: Optional[str] = None


@dataclass
class DevelopmentMilestone:
    id_evaluacion: int
    area_desarrollo: str
    hito_evaluado: str
    cumple_hito: bool = True
    observaciones: Optional[str] = None


@dataclass
class AllergyRecord:
    id_alergia: int
    alergeno: str
    tipo_alergeno: str
    severidad: str
    fecha_deteccion: str


@dataclass
class DentalTooth:
    codigo_fdi: int
    cuadrante: int
    nombre_anatomico: str
    tipo_diente: str


@dataclass
class OdontogramDetail:
    id_detalle: int
    codigo_fdi: int
    cara: str
    hallazgo: str
    color_hex: str = "#FF0000"
    notas: Optional[str] = None


@dataclass
class DentalTreatmentPlan:
    id_plan: int
    id_paciente: int
    costo_total_estimado: float
    estado_aprobacion: str = "pendiente"
    etapas: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Consultation:
    id_consulta: int
    id_cita: int
    fecha_hora_atencion: str
    motivo: str
    presion_arterial: Optional[str] = None
    temperatura: Optional[float] = None
    pulso: Optional[int] = None
    notas_clinicas: Optional[str] = None
    tipo_consulta: str = "ordinaria"
    profesional_nombre: Optional[str] = None
    diagnosticos: List[Diagnosis] = field(default_factory=list)
    # Todas las recetas emitidas en la consulta (vista uniforme para la interfaz)
    recetas: List[Prescription] = field(default_factory=list)
    # Específicos por institución
    hospitalizacion: Optional[HospitalizationRecord] = None
    somatometria: Optional[SomatometryRecord] = None
    vacunaciones: List[VaccinationRecord] = field(default_factory=list)
    recetas_pediatricas: List[Prescription] = field(default_factory=list)
    procedimientos_dentales: List[DentalProcedureRecord] = field(default_factory=list)
    examenes_laboratorio: List[LabExamResult] = field(default_factory=list)
    estado_orden: Optional[str] = None   # solo laboratorio: en qué paso va la orden


@dataclass
class Appointment:
    id_cita: int
    id_paciente: int
    id_profesional: int
    profesional_nombre: str
    fecha_hora_programada: str
    motivo_consulta: str
    estado_cita: str
    fecha_creacion: str
    id_secretaria: Optional[int] = None
    id_orden: Optional[int] = None      # laboratorio: la toma pertenece a una orden
    preparacion: Optional[str] = None


@dataclass
class UnifiedClinicalRecord:
    id_historial: int
    id_paciente: int
    paciente: Patient
    fecha_apertura: str
    fecha_ultima_actualizacion: str
    estado: str
    motivo_baja: Optional[str] = None
    institucion: InstitutionType = InstitutionType.HOSPITAL_GENERAL
    motor: DatabaseEngine = DatabaseEngine.POSTGRESQL
    consultas: List[Consultation] = field(default_factory=list)
    citas: List[Appointment] = field(default_factory=list)
    datos_adicionales: Dict[str, Any] = field(default_factory=dict)

