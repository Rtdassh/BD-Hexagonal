"""
Servicios de aplicación (casos de uso).

Aquí viven las reglas de negocio que son IGUALES para los cuatro motores:
quién puede hacer qué, qué datos son obligatorios, y cómo se arma la solicitud
antes de entregarla al adaptador. Ningún servicio sabe qué motor hay detrás.
"""

from typing import Any, Dict, List, Optional

from ..domain.entities import (
    Appointment,
    Consultation,
    Patient,
    UnifiedClinicalRecord,
    User,
    UserRole,
)
from ..domain.ports import AuthPort
from .router import EngineRouter

ROLES_CLINICOS = {UserRole.MEDICO, UserRole.PEDIATRA, UserRole.LABORATORISTA, UserRole.ODONTOLOGO, UserRole.ADMIN}
CATEGORIAS_BAJA = {"traslado", "fallecimiento", "administrativa"}


class PermisoDenegado(Exception):
    """El rol del usuario no permite la operación (HTTP 403)."""


def _exigir_clinico(user: User, accion: str) -> None:
    if user.rol not in ROLES_CLINICOS:
        raise PermisoDenegado(f"Su rol ({user.rol.value}) no puede {accion}")


class PatientService:
    def __init__(self, router: EngineRouter):
        self.router = router

    def register_new_patient(self, user: User, data: Dict[str, Any], override_inst: Optional[str] = None) -> Patient:
        return self.router.get_adapter_for_user(user, override_inst).create_patient(data)

    def search_patients(self, user: User, query: str, override_inst: Optional[str] = None) -> List[Patient]:
        return self.router.get_adapter_for_user(user, override_inst).search_patients(query)

    def get_patient_by_id(self, user: User, patient_id: int, override_inst: Optional[str] = None) -> Optional[Patient]:
        return self.router.get_adapter_for_user(user, override_inst).get_patient(patient_id)

    def update_patient_info(self, user: User, patient_id: int, updates: Dict[str, Any],
                            override_inst: Optional[str] = None) -> Patient:
        return self.router.get_adapter_for_user(user, override_inst).update_patient(patient_id, updates)

    def archive_patient_record(self, user: User, patient_id: int, motivo_baja: str, categoria: str = "administrativa",
                               override_inst: Optional[str] = None) -> Dict[str, Any]:
        _exigir_clinico(user, "dar de baja un historial")
        categoria = (categoria or "administrativa").lower()
        if categoria not in CATEGORIAS_BAJA:
            raise ValueError(f"Categoría de baja inválida. Use: {', '.join(sorted(CATEGORIAS_BAJA))}")
        if not (motivo_baja or "").strip():
            raise ValueError("Indique el motivo de la baja")
        return self.router.get_adapter_for_user(user, override_inst).deactivate_patient(
            patient_id, motivo_baja.strip(), categoria
        )


class ClinicalHistoryService:
    def __init__(self, router: EngineRouter):
        self.router = router

    def get_unified_history(self, user: User, patient_id: int,
                            override_inst: Optional[str] = None) -> Optional[UnifiedClinicalRecord]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        # El filtro de información restringida se aplica según el rol del usuario.
        return adapter.get_clinical_history(patient_id, user_role=user.rol)

    def get_specialized_records(self, user: User, patient_id: int,
                                override_inst: Optional[str] = None) -> Dict[str, Any]:
        _exigir_clinico(user, "ver registros clínicos especializados")
        return self.router.get_adapter_for_user(user, override_inst).get_specialized_records(patient_id)

    def get_catalogs(self, user: User, override_inst: Optional[str] = None) -> Dict[str, Any]:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        return adapter.get_catalogs() if hasattr(adapter, "get_catalogs") else {}


class ConsultationService:
    def __init__(self, router: EngineRouter):
        self.router = router

    def register_consultation_transaction(self, user: User, data: Dict[str, Any],
                                          override_inst: Optional[str] = None) -> Consultation:
        """Registrar consulta + agregar diagnóstico + recetar medicamento (una sola operación atómica)."""
        _exigir_clinico(user, "registrar consultas, diagnósticos ni recetas")
        if not (data.get("motivo") or "").strip():
            raise ValueError("El motivo de la consulta es obligatorio")

        payload = dict(data)
        payload["id_profesional"] = user.id_profesional
        payload["rol"] = user.rol.value
        recetas = [r for r in (payload.get("recetas") or []) if (r or {}).get("medicamento")]
        payload["recetas"] = recetas
        # Regla de negocio común: no se receta sin diagnóstico.
        if recetas and not (payload.get("codigo_cie10") or payload.get("descripcion_diagnostico")):
            raise ValueError("Para recetar se necesita un diagnóstico")
        # Compatibilidad con los adaptadores simulados (esperan la primera receta en campos planos).
        if recetas:
            for k, v in recetas[0].items():
                payload.setdefault(k, v)
        procs = payload.get("procedimientos") or []
        if procs:
            for k, v in procs[0].items():
                payload.setdefault(k, v)

        return self.router.get_adapter_for_user(user, override_inst).register_consultation(payload)

    def schedule_appointment(self, user: User, data: Dict[str, Any],
                             override_inst: Optional[str] = None) -> Appointment:
        payload = {**data, "id_profesional": user.id_profesional, "rol": user.rol.value}
        return self.router.get_adapter_for_user(user, override_inst).create_appointment(payload)

    def list_appointments(self, user: User, patient_id: Optional[int] = None,
                          override_inst: Optional[str] = None) -> List[Appointment]:
        return self.router.get_adapter_for_user(user, override_inst).get_appointments(patient_id)


class AuthService:
    def __init__(self, auth_port: AuthPort):
        self.auth_port = auth_port

    def login(self, username: str, password: str) -> Optional[User]:
        return self.auth_port.authenticate(username, password)

    def validate_session(self, token: str) -> Optional[User]:
        return self.auth_port.get_user_by_token(token)

    def logout(self, token: str) -> None:
        if hasattr(self.auth_port, "logout"):
            self.auth_port.logout(token)

    def get_demo_accounts(self) -> List[Dict[str, Any]]:
        return self.auth_port.list_available_users()
