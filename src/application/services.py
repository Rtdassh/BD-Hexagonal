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
from ..domain.ports import AuthPort, HospitalOperationsPort, LaboratoryOrdersPort, PediatricOperationsPort, DentalOperationsPort
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


class PediatricService:
    """
    Casos de uso exclusivos del Centro Médico Pediátrico: tutores legales,
    antecedentes perinatales, antropometría / somatometría detallada, percentiles OMS,
    hitos de desarrollo Denver II, control de vacunas y lotes con cadena de frío, y alergias.
    """

    def __init__(self, router: EngineRouter):
        self.router = router

    def _pediatrico(self, user: User) -> PediatricOperationsPort:
        adapter = self.router.get_adapter_for_user(user)
        if not isinstance(adapter, PediatricOperationsPort):
            raise ValueError("Operación clínica exclusiva del Centro Médico Pediátrico")
        return adapter

    def detalles(self, user: User, patient_id: int):
        _exigir_clinico(user, "consultar el expediente pediátrico integral")
        return self._pediatrico(user).get_pediatric_details(patient_id)

    def actualizar_perinatal(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "actualizar antecedentes perinatales")
        data = V.validar_antecedente_perinatal(dict(data))
        return self._pediatrico(user).update_perinatal(patient_id, data)

    def actualizar_tutor(self, user: User, patient_id: int, data: Dict[str, Any]):
        return self._pediatrico(user).update_guardian(patient_id, dict(data))

    def registrar_somatometria(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "registrar mediciones de somatometría")
        data = V.validar_somatometria_pediatrica(dict(data))
        return self._pediatrico(user).add_somatometry(patient_id, data)

    def somatometria(self, user: User, patient_id: Optional[int] = None):
        _exigir_clinico(user, "consultar historial de somatometría")
        return self._pediatrico(user).list_somatometry(patient_id)

    def vacunas_catalogo(self, user: User):
        return self._pediatrico(user).list_vaccines_catalog()

    def lotes_vacunas(self, user: User):
        return self._pediatrico(user).list_vaccine_batches()

    def crear_lote_vacuna(self, user: User, data: Dict[str, Any]):
        _exigir_admin(user)
        data = V.validar_lote_vacuna(dict(data))
        return self._pediatrico(user).create_vaccine_batch(data)

    def aplicar_vacuna(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "registrar la aplicación de biológicos")
        return self._pediatrico(user).add_vaccination(patient_id, dict(data))

    def vacunaciones(self, user: User, patient_id: Optional[int] = None):
        _exigir_clinico(user, "consultar registros de vacunación")
        return self._pediatrico(user).list_vaccinations(patient_id)

    def hitos_desarrollo(self, user: User, patient_id: Optional[int] = None):
        _exigir_clinico(user, "consultar evaluaciones del desarrollo infantil")
        return self._pediatrico(user).list_development_milestones(patient_id)

    def evaluar_hito(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "evaluar hitos psicomotores")
        if not data.get("hito_evaluado"):
            raise ValueError("El hito psicomotor a evaluar es obligatorio")
        return self._pediatrico(user).add_development_milestone(patient_id, dict(data))

    def alergias(self, user: User, patient_id: Optional[int] = None):
        _exigir_clinico(user, "consultar alergias pediátricas")
        return self._pediatrico(user).list_patient_allergies(patient_id)

    def registrar_alergia(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "registrar diagnósticos de alergia infantil")
        if not data.get("id_alergeno"):
            raise ValueError("Debe seleccionar un alérgeno del catálogo")
        return self._pediatrico(user).add_patient_allergy(patient_id, dict(data))

    def alergenos_catalogo(self, user: User):
        return self._pediatrico(user).list_allergens_catalog()

    def percentiles_oms(self, user: User, sexo: Optional[str] = None, parametro: Optional[str] = None):
        return self._pediatrico(user).list_growth_percentiles(sexo, parametro)


class DentalService:
    """
    Casos de uso exclusivos de la Clínica Odontológica: anamnesis sistémica médica,
    odontograma tridimensional (5 caras FDI), planes y etapas de tratamiento,
    aranceles de procedimientos, cobros, facturación y pagos/abonos.
    """

    def __init__(self, router: EngineRouter):
        self.router = router

    def _odontologia(self, user: User) -> DentalOperationsPort:
        adapter = self.router.get_adapter_for_user(user)
        if not isinstance(adapter, DentalOperationsPort):
            raise ValueError("Operación clínica exclusiva de la Clínica Odontológica")
        return adapter

    def detalles(self, user: User, patient_id: int):
        _exigir_clinico(user, "consultar el expediente odontológico completo")
        return self._odontologia(user).get_dental_details(patient_id)

    def actualizar_sistemico(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "actualizar antecedentes médicos sistémicos")
        data = V.validar_antecedente_sistemico_dental(dict(data))
        return self._odontologia(user).update_systemic_background(patient_id, data)

    def odontograma(self, user: User, patient_id: Optional[int] = None):
        _exigir_clinico(user, "consultar el odontograma del paciente")
        return self._odontologia(user).get_odontogram(patient_id)

    def registrar_hallazgo(self, user: User, patient_id: int, data: Dict[str, Any]):
        _exigir_clinico(user, "registrar hallazgos patológicos en el odontograma")
        data = V.validar_hallazgo_odontograma(dict(data))
        return self._odontologia(user).save_odontogram_finding(patient_id, data)

    def planes(self, user: User, patient_id: Optional[int] = None):
        return self._odontologia(user).list_treatment_plans(patient_id)

    def crear_plan(self, user: User, data: Dict[str, Any]):
        _exigir_clinico(user, "formular planes de tratamiento dental")
        data = V.validar_plan_tratamiento(dict(data))
        return self._odontologia(user).create_treatment_plan(data)

    def actualizar_etapa_plan(self, user: User, plan_id: int, etapa_id: int, estado: str):
        _exigir_clinico(user, "actualizar el avance de etapas del plan")
        if estado not in ("pendiente", "en_curso", "completada"):
            raise ValueError("Estado de fase inválido: pendiente, en_curso o completada")
        return self._odontologia(user).update_treatment_plan_stage(plan_id, etapa_id, estado)

    def procedimientos(self, user: User):
        return self._odontologia(user).list_dental_procedures_catalog()

    def crear_procedimiento(self, user: User, data: Dict[str, Any]):
        _exigir_admin(user)
        if not data.get("nombre_procedimiento"):
            raise ValueError("El nombre del procedimiento es obligatorio")
        if float(data.get("costo", 0)) < 0:
            raise ValueError("El costo base no puede ser negativo")
        return self._odontologia(user).create_dental_procedure(dict(data))

    def facturacion(self, user: User, patient_id: Optional[int] = None):
        return self._odontologia(user).list_billing_and_payments(patient_id)

    def registrar_pago(self, user: User, data: Dict[str, Any]):
        data = V.validar_pago_dental(dict(data))
        data["secretaria"] = user.nombre_completo
        return self._odontologia(user).register_payment(data)

    def hallazgos_catalogo(self, user: User):
        return self._odontologia(user).list_dental_findings_catalog()

    def insumos(self, user: User):
        return self._odontologia(user).list_dental_supplies()


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



class LabService:
    """
    Órdenes del Laboratorio Clínico. Solo existen con MongoDB conectado: si el adaptador
    del usuario no implementa LaboratoryOrdersPort, la operación se rechaza.
    """

    def __init__(self, router: EngineRouter):
        self.router = router

    def _lab(self, user: User) -> LaboratoryOrdersPort:
        adapter = self.router.get_adapter_for_user(user)
        if not isinstance(adapter, LaboratoryOrdersPort):
            raise ValueError("Las órdenes solo existen en el Laboratorio Clínico (con MongoDB conectado)")
        return adapter

    def ordenes(self, user, estado=None, id_paciente=None):
        if estado and estado not in LaboratoryOrdersPort.ESTADOS:
            raise ValueError("Estado de orden inválido")
        return self._lab(user).list_lab_orders(estado, id_paciente)

    def orden(self, user, id_orden):
        return self._lab(user).get_lab_order(id_orden)

    def crear(self, user, data):
        _exigir_admin(user)
        payload = V.validar_orden_laboratorio(dict(data))
        if payload.get("fecha_toma"):
            payload["id_laboratorista"] = _exigir_profesional_activo(self._lab(user), data.get("id_laboratorista") or 1)
        return self._lab(user).create_lab_order(payload)

    def agendar(self, user, id_orden, data):
        _exigir_admin(user)
        payload = dict(data)
        V.fecha_hora(payload, "fecha_toma", "La toma de muestra", tolerancia_min=5, max_dias=90)
        return self._lab(user).schedule_sample(id_orden, payload)

    def muestra(self, user, id_orden, data):
        _exigir_admin(user)
        payload = dict(data)
        V.texto(payload, "tipo_muestra", "Tipo de muestra", 80, 3, req=True)
        V.texto(payload, "condicion_muestra", "Condición de la muestra", 200)
        if payload.get("preparacion_cumplida") not in (True, "1", "true", "on", 1):
            payload["motivo_rechazo"] = V.motivo(payload.get("motivo_rechazo"), "El motivo del rechazo")
        return self._lab(user).register_sample(id_orden, payload)

    def resultados(self, user, id_orden, data):
        _exigir_admin(user)
        payload = dict(data)
        payload["parametros"] = [dict(p) for p in (payload.get("parametros") or []) if (p or {}).get("nombre_parametro")]
        for i, p in enumerate(payload["parametros"], 1):
            V.texto(p, "valor_resultado", f"Parámetro {i}: resultado", 40)
        V.texto(payload, "observaciones_tecnicas", "Observaciones técnicas", 300)
        return self._lab(user).register_results(id_orden, payload)

    def validar(self, user, id_orden, data):
        _exigir_admin(user)
        return self._lab(user).validate_order(id_orden, dict(data))

    def entregar(self, user, id_orden, data):
        _exigir_admin(user)
        payload = dict(data)
        V.nombre(payload, "entregado_a", "Entregado a", 100, req=True)
        return self._lab(user).deliver_order(id_orden, payload)

    def cancelar(self, user, id_orden, motivo):
        _exigir_admin(user)
        return self._lab(user).cancel_order(id_orden, V.motivo(motivo, "El motivo de la cancelación"))

    def agenda(self, user, desde=None):
        return self._lab(user).sample_agenda(desde)
