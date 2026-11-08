"""
Ports (Contracts / Interfaces) of the Hexagonal Architecture.
Defines boundary interfaces between Domain/Application and Database Adapters.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .entities import (
    InstitutionType,
    DatabaseEngine,
    UserRole,
    Patient,
    UnifiedClinicalRecord,
    Appointment,
    Consultation,
    Professional,
    ShiftAssignment,
    Surgery,
    User
)


class ClinicalRepositoryPort(ABC):
    """
    Primary Port for clinical records data access.
    Implemented by PostgreSQL, MySQL, MongoDB, and Firebase Adapters.
    """

    @property
    @abstractmethod
    def institution_type(self) -> InstitutionType:
        """Returns the institution handled by this adapter."""
        pass

    @property
    @abstractmethod
    def database_engine(self) -> DatabaseEngine:
        """Returns the database engine type of this adapter."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Verifies connection health, latency and engine statistics."""
        pass

    # --- Patient Management ---
    @abstractmethod
    def create_patient(self, patient_data: Dict[str, Any]) -> Patient:
        """Registers a new patient and creates their initial clinical record."""
        pass

    @abstractmethod
    def get_patient(self, patient_id: int) -> Optional[Patient]:
        """Retrieves patient demographics by identifier."""
        pass

    @abstractmethod
    def search_patients(self, query: str) -> List[Patient]:
        """Searches patients by name, DPI or identifier."""
        pass

    @abstractmethod
    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        """Updates contact or demographic information of an existing patient."""
        pass

    @abstractmethod
    def deactivate_patient(
        self, patient_id: int, motivo_baja: str, categoria: str = "administrativa"
    ) -> Dict[str, Any]:
        """
        Archiva el historial (nunca se borra). categoria: traslado | fallecimiento | administrativa.
        Cancela las citas pendientes en la misma operación atómica.
        """
        pass

    # --- Appointment Management ---
    @abstractmethod
    def create_appointment(self, appointment_data: Dict[str, Any]) -> Appointment:
        """Schedules a new appointment with an institution professional."""
        pass

    @abstractmethod
    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        """Retrieves appointments for a specific patient or all upcoming appointments."""
        pass

    # --- Clinical Consultations & History ---
    @abstractmethod
    def register_consultation(self, consultation_data: Dict[str, Any]) -> Consultation:
        """
        Registers a clinical consultation atomically (ACID transaction in SQL,
        atomic document operation in NoSQL) along with diagnoses, treatments,
        prescriptions, and institution-specific components.
        """
        pass

    @abstractmethod
    def get_clinical_history(
        self, patient_id: int, user_role: UserRole = UserRole.MEDICO
    ) -> Optional[UnifiedClinicalRecord]:
        """
        Retrieves the unified clinical history of a patient,
        applying role-based filtering (Public, Confidential, Restricted).
        """
        pass

    # --- Specialized Institution Operations ---
    @abstractmethod
    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        """
        Returns specialized domain records:
          - Hospital: hospitalizations and bed assignments
          - Pediatría: growth somatometry charts and vaccination card
          - Laboratorio: lab orders, samples, and dynamic analyte results
          - Odontología: dental procedures executed per tooth piece
        """
        pass


    # --- Personal médico (lo gestiona el administrador de la institución) ---
    @abstractmethod
    def list_professionals(self) -> List[Professional]:
        """Lista los profesionales de la institución (activos e inactivos)."""
        pass

    @abstractmethod
    def create_professional(self, data: Dict[str, Any]) -> Professional:
        """Registra un profesional. numero_colegiado es único."""
        pass

    @abstractmethod
    def update_professional(self, professional_id: int, data: Dict[str, Any]) -> Professional:
        """Actualiza datos o estado (activo / inactivo). Nunca se borra: tiene citas asociadas."""
        pass

    def get_catalogs(self) -> Dict[str, Any]:
        """Catálogos públicos de la institución (tipos de examen, procedimientos...). Opcional."""
        return {}


class HospitalOperationsPort(ABC):
    """
    Puerto EXCLUSIVO del Hospital General: quirófanos, cirugías y enfermería.
    Solo lo implementa el adaptador de PostgreSQL. Las otras instituciones no
    tienen estas operaciones, así que no ensucian el puerto común.
    """

    @abstractmethod
    def list_operating_rooms(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_surgeries(self, fecha: Optional[str] = None, patient_id: Optional[int] = None,
                       solo_pendientes: bool = False) -> List[Surgery]:
        pass

    @abstractmethod
    def schedule_surgery(self, data: Dict[str, Any]) -> Surgery:
        pass

    @abstractmethod
    def start_surgery(self, surgery_id: int) -> Surgery:
        pass

    @abstractmethod
    def finish_surgery(self, surgery_id: int, notas: Optional[str] = None) -> Surgery:
        pass

    @abstractmethod
    def cancel_surgery(self, surgery_id: int, motivo: str) -> Surgery:
        pass

    @abstractmethod
    def list_nurses(self) -> List[Professional]:
        pass

    @abstractmethod
    def create_nurse(self, data: Dict[str, Any]) -> Professional:
        pass

    @abstractmethod
    def update_nurse(self, nurse_id: int, data: Dict[str, Any]) -> Professional:
        pass

    @abstractmethod
    def list_shift_assignments(self, fecha: Optional[str] = None, patient_id: Optional[int] = None) -> List[ShiftAssignment]:
        pass

    @abstractmethod
    def assign_shift(self, data: Dict[str, Any]) -> ShiftAssignment:
        pass

    @abstractmethod
    def annul_shift(self, assignment_id: int) -> ShiftAssignment:
        pass

    @abstractmethod
    def list_hospitalizations(self, solo_ingresados: bool = True) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def discharge(self, hospitalization_id: int, tipo: str = "alta") -> Dict[str, Any]:
        pass

    # ---- Departamentos y habitaciones ----
    @abstractmethod
    def list_departments(self) -> List[Dict[str, Any]]:
        """Departamentos con sus habitaciones, camas y pacientes que las ocupan."""
        pass

    @abstractmethod
    def change_room(self, hospitalization_id: int, codigo_habitacion: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_department(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_room(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Nueva habitación con sus camas dentro de un departamento."""
        pass

    @abstractmethod
    def update_room(self, codigo: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cambia camas, tipo o estado (disponible / mantenimiento)."""
        pass

    # ---- Medicación del internamiento (kárdex) ----
    @abstractmethod
    def list_medicines(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_medication_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea la orden y genera todas sus dosis programadas."""
        pass

    @abstractmethod
    def list_medication_orders(self, hospitalization_id: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def suspend_medication_order(self, order_id: int, motivo: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_doses(self, hospitalization_id: Optional[int] = None, fecha: Optional[str] = None,
                   turno: Optional[str] = None) -> List[Dict[str, Any]]:
        """Dosis con el enfermero encargado según el turno en que caen."""
        pass

    @abstractmethod
    def apply_dose(self, dose_id: int, nurse_id: int, observaciones: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def omit_dose(self, dose_id: int, nurse_id: Optional[int], motivo: str) -> Dict[str, Any]:
        pass


class PediatricOperationsPort(ABC):
    """
    Puerto EXCLUSIVO del Centro Médico Pediátrico: tutores legales, antecedentes perinatales,
    somatometría detallada, curvas de crecimiento OMS, hitos del desarrollo (Denver II),
    control de biológicos / lotes con cadena de frío y catálogo de alergias infantiles.
    """

    @abstractmethod
    def get_pediatric_details(self, patient_id: int) -> Dict[str, Any]:
        """Obtiene la ficha pediátrica integral (perinatal, tutor, somatometría, vacunas, hitos, alergias)."""
        pass

    @abstractmethod
    def update_perinatal(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza antecedentes perinatales del menor (Apgar, semanas, parto, complicaciones)."""
        pass

    @abstractmethod
    def update_guardian(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza los datos del tutor legal y relación de custodia."""
        pass

    @abstractmethod
    def add_somatometry(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra una evaluación somatométrica (peso, talla, perímetro cefálico, IMC y percentil)."""
        pass

    @abstractmethod
    def list_somatometry(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Historial de evaluaciones somatométricas de uno o todos los pacientes infantiles."""
        pass

    @abstractmethod
    def list_vaccines_catalog(self) -> List[Dict[str, Any]]:
        """Catálogo oficial de vacunas e inmunizaciones pediátricas."""
        pass

    @abstractmethod
    def list_vaccine_batches(self) -> List[Dict[str, Any]]:
        """Lotes de biológicos con trazabilidad, stock y rango de cadena de frío."""
        pass

    @abstractmethod
    def create_vaccine_batch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un nuevo lote de vacuna con temperatura y fecha de vencimiento."""
        pass

    @abstractmethod
    def add_vaccination(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra la aplicación de una dosis de biológico a un paciente infantil."""
        pass

    @abstractmethod
    def list_vaccinations(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Historial de aplicaciones de vacunas en la institución pediátrica."""
        pass

    @abstractmethod
    def list_development_milestones(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Hitos del desarrollo psicomotor evaluados según escala Denver II / OMS."""
        pass

    @abstractmethod
    def add_development_milestone(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra la evaluación de un hito psicomotor en motricidad, lenguaje o social."""
        pass

    @abstractmethod
    def list_patient_allergies(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Alergias diagnosticadas en el paciente pediátrico con severidad y riesgo."""
        pass

    @abstractmethod
    def add_patient_allergy(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra una alergia infantil (medicamento, alimento, ambiental)."""
        pass

    @abstractmethod
    def list_allergens_catalog(self) -> List[Dict[str, Any]]:
        """Catálogo estandarizado de alérgenos pediátricos."""
        pass

    @abstractmethod
    def list_growth_percentiles(self, sexo: Optional[str] = None, parametro: Optional[str] = None) -> List[Dict[str, Any]]:
        """Curvas y tablas de percentiles oficiales de la OMS para comparación."""
        pass


class DentalOperationsPort(ABC):
    """
    Puerto EXCLUSIVO de la Clínica Odontológica: odontograma digital de 5 caras por pieza FDI,
    hallazgos patológicos, anamnesis sistémica médica, planes y etapas de tratamiento,
    procedimientos arancelarios, insumos y cobros con abonos por secretaría.
    """

    @abstractmethod
    def get_dental_details(self, patient_id: int) -> Dict[str, Any]:
        """Obtiene la ficha odontológica completa (anamnesis médica, odontograma, planes, cobros)."""
        pass

    @abstractmethod
    def update_systemic_background(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza antecedentes médicos generales (diabetes, hipertensión, alergia a anestesia/látex, embarazo)."""
        pass

    @abstractmethod
    def get_odontogram(self, patient_id: Optional[int] = None) -> Dict[str, Any]:
        """Devuelve el odontograma digital estructurado por piezas FDI (11-48, 51-85) y caras (V, M, D, O, L/P)."""
        pass

    @abstractmethod
    def save_odontogram_finding(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un hallazgo patológico o diagnóstico en una cara y pieza dental específica."""
        pass

    @abstractmethod
    def list_treatment_plans(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lista presupuestos y planes globales de rehabilitación dental con sus etapas."""
        pass

    @abstractmethod
    def create_treatment_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo plan de tratamiento con desglose de fases programadas."""
        pass

    @abstractmethod
    def update_treatment_plan_stage(self, plan_id: int, etapa_id: int, estado: str) -> Dict[str, Any]:
        """Actualiza el estado de una fase del plan (pendiente, en_curso, completada)."""
        pass

    @abstractmethod
    def list_dental_procedures_catalog(self) -> List[Dict[str, Any]]:
        """Catálogo arancelario de procedimientos odontológicos clasificados."""
        pass

    @abstractmethod
    def create_dental_procedure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un nuevo procedimiento con arancel, duración y código en el catálogo."""
        pass

    @abstractmethod
    def list_billing_and_payments(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Historial de facturas y abonos cobrados en secretaría."""
        pass

    @abstractmethod
    def register_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un abono o cancelación de cuenta con recibo y método de pago."""
        pass

    @abstractmethod
    def list_dental_findings_catalog(self) -> List[Dict[str, Any]]:
        """Catálogo de hallazgos dentales con simbología de color oficial para el odontograma."""
        pass

    @abstractmethod
    def list_dental_supplies(self) -> List[Dict[str, Any]]:
        """Catálogo e inventario de insumos clínicos odontológicos y stock."""
        pass


class AuthPort(ABC):
    """
    Port for user authentication and institution discovery.
    """

    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticates user credentials and returns session context."""
        pass

    @abstractmethod
    def get_user_by_token(self, token: str) -> Optional[User]:
        """Resolves user session from a bearer token."""
        pass

    @abstractmethod
    def list_available_users(self) -> List[Dict[str, Any]]:
        """Returns pre-configured demonstration users for all 4 institutions."""
        pass

