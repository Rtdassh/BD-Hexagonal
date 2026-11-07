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
    Professional,
    UnifiedClinicalRecord,
    User,
    UserRole,
)
from ..domain import validaciones as V
from ..domain.ports import AuthPort, HospitalOperationsPort
from .router import EngineRouter

ROLES_CLINICOS = {UserRole.MEDICO, UserRole.PEDIATRA, UserRole.LABORATORISTA, UserRole.ODONTOLOGO, UserRole.ADMIN}
CATEGORIAS_BAJA = {"traslado", "fallecimiento", "administrativa"}


class PermisoDenegado(Exception):
    """El rol del usuario no permite la operación (HTTP 403)."""


def _exigir_clinico(user: User, accion: str) -> None:
    if user.rol not in ROLES_CLINICOS:
        raise PermisoDenegado(f"Su rol ({user.rol.value}) no puede {accion}")


def _exigir_profesional_activo(adapter, id_profesional) -> int:
    """Regla común a los 4 motores: toda cita y consulta se asigna a un profesional ACTIVO."""
    if id_profesional in (None, ""):
        raise ValueError("Seleccione el profesional que atiende")
    pid = int(id_profesional)
    prof = next((p for p in adapter.list_professionals() if p.id_profesional == pid), None)
    if not prof:
        raise ValueError(f"El profesional {pid} no existe en esta institución")
    if prof.estado != "activo":
        raise ValueError(f"{prof.nombre_completo} está inactivo; no se le pueden asignar citas ni consultas")
    return pid


class ProfessionalService:
    """Gestión del personal médico. Solo el administrador de la institución."""

    def __init__(self, router: EngineRouter):
        self.router = router

    def listar(self, user: User) -> List[Professional]:
        return self.router.get_adapter_for_user(user).list_professionals()

    def registrar(self, user: User, data: Dict[str, Any]) -> Professional:
        _exigir_admin(user)
        data = V.validar_profesional(dict(data), nuevo=True)
        return self.router.get_adapter_for_user(user).create_professional(data)

    def actualizar(self, user: User, professional_id: int, data: Dict[str, Any]) -> Professional:
        _exigir_admin(user)
        data = V.validar_profesional(dict(data), nuevo=False)
        return self.router.get_adapter_for_user(user).update_professional(professional_id, data)


def _exigir_admin(user: User) -> None:
    if user.rol != UserRole.ADMIN:
        raise PermisoDenegado("Solo el administrador de la institución gestiona el personal médico")


TURNOS = ("manana", "tarde", "noche")


class HospitalService:
    """
    Quirófanos, cirugías y enfermería. Solo existen en el Hospital General: si el
    adaptador del usuario no implementa HospitalOperationsPort, la operación se rechaza.
    """

    def __init__(self, router: EngineRouter):
        self.router = router

    def _hospital(self, user: User) -> HospitalOperationsPort:
        adapter = self.router.get_adapter_for_user(user)
        if not isinstance(adapter, HospitalOperationsPort):
            raise ValueError("Quirófanos y enfermería solo existen en el Hospital General (con PostgreSQL conectado)")
        return adapter

    # Quirófanos y cirugías
    def quirofanos(self, user):
        return self._hospital(user).list_operating_rooms()

    def cirugias(self, user, fecha=None, id_paciente=None, pendientes=False):
        return self._hospital(user).list_surgeries(fecha, id_paciente, pendientes)

    def programar_cirugia(self, user, data):
        _exigir_admin(user)
        h = self._hospital(user)
        if (data.get("tipo") or "electiva") not in ("electiva", "urgencia"):
            raise ValueError("Tipo de cirugía inválido")
        payload = V.validar_cirugia(dict(data))
        payload["id_medico"] = _exigir_profesional_activo(h, data.get("id_medico"))
        return h.schedule_surgery(payload)

    def iniciar_cirugia(self, user, id_cirugia):
        _exigir_admin(user)
        return self._hospital(user).start_surgery(id_cirugia)

    def finalizar_cirugia(self, user, id_cirugia, notas=None):
        _exigir_admin(user)
        if notas and len(notas.strip()) > 1000:
            raise ValueError("Las notas operatorias admiten como máximo 1000 caracteres")
        return self._hospital(user).finish_surgery(id_cirugia, (notas or "").strip() or None)

    def cancelar_cirugia(self, user, id_cirugia, motivo):
        _exigir_admin(user)
        return self._hospital(user).cancel_surgery(id_cirugia, V.motivo(motivo, "El motivo de la cancelación"))

    # Enfermería
    def enfermeros(self, user):
        return self._hospital(user).list_nurses()

    def registrar_enfermero(self, user, data):
        _exigir_admin(user)
        return self._hospital(user).create_nurse(V.validar_profesional(dict(data), nuevo=True))

    def actualizar_enfermero(self, user, id_enfermero, data):
        _exigir_admin(user)
        return self._hospital(user).update_nurse(id_enfermero, V.validar_profesional(dict(data), nuevo=False))

    def turnos(self, user, fecha=None, id_paciente=None):
        return self._hospital(user).list_shift_assignments(fecha, id_paciente)

    def asignar_turno(self, user, data):
        _exigir_admin(user)
        if data.get("turno") not in TURNOS:
            raise ValueError("Turno inválido: mañana, tarde o noche")
        data = dict(data)
        V.texto(data, "observaciones", "Indicaciones para el turno", 200)
        return self._hospital(user).assign_shift(data)

    def anular_turno(self, user, id_asignacion):
        _exigir_admin(user)
        return self._hospital(user).annul_shift(id_asignacion)

    def hospitalizados(self, user, todos=False):
        return self._hospital(user).list_hospitalizations(not todos)

    def dar_alta(self, user, id_hospitalizacion, tipo="alta"):
        _exigir_admin(user)
        return self._hospital(user).discharge(id_hospitalizacion, tipo)

    # Departamentos y habitaciones
    def departamentos(self, user):
        return self._hospital(user).list_departments()

    def cambiar_habitacion(self, user, id_hospitalizacion, codigo):
        _exigir_admin(user)
        return self._hospital(user).change_room(id_hospitalizacion, codigo)

    def crear_departamento(self, user, data):
        _exigir_admin(user)
        return self._hospital(user).create_department(V.validar_departamento(dict(data)))

    def crear_habitacion(self, user, data):
        _exigir_admin(user)
        return self._hospital(user).create_room(V.validar_habitacion(dict(data), nueva=True))

    def editar_habitacion(self, user, codigo, data):
        _exigir_admin(user)
        return self._hospital(user).update_room(codigo, V.validar_habitacion(dict(data), nueva=False))

    # Medicación del internamiento
    def medicamentos(self, user):
        return self._hospital(user).list_medicines()

    def indicar_medicacion(self, user, data):
        _exigir_admin(user)
        h = self._hospital(user)
        if not data.get("id_medicamento"):
            raise ValueError("Elija el medicamento")
        payload = V.validar_orden_medicacion(dict(data))
        payload["id_medico"] = _exigir_profesional_activo(h, data.get("id_medico"))
        return h.create_medication_order(payload)

    def ordenes_medicacion(self, user, id_hospitalizacion):
        return self._hospital(user).list_medication_orders(id_hospitalizacion)

    def suspender_medicacion(self, user, id_orden, motivo):
        _exigir_admin(user)
        return self._hospital(user).suspend_medication_order(id_orden, V.motivo(motivo, "El motivo de la suspensión"))

    def dosis(self, user, id_hospitalizacion=None, fecha=None, turno=None):
        if turno and turno not in TURNOS:
            raise ValueError("Turno inválido")
        return self._hospital(user).list_doses(id_hospitalizacion, fecha, turno)

    def aplicar_dosis(self, user, id_dosis, id_enfermero, observaciones=None):
        _exigir_admin(user)
        if not id_enfermero:
            raise ValueError("Indique qué enfermero aplicó la dosis")
        if observaciones and len(observaciones.strip()) > 200:
            raise ValueError("Las observaciones admiten como máximo 200 caracteres")
        return self._hospital(user).apply_dose(id_dosis, id_enfermero, observaciones)

    def omitir_dosis(self, user, id_dosis, id_enfermero, motivo):
        _exigir_admin(user)
        return self._hospital(user).omit_dose(id_dosis, id_enfermero, V.motivo(motivo, "El motivo"))


class PatientService:
    def __init__(self, router: EngineRouter):
        self.router = router

    def register_new_patient(self, user: User, data: Dict[str, Any], override_inst: Optional[str] = None) -> Patient:
        data = V.validar_paciente(dict(data), user.institucion.value, nuevo=True)
        return self.router.get_adapter_for_user(user, override_inst).create_patient(data)

    def search_patients(self, user: User, query: str, override_inst: Optional[str] = None) -> List[Patient]:
        return self.router.get_adapter_for_user(user, override_inst).search_patients(query)

    def get_patient_by_id(self, user: User, patient_id: int, override_inst: Optional[str] = None) -> Optional[Patient]:
        return self.router.get_adapter_for_user(user, override_inst).get_patient(patient_id)

    def update_patient_info(self, user: User, patient_id: int, updates: Dict[str, Any],
                            override_inst: Optional[str] = None) -> Patient:
        updates = {k: v for k, v in dict(updates).items() if k not in ("dpi", "id_paciente")}   # el DPI no se cambia
        updates = V.validar_paciente(updates, user.institucion.value, nuevo=False)
        return self.router.get_adapter_for_user(user, override_inst).update_patient(patient_id, updates)

    def archive_patient_record(self, user: User, patient_id: int, motivo_baja: str, categoria: str = "administrativa",
                               override_inst: Optional[str] = None) -> Dict[str, Any]:
        _exigir_clinico(user, "dar de baja un historial")
        categoria = (categoria or "administrativa").lower()
        if categoria not in CATEGORIAS_BAJA:
            raise ValueError(f"Categoría de baja inválida. Use: {', '.join(sorted(CATEGORIAS_BAJA))}")
        motivo_baja = V.motivo(motivo_baja, "El motivo de la baja", 150)
        return self.router.get_adapter_for_user(user, override_inst).deactivate_patient(
            patient_id, motivo_baja, categoria
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
        adapter = self.router.get_adapter_for_user(user, override_inst)
        payload = dict(data)
        payload["recetas"] = [dict(r) for r in (payload.get("recetas") or []) if (r or {}).get("medicamento")]
        payload["procedimientos"] = [dict(r) for r in (payload.get("procedimientos") or []) if r]
        payload["parametros"] = [dict(r) for r in (payload.get("parametros") or []) if (r or {}).get("nombre_parametro")]
        V.validar_consulta(payload, user.institucion.value)
        payload["id_profesional"] = _exigir_profesional_activo(adapter, data.get("id_profesional"))
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

        return adapter.register_consultation(payload)

    def schedule_appointment(self, user: User, data: Dict[str, Any],
                             override_inst: Optional[str] = None) -> Appointment:
        adapter = self.router.get_adapter_for_user(user, override_inst)
        payload = V.validar_cita(dict(data))
        payload["id_profesional"] = _exigir_profesional_activo(adapter, data.get("id_profesional"))
        return adapter.create_appointment(payload)

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
