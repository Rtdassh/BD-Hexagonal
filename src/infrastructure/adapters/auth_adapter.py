"""
Authentication and Session Adapter.
Implements AuthPort, providing authentication, role validation,
and automatic routing mapping to the user's institution.
"""

import hmac
import secrets
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
            if u["username"].lower() == (username or "").lower().strip() and hmac.compare_digest(
                u["password"], password or ""
            ):
                token = secrets.token_urlsafe(32)
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
                    token=token,
                    id_profesional=u.get("id_profesional"),
                )
                self.active_sessions[token] = user_domain
                return user_domain
        return None

    def get_user_by_token(self, token: str) -> Optional[User]:
        return self.active_sessions.get(token)

    def logout(self, token: str) -> None:
        self.active_sessions.pop(token, None)

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

