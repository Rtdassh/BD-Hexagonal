"""
Caja de la Clínica Odontológica (Firestore) con un Firestore en memoria.

    python -m pytest tests/test_caja_odontologia.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.fake_firestore import adaptador_odontologia  # noqa: E402
from src.domain.ports import BillingPort  # noqa: E402


class TestCajaOdontologia(unittest.TestCase):
    def setUp(self):
        self.a = adaptador_odontologia()

    def test_es_caja(self):
        self.assertIsInstance(self.a, BillingPort)

    def test_datos_iniciales(self):
        facturas = self.a.list_invoices()
        self.assertEqual([f["numero_factura"] for f in facturas], ["CO-000002", "CO-000001"])
        f2 = self.a.get_invoice(2)
        self.assertEqual((f2["estado"], f2["saldo"], len(f2["pagos"])), ("parcial", 575.0, 2))
        self.assertEqual(self.a.list_invoices(estado="pagada")[0]["numero_factura"], "CO-000001")

    def test_aranceles_son_el_catalogo(self):
        t = {x["codigo"]: x for x in self.a.list_tariffs()}
        self.assertEqual(t["OD-04"]["precio"], 800.0)
        self.a.save_tariff({"codigo": "OD-04", "descripcion": "Endodoncia unirradicular", "categoria": "procedimiento",
                            "precio": 850.0, "activo": True})
        self.assertEqual({x["codigo"]: x for x in self.a.list_tariffs()}["OD-04"]["precio"], 850.0)
        nuevo = self.a.save_tariff({"codigo": "BLANQ", "descripcion": "Blanqueamiento", "categoria": "procedimiento",
                                    "precio": 900.0})
        self.assertEqual(nuevo["precio"], 900.0)
        self.assertTrue(any(p["nombre_procedimiento"] == "Blanqueamiento" for p in self.a.list_dental_procedures_catalog()))

    def test_factura_abonos_y_limites(self):
        f = self.a.create_invoice({"id_paciente": 1, "nit": "CF", "lineas": [
            {"codigo_arancel": "OD-01", "concepto": "Limpieza", "cantidad": 1, "precio_unitario": 250},
            {"codigo_arancel": "OD-05", "concepto": "Sellante", "cantidad": 2, "precio_unitario": 125}]})
        self.assertEqual((f["numero_factura"], f["monto_total"], f["estado"]), ("CO-000003", 500.0, "pendiente"))
        f = self.a.register_invoice_payment(f["id_factura"], {"monto": 200, "metodo_pago": "efectivo"})
        self.assertEqual((f["estado"], f["saldo"], f["pagos"][0]["numero_recibo"]), ("parcial", 300.0, "R-CO-000004"))
        with self.assertRaisesRegex(ValueError, "supera el saldo"):
            self.a.register_invoice_payment(f["id_factura"], {"monto": 300.01, "metodo_pago": "efectivo"})
        with self.assertRaisesRegex(ValueError, "tiene pagos"):
            self.a.void_invoice(f["id_factura"], "Error")
        f = self.a.register_invoice_payment(f["id_factura"], {"monto": 300, "metodo_pago": "tarjeta", "referencia": "AUT-1"})
        self.assertEqual((f["estado"], f["estado_factura"], f["saldo"]), ("pagada", "pagada", 0.0))
        with self.assertRaisesRegex(ValueError, "ya está pagada"):
            self.a.register_invoice_payment(f["id_factura"], {"monto": 1, "metodo_pago": "efectivo"})

    def test_anular_y_no_cobrar_anulada(self):
        f = self.a.create_invoice({"id_paciente": 2, "lineas": [{"concepto": "Radiografía", "cantidad": 1, "precio_unitario": 75}]})
        f = self.a.void_invoice(f["id_factura"], "Se registró dos veces")
        self.assertEqual(f["estado"], "anulada")
        with self.assertRaisesRegex(ValueError, "anulada"):
            self.a.register_invoice_payment(f["id_factura"], {"monto": 10, "metodo_pago": "efectivo"})

    def test_consulta_con_procedimientos_genera_cobro(self):
        c = self.a.register_consultation({"id_paciente": 2, "id_profesional": 1, "motivo": "Dolor en molar",
                                          "procedimientos": [{"id_procedimiento": 3, "pieza_dental": "36"},
                                                             {"id_procedimiento": 5, "pieza_dental": "17"}]})
        f = self.a.list_invoices(patient_id=2)[0]
        self.assertEqual((f["origen_tipo"], f["origen_id"], f["monto_total"]), ("consulta", c.id_consulta, 425.0))
        self.assertEqual(f["detalle"][0]["codigo_arancel"], "OD-03")
        self.assertIn("pieza 36", f["detalle"][0]["concepto"])
        with self.assertRaisesRegex(ValueError, "ya está facturado"):
            self.a.create_invoice({"id_paciente": 2, "origen_tipo": "consulta", "origen_id": c.id_consulta,
                                   "lineas": [{"concepto": "x", "cantidad": 1, "precio_unitario": 1}]})

    def test_consulta_sin_costo_no_factura(self):
        antes = len(self.a.list_invoices())
        self.a.register_consultation({"id_paciente": 1, "id_profesional": 1, "motivo": "Control"})
        self.assertEqual(len(self.a.list_invoices()), antes)

    def test_plan_de_tratamiento_y_abono_por_ruta_antigua(self):
        plan = self.a.create_treatment_plan({"id_paciente": 1, "diagnostico_general": "Rehabilitación", "costo_total_estimado": 1850,
                                             "etapas": [{"nombre_etapa": "Higiene", "costo_estimado": 350,
                                                         "procedimientos_planificados": "Profilaxis"}]})
        self.assertEqual((plan["id_plan"], plan["etapas"][0]["nombre_etapa"], plan["estado"]), (2, "Higiene", "propuesto"))
        f = self.a.get_invoice(plan["id_factura"])
        self.assertEqual((f["monto_total"], len(f["detalle"]), f["id_plan"]), (1850.0, 2, 2))
        r = self.a.register_payment({"id_factura": f["id_factura"], "monto_abonado": 500, "metodo_pago": "Efectivo",
                                     "numero_recibo": "REC-1", "secretaria": "Claudia"})
        self.assertEqual((r["factura"]["saldo"], r["numero_recibo"], r["secretaria"]), (1350.0, "R-CO-000004", "Claudia"))
        lista = self.a.list_billing_and_payments(1)
        self.assertEqual(len([x for x in lista if x["id_factura"] == f["id_factura"]][0]["abonos"]), 1)
        p = self.a.update_treatment_plan_stage(plan["id_plan"], 1, "completada")
        self.assertEqual((p["etapas"][0]["estado"], p["estado"]), ("completada", "finalizado"))
        with self.assertRaisesRegex(ValueError, "menor que la suma"):
            self.a.create_treatment_plan({"id_paciente": 1, "costo_total_estimado": 100, "titulo": "X",
                                          "etapas": [{"nombre_etapa": "A", "costo_estimado": 200}]})

    def test_expediente_resume_la_cuenta(self):
        d = self.a.get_dental_details(2)
        self.assertEqual((d["facturacion"]["total_facturado"], d["facturacion"]["total_pagado"],
                          d["facturacion"]["saldo_pendiente"]), (975.0, 400.0, 575.0))
        self.assertEqual(len(d["planes_tratamiento"]), 1)


if __name__ == "__main__":
    unittest.main()
