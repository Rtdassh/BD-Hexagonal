"""
Application Services (Use Cases).
Coordinates business rules and interacts through Ports and the EngineRouter.
"""

from typing import Dict, Any, List, Optional
from ..domain.entities import (
    User,
    Patient,
    UnifiedClinicalRecord,
    Appointment,
    Consultation,
    InstitutionType,
    UserRole
)
from ..domain.ports import AuthPort
from .router import EngineRouter


class PatientService:
    """Use cases for patient management across all four institutions."""

    def __init__(self, router: EngineRouter):
        self.router = router

    def register_new_patient(
        self, user: User, patient_data: Dict[str, Any], override_inst: Optional[str] = None
    ) -> Patient:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.create_patient(patient_data)

    def search_patients(
        self, user: User, query: str, override_inst: Optional[str] = None
    ) -> List[Patient]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.search_patients(query)

    def get_patient_by_id(
        self, user: User, patient_id: int, override_inst: Optional[str] = None
    ) -> Optional[Patient]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.get_patient(patient_id)

    def update_patient_info(
        self, user: User, patient_id: int, updates: Dict[str, Any], override_inst: Optional[str] = None
    ) -> Patient:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.update_patient(patient_id, updates)

    def archive_patient_record(
        self, user: User, patient_id: int, motivo_baja: str, override_inst: Optional[str] = None
    ) -> Dict[str, Any]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.deactivate_patient(patient_id, motivo_baja)


class ClinicalHistoryService:
    """Use cases for unified clinical history retrieval with RBAC data classification."""

    def __init__(self, router: EngineRouter):
        self.router = router

    def get_unified_history(
        self, user: User, patient_id: int, override_inst: Optional[str] = None
    ) -> Optional[UnifiedClinicalRecord]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.get_clinical_history(patient_id, user_role=user.rol)

    def get_specialized_records(
        self, user: User, patient_id: int, override_inst: Optional[str] = None
    ) -> Dict[str, Any]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.get_specialized_records(patient_id)


class ConsultationService:
    """Use cases for clinical consultations and appointment scheduling."""

    def __init__(self, router: EngineRouter):
        self.router = router

    def register_consultation_transaction(
        self, user: User, consultation_data: Dict[str, Any], override_inst: Optional[str] = None
    ) -> Consultation:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.register_consultation(consultation_data)

    def schedule_appointment(
        self, user: User, appointment_data: Dict[str, Any], override_inst: Optional[str] = None
    ) -> Appointment:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.create_appointment(appointment_data)

    def list_appointments(
        self, user: User, patient_id: Optional[int] = None, override_inst: Optional[str] = None
    ) -> List[Appointment]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.get_appointments(patient_id)


class AuthService:
    """Use cases for user authentication and session management."""

    def __init__(self, auth_port: AuthPort):
        self.auth_port = auth_port

    def login(self, username: str, password: str) -> Optional[User]:
        return self.auth_port.authenticate(username, password)

    def validate_session(self, token: str) -> Optional[User]:
        return self.auth_port.get_user_by_token(token)

    def get_demo_accounts(self) -> List[Dict[str, Any]]:
        return self.auth_port.list_available_users()

