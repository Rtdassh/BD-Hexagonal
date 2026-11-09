"""
Odontograma de la Clínica Odontológica (Firestore en memoria).

    python -m pytest tests/test_odontograma.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.fake_firestore import adaptador_odontologia  # noqa: E402
from src.domain import validaciones as V  # noqa: E402


class TestOdontograma(unittest.TestCase):
    def setUp(self):
        self.a = adaptador_odontologia()

    def test_catalogo_con_nombres_de_pantalla(self):
        cat = self.a.list_dental_findings_catalog()
        self.assertGreaterEqual(len(cat), 9)
        for h in cat:
            self.assertTrue(h["nombre"] and h["nombre_hallazgo"] == h["nombre"])
            self.assertRegex(h["color_sugerido"], r"^#[0-9A-F]{6}$")

    def test_datos_iniciales_y_resumen(self):
        o = self.a.get_odontogram(1)
        self.assertEqual(sorted(o["piezas"]), ["18", "36", "46"])
        self.assertEqual(o["resumen"], {"piezas_con_hallazgos": 3, "por_tratar": 1, "tratados": 2})
        self.assertEqual(self.a.get_dental_details(1)["odontograma"]["resumen"]["por_tratar"], 1)

    def test_registrar_reemplaza_y_guarda_historial(self):
        d = V.validar_hallazgo_odontograma({"codigo_fdi": 36, "cara": "O", "hallazgo": "Restauración con resina",
                                            "estado": "tratado", "color_hex": "#2F5E9E"})
        h = self.a.save_odontogram_finding(1, {**d, "registrado_por": "Dra. Cifuentes"})
        self.assertEqual((h["codigo_hallazgo"], h["estado"], h["historial"][-1]["hallazgo"]),
                         ("resina", "tratado", "Caries activa"))
        self.assertEqual(self.a.get_odontogram(1)["resumen"]["por_tratar"], 0)

    def test_cara_general_y_validaciones(self):
        self.assertEqual(V.validar_cara_dental("general"), "G")
        with self.assertRaisesRegex(ValueError, "Cara dental inválida"):
            V.validar_cara_dental("X")
        with self.assertRaisesRegex(ValueError, "no es válida"):
            V.validar_hallazgo_odontograma({"codigo_fdi": 19, "cara": "O", "hallazgo": "Caries activa"})
        with self.assertRaisesRegex(ValueError, "Estado"):
            V.validar_hallazgo_odontograma({"codigo_fdi": 11, "cara": "O", "hallazgo": "Caries activa", "estado": "x"})
        with self.assertRaisesRegex(ValueError, "no encontrado"):
            self.a.save_odontogram_finding(99, {"codigo_fdi": 11, "cara": "G", "hallazgo": "Corona protésica"})

    def test_marcar_tratado_y_quitar(self):
        self.assertEqual(self.a.update_odontogram_finding(2, 17, "O", "tratado")["estado"], "tratado")
        self.a.delete_odontogram_finding(2, 36, "M")
        self.assertEqual(sorted(self.a.get_odontogram(2)["piezas"]), ["17", "46"])
        with self.assertRaisesRegex(ValueError, "no tiene hallazgo"):
            self.a.delete_odontogram_finding(2, 36, "M")


if __name__ == "__main__":
    unittest.main()
