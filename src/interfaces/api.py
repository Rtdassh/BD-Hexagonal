"""
API REST (adaptador primario / de entrada) y servidor de la interfaz web.
"""

import json
import logging
from dataclasses import asdict, is_dataclass
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory

from ..application.router import EngineRouter
from ..application.services import (
    AuthService,
    ClinicalHistoryService,
    ConsultationService,
    DentalService,
    HospitalService,
    LabService,
    PatientService,
    PediatricService,
    PermisoDenegado,
    ProfessionalService,
)
from ..domain.entities import User
from ..infrastructure.adapters.auth_adapter import AuthAdapter
from ..infrastructure.config import Config

log = logging.getLogger(__name__)

INSTITUCIONES = {
    "hospital": {"nombre": "Hospital General", "motor": "PostgreSQL"},
    "pediatrico": {"nombre": "Centro Médico Pediátrico", "motor": "MySQL"},
    "laboratorio": {"nombre": "Laboratorio Clínico", "motor": "MongoDB"},
    "odontologia": {"nombre": "Clínica Odontológica", "motor": "Firebase Cloud Firestore"},
}


def _serializar(obj):
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


def _json(data, status=200):
    if is_dataclass(data):
        data = asdict(data)
    elif isinstance(data, list):
        data = [asdict(d) if is_dataclass(d) else d for d in data]
    return json.dumps(data, default=_serializar, ensure_ascii=False), status, {"Content-Type": "application/json"}


def create_app(config: Config = None, router: EngineRouter = None):
    config = config or Config()
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.json.ensure_ascii = False

    auth_service = AuthService(AuthAdapter())
    engine_router = router or EngineRouter(config)
    patient_service = PatientService(engine_router)
    history_service = ClinicalHistoryService(engine_router)
    consultation_service = ConsultationService(engine_router)
    professional_service = ProfessionalService(engine_router)
    hospital_service = HospitalService(engine_router)
    lab_service = LabService(engine_router)
    pediatric_service = PediatricService(engine_router)
    dental_service = DentalService(engine_router)
    app.engine_router = engine_router

    def _usuario_json(user: User):
        return {
            "token": user.token,
            "username": user.username,
            "nombre_completo": user.nombre_completo,
            "institucion": user.institucion.value,
            "institucion_nombre": INSTITUCIONES[user.institucion.value]["nombre"],
            "rol": user.rol.value,
            "motor_asignado": user.motor_asignado.value,
            "numero_colegiado": user.numero_colegiado,
        }

    def require_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
            user = auth_service.validate_session(token) if token else None
            if not user:
                return jsonify({"error": "Sesión no válida o expirada. Inicie sesión de nuevo."}), 401
            request.current_user = user
            try:
                return f(*args, **kwargs)
            except PermisoDenegado as e:
                return jsonify({"error": str(e)}), 403
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            except Exception as e:  # error del motor u otro inesperado
                log.exception("Error no controlado")
                return jsonify({"error": f"Error del servidor: {type(e).__name__}: {e}"}), 500
        return decorated

    def inst():
        return request.args.get("institucion") or None

    # ------------------------------------------------------------------
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # Autenticación ------------------------------------------------------
    @app.route("/api/auth/demo-users", methods=["GET"])
    def demo_users():
        return jsonify(auth_service.get_demo_accounts())

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        user = auth_service.login(data.get("username", ""), data.get("password", ""))
        if not user:
            return jsonify({"error": "Usuario o contraseña incorrectos"}), 401
        return jsonify(_usuario_json(user))

    @app.route("/api/auth/me", methods=["GET"])
    @require_auth
    def me():
        return jsonify(_usuario_json(request.current_user))

    @app.route("/api/auth/logout", methods=["POST"])
    @require_auth
    def logout():
        auth_service.logout(request.current_user.token)
        return jsonify({"ok": True})

    # Pacientes ----------------------------------------------------------
    @app.route("/api/patients", methods=["GET"])
    @require_auth
    def list_patients():
        return _json(patient_service.search_patients(request.current_user, request.args.get("q", ""), inst()))

    @app.route("/api/patients", methods=["POST"])
    @require_auth
    def create_patient():
        data = request.get_json(silent=True) or {}
        return _json(patient_service.register_new_patient(request.current_user, data, inst()), 201)

    @app.route("/api/patients/<int:patient_id>", methods=["GET"])
    @require_auth
    def get_patient(patient_id):
        p = patient_service.get_patient_by_id(request.current_user, patient_id, inst())
        return _json(p) if p else (jsonify({"error": "Paciente no encontrado"}), 404)

    @app.route("/api/patients/<int:patient_id>", methods=["PUT"])
    @require_auth
    def update_patient(patient_id):
        data = request.get_json(silent=True) or {}
        return _json(patient_service.update_patient_info(request.current_user, patient_id, data, inst()))

    @app.route("/api/patients/<int:patient_id>/deactivate", methods=["POST"])
    @require_auth
    def deactivate_patient(patient_id):
        data = request.get_json(silent=True) or {}
        return jsonify(patient_service.archive_patient_record(
            request.current_user, patient_id, data.get("motivo_baja", ""), data.get("categoria", "administrativa"),
            inst(),
        ))

    # Historial ----------------------------------------------------------
    @app.route("/api/patients/<int:patient_id>/history", methods=["GET"])
    @require_auth
    def history(patient_id):
        h = history_service.get_unified_history(request.current_user, patient_id, inst())
        return _json(h) if h else (jsonify({"error": "Historial no encontrado"}), 404)

    @app.route("/api/patients/<int:patient_id>/specialized", methods=["GET"])
    @require_auth
    def specialized(patient_id):
        return _json(history_service.get_specialized_records(request.current_user, patient_id, inst()))

    @app.route("/api/catalogs", methods=["GET"])
    @require_auth
    def catalogs():
        return _json(history_service.get_catalogs(request.current_user, inst()))

    # Citas y consultas --------------------------------------------------
    @app.route("/api/appointments", methods=["GET"])
    @require_auth
    def list_appointments():
        pid = request.args.get("id_paciente", type=int)
        return _json(consultation_service.list_appointments(request.current_user, pid, inst()))

    @app.route("/api/appointments", methods=["POST"])
    @require_auth
    def schedule_appointment():
        data = request.get_json(silent=True) or {}
        return _json(consultation_service.schedule_appointment(request.current_user, data, inst()), 201)

    @app.route("/api/consultations", methods=["POST"])
    @require_auth
    def register_consultation():
        data = request.get_json(silent=True) or {}
        return _json(consultation_service.register_consultation_transaction(request.current_user, data, inst()), 201)

    # Personal médico (lo gestiona el administrador) ------------------------
    @app.route("/api/professionals", methods=["GET"])
    @require_auth
    def list_professionals():
        return _json(professional_service.listar(request.current_user))

    @app.route("/api/professionals", methods=["POST"])
    @require_auth
    def create_professional():
        return _json(professional_service.registrar(request.current_user, request.get_json(silent=True) or {}), 201)

    @app.route("/api/professionals/<int:professional_id>", methods=["PUT"])
    @require_auth
    def update_professional(professional_id):
        data = request.get_json(silent=True) or {}
        return _json(professional_service.actualizar(request.current_user, professional_id, data))

    # Hospital: quirófanos, cirugías, enfermería y altas -------------------
    def body():
        return request.get_json(silent=True) or {}

    @app.route("/api/hospital/rooms", methods=["GET"])
    @require_auth
    def hosp_rooms():
        return _json(hospital_service.quirofanos(request.current_user))

    @app.route("/api/hospital/surgeries", methods=["GET"])
    @require_auth
    def hosp_surgeries():
        a = request.args
        return _json(hospital_service.cirugias(request.current_user, a.get("fecha") or None,
                                               a.get("id_paciente", type=int), a.get("pendientes") == "1"))

    @app.route("/api/hospital/surgeries", methods=["POST"])
    @require_auth
    def hosp_schedule():
        return _json(hospital_service.programar_cirugia(request.current_user, body()), 201)

    @app.route("/api/hospital/surgeries/<int:sid>/<accion>", methods=["POST"])
    @require_auth
    def hosp_surgery_action(sid, accion):
        u = request.current_user
        if accion == "start":
            return _json(hospital_service.iniciar_cirugia(u, sid))
        if accion == "finish":
            return _json(hospital_service.finalizar_cirugia(u, sid, body().get("notas")))
        if accion == "cancel":
            return _json(hospital_service.cancelar_cirugia(u, sid, body().get("motivo", "")))
        return jsonify({"error": "Acción desconocida"}), 404

    @app.route("/api/hospital/nurses", methods=["GET"])
    @require_auth
    def hosp_nurses():
        return _json(hospital_service.enfermeros(request.current_user))

    @app.route("/api/hospital/nurses", methods=["POST"])
    @require_auth
    def hosp_nurse_create():
        return _json(hospital_service.registrar_enfermero(request.current_user, body()), 201)

    @app.route("/api/hospital/nurses/<int:nid>", methods=["PUT"])
    @require_auth
    def hosp_nurse_update(nid):
        return _json(hospital_service.actualizar_enfermero(request.current_user, nid, body()))

    @app.route("/api/hospital/shifts", methods=["GET"])
    @require_auth
    def hosp_shifts():
        a = request.args
        return _json(hospital_service.turnos(request.current_user, a.get("fecha") or None, a.get("id_paciente", type=int)))

    @app.route("/api/hospital/shifts", methods=["POST"])
    @require_auth
    def hosp_shift_assign():
        return _json(hospital_service.asignar_turno(request.current_user, body()), 201)

    @app.route("/api/hospital/shifts/<int:aid>/annul", methods=["POST"])
    @require_auth
    def hosp_shift_annul(aid):
        return _json(hospital_service.anular_turno(request.current_user, aid))

    @app.route("/api/hospital/hospitalizations", methods=["GET"])
    @require_auth
    def hosp_hospitalizations():
        return _json(hospital_service.hospitalizados(request.current_user, request.args.get("todos") == "1"))

    @app.route("/api/hospital/hospitalizations/<int:hid>/discharge", methods=["POST"])
    @require_auth
    def hosp_discharge(hid):
        return _json(hospital_service.dar_alta(request.current_user, hid, body().get("tipo", "alta")))

    @app.route("/api/hospital/hospitalizations/<int:hid>/room", methods=["POST"])
    @require_auth
    def hosp_change_room(hid):
        return _json(hospital_service.cambiar_habitacion(request.current_user, hid, body().get("numero_habitacion")))

    @app.route("/api/hospital/departments", methods=["GET"])
    @require_auth
    def hosp_departments():
        return _json(hospital_service.departamentos(request.current_user))

    @app.route("/api/hospital/departments", methods=["POST"])
    @require_auth
    def hosp_create_department():
        return _json(hospital_service.crear_departamento(request.current_user, body()), 201)

    @app.route("/api/hospital/beds", methods=["POST"])
    @require_auth
    def hosp_create_room():
        return _json(hospital_service.crear_habitacion(request.current_user, body()), 201)

    @app.route("/api/hospital/beds/<codigo>", methods=["PUT"])
    @require_auth
    def hosp_update_room(codigo):
        return _json(hospital_service.editar_habitacion(request.current_user, codigo.upper(), body()))

    # Medicación del internamiento ----------------------------------------
    @app.route("/api/hospital/medicines", methods=["GET"])
    @require_auth
    def hosp_medicines():
        return _json(hospital_service.medicamentos(request.current_user))

    @app.route("/api/hospital/hospitalizations/<int:hid>/medication", methods=["GET"])
    @require_auth
    def hosp_orders(hid):
        return _json(hospital_service.ordenes_medicacion(request.current_user, hid))

    @app.route("/api/hospital/medication", methods=["POST"])
    @require_auth
    def hosp_create_order():
        return _json(hospital_service.indicar_medicacion(request.current_user, body()), 201)

    @app.route("/api/hospital/medication/<int:oid>/suspend", methods=["POST"])
    @require_auth
    def hosp_suspend_order(oid):
        return _json(hospital_service.suspender_medicacion(request.current_user, oid, body().get("motivo", "")))

    @app.route("/api/hospital/doses", methods=["GET"])
    @require_auth
    def hosp_doses():
        a = request.args
        return _json(hospital_service.dosis(request.current_user, a.get("id_hospitalizacion", type=int),
                                            a.get("fecha") or None, a.get("turno") or None))

    @app.route("/api/hospital/doses/<int:did>/<accion>", methods=["POST"])
    @require_auth
    def hosp_dose_action(did, accion):
        u, b = request.current_user, body()
        if accion == "apply":
            return _json(hospital_service.aplicar_dosis(u, did, b.get("id_enfermero"), b.get("observaciones")))
        if accion == "omit":
            return _json(hospital_service.omitir_dosis(u, did, b.get("id_enfermero"), b.get("motivo", "")))
        return _json({"error": "Acción inválida"}, 404)

    # --------------------------------------------------------------------
    # Centro Médico Pediátrico: tutores, perinatal, somatometría, vacunas, hitos, alergias
    # --------------------------------------------------------------------
    @app.route("/api/pediatric/patients/<int:pid>/details", methods=["GET"])
    @require_auth
    def ped_patient_details(pid):
        return _json(pediatric_service.detalles(request.current_user, pid))

    @app.route("/api/pediatric/patients/<int:pid>/perinatal", methods=["PUT"])
    @require_auth
    def ped_update_perinatal(pid):
        return _json(pediatric_service.actualizar_perinatal(request.current_user, pid, body()))

    @app.route("/api/pediatric/patients/<int:pid>/guardian", methods=["PUT"])
    @require_auth
    def ped_update_guardian(pid):
        return _json(pediatric_service.actualizar_tutor(request.current_user, pid, body()))

    @app.route("/api/pediatric/patients/<int:pid>/somatometry", methods=["POST"])
    @require_auth
    def ped_add_somatometry(pid):
        return _json(pediatric_service.registrar_somatometria(request.current_user, pid, body()), 201)

    @app.route("/api/pediatric/somatometry", methods=["GET"])
    @require_auth
    def ped_list_all_somatometry():
        pid = request.args.get("patient_id", type=int)
        return _json(pediatric_service.somatometria(request.current_user, pid))

    @app.route("/api/pediatric/vaccines", methods=["GET"])
    @require_auth
    def ped_vaccines_catalog():
        return _json(pediatric_service.vacunas_catalogo(request.current_user))

    @app.route("/api/pediatric/vaccine-batches", methods=["GET"])
    @require_auth
    def ped_vaccine_batches():
        return _json(pediatric_service.lotes_vacunas(request.current_user))

    @app.route("/api/pediatric/vaccine-batches", methods=["POST"])
    @require_auth
    def ped_create_vaccine_batch():
        return _json(pediatric_service.crear_lote_vacuna(request.current_user, body()), 201)

    @app.route("/api/pediatric/patients/<int:pid>/vaccinations", methods=["POST"])
    @require_auth
    def ped_add_vaccination(pid):
        return _json(pediatric_service.aplicar_vacuna(request.current_user, pid, body()), 201)

    @app.route("/api/pediatric/vaccinations", methods=["GET"])
    @require_auth
    def ped_list_all_vaccinations():
        pid = request.args.get("patient_id", type=int)
        return _json(pediatric_service.vacunaciones(request.current_user, pid))

    @app.route("/api/pediatric/patients/<int:pid>/milestones", methods=["GET"])
    @require_auth
    def ped_list_milestones(pid):
        return _json(pediatric_service.hitos_desarrollo(request.current_user, pid))

    @app.route("/api/pediatric/milestones", methods=["GET"])
    @require_auth
    def ped_list_all_milestones():
        pid = request.args.get("patient_id", type=int)
        return _json(pediatric_service.hitos_desarrollo(request.current_user, pid))

    @app.route("/api/pediatric/patients/<int:pid>/milestones", methods=["POST"])
    @require_auth
    def ped_add_milestone(pid):
        return _json(pediatric_service.evaluar_hito(request.current_user, pid, body()), 201)

    @app.route("/api/pediatric/patients/<int:pid>/allergies", methods=["GET"])
    @require_auth
    def ped_list_allergies(pid):
        return _json(pediatric_service.alergias(request.current_user, pid))

    @app.route("/api/pediatric/allergies", methods=["GET"])
    @require_auth
    def ped_list_all_allergies():
        pid = request.args.get("patient_id", type=int)
        return _json(pediatric_service.alergias(request.current_user, pid))

    @app.route("/api/pediatric/patients/<int:pid>/allergies", methods=["POST"])
    @require_auth
    def ped_add_allergy(pid):
        return _json(pediatric_service.registrar_alergia(request.current_user, pid, body()), 201)

    @app.route("/api/pediatric/allergens", methods=["GET"])
    @require_auth
    def ped_allergens_catalog():
        return _json(pediatric_service.alergenos_catalogo(request.current_user))

    @app.route("/api/pediatric/growth-percentiles", methods=["GET"])
    @require_auth
    def ped_growth_percentiles():
        return _json(pediatric_service.percentiles_oms(
            request.current_user, request.args.get("sexo"), request.args.get("parametro")
        ))

    # --------------------------------------------------------------------
    # Clínica Odontológica: anamnesis sistémica, odontograma FDI, planes, cobros, aranceles
    # --------------------------------------------------------------------
    @app.route("/api/dental/patients/<int:pid>/details", methods=["GET"])
    @require_auth
    def dental_patient_details(pid):
        return _json(dental_service.detalles(request.current_user, pid))

    @app.route("/api/dental/patients/<int:pid>/systemic", methods=["PUT"])
    @require_auth
    def dental_update_systemic(pid):
        return _json(dental_service.actualizar_sistemico(request.current_user, pid, body()))

    @app.route("/api/dental/patients/<int:pid>/odontogram", methods=["GET"])
    @require_auth
    def dental_get_odontogram(pid):
        return _json(dental_service.odontograma(request.current_user, pid))

    @app.route("/api/dental/odontogram", methods=["GET"])
    @require_auth
    def dental_get_all_odontogram():
        pid = request.args.get("id_paciente", type=int) or request.args.get("patient_id", type=int)
        return _json(dental_service.odontograma(request.current_user, pid))

    @app.route("/api/dental/patients/<int:pid>/odontogram/findings", methods=["POST"])
    @require_auth
    def dental_save_finding(pid):
        return _json(dental_service.registrar_hallazgo(request.current_user, pid, body()), 201)

    @app.route("/api/dental/treatment-plans", methods=["GET"])
    @require_auth
    def dental_list_treatment_plans():
        return _json(dental_service.planes(request.current_user, request.args.get("id_paciente", type=int)))

    @app.route("/api/dental/treatment-plans", methods=["POST"])
    @require_auth
    def dental_create_treatment_plan():
        return _json(dental_service.crear_plan(request.current_user, body()), 201)

    @app.route("/api/dental/treatment-plans/<int:plan_id>/stages/<int:stage_id>", methods=["PUT"])
    @require_auth
    def dental_update_plan_stage(plan_id, stage_id):
        return _json(dental_service.actualizar_etapa_plan(
            request.current_user, plan_id, stage_id, body().get("estado", "completada")
        ))

    @app.route("/api/dental/procedures", methods=["GET"])
    @require_auth
    def dental_list_procedures():
        return _json(dental_service.procedimientos(request.current_user))

    @app.route("/api/dental/procedures", methods=["POST"])
    @require_auth
    def dental_create_procedure():
        return _json(dental_service.crear_procedimiento(request.current_user, body()), 201)

    @app.route("/api/dental/billing", methods=["GET"])
    @require_auth
    def dental_billing():
        return _json(dental_service.facturacion(request.current_user, request.args.get("id_paciente", type=int)))

    @app.route("/api/dental/payments", methods=["POST"])
    @require_auth
    def dental_create_payment():
        return _json(dental_service.registrar_pago(request.current_user, body()), 201)

    @app.route("/api/dental/findings-catalog", methods=["GET"])
    @require_auth
    def dental_findings_catalog():
        return _json(dental_service.hallazgos_catalogo(request.current_user))

    @app.route("/api/dental/supplies", methods=["GET"])
    @require_auth
    def dental_supplies():
        return _json(dental_service.insumos(request.current_user))

    # Estado de los motores ----------------------------------------------
    # ---------------------------------------------------------------- Laboratorio
    @app.route("/api/lab/orders", methods=["GET"])
    @require_auth
    def lab_orders():
        return _json(lab_service.ordenes(request.current_user, request.args.get("estado") or None,
                                         request.args.get("id_paciente", type=int)))

    @app.route("/api/lab/orders", methods=["POST"])
    @require_auth
    def lab_create_order():
        return _json(lab_service.crear(request.current_user, body()), 201)

    @app.route("/api/lab/orders/<int:oid>", methods=["GET"])
    @require_auth
    def lab_order(oid):
        return _json(lab_service.orden(request.current_user, oid))

    @app.route("/api/lab/orders/<int:oid>/<accion>", methods=["POST"])
    @require_auth
    def lab_order_action(oid, accion):
        u, b = request.current_user, body()
        acciones = {
            "schedule": lambda: lab_service.agendar(u, oid, b),
            "sample": lambda: lab_service.muestra(u, oid, b),
            "results": lambda: lab_service.resultados(u, oid, b),
            "validate": lambda: lab_service.validar(u, oid, b),
            "deliver": lambda: lab_service.entregar(u, oid, b),
            "cancel": lambda: lab_service.cancelar(u, oid, b.get("motivo", "")),
        }
        if accion not in acciones:
            return _json({"error": "Acción inválida"}, 404)
        return _json(acciones[accion]())

    @app.route("/api/lab/agenda", methods=["GET"])
    @require_auth
    def lab_agenda():
        return _json(lab_service.agenda(request.current_user, request.args.get("desde") or None))

    @app.route("/api/engine/status", methods=["GET"])
    def engine_status():
        return jsonify({"modo": config.ENGINE_MODE, "motores": engine_router.health_check_all()})

    return app
