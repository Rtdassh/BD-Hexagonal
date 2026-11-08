"""
Flujo de órdenes del laboratorio con MongoDB en memoria (mongomock).
Sirve sin Docker: pip install mongomock. Si no está instalado, la prueba se omite.
La versión contra el MongoDB real está en test_motores_reales.py (TestMongoDB).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import mongomock
except ImportError:
    mongomock = None


@unittest.skipIf(mongomock is None, "mongomock no está instalado")
class TestOrdenesLaboratorio(unittest.TestCase):
    def setUp(self):
        from src.infrastructure.adapters.mongodb_adapter import MongoDBAdapter

        class Cfg:
            MONGO_URI = "mongodb://memoria"
            MONGO_DATABASE = "lab"

        cli = mongomock.MongoClient()
        db = cli["lab"]
        db.tipos_examen.insert_many([
            {"codigo": "QUI-01", "nombre_examen": "Perfil glucémico", "indicaciones_preparacion": "Ayuno de 8 horas",
             "requiere_cita": True, "costo": 95.0},
            {"codigo": "URO-01", "nombre_examen": "Uroanálisis", "requiere_cita": False, "costo": 60.0},
        ])
        db.laboratoristas.insert_many([
            {"id_laboratorista": 1, "nombre_completo": "Lab Uno", "estado": "activo"},
            {"id_laboratorista": 2, "nombre_completo": "Lab Dos", "estado": "activo"},
            {"id_laboratorista": 3, "nombre_completo": "Lab Inactivo", "estado": "inactivo"},
        ])
        db.pacientes.insert_one({"id_paciente": 1, "nombres": "Ana", "apellidos": "Ruiz", "dpi": "1234567890101",
                                 "fecha_nacimiento": "1990-01-01", "sexo": "F"})
        db.historiales_clinicos.insert_one({"id_paciente": 1, "estado": "activo", "id_historial": 1})
        self.a = MongoDBAdapter(Cfg(), client=cli)

    def resultado(self, oid, codigo, lab=1, valor="90"):
        return self.a.register_results(oid, {"codigo_examen": codigo, "id_laboratorista": lab, "parametros": [
            {"nombre_parametro": "Valor", "valor_resultado": valor, "rango_referencia_min": 70, "rango_referencia_max": 100}]})

    def test_flujo_completo_con_dos_examenes(self):
        a = self.a
        o = a.create_lab_order({"id_paciente": 1, "examenes": ["QUI-01", "URO-01"], "fecha_toma": "2030-01-01 07:00"})
        oid = o["id_orden"]
        self.assertEqual(o["cita"]["estado_cita"], "programada")
        with self.assertRaises(ValueError):   # sin muestra no hay resultados
            self.resultado(oid, "QUI-01")
        o = a.register_sample(oid, {"id_laboratorista": 1, "tipo_muestra": "Suero", "preparacion_cumplida": True})
        self.assertEqual((o["estado_orden"], o["cita"]["estado_cita"]), ("en_analisis", "atendida"))
        o = self.resultado(oid, "QUI-01", valor="250")
        self.assertEqual(o["estado_orden"], "en_analisis")           # falta el uroanálisis
        self.assertTrue(o["alertas_criticas"])
        with self.assertRaises(ValueError):                           # no se repite
            self.resultado(oid, "QUI-01")
        o = self.resultado(oid, "URO-01")
        self.assertEqual(o["estado_orden"], "por_validar")
        with self.assertRaises(ValueError):                           # doble verificación
            a.validate_order(oid, {"id_laboratorista": 1})
        o = a.validate_order(oid, {"id_laboratorista": 2})
        self.assertEqual(o["estado_orden"], "lista_entrega")
        self.assertTrue(all(m["estado"] == "procesada" for m in o["muestras"]))
        # La factura nació con la orden (Q95 + Q60): sin pagar no se entregan resultados
        self.assertEqual((o["factura"]["estado"], o["factura"]["saldo"]), ("pendiente", 155.0))
        with self.assertRaises(ValueError):
            a.deliver_order(oid, {"entregado_a": "Ana Ruiz"})
        fid = o["factura"]["id_factura"]
        with self.assertRaises(ValueError):   # no se cobra de más
            a.register_invoice_payment(fid, {"monto": 200, "metodo_pago": "efectivo"})
        a.register_invoice_payment(fid, {"monto": 100, "metodo_pago": "efectivo"})
        f = a.register_invoice_payment(fid, {"monto": 55, "metodo_pago": "tarjeta", "referencia": "AUT-1"})
        self.assertEqual((f["estado"], len(f["pagos"])), ("pagada", 2))
        o = a.deliver_order(oid, {"entregado_a": "Ana Ruiz"})
        self.assertEqual(o["estado_orden"], "entregada")
        self.assertEqual([h["estado"] for h in o["historial_estados"]][-1], "entregada")

    def test_muestra_rechazada_y_cancelacion(self):
        a = self.a
        oid = a.create_lab_order({"id_paciente": 1, "examenes": ["QUI-01"]})["id_orden"]
        with self.assertRaises(ValueError):   # laboratorista inactivo
            a.register_sample(oid, {"id_laboratorista": 3, "tipo_muestra": "Suero", "preparacion_cumplida": True})
        o = a.register_sample(oid, {"id_laboratorista": 1, "tipo_muestra": "Suero", "preparacion_cumplida": False,
                                    "motivo_rechazo": "No vino en ayunas"})
        self.assertEqual((o["estado_orden"], o["muestras"][0]["estado"]), ("pendiente_muestra", "rechazada"))
        o = a.cancel_order(oid, "El paciente no regresó")
        self.assertEqual(o["estado_orden"], "cancelada")
        self.assertEqual(a.list_invoices("anulada")[0]["origen_id"], oid)   # la factura se anula con la orden
        with self.assertRaises(ValueError):
            a.register_sample(oid, {"id_laboratorista": 1, "tipo_muestra": "Suero", "preparacion_cumplida": True})

    def test_examen_desconocido_e_historial_de_baja(self):
        with self.assertRaises(ValueError):
            self.a.create_lab_order({"id_paciente": 1, "examenes": ["XXX-99"]})
        self.a.db.historiales_clinicos.update_one({"id_paciente": 1}, {"$set": {"estado": "dado_de_baja"}})
        with self.assertRaises(ValueError):
            self.a.create_lab_order({"id_paciente": 1, "examenes": ["URO-01"]})


if __name__ == "__main__":
    unittest.main()
