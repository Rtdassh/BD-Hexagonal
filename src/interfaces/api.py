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
    PatientService,
    PermisoDenegado,
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

    # Estado de los motores ----------------------------------------------
    @app.route("/api/engine/status", methods=["GET"])
    def engine_status():
        return jsonify({"modo": config.ENGINE_MODE, "motores": engine_router.health_check_all()})

    return app
