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

