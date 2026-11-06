"""
Enrutador de motores (mecanismo central de la arquitectura hexagonal).

Cada institución tiene un adaptador que implementa el mismo puerto
(ClinicalRepositoryPort). Los servicios piden "el adaptador del usuario" y no
saben qué motor hay detrás: cambiar de motor es cuestión de configuración.
"""

import logging
from typing import Any, Callable, Dict, List

from ..domain.entities import InstitutionType, User, UserRole
from ..domain.ports import ClinicalRepositoryPort
from ..infrastructure.config import Config

log = logging.getLogger(__name__)


def _fabricas_reales() -> Dict[InstitutionType, Callable[[Config], ClinicalRepositoryPort]]:
    # Importación diferida: si falta un driver, solo se pierde ese motor.
    def pg(c):
        from ..infrastructure.adapters.postgresql_adapter import PostgreSQLAdapter
        return PostgreSQLAdapter(c)

    def my(c):
        from ..infrastructure.adapters.mysql_adapter import MySQLAdapter
        return MySQLAdapter(c)

    def mg(c):
        from ..infrastructure.adapters.mongodb_adapter import MongoDBAdapter
        return MongoDBAdapter(c)

    def fb(c):
        from ..infrastructure.adapters.firebase_adapter import FirebaseAdapter
        return FirebaseAdapter(c)

    return {
        InstitutionType.HOSPITAL_GENERAL: pg,
        InstitutionType.CENTRO_PEDIATRICO: my,
        InstitutionType.LABORATORIO_CLINICO: mg,
        InstitutionType.CLINICA_ODONTOLOGICA: fb,
    }


def _fabricas_simuladas() -> Dict[InstitutionType, Callable[[Config], ClinicalRepositoryPort]]:
    from ..infrastructure.adapters.simulated import (
        SimulatedFirebaseAdapter,
        SimulatedMongoDBAdapter,
        SimulatedMySQLAdapter,
        SimulatedPostgreSQLAdapter,
    )

    return {
        InstitutionType.HOSPITAL_GENERAL: SimulatedPostgreSQLAdapter,
        InstitutionType.CENTRO_PEDIATRICO: SimulatedMySQLAdapter,
        InstitutionType.LABORATORIO_CLINICO: SimulatedMongoDBAdapter,
        InstitutionType.CLINICA_ODONTOLOGICA: SimulatedFirebaseAdapter,
    }


class EngineRouter:
    def __init__(self, config: Config):
        self.config = config
        self._adapters: Dict[InstitutionType, ClinicalRepositoryPort] = {}
        self.errores: Dict[InstitutionType, str] = {}
        self._init_adapters()

    def _init_adapters(self):
        modo = self.config.ENGINE_MODE
        simuladas = _fabricas_simuladas()
        if modo == "simulated":
            self._adapters = {inst: f(self.config) for inst, f in simuladas.items()}
            return

        for inst, fabrica in _fabricas_reales().items():
            try:
                self._adapters[inst] = fabrica(self.config)
                log.info("%s -> motor real conectado", inst.value)
            except Exception as e:  # el motor no responde o no está configurado
                self.errores[inst] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
                if modo in ("live", "force_live"):
                    raise RuntimeError(f"No se pudo conectar el motor de '{inst.value}': {e}") from e
                log.warning("%s -> motor real NO disponible (%s); usando simulado", inst.value, self.errores[inst])
                self._adapters[inst] = simuladas[inst](self.config)

    def get_adapter(self, institution: InstitutionType) -> ClinicalRepositoryPort:
        if institution not in self._adapters:
            raise ValueError(f"La institución '{institution}' no tiene motor registrado")
        return self._adapters[institution]

    def get_adapter_for_user(self, user: User, override_institution: str = None) -> ClinicalRepositoryPort:
        """
        Enrutamiento por usuario: la institución del usuario autenticado decide el motor.
        Solo el administrador puede consultar otra institución.
        """
        target = user.institucion
        if override_institution and user.rol == UserRole.ADMIN:
            target = InstitutionType(override_institution)
        return self.get_adapter(target)

    def get_all_adapters(self) -> Dict[InstitutionType, ClinicalRepositoryPort]:
        return self._adapters

    def health_check_all(self) -> List[Dict[str, Any]]:
        estados = []
        for inst, adapter in self._adapters.items():
            try:
                h = adapter.health_check()
            except Exception as e:
                h = {"institucion": inst.value, "motor": adapter.database_engine.value,
                     "estado": "error", "detalle": str(e)}
            h["clave"] = inst.value
            h["real"] = bool(getattr(adapter, "is_live", False))
            if inst in self.errores:
                h["detalle_conexion"] = self.errores[inst]
            estados.append(h)
        return estados
