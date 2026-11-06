"""
Configuración de motores de base de datos, modo de ejecución y usuarios de la aplicación.

Los valores se leen de variables de entorno (archivo .env en la raíz del proyecto).
Los valores por defecto coinciden con docker-compose.yml.
"""

import os
from typing import Dict, Any, List

try:
    # Carga opcional del archivo .env (pip install python-dotenv)
    from dotenv import load_dotenv

    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_dotenv(os.path.join(_ROOT, ".env"))
except ImportError:  # pragma: no cover
    pass


class Config:
    def __init__(self):
        self.SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esta-clave-en-produccion")
        self.PORT = int(os.getenv("PORT", 5000))
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"

        # PostgreSQL - Hospital General
        self.PG_HOST = os.getenv("PG_HOST", "localhost")
        self.PG_PORT = int(os.getenv("PG_PORT", 5433))
        self.PG_DATABASE = os.getenv("PG_DATABASE", "hospital_db")
        self.PG_USER = os.getenv("PG_USER", "app_hospital")
        self.PG_PASSWORD = os.getenv("PG_PASSWORD", "HospitalApp2026!")

        # MySQL - Centro Médico Pediátrico
        self.MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3307))
        self.MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "centro_pediatrico")
        self.MYSQL_USER = os.getenv("MYSQL_USER", "app_pediatrico")
        self.MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "PediatricoApp2026!")

        # MongoDB - Laboratorio Clínico
        self.MONGO_URI = os.getenv(
            "MONGO_URI",
            "mongodb://app_laboratorio:LaboratorioApp2026!@localhost:27018/"
            "laboratorio_clinico?directConnection=true&authSource=laboratorio_clinico",
        )
        self.MONGO_DATABASE = os.getenv("MONGO_DATABASE", "laboratorio_clinico")

        # Firebase Cloud Firestore - Clínica Odontológica
        # Opción A (emulador local):  FIRESTORE_EMULATOR_HOST=localhost:8085
        # Opción B (proyecto real):   FIREBASE_CREDENTIALS_PATH=ruta/al/serviceAccount.json
        self.FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "clinica-odontologica-landivar")
        self.FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
        self.FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "")

        # Modo de ejecución de los adaptadores:
        #   'auto'       -> intenta conectar al motor real; si no responde usa el simulado en memoria.
        #   'live'       -> exige conexión real (falla al arrancar si un motor no responde).
        #   'simulated'  -> usa siempre los motores simulados en memoria (demo sin bases de datos).
        self.ENGINE_MODE = os.getenv("ENGINE_MODE", "auto").lower()


# ---------------------------------------------------------------------------
# Usuarios de la plataforma.
# 'institucion' decide a qué motor se enrutan sus operaciones.
# 'id_profesional' es el id del profesional dentro de la base de su institución
# (hospital.Medico, pediatra, laboratoristas, odontologos/secretarias).
# Para la demo todos usan la contraseña "123".
# ---------------------------------------------------------------------------
DEMO_USERS: List[Dict[str, Any]] = [
    {
        "username": "dr_garcia",
        "password": "123",
        "nombre_completo": "Dr. Carlos Roberto Mendoza",
        "institucion": "hospital",
        "rol": "medico",
        "motor": "PostgreSQL",
        "numero_colegiado": "COL-12450",
        "id_profesional": 1,
        "cargo": "Médico internista - Hospital General",
    },
    {
        "username": "dra_lopez",
        "password": "123",
        "nombre_completo": "Dra. Mariana Lucía Batres",
        "institucion": "pediatrico",
        "rol": "pediatra",
        "motor": "MySQL",
        "numero_colegiado": "PED-08912",
        "id_profesional": 1,
        "cargo": "Pediatra - Centro Médico Pediátrico",
    },
    {
        "username": "lic_mendez",
        "password": "123",
        "nombre_completo": "Licda. Brenda Marisol Morales",
        "institucion": "laboratorio",
        "rol": "laboratorista",
        "motor": "MongoDB",
        "numero_colegiado": "QB-4521",
        "id_profesional": 1,
        "cargo": "Química bióloga - Laboratorio Clínico",
    },
    {
        "username": "sec_claudia",
        "password": "123",
        "nombre_completo": "Claudia Maricela Fuentes",
        "institucion": "odontologia",
        "rol": "secretaria",
        "motor": "Firebase Cloud Firestore",
        "numero_colegiado": None,
        "id_profesional": 1,
        "cargo": "Secretaria de recepción - Clínica Odontológica",
    },
    {
        "username": "dr_molina",
        "password": "123",
        "nombre_completo": "Dr. Rodrigo Andrés Molina",
        "institucion": "odontologia",
        "rol": "odontologo",
        "motor": "Firebase Cloud Firestore",
        "numero_colegiado": "ODONT-3210",
        "id_profesional": 1,
        "cargo": "Odontólogo - Clínica Odontológica",
    },
    {
        "username": "admin_general",
        "password": "123",
        "nombre_completo": "Administrador de la red",
        "institucion": "hospital",
        "rol": "administrador",
        "motor": "PostgreSQL",
        "numero_colegiado": None,
        "id_profesional": 1,
        "cargo": "Administrador del sistema (puede consultar las 4 instituciones)",
    },
]
