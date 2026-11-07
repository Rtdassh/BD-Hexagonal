"""
Punto de entrada: levanta la API REST y la interfaz web.

    python src/main.py
"""

import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.infrastructure.config import Config  # noqa: E402
from src.interfaces.api import create_app  # noqa: E402


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = Config()
    app = create_app(config)

    print("=" * 72)
    print("  RED DE HISTORIALES CLÍNICOS - Bases de Datos II (URL)")
    print(f"  Modo de motores: {config.ENGINE_MODE}")
    print("-" * 72)
    for estado in app.engine_router.health_check_all():
        tipo = "REAL     " if estado.get("real") else "SIMULADO "
        print(f"  [{tipo}] {estado.get('institucion', ''):<28} {estado.get('motor', '')}")
        if estado.get("detalle_conexion"):
            print(f"             motivo: {estado['detalle_conexion'][:90]}")
    print("-" * 72)
    print(f"  Abrir en el navegador: http://localhost:{config.PORT}")
    print("  Usuarios: admin_hospital, admin_pediatria, admin_laboratorio, admin_odontologia (clave 123)")
    print("=" * 72)

    app.run(host="127.0.0.1", port=config.PORT, debug=config.DEBUG)


if __name__ == "__main__":
    main()
