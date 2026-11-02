"""
REST API and Static Web Controller.
Provides HTTP endpoints adhering to Clean Code and Hexagonal Architecture.
"""

from functools import wraps
import json
from dataclasses import asdict, is_dataclass
from flask import Flask, request, jsonify, send_from_directory
import os

from ..infrastructure.config import Config
from ..infrastructure.adapters.auth_adapter import AuthAdapter
from ..application.router import EngineRouter
from ..application.services import (
    PatientService,
    ClinicalHistoryService,
    ConsultationService,
    AuthService
)
from ..domain.entities import User, UserRole, InstitutionType


def create_app(config: Config = None):
    if config is None:
        config = Config()

    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config["SECRET_KEY"] = config.SECRET_KEY

    # Inicializar puertos y enrutador hexagonal
    auth_adapter = AuthAdapter()
    engine_router = EngineRouter(config)

    # Inyección de dependencias en casos de uso
    auth_service = AuthService(auth_adapter)
    patient_service = PatientService(engine_router)
    history_service = ClinicalHistoryService(engine_router)
    consultation_service = ConsultationService(engine_router)

    def custom_json_serializer(obj):
        if is_dataclass(obj):
            return asdict(obj)
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "value"):
            return obj.value
        raise TypeError(f"Type {type(obj)} not serializable")

    def require_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get("Authorization")
            if token and token.startswith("Bearer "):
                token = token[7:]
            if not token:
                token = request.args.get("token")

            user = None
            if token:
                user = auth_service.validate_session(token)

            # Fallback a usuario por defecto para facilidad de pruebas
            if not user:
                default_username = request.headers.get("X-Demo-User", "dr_garcia")
                user = auth_service.login(default_username, "123")

            request.current_user = user
            return f(*args, **kwargs)
        return decorated

    # ------------------------------------------------------------------------
    # RUTAS ESTÁTICAS Y DE LA INTERFAZ WEB
    # ------------------------------------------------------------------------
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # ------------------------------------------------------------------------
    # RUTAS DE AUTENTICACIÓN Y SESIÓN
    # ------------------------------------------------------------------------
    @app.route("/api/auth/demo-users", methods=["GET"])
    def get_demo_users():
        return jsonify(auth_service.get_demo_accounts())

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")
        user = auth_service.login(username, password)
        if not user:
            return jsonify({"error": "Credenciales inválidas"}), 401

        return jsonify({
            "token": user.token,
            "username": user.username,
            "nombre_completo": user.nombre_completo,
            "institucion": user.institucion.value,
            "rol": user.rol.value,
            "motor_asignado": user.motor_asignado.value,
            "numero_colegiado": user.numero_colegiado
        })

    @app.route("/api/auth/me", methods=["GET"])
    @require_auth
    def me():
        user: User = request.current_user
        return jsonify({
            "token": user.token,
            "username": user.username,
            "nombre_completo": user.nombre_completo,
            "institucion": user.institucion.value,
            "rol": user.rol.value,
            "motor_asignado": user.motor_asignado.value,
            "numero_colegiado": user.numero_colegiado
        })

    # ------------------------------------------------------------------------
    # RUTAS DE GESTIÓN DE PACIENTES (ENRUTADAS POR INSTITUCIÓN)
    # ------------------------------------------------------------------------
    @app.route("/api/patients", methods=["GET"])
    @require_auth
    def list_patients():
        user: User = request.current_user
        query = request.args.get("q", "")
        override_inst = request.args.get("institucion")
        patients = patient_service.search_patients(user, query, override_inst)
        return json.dumps([asdict(p) for p in patients], default=custom_json_serializer), 200, {"Content-Type": "application/json"}

    @app.route("/api/patients", methods=["POST"])
    @require_auth
    def create_patient():
        user: User = request.current_user
        data = request.get_json(silent=True) or {}
        override_inst = request.args.get("institucion")
        try:
            patient = patient_service.register_new_patient(user, data, override_inst)
            return json.dumps(asdict(patient), default=custom_json_serializer), 201, {"Content-Type": "application/json"}
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Error interno: {str(e)}"}), 500

    @app.route("/api/patients/<int:patient_id>", methods=["GET"])
    @require_auth
    def get_patient(patient_id):
        user: User = request.current_user
        override_inst = request.args.get("institucion")
        patient = patient_service.get_patient_by_id(user, patient_id, override_inst)
        if not patient:
            return jsonify({"error": "Paciente no encontrado"}), 404
        return json.dumps(asdict(patient), default=custom_json_serializer), 200, {"Content-Type": "application/json"}

    @app.route("/api/patients/<int:patient_id>", methods=["PUT"])
    @require_auth
    def update_patient(patient_id):
        user: User = request.current_user
        data = request.get_json(silent=True) or {}
        override_inst = request.args.get("institucion")
        try:
            updated = patient_service.update_patient_info(user, patient_id, data, override_inst)
            return json.dumps(asdict(updated), default=custom_json_serializer), 200, {"Content-Type": "application/json"}
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/patients/<int:patient_id>/deactivate", methods=["POST"])
    @app.route("/api/patients/<int:patient_id>", methods=["DELETE"])
    @require_auth
    def deactivate_patient(patient_id):
        user: User = request.current_user
        data = request.get_json(silent=True) or {}
        motivo = data.get("motivo_baja", "Causa administrativa no especificada")
        override_inst = request.args.get("institucion")
        try:
            result = patient_service.archive_patient_record(user, patient_id, motivo, override_inst)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # ------------------------------------------------------------------------
    # HISTORIAL CLÍNICO UNIFICADO (FILTRADO POR SEGURIDAD Y ROLES)
    # ------------------------------------------------------------------------
    @app.route("/api/patients/<int:patient_id>/history", methods=["GET"])
    @require_auth
    def get_clinical_history(patient_id):
        user: User = request.current_user
        override_inst = request.args.get("institucion")
        history = history_service.get_unified_history(user, patient_id, override_inst)
        if not history:
            return jsonify({"error": "Historial clínico no encontrado para el paciente indicado"}), 404
        return json.dumps(asdict(history), default=custom_json_serializer), 200, {"Content-Type": "application/json"}

    @app.route("/api/patients/<int:patient_id>/specialized", methods=["GET"])
    @require_auth
    def get_specialized(patient_id):
        user: User = request.current_user
        override_inst = request.args.get("institucion")
        data = history_service.get_specialized_records(user, patient_id, override_inst)
        return jsonify(data)

    # ------------------------------------------------------------------------
    # CITAS Y CONSULTAS CLÍNICAS (TRANSACCIONES ATÓMICAS)
    # ------------------------------------------------------------------------
    @app.route("/api/appointments", methods=["GET"])
    @require_auth
    def list_appointments():
        user: User = request.current_user
        pid = request.args.get("id_paciente", type=int)
        override_inst = request.args.get("institucion")
        citas = consultation_service.list_appointments(user, pid, override_inst)
        return json.dumps([asdict(c) for c in citas], default=custom_json_serializer), 200, {"Content-Type": "application/json"}

    @app.route("/api/appointments", methods=["POST"])
    @require_auth
    def schedule_appointment():
        user: User = request.current_user
        data = request.get_json(silent=True) or {}
        override_inst = request.args.get("institucion")
        try:
            cita = consultation_service.schedule_appointment(user, data, override_inst)
            return json.dumps(asdict(cita), default=custom_json_serializer), 201, {"Content-Type": "application/json"}
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/consultations", methods=["POST"])
    @require_auth
    def register_consultation():
        user: User = request.current_user
        data = request.get_json(silent=True) or {}
        override_inst = request.args.get("institucion")
        try:
            consultation = consultation_service.register_consultation_transaction(user, data, override_inst)
            return json.dumps(asdict(consultation), default=custom_json_serializer), 201, {"Content-Type": "application/json"}
        except Exception as e:
            return jsonify({"error": f"Fallo en transacción: {str(e)}"}), 400

    # ------------------------------------------------------------------------
    # AUDITORÍA Y SALUD DE LOS 4 MOTORES DE BASE DE DATOS
    # ------------------------------------------------------------------------
    @app.route("/api/engine/status", methods=["GET"])
    def engine_status():
        status_list = engine_router.health_check_all()
        return jsonify({
            "arquitectura": "Arquitectura Hexagonal (Puertos y Adaptadores)",
            "desacoplamiento": "Lógica de negocio 100% agnóstica de motor",
            "motores": status_list
        })

    return app

