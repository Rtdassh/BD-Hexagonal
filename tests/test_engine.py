"""
Comprehensive Unit and Integration Test Suite.
Validates the 4 Database Adapters, the Hexagonal EngineRouter,
the Application Use Cases, and the REST API.
"""

import unittest
import dataclasses
import json
import os
import sys

# Agregar raíz al path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.infrastructure.config import Config
from src.infrastructure.adapters.auth_adapter import AuthAdapter
from src.application.router import EngineRouter
from src.application.services import PatientService, ClinicalHistoryService, ConsultationService, AuthService
from src.domain.entities import InstitutionType, DatabaseEngine, UserRole
from src.interfaces.api import create_app


class TestHexagonalEngine(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.ENGINE_MODE = "simulated"
        self.auth_adapter = AuthAdapter()
        self.router = EngineRouter(self.config)
        self.patient_service = PatientService(self.router)
        self.history_service = ClinicalHistoryService(self.router)
        self.consultation_service = ConsultationService(self.router)
        self.auth_service = AuthService(self.auth_adapter)

    # ------------------------------------------------------------------------
    # 1. PRUEBAS DE ENRUTAMIENTO DINÁMICO POR USUARIO
    # ------------------------------------------------------------------------
    def test_dynamic_user_routing(self):
        """Verifica que cada usuario se enruta a su motor específico sin alterar lógica."""
        user_hosp = self.auth_service.login("admin_hospital", "123")
        self.assertIsNotNone(user_hosp)
        adapter_hosp = self.router.get_adapter_for_user(user_hosp)
        self.assertEqual(adapter_hosp.database_engine, DatabaseEngine.POSTGRESQL)

        user_ped = self.auth_service.login("admin_pediatria", "123")
        adapter_ped = self.router.get_adapter_for_user(user_ped)
        self.assertEqual(adapter_ped.database_engine, DatabaseEngine.MYSQL)

        user_lab = self.auth_service.login("admin_laboratorio", "123")
        adapter_lab = self.router.get_adapter_for_user(user_lab)
        self.assertEqual(adapter_lab.database_engine, DatabaseEngine.MONGODB)

        user_dent = self.auth_service.login("admin_odontologia", "123")
        adapter_dent = self.router.get_adapter_for_user(user_dent)
        self.assertEqual(adapter_dent.database_engine, DatabaseEngine.FIREBASE)

    # ------------------------------------------------------------------------
    # 2. PRUEBAS DEL MOTOR POSTGRESQL (Hospital General)
    # ------------------------------------------------------------------------
    def test_postgresql_hospital_general(self):
        """Verifica la integridad transaccional ACID y hospitalizaciones en PostgreSQL."""
        user = self.auth_service.login("admin_hospital", "123")

        # 1. Registrar paciente nuevo
        p_data = {
            "nombres": "Rosa María",
            "apellidos": "Solórzano",
            "dpi": "9999000010101",
            "fecha_nacimiento": "1990-06-20",
            "sexo": "F",
            "direccion": "Zona 1, Quetzaltenango",
            "telefono": "5555-8888",
            "tipo_sangre": "A+"
        }
        patient = self.patient_service.register_new_patient(user, p_data)
        self.assertEqual(patient.nombres, "Rosa María")
        self.assertEqual(patient.dpi, "9999000010101")

        # 2. Transacción de Consulta + Diagnóstico + Tratamiento + Hospitalización
        cons_data = {
            "id_paciente": patient.id_paciente,
            "motivo": "Apendicitis Aguda",
            "presion_arterial": "120/80",
            "temperatura": 38.5,
            "pulso": 90,
            "codigo_cie10": "K35.8",
            "descripcion_diagnostico": "Apendicitis aguda supurada",
            "descripcion_tratamiento": "Apendicectomía de urgencia",
            "medicamento": "Metronidazol 500mg IV",
            "requiere_hospitalizacion": True,
            "numero_habitacion": "HAB-105",
            "motivo_hospitalizacion": "Post-operatorio de apendicectomía"
        }
        cons = self.consultation_service.register_consultation_transaction(user, {**cons_data, "id_profesional": 1})
        self.assertIsNotNone(cons.id_consulta)
        self.assertIsNotNone(cons.hospitalizacion)
        self.assertEqual(cons.hospitalizacion.numero_habitacion, "HAB-105")

        # 3. Consultar historial unificado
        hist = self.history_service.get_unified_history(user, patient.id_paciente)
        self.assertEqual(hist.motor, DatabaseEngine.POSTGRESQL)
        self.assertTrue(len(hist.consultas) >= 1)

    # ------------------------------------------------------------------------
    # 3. PRUEBAS DEL MOTOR MYSQL (Centro Médico Pediátrico)
    # ------------------------------------------------------------------------
    def test_mysql_centro_pediatrico(self):
        """Verifica somatometría, percentiles OMS y vacunas en MySQL."""
        user = self.auth_service.login("admin_pediatria", "123")

        p_data = {
            "nombres": "Lucas Gabriel",
            "apellidos": "Álvarez",
            "dpi": "8888000020101",
            "cui_nacimiento": "8888000020101",
            "fecha_nacimiento": "2024-08-10",
            "sexo": "M",
            "nombre_tutor": "Valeria de Álvarez",
            "parentesco_tutor": "Madre",
            "dpi_tutor": "2222333340101",
            "telefono_tutor": "4444-1111",
            "semanas_gestacion": 40,
            "peso_nacer_kg": 3.4,
            "talla_nacer_cm": 50.0
        }
        patient = self.patient_service.register_new_patient(user, p_data)
        self.assertEqual(patient.nombres, "Lucas Gabriel")

        cons_data = {
            "id_paciente": patient.id_paciente,
            "motivo": "Control de niño sano de 6 meses",
            "peso_kg": 7.80,
            "talla_cm": 67.5,
            "perimetro_cefalico_cm": 43.5,
            "percentil_crecimiento": 65.0,
            "codigo_cie10": "Z00.1",
            "descripcion_diagnostico": "Lactante sano con crecimiento normal",
            "nombre_vacuna": "Pentavalente (3ra dosis)",
            "dosis_vacuna": "3ra dosis",
            "lote_vacuna": "PENT-2026-03",
            "medicamento": "Paracetamol Gotas",
            "dosis_mg_kg": 15.0
        }
        cons = self.consultation_service.register_consultation_transaction(user, {**cons_data, "id_profesional": 1})
        self.assertIsNotNone(cons.somatometria)
        self.assertEqual(cons.somatometria.peso_kg, 7.80)
        self.assertEqual(cons.somatometria.percentil_crecimiento, 65.0)
        self.assertEqual(len(cons.vacunaciones), 1)

    # ------------------------------------------------------------------------
    # 4. PRUEBAS DEL MOTOR MONGODB (Laboratorio Clínico)
    # ------------------------------------------------------------------------
    def test_mongodb_laboratorio_clinico(self):
        """Verifica esquema dinámico polimórfico y detección de alertas críticas en MongoDB."""
        user = self.auth_service.login("admin_laboratorio", "123")

        p_data = {
            "nombres": "César Augusto",
            "apellidos": "Navarro",
            "dpi": "7777000030101",
            "fecha_nacimiento": "1975-03-12",
            "sexo": "M",
            "telefono": "4900-1122"
        }
        patient = self.patient_service.register_new_patient(user, p_data)

        # Registrar examen con valor crítico (> 200 mg/dL)
        lab_data = {
            "id_paciente": patient.id_paciente,
            "motivo": "Perfil Metabólico de Urgencia",
            "codigo_examen": "QUI-01",
            "nombre_parametro": "Glucosa Sérica Basal",
            "valor_analitico": 310.0,
            "unidad_medida": "mg/dL"
        }
        cons = self.consultation_service.register_consultation_transaction(user, {**lab_data, "id_profesional": 1})
        self.assertEqual(len(cons.examenes_laboratorio), 1)
        exam = cons.examenes_laboratorio[0]
        self.assertTrue(exam.alertas_criticas)
        self.assertEqual(exam.parametros[0].interpretacion_alerta, "CRITICO_ALTO")

    # ------------------------------------------------------------------------
    # 5. PRUEBAS DEL MOTOR FIREBASE (Clínica Odontológica)
    # ------------------------------------------------------------------------
    def test_firebase_clinica_odontologica(self):
        """Verifica procedimientos por pieza dental y el filtro de información restringida."""
        dent_user = self.auth_service.login("admin_odontologia", "123")
        # El rol secretaria ya no tiene cuenta de demostración, pero el filtro sigue en el código.
        sec_user = dataclasses.replace(dent_user, rol=UserRole.SECRETARIA)

        p_data = {
            "nombres": "Elena Beatriz",
            "apellidos": "Cifuentes",
            "dpi": "6666000040101",
            "fecha_nacimiento": "2001-10-05",
            "sexo": "F",
            "telefono": "5511-9988"
        }
        # Secretaria puede registrar paciente
        patient = self.patient_service.register_new_patient(sec_user, p_data)
        self.assertEqual(patient.nombres, "Elena Beatriz")

        # Odontólogo registra procedimiento dental en pieza específica
        proc_data = {
            "id_paciente": patient.id_paciente,
            "motivo": "Restauración dental estética",
            "nombre_procedimiento": "Restauración con Resina Fotocurable (Calza)",
            "pieza_dental": "Pieza 16 (Primer molar superior derecho)",
            "costo": 350.0,
            "notas_clinicas": "Grabado total y resina compuesta A1"
        }
        cons = self.consultation_service.register_consultation_transaction(dent_user, {**proc_data, "id_profesional": 1})
        self.assertEqual(len(cons.procedimientos_dentales), 1)
        self.assertEqual(cons.procedimientos_dentales[0].pieza_dental, "Pieza 16 (Primer molar superior derecho)")

        # Enmascaramiento de seguridad para secretaria (RBAC)
        hist_sec = self.history_service.get_unified_history(sec_user, patient.id_paciente)
        # Notas clínicas deben estar enmascaradas
        self.assertIn("Restringido", hist_sec.consultas[0].notas_clinicas)

        # Odontólogo ve todo el detalle
        hist_dent = self.history_service.get_unified_history(dent_user, patient.id_paciente)
        self.assertNotIn("[INFORMACIÓN RESTRINGIDA", hist_dent.consultas[0].notas_clinicas)

    # ------------------------------------------------------------------------
    # 6. PRUEBA DE DESACTIVACIÓN / ARCHIVO
    # ------------------------------------------------------------------------
    def test_deactivate_patient(self):
        """Verifica el archivo o baja administrativa de un expediente."""
        user = self.auth_service.login("admin_hospital", "123")
        res = self.patient_service.archive_patient_record(user, 1, "Traslado a Hospital Regional de Coatepeque")
        self.assertEqual(res["estado"], "archivado")
        self.assertEqual(res["motivo_baja"], "Traslado a Hospital Regional de Coatepeque")

    # ------------------------------------------------------------------------
    # 7. PRUEBA DE LA API REST (CLIENTE FLASK)
    # ------------------------------------------------------------------------
    def test_rest_api_endpoints(self):
        """Prueba los endpoints HTTP de la API REST."""
        app = create_app(self.config)
        client = app.test_client()

        # 1. Health check de los 4 motores
        res_health = client.get("/api/engine/status")
        self.assertEqual(res_health.status_code, 200)
        data_health = json.loads(res_health.data)
        self.assertEqual(len(data_health["motores"]), 4)

        # 2. Login
        res_login = client.post("/api/auth/login", json={"username": "admin_hospital", "password": "123"})
        self.assertEqual(res_login.status_code, 200)
        token = json.loads(res_login.data)["token"]

        # 3. Listar pacientes
        res_patients = client.get("/api/patients", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_patients.status_code, 200)
        patients = json.loads(res_patients.data)
        self.assertTrue(len(patients) >= 1)

        # 4. Historial clínico
        pid = patients[0]["id_paciente"]
        res_hist = client.get(f"/api/patients/{pid}/history", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_hist.status_code, 200)
        hist = json.loads(res_hist.data)
        self.assertEqual(hist["motor"], "PostgreSQL")

        # 5. Sin token -> 401 (ya no hay usuario por defecto)
        self.assertEqual(client.get("/api/patients").status_code, 401)

        auth = {"Authorization": f"Bearer {token}"}

        # 6. Consulta sin profesional asignado -> 400
        res = client.post("/api/consultations", json={"id_paciente": 1, "motivo": "x"}, headers=auth)
        self.assertEqual(res.status_code, 400)

        # 6b. El administrador registra un médico, lo desactiva y ya no se le pueden asignar citas
        res = client.post("/api/professionals", json={"nombre_completo": "Dra. Prueba", "numero_colegiado": "T-1"}, headers=auth)
        self.assertEqual(res.status_code, 201)
        prof = json.loads(res.data)
        res = client.put(f"/api/professionals/{prof['id_profesional']}", json={"estado": "inactivo"}, headers=auth)
        self.assertEqual(json.loads(res.data)["estado"], "inactivo")
        res = client.post("/api/appointments", json={"id_paciente": 1, "fecha_hora_programada": "2030-01-01 08:00",
                          "motivo_consulta": "x", "id_profesional": prof["id_profesional"]}, headers=auth)
        self.assertEqual(res.status_code, 400)

        # 7. Recetar sin diagnóstico -> 400 (regla común a los 4 motores)
        res = client.post("/api/consultations", json={"id_paciente": 1, "motivo": "x",
                          "id_profesional": 1, "recetas": [{"medicamento": "Ibuprofeno"}]}, headers=auth)
        self.assertEqual(res.status_code, 400)

        # 8. Cada administrador solo ve su institución, aunque pida otra
        res = client.get("/api/patients?institucion=laboratorio", headers={"Authorization": f"Bearer {token}"})
        self.assertNotIn("Estuardo", res.get_data(as_text=True))

    # ------------------------------------------------------------------------
    # 8. PRUEBAS DE INTEGRACIÓN DE MODELOS RELACIONALES EXPANDIDOS (+20 TABLAS)
    # ------------------------------------------------------------------------
    def test_expanded_relational_models_integration(self):
        """Verifica que los modelos expandidos del Centro Pediátrico (+20 tablas)
        y la Clínica Odontológica cuenten con todas las tablas 3FN requeridas."""
        # 1. PEDIÁTRICO: Verificar que el motor contiene >= 20 tablas normalizadas
        user_ped = self.auth_service.login("admin_pediatria", "123")
        adapter_ped = self.router.get_adapter_for_user(user_ped)
        mysql_engine = getattr(adapter_ped, "simulated", getattr(adapter_ped, "engine", None))

        tablas_pediatrico = list(mysql_engine.tables.keys())
        self.assertGreaterEqual(len(tablas_pediatrico), 20, f"Debe tener al menos 20 tablas, tiene {len(tablas_pediatrico)}")
        self.assertIn("tutor_legal", tablas_pediatrico)
        self.assertIn("tutor_paciente", tablas_pediatrico)
        self.assertIn("antecedente_perinatal", tablas_pediatrico)
        self.assertIn("antropometria_somatometria", tablas_pediatrico)
        self.assertIn("normativa_percentil_oms", tablas_pediatrico)
        self.assertIn("evaluacion_desarrollo", tablas_pediatrico)
        self.assertIn("catalogo_cie10_pediatrico", tablas_pediatrico)
        self.assertIn("diagnostico_consulta", tablas_pediatrico)
        self.assertIn("vacuna_catalogo", tablas_pediatrico)
        self.assertIn("lote_vacuna", tablas_pediatrico)
        self.assertIn("detalle_receta_pediatrica", tablas_pediatrico)

        # 2. Registrar paciente y verificar sincronización 3FN en tablas hijas
        p_data = {
            "nombres": "Camila",
            "apellidos": "Santizo",
            "dpi": "7777111120101",
            "cui_nacimiento": "7777111120101",
            "fecha_nacimiento": "2024-05-10",
            "sexo": "F",
            "direccion": "Zona 1, Quetzaltenango",
            "nombre_tutor": "Patricia Santizo",
            "parentesco_tutor": "Madre",
            "dpi_tutor": "1111222230101",
            "telefono_tutor": "5555-4433",
            "semanas_gestacion": 38,
            "peso_nacer_kg": 3.10,
            "talla_nacer_cm": 48.0
        }
        paciente = self.patient_service.register_new_patient(user_ped, p_data)
        self.assertIsNotNone(paciente)

        # Verificar que el tutor y antecedente perinatal se insertaron en 3FN
        tutores = [t for t in mysql_engine.tables["tutor_legal"] if t["dpi"] == "1111222230101"]
        self.assertEqual(len(tutores), 1)
        self.assertEqual(tutores[0]["nombres"], "Patricia Santizo")

        perinatales = [a for a in mysql_engine.tables["antecedente_perinatal"] if a["id_paciente"] == paciente.id_paciente]
        self.assertEqual(len(perinatales), 1)
        self.assertEqual(perinatales[0]["semanas_gestacion"], 38)
        self.assertEqual(perinatales[0]["peso_nacer_kg"], 3.10)

        # 3. Registrar consulta y verificar antropometría somatométrica
        cons_data = {
            "id_paciente": paciente.id_paciente,
            "id_profesional": 1,
            "motivo": "Control de los 9 meses",
            "peso_kg": 8.5,
            "talla_cm": 70.0,
            "perimetro_cefalico_cm": 44.0,
            "percentil_crecimiento": 55.0,
            "codigo_cie10": "Z00.1",
            "descripcion_diagnostico": "Crecimiento adecuado",
            "medicamento": "Vitamina C Gotas",
            "dosis_mg_kg": 5.0
        }
        cons = self.consultation_service.register_consultation_transaction(user_ped, cons_data)
        somato = [s for s in mysql_engine.tables["antropometria_somatometria"] if s["id_consulta"] == cons.id_consulta]
        self.assertEqual(len(somato), 1)
        self.assertEqual(somato[0]["peso_kg"], 8.5)

        # 4. ODONTOLOGÍA: Verificar colecciones y catálogo anatómico FDI
        user_dent = self.auth_service.login("admin_odontologia", "123")
        adapter_dent = self.router.get_adapter_for_user(user_dent)
        fb_engine = getattr(adapter_dent, "simulated", getattr(adapter_dent, "engine", None))

        colls = list(fb_engine.collections.keys())
        self.assertIn("piezas_dentales", colls)
        self.assertIn("odontogramas", colls)
        self.assertIn("planes_tratamiento", colls)
        self.assertIn("insumos_dentales", colls)
        self.assertTrue(len(fb_engine.collections["piezas_dentales"]) >= 4)

    # ------------------------------------------------------------------------
    # 7. PRUEBAS INTEGRALES DE SERVICIOS Y ENDPOINTS: CENTRO PEDIÁTRICO
    # ------------------------------------------------------------------------
    def test_pediatric_services_and_api(self):
        """Valida casos de uso y endpoints especializados del Centro Médico Pediátrico."""
        app = create_app(self.config, self.router)
        client = app.test_client()

        # Login con administrador del Centro Pediátrico
        login_resp = client.post("/api/auth/login", json={"username": "admin_pediatria", "password": "123"})
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Obtener detalles pediátricos
        det_resp = client.get("/api/pediatric/patients/1/details", headers=headers)
        self.assertEqual(det_resp.status_code, 200)
        det_data = det_resp.get_json()
        self.assertIn("antecedente_perinatal", det_data)
        self.assertIn("tutores", det_data)
        self.assertIn("somatometria", det_data)
        self.assertIn("vacunaciones", det_data)

        # 2. Actualizar antecedentes perinatales
        peri_resp = client.put("/api/pediatric/patients/1/perinatal", headers=headers, json={
            "semanas_gestacion": 39,
            "peso_nacer_kg": 3.45,
            "talla_nacer_cm": 50.5,
            "tipo_parto": "Eutócico vaginal",
            "apgar_1min": 9,
            "apgar_5min": 10,
            "complicaciones_neonatales": "Sin complicaciones clínicas"
        })
        self.assertEqual(peri_resp.status_code, 200)
        self.assertEqual(peri_resp.get_json()["semanas_gestacion"], 39)

        # 3. Registrar somatometría
        som_resp = client.post("/api/pediatric/patients/1/somatometry", headers=headers, json={
            "peso_kg": 11.2,
            "talla_cm": 82.0,
            "perimetro_cefalico_cm": 46.5,
            "edad_meses_atencion": 18,
            "observaciones": "Percentil ponderal óptimo"
        })
        self.assertEqual(som_resp.status_code, 201)
        self.assertEqual(som_resp.get_json()["peso_kg"], 11.2)

        # 4. Catálogo y lotes de vacunas
        vac_cat_resp = client.get("/api/pediatric/vaccines", headers=headers)
        self.assertEqual(vac_cat_resp.status_code, 200)
        self.assertTrue(len(vac_cat_resp.get_json()) > 0)

        # Login admin para crear lote
        adm_resp = client.post("/api/auth/login", json={"username": "admin_pediatria", "password": "123"})
        adm_headers = {"Authorization": f"Bearer {adm_resp.get_json()['token']}"}
        lote_resp = client.post("/api/pediatric/vaccine-batches", headers=adm_headers, json={
            "id_vacuna": 1,
            "numero_lote": "TEST-LOT-99",
            "fecha_vencimiento": "2027-12-31",
            "dosis_disponibles": 100,
            "temp_min_celsius": 2.5,
            "temp_max_celsius": 6.5,
            "fabricante": "GlaxoSmithKline"
        })
        self.assertEqual(lote_resp.status_code, 201)
        self.assertEqual(lote_resp.get_json()["numero_lote"], "TEST-LOT-99")

        # 5. Aplicar vacuna
        ap_resp = client.post("/api/pediatric/patients/1/vaccinations", headers=headers, json={
            "id_lote": lote_resp.get_json()["id_lote"],
            "numero_dosis": 1,
            "dosis": "1.ª dosis",
            "via_administracion": "Intramuscular",
            "profesional_aplico": "Dra. Sofía Reyes"
        })
        self.assertEqual(ap_resp.status_code, 201)

        # 6. Evaluar hito psicomotor
        hito_resp = client.post("/api/pediatric/patients/1/milestones", headers=headers, json={
            "area_desarrollo": "lenguaje",
            "hito_evaluado": "Dice palabras con intención comunicativa",
            "cumple_hito": True,
            "observaciones": "Vocabulario de 10 palabras"
        })
        self.assertEqual(hito_resp.status_code, 201)

        # 7. Registrar alergia pediátrica
        alerg_resp = client.post("/api/pediatric/patients/1/allergies", headers=headers, json={
            "id_alergeno": 2,
            "severidad": "grave",
            "sintomas_observados": "Urticaria aguda y estridor",
            "fecha_deteccion": "2026-02-15"
        })
        self.assertEqual(alerg_resp.status_code, 201)

    # ------------------------------------------------------------------------
    # 8. PRUEBAS INTEGRALES DE SERVICIOS Y ENDPOINTS: CLÍNICA ODONTOLÓGICA
    # ------------------------------------------------------------------------
    def test_dental_services_and_api(self):
        """Valida casos de uso y endpoints especializados de la Clínica Odontológica."""
        app = create_app(self.config, self.router)
        client = app.test_client()

        # Login con administrador odontológico
        login_resp = client.post("/api/auth/login", json={"username": "admin_odontologia", "password": "123"})
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Obtener detalles odontológicos
        det_resp = client.get("/api/dental/patients/1/details", headers=headers)
        self.assertEqual(det_resp.status_code, 200)
        det_data = det_resp.get_json()
        self.assertIn("antecedentes_sistemicos", det_data)
        self.assertIn("odontograma", det_data)
        self.assertIn("planes_tratamiento", det_data)
        self.assertIn("facturacion", det_data)

        # 2. Actualizar anamnesis sistémica médica
        sist_resp = client.put("/api/dental/patients/1/systemic", headers=headers, json={
            "hipertension": True,
            "diabetes": False,
            "enfermedad_cardiaca": False,
            "trastornos_hemorragicos": False,
            "alergia_anestesia_local": True,
            "alergia_latex": False,
            "embarazo": False,
            "medicamentos_actuales": "Losartán 50mg cada 24 horas",
            "observaciones_medicas": "Precaución con anestésicos locales tipo amida"
        })
        self.assertEqual(sist_resp.status_code, 200)
        self.assertTrue(sist_resp.get_json()["alergia_anestesia_local"])

        # 3. Registrar hallazgo en odontograma (Pieza 46, Cara Oclusal)
        hall_resp = client.post("/api/dental/patients/1/odontogram/findings", headers=headers, json={
            "codigo_fdi": 46,
            "cara": "O",
            "hallazgo": "Caries de dentina",
            "color_hex": "#B42318",
            "estado": "activo",
            "severidad": "moderada",
            "notas": "Fosa central profunda con desmineralización"
        })
        self.assertEqual(hall_resp.status_code, 201)
        self.assertEqual(hall_resp.get_json()["codigo_fdi"], 46)

        # 4. Formular plan de tratamiento
        plan_resp = client.post("/api/dental/treatment-plans", headers=headers, json={
            "id_paciente": 1,
            "diagnostico_general": "Caries oclusal en primer molar inferior y gingivitis",
            "costo_total_estimado": 850.00,
            "etapas": [
                {
                    "numero_etapa": 1,
                    "nombre_etapa": "Fase Higiénica",
                    "procedimientos_planificados": "Profilaxis y detartraje",
                    "costo_estimado": 250.00,
                    "estado": "pendiente"
                },
                {
                    "numero_etapa": 2,
                    "nombre_etapa": "Fase Restauradora",
                    "procedimientos_planificados": "Restauración con resina compuesta en pieza 46",
                    "costo_estimado": 600.00,
                    "estado": "pendiente"
                }
            ]
        })
        self.assertEqual(plan_resp.status_code, 201)
        plan_id = plan_resp.get_json()["id_plan"]

        # 5. Avanzar etapa de plan
        etapa_resp = client.put(f"/api/dental/treatment-plans/{plan_id}/stages/1", headers=headers, json={
            "estado": "completada"
        })
        self.assertEqual(etapa_resp.status_code, 200)

        # 6. Registrar abono de pago
        pago_resp = client.post("/api/dental/payments", headers=headers, json={
            "id_factura": 1,
            "numero_recibo": "REC-TEST-001",
            "monto": 250.00,
            "metodo_pago": "efectivo",
            "referencia": "PAGO-IN-SITU"
        })
        self.assertEqual(pago_resp.status_code, 201)
        self.assertEqual(pago_resp.get_json()["monto"], 250.00)


if __name__ == "__main__":
    unittest.main()

