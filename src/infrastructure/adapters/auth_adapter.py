"""
Authentication and Session Adapter.
Implements AuthPort, providing authentication, role validation,
and automatic routing mapping to the user's institution.
"""

import uuid
from typing import Dict, Any, List, Optional
from ...domain.entities import User, UserRole, InstitutionType, DatabaseEngine
from ...domain.ports import AuthPort
from ..config import DEMO_USERS


class AuthAdapter(AuthPort):
    def __init__(self):
        self.active_sessions: Dict[str, User] = {}
        self.users: List[Dict[str, Any]] = DEMO_USERS

    def authenticate(self, username: str, password: str) -> Optional[User]:
        for u in self.users:
            if u["username"].lower() == username.lower().strip() and u["password"] == password:
                token = f"token_{uuid.uuid4().hex[:16]}"
                institucion = InstitutionType(u["institucion"])
                rol = UserRole(u["rol"])
                motor = DatabaseEngine(u["motor"])

                user_domain = User(
                    username=u["username"],
                    nombre_completo=u["nombre_completo"],
                    institucion=institucion,
                    rol=rol,
                    motor_asignado=motor,
                    numero_colegiado=u.get("numero_colegiado"),
                    token=token
                )
                self.active_sessions[token] = user_domain
                return user_domain
        return None

    def get_user_by_token(self, token: str) -> Optional[User]:
        return self.active_sessions.get(token)

    def list_available_users(self) -> List[Dict[str, Any]]:
        return [
            {
                "username": u["username"],
                "nombre_completo": u["nombre_completo"],
                "institucion": u["institucion"],
                "rol": u["rol"],
                "motor": u["motor"],
                "cargo": u.get("cargo", "")
            }
            for u in self.users
        ]

