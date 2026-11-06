"""
Adaptador base: utilidades comunes a los 4 adaptadores y el filtro de seguridad
por clasificación de la información (pública, confidencial, restringida).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ...domain.entities import UnifiedClinicalRecord, UserRole
from ...domain.ports import ClinicalRepositoryPort


# Motivos de baja que acepta la aplicación y el estado de historial que generan.
MOTIVOS_BAJA = {
    "traslado": "trasladado",
    "fallecimiento": "fallecido",
    "administrativa": "archivado",
}


class BaseClinicalAdapter(ClinicalRepositoryPort):
    """Comportamiento común: conversión de tipos y filtro de seguridad por rol."""

    # Si True, el adaptador está conectado a un motor real.
    is_live: bool = False

    # ------------------------------------------------------------------
    # Utilidades de conversión
    # ------------------------------------------------------------------
    @staticmethod
    def _s(value: Any) -> Optional[str]:
        """Convierte fechas/decimales de la base de datos a texto ISO para la API."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="minutes")
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _f(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    @staticmethod
    def _i(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        return int(value)

    @staticmethod
    def recetas_del_payload(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Devuelve la lista de recetas de la solicitud (lista 'recetas' o campos planos)."""
        recetas = [r for r in (data.get("recetas") or []) if (r or {}).get("medicamento")]
        if not recetas and data.get("medicamento"):
            recetas = [{
                "medicamento": data.get("medicamento"),
                "presentacion": data.get("presentacion"),
                "dosis": data.get("dosis"),
                "frecuencia": data.get("frecuencia"),
                "duracion_dias": data.get("duracion_dias"),
                "via_administracion": data.get("via_administracion"),
                "indicaciones": data.get("indicaciones"),
                "dosis_mg_kg": data.get("dosis_mg_kg"),
            }]
        return recetas

    @staticmethod
    def estado_por_motivo(categoria: str) -> str:
        return MOTIVOS_BAJA.get((categoria or "").lower(), "archivado")

    @staticmethod
    def requerido(data: Dict[str, Any], *campos: str) -> None:
        faltantes = [c for c in campos if data.get(c) in (None, "")]
        if faltantes:
            raise ValueError(f"Campos obligatorios faltantes: {', '.join(faltantes)}")

    # ------------------------------------------------------------------
    # Seguridad: clasificación de la información
    # ------------------------------------------------------------------
    def apply_security_filter(
        self, clinical_record: UnifiedClinicalRecord, user_role: UserRole
    ) -> UnifiedClinicalRecord:
        """
        Niveles de clasificación:
          - Pública: catálogos (especialidades, procedimientos, exámenes).
          - Confidencial: datos personales, citas -> todo el personal.
          - Restringida: notas, diagnósticos, tratamientos, recetas, resultados
            -> solo personal clínico (médicos, pediatras, laboratoristas, odontólogos).
        La secretaria ve datos de contacto y citas, pero no información clínica.
        """
        if user_role != UserRole.SECRETARIA:
            return clinical_record

        oculto = "[Restringido - requiere rol clínico]"
        clinical_record.paciente.tipo_sangre = None
        for consulta in clinical_record.consultas:
            consulta.notas_clinicas = oculto
            consulta.presion_arterial = None
            consulta.temperatura = None
            consulta.pulso = None
            for diag in consulta.diagnosticos:
                diag.descripcion = oculto
                diag.codigo_cie10 = "---"
                diag.tratamientos = []
            consulta.recetas = []
            consulta.recetas_pediatricas = []
            consulta.somatometria = None
            if consulta.hospitalizacion:
                consulta.hospitalizacion.motivo_ingreso = oculto
            for exam in consulta.examenes_laboratorio:
                exam.conclusiones_diagnosticas = oculto
                exam.observaciones_tecnicas = oculto
                for param in exam.parametros:
                    param.valor_resultado = "***"
                    param.interpretacion_alerta = "RESTRINGIDO"
            for proc in consulta.procedimientos_dentales:
                # La secretaria necesita el costo para cobrar, pero no las notas clínicas.
                proc.observaciones = oculto
        return clinical_record
