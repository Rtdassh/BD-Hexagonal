"""
Punto de Entrada Principal de la Aplicación.
Inicia el servidor Flask y expone la API REST junto con la interfaz cliente ligera.
"""

import sys
import os

# Asegurar que el directorio raíz esté en sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.infrastructure.config import Config
from src.interfaces.api import create_app


def main():
    config = Config()
    app = create_app(config)

    print("=" * 78)
    print("  RED MÉDICA INTERINSTITUCIONAL - PLATAFORMA DE HISTORIALES CLÍNICOS")
    print("  PROYECTO FINAL BASES DE DATOS II - UNIVERSIDAD RAFAEL LANDÍVAR")
    print("  ARQUITECTURA HEXAGONAL (PUERTOS Y ADAPTADORES)")
    print("=" * 78)
    print("  1. Hospital General:           PostgreSQL (schema: hospital) [ACID]")
    print("  2. Centro Médico Pediátrico:   MySQL (InnoDB) [Somatometría & Vacunas]")
    print("  3. Laboratorio Clínico:        MongoDB (Documental NoSQL) [Polimórfico]")
    print("  4. Clínica Odontológica:       Firebase Firestore [Serverless Cloud]")
    print("=" * 78)
    print(f"  Servidor Web y API REST activos en: http://localhost:{config.PORT}")
    print("  Usuarios demo: dr_garcia, dra_lopez, lic_mendez, sec_claudia, dr_molina")
    print("  Contraseña demo para todos: 123")
    print("=" * 78)

    app.run(host="0.0.0.0", port=config.PORT, debug=False)


if __name__ == "__main__":
    main()

