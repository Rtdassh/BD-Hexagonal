"""Adaptadores simulados en memoria (modo demo sin bases de datos reales)."""
from .postgresql_simulated_adapter import SimulatedPostgreSQLAdapter
from .mysql_simulated_adapter import SimulatedMySQLAdapter
from .mongodb_simulated_adapter import SimulatedMongoDBAdapter
from .firebase_simulated_adapter import SimulatedFirebaseAdapter

__all__ = [
    "SimulatedPostgreSQLAdapter",
    "SimulatedMySQLAdapter",
    "SimulatedMongoDBAdapter",
    "SimulatedFirebaseAdapter",
]
