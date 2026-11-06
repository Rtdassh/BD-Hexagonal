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


if __name__ == "__main__":
    unittest.main()
