"""
Engine Router (Hexagonal Routing Mechanism).
Dynamically routes business logic operations to the corresponding database adapter
based on the authenticated user's institution, completely decoupling the domain.
"""

from typing import Dict, Any, List
from ..domain.entities import InstitutionType, DatabaseEngine, User
from ..domain.ports import ClinicalRepositoryPort
from ..infrastructure.config import Config
from ..infrastructure.adapters.postgresql_adapter import PostgreSQLAdapter
from ..infrastructure.adapters.mysql_adapter import MySQLAdapter
from ..infrastructure.adapters.mongodb_adapter import MongoDBAdapter
from ..infrastructure.adapters.firebase_adapter import FirebaseAdapter


class EngineRouter:
    """
    Central dispatcher in the Hexagonal Architecture.
    Directs incoming requests to the specific adapter without business logic rewrite.
    """

    def __init__(self, config: Config):
        self.config = config
        self._adapters: Dict[InstitutionType, ClinicalRepositoryPort] = {}
        self._init_adapters()

    def _init_adapters(self):
        # Inicializar los 4 adaptadores con sus respectivos motores
        self._adapters[InstitutionType.HOSPITAL_GENERAL] = PostgreSQLAdapter(self.config)
        self._adapters[InstitutionType.CENTRO_PEDIATRICO] = MySQLAdapter(self.config)
        self._adapters[InstitutionType.LABORATORIO_CLINICO] = MongoDBAdapter(self.config)
        self._adapters[InstitutionType.CLINICA_ODONTOLOGICA] = FirebaseAdapter(self.config)

    def get_adapter(self, institution: InstitutionType) -> ClinicalRepositoryPort:
        """Retrieves the database adapter assigned to the institution."""
        if institution not in self._adapters:
            raise ValueError(f"Institución '{institution}' no tiene un motor de base de datos registrado.")
        return self._adapters[institution]

    def get_adapter_for_user(self, user: User, override_institution: str = None) -> ClinicalRepositoryPort:
        """
        Enruta automáticamente al motor correspondiente de la institución del usuario.
        Si el usuario es administrador, puede opcionalmente especificar qué motor consultar.
        """
        target = user.institucion
        if user.rol.value == "administrador" and override_institution:
            target = InstitutionType(override_institution)
        return self.get_adapter(target)

    def get_all_adapters(self) -> Dict[InstitutionType, ClinicalRepositoryPort]:
        return self._adapters

    def health_check_all(self) -> List[Dict[str, Any]]:
        """Verifica la salud de los 4 motores simultáneamente."""
        return [adapter.health_check() for adapter in self._adapters.values()]

