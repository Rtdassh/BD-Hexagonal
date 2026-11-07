"""
Pruebas de integración contra los motores REALES (PostgreSQL y MySQL de docker-compose,
MongoDB y Firestore si están disponibles). Si un motor no responde, su prueba se omite.

    python -m pytest tests -v
"""

import os
import sys
import time
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.domain.entities import UserRole  # noqa: E402
from src.infrastructure.config import Config  # noqa: E402


def _adaptador(nombre):
    config = Config()
    try:
        if nombre == "pg":
            from src.infrastructure.adapters.postgresql_adapter import PostgreSQLAdapter
            return PostgreSQLAdapter(config)
        if nombre == "mysql":
            from src.infrastructure.adapters.mysql_adapter import MySQLAdapter
            return MySQLAdapter(config)
        if nombre == "mongo":
            from src.infrastructure.adapters.mongodb_adapter import MongoDBAdapter
            return MongoDBAdapter(config)
        if nombre == "firestore":
            from src.infrastructure.adapters.firebase_adapter import FirebaseAdapter
            return FirebaseAdapter(config)
    except Exception as e:  # motor apagado
        raise unittest.SkipTest(f"{nombre} no disponible: {e}")


class FlujoComun:
    """El MISMO flujo de negocio se prueba en los cuatro motores."""

    motor = ""
    paciente_extra = {}
    consulta_extra = {}

    def setUp(self):
        self.a = _adaptador(self.motor)
        self.dpi = str(int(time.time() * 1000))[-13:]

    def test_flujo_completo(self):
        a = self.a
        p = a.create_patient({"nombres": "Prueba", "apellidos": "Integración", "fecha_nacimiento": "2020-05-05",
                              "sexo": "F", "dpi": self.dpi, **self.paciente_extra})
        with self.assertRaises(ValueError):  # DPI único
            a.create_patient({"nombres": "Otra", "apellidos": "X", "fecha_nacimiento": "2020-05-05",
                              "sexo": "F", "dpi": self.dpi, **self.paciente_extra})

        cita = a.create_appointment({"id_paciente": p.id_paciente, "fecha_hora_programada": "2030-01-01 08:00",
                                     "motivo_consulta": "Prueba", "id_profesional": 1})
        con = a.register_consultation({"id_paciente": p.id_paciente, "id_cita": cita.id_cita, "motivo": "Prueba",
                                       "codigo_cie10": "Z00.0", "descripcion_diagnostico": "Examen general",
                                       "id_profesional": 1, **self.consulta_extra})
        self.assertEqual(con.diagnosticos[0].codigo_cie10, "Z00.0")

        with self.assertRaises(ValueError):  # la cita ya fue atendida
            a.register_consultation({"id_paciente": p.id_paciente, "id_cita": cita.id_cita, "motivo": "x",
                                     **self.consulta_extra})

        h = a.get_clinical_history(p.id_paciente)
        self.assertEqual(len(h.consultas), 1)
        hs = a.get_clinical_history(p.id_paciente, UserRole.SECRETARIA)
        self.assertIn("Restringido", hs.consultas[0].diagnosticos[0].descripcion)

        # Personal médico: registrar, colegiado único, editar y desactivar
        prof = a.create_professional({"nombre_completo": "Prof. Prueba", "numero_colegiado": f"T-{self.dpi}",
                                      "especialidad": "General"})
        with self.assertRaises(ValueError):
            a.create_professional({"nombre_completo": "Otro", "numero_colegiado": f"T-{self.dpi}"})
        prof = a.update_professional(prof.id_profesional, {"estado": "inactivo", "telefono": "5555-0000"})
        self.assertEqual(prof.estado, "inactivo")
        self.assertIn(prof.id_profesional, [x.id_profesional for x in a.list_professionals()])

        res = a.deactivate_patient(p.id_paciente, "Prueba de baja", "traslado")
        self.assertEqual(res["estado"], "trasladado")
        with self.assertRaises(ValueError):  # historial archivado no admite registros
            a.register_consultation({"id_paciente": p.id_paciente, "motivo": "x", **self.consulta_extra})


class TestPostgreSQL(FlujoComun, unittest.TestCase):
    motor = "pg"
    consulta_extra = {"recetas": [{"medicamento": "Paracetamol", "dosis": "500 mg", "frecuencia": "c/8h",
                                   "duracion_dias": 3}]}


class TestMySQL(FlujoComun, unittest.TestCase):
    motor = "mysql"
    paciente_extra = {"nombre_tutor": "Tutor", "parentesco_tutor": "Madre", "dpi_tutor": "1", "telefono_tutor": "1"}
    consulta_extra = {"peso_kg": 12, "talla_cm": 85,
                      "recetas": [{"medicamento": "Amoxicilina", "dosis_mg_kg": 25, "concentracion_mg_ml": 50,
                                   "frecuencia": "c/8h", "duracion_dias": 7}]}


class TestMongoDB(FlujoComun, unittest.TestCase):
    motor = "mongo"
    consulta_extra = {"codigo_examen": "QUI-01", "parametros": [
        {"nombre_parametro": "Glucosa", "valor_resultado": 90, "rango_referencia_min": 70, "rango_referencia_max": 100}]}


class TestFirestore(FlujoComun, unittest.TestCase):
    motor = "firestore"
    consulta_extra = {"procedimientos": [{"id_procedimiento": 1, "pieza_dental": "11"}]}


def _cama_libre(a, excepto=()):
    for d in a.list_departments():
        for h in d["habitaciones"]:
            if h["estado"] == "disponible" and len(h["ocupantes"]) < h["camas"] and h["codigo"] not in excepto:
                return h["codigo"]
    raise unittest.SkipTest("No hay camas libres")


def _ingresar(a, nombre):
    dpi = str(int(time.time() * 1000000))[-13:]
    p = a.create_patient({"nombres": nombre, "apellidos": "Prueba", "fecha_nacimiento": "1990-01-01",
                          "sexo": "M", "dpi": dpi})
    a.register_consultation({"id_paciente": p.id_paciente, "motivo": "Ingreso de prueba", "id_profesional": 1,
                             "codigo_cie10": "K35.8", "descripcion_diagnostico": "Apendicitis",
                             "requiere_hospitalizacion": True, "numero_habitacion": _cama_libre(a)})
    hosp = next(h for h in a.list_hospitalizations() if h["id_paciente"] == p.id_paciente)
    return p, hosp, dpi


class TestHospitalCirugiasEnfermeria(unittest.TestCase):
    """Reglas que garantiza PostgreSQL: quirófano y cirujano sin traslapes, máximo por turno."""

    def setUp(self):
        self.a = _adaptador("pg")

    def test_flujo_quirofano_y_turnos(self):
        a = self.a
        p, hosp, dpi = _ingresar(a, "Qx")
        cuando = "2031-01-15 10:00"
        c = a.schedule_surgery({"id_paciente": p.id_paciente, "id_medico": 1, "procedimiento": "Apendicectomía",
                                "codigo_quirofano": "QX-2", "fecha_hora_programada": cuando, "duracion_estimada_min": 60})
        self.assertEqual(c.id_hospitalizacion, hosp["id_hospitalizacion"])
        with self.assertRaises(ValueError):   # mismo quirófano, horario traslapado
            a.schedule_surgery({"id_paciente": p.id_paciente, "id_medico": 2, "procedimiento": "X",
                                "codigo_quirofano": "QX-2", "fecha_hora_programada": "2031-01-15 10:30",
                                "duracion_estimada_min": 30})
        with self.assertRaises(ValueError):   # mismo cirujano, otro quirófano, horario traslapado
            a.schedule_surgery({"id_paciente": p.id_paciente, "id_medico": 1, "procedimiento": "X",
                                "codigo_quirofano": "QX-3", "fecha_hora_programada": "2031-01-15 10:30",
                                "duracion_estimada_min": 30})
        self.assertEqual(a.start_surgery(c.id_cirugia).estado, "en_curso")
        with self.assertRaises(ValueError):   # no hay alta durante la cirugía
            a.discharge(hosp["id_hospitalizacion"])
        self.assertEqual(a.finish_surgery(c.id_cirugia, "Sin complicaciones").estado, "realizada")

        enf = a.create_nurse({"nombre_completo": "Enf. Prueba", "numero_colegiado": f"E-{dpi}"})
        t = a.assign_shift({"id_enfermero": enf.id_profesional, "id_hospitalizacion": hosp["id_hospitalizacion"],
                            "fecha": "2031-01-16", "turno": "manana"})
        with self.assertRaises(ValueError):   # duplicado
            a.assign_shift({"id_enfermero": enf.id_profesional, "id_hospitalizacion": hosp["id_hospitalizacion"],
                            "fecha": "2031-01-16", "turno": "manana"})
        self.assertEqual(a.annul_shift(t.id_asignacion).estado, "anulada")
        a.discharge(hosp["id_hospitalizacion"], "alta")
        with self.assertRaises(ValueError):   # ya no está ingresado
            a.assign_shift({"id_enfermero": enf.id_profesional, "id_hospitalizacion": hosp["id_hospitalizacion"],
                            "fecha": "2031-01-17", "turno": "tarde"})


    def test_habitaciones_y_medicacion(self):
        a = self.a
        with self.assertRaises(ValueError):   # sin habitación no hay ingreso
            pp = a.create_patient({"nombres": "Sin", "apellidos": "Cama", "fecha_nacimiento": "1990-01-01",
                                   "sexo": "F", "dpi": str(int(time.time() * 1000000))[-13:]})
            a.register_consultation({"id_paciente": pp.id_paciente, "motivo": "x", "id_profesional": 1,
                                     "requiere_hospitalizacion": True})
        p, hosp, dpi = _ingresar(a, "Kardex")
        hid = hosp["id_hospitalizacion"]
        self.assertTrue(hosp["departamento"])
        with self.assertRaises(ValueError):   # habitación llena (CG-304 tiene 1 cama ocupada por el seed)
            a.change_room(hid, "CG-304")
        with self.assertRaises(ValueError):   # no existe
            a.change_room(hid, "ZZ-999")
        destino = _cama_libre(a, excepto=(hosp["numero_habitacion"],))
        self.assertEqual(a.change_room(hid, destino)["numero_habitacion"], destino)

        orden = a.create_medication_order({"id_hospitalizacion": hid, "id_medicamento": 2, "id_medico": 1,
                                           "dosis": "40 mg", "via_administracion": "Intravenosa",
                                           "frecuencia_horas": 12, "duracion_dias": 2})
        self.assertEqual(orden["total_dosis"], 4)
        enf = a.create_nurse({"nombre_completo": "Enf. Kardex", "numero_colegiado": f"K-{dpi}"})
        dosis = a.list_doses(hid)
        primera = dosis[0]
        self.assertEqual(a.apply_dose(primera["id_administracion"], enf.id_profesional)["estado"], "aplicada")
        with self.assertRaises(ValueError):   # no se aplica dos veces
            a.apply_dose(primera["id_administracion"], enf.id_profesional)
        with self.assertRaises(ValueError):   # la última dosis aún no toca
            a.apply_dose(dosis[-1]["id_administracion"], enf.id_profesional)
        self.assertEqual(a.omit_dose(dosis[1]["id_administracion"], enf.id_profesional, "Paciente en ayuno")["estado"],
                         "omitida")
        susp = a.suspend_medication_order(orden["id_orden"], "Cambio de tratamiento")
        self.assertEqual((susp["estado"], susp["aplicadas"], susp["omitidas"]), ("suspendida", 1, 1))
        with self.assertRaises(ValueError):   # orden suspendida
            a.apply_dose(dosis[2]["id_administracion"], enf.id_profesional)
        a.create_medication_order({"id_hospitalizacion": hid, "id_medicamento": 4, "id_medico": 1,
                                   "dosis": "1 g", "frecuencia_horas": 8, "duracion_dias": 1})
        a.discharge(hid, "alta")
        self.assertTrue(all(o["estado"] != "activa" for o in a.list_medication_orders(hid)))
        with self.assertRaises(ValueError):   # ya no se indica medicación tras el alta
            a.create_medication_order({"id_hospitalizacion": hid, "id_medicamento": 4, "id_medico": 1,
                                       "dosis": "1 g", "frecuencia_horas": 8})


if __name__ == "__main__":
    unittest.main()
