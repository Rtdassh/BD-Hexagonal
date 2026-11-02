"""
Configuration module for databases, environments, and demonstration users.
"""

import os
from typing import Dict, Any


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "bases-datos-2-landivar-secret-key-2026")
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

    # PostgreSQL Configuration (Hospital General)
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = int(os.getenv("PG_PORT", 5432))
    PG_DATABASE = os.getenv("PG_DATABASE", "hospital_db")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

    # MySQL Configuration (Centro Médico Pediátrico)
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "centro_pediatrico")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")

    # MongoDB Configuration (Laboratorio Clínico)
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DATABASE = os.getenv("MONGO_DATABASE", "laboratorio_clinico")

    # Firebase Configuration (Clínica Odontológica)
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "clinica-odontologica-landivar")

    # Modo de ejecución de adaptadores:
    # 'auto' intenta conectar al motor real; si no está disponible, conmuta limpiamente al motor simulado.
    # 'force_live' exige conexión real.
    # 'simulated' usa directamente los motores simulados precargados.
    ENGINE_MODE = os.getenv("ENGINE_MODE", "auto")


# Usuarios demostrativos configurados para el inicio de sesión y enrutamiento
DEMO_USERS = [
    {
        "username": "dr_garcia",
        "password": "123",
        "nombre_completo": "Dr. Carlos Roberto Mendoza",
        "institucion": "hospital",
        "rol": "medico",
        "motor": "PostgreSQL",
        "numero_colegiado": "COL-12450",
        "cargo": "Médico Cirujano - Hospital General"
    },
    {
        "username": "dra_lopez",
        "password": "123",
        "nombre_completo": "Dra. Mariana Lucía Batres",
        "institucion": "pediatrico",
        "rol": "pediatra",
        "motor": "MySQL",
        "numero_colegiado": "PED-08912",
        "cargo": "Pediatra Especialista - Centro Pediátrico"
    },
    {
        "username": "lic_mendez",
        "password": "123",
        "nombre_completo": "Licda. Brenda Marisol Morales",
        "institucion": "laboratorio",
        "rol": "laboratorista",
        "motor": "MongoDB",
        "numero_colegiado": "QB-4521",
        "cargo": "Química Bióloga - Laboratorio Clínico"
    },
    {
        "username": "sec_claudia",
        "password": "123",
        "nombre_completo": "Claudia Maricela Fuentes",
        "institucion": "odontologia",
        "rol": "secretaria",
        "motor": "Firebase Cloud Firestore",
        "numero_colegiado": None,
        "cargo": "Secretaria de Recepción - Clínica Odontológica"
    },
    {
        "username": "dr_molina",
        "password": "123",
        "nombre_completo": "Dr. Rodrigo Andrés Molina",
        "institucion": "odontologia",
        "rol": "odontologo",
        "motor": "Firebase Cloud Firestore",
        "numero_colegiado": "ODONT-3210",
        "cargo": "Odontólogo Especialista - Clínica Odontológica"
    },
    {
        "username": "admin_general",
        "password": "123",
        "nombre_completo": "Ing. Administrador de Red Médica",
        "institucion": "hospital",
        "rol": "administrador",
        "motor": "PostgreSQL",
        "numero_colegiado": None,
        "cargo": "Super Administrador del Sistema"
    }
]

