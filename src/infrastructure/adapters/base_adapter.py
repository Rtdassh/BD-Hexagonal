"""
Base Adapter implementing common filtering, role-based access control,
and domain mapping for all four database adapters.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from ...domain.entities import (
    InstitutionType,
    DatabaseEngine,
    UserRole,
    InfoClassification,
    Patient,
    UnifiedClinicalRecord,
    Consultation,
    Appointment
)
from ...domain.ports import ClinicalRepositoryPort


class BaseClinicalAdapter(ClinicalRepositoryPort):
    """
    Common foundational adapter enforcing security classifications
    and standard clinical record formatting.
    """

    def apply_security_filter(
        self, clinical_record: UnifiedClinicalRecord, user_role: UserRole
    ) -> UnifiedClinicalRecord:
        """
        Filters information based on the 3 classification levels:
          - Public: Visible to all
          - Confidential: Visible to staff (secretaries, doctors, admins)
          - Restricted: Visible ONLY to clinical staff (doctors, biochemists, pediatricians, dentists)
        """
        # Secretarias no tienen acceso a información clínica restringida
        if user_role == UserRole.SECRETARIA:
            for consulta in clinical_record.consultas:
                # Ocultar o anonimizar notas clínicas, diagnósticos y tratamientos
                consulta.notas_clinicas = "[INFORMACIÓN RESTRINGIDA - Requiere rol clínico autorizado]"
                for diag in consulta.diagnosticos:
                    diag.descripcion = "[DIAGNÓSTICO RESTRINGIDO - Ley de Confidencialidad Médica]"
                    diag.codigo_cie10 = "---"
                    diag.tratamientos = []
                # Ocultar recetas
                consulta.recetas_pediatricas = []
                # Ocultar hospitalizaciones
                if consulta.hospitalizacion:
                    consulta.hospitalizacion.motivo_ingreso = "[RESTRINGIDO]"
                # Ocultar valores de laboratorio
                for exam in consulta.examenes_laboratorio:
                    exam.conclusiones_diagnosticas = "[RESTRINGIDO - Confidencialidad de Laboratorio]"
                    for param in exam.parametros:
                        param.valor_resultado = "[CONFIDENCIAL]"
                        param.interpretacion_alerta = "RESTRINGIDO"
                # Ocultar costos o diagnósticos dentales
                for proc in consulta.procedimientos_dentales:
                    proc.observaciones = "[RESTRINGIDO]"
                    proc.costo = 0.0

        return clinical_record

