"""
MongoDB Database Adapter for Laboratorio Clínico.
Hexagonal Architecture Adapter implementing ClinicalRepositoryPort.
Optimized for dynamic, heterogeneous analytical exam results, critical value alerts,
and flexible document schemas (referencing patients and embedding test parameters).
"""

import time
import pymongo
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timezone
from .base_adapter import BaseClinicalAdapter
from .simulated_engines import SimulatedMongoDBEngine
from ..config import Config
from ...domain.entities import (
    InstitutionType,
    DatabaseEngine,
    UserRole,
    Patient,
    UnifiedClinicalRecord,
    Consultation,
    Appointment,
    Diagnosis,
    LabExamResult,
    LabParameter
)


class MongoDBAdapter(BaseClinicalAdapter):
    def __init__(self, config: Config, simulated_engine: Optional[SimulatedMongoDBEngine] = None):
        self.config = config
        self.simulated = simulated_engine or SimulatedMongoDBEngine()
        self.is_live = False
        self._init_connection()

    def _init_connection(self):
        if self.config.ENGINE_MODE == "simulated":
            self.is_live = False
            return

        try:
            client = pymongo.MongoClient(self.config.MONGO_URI, serverSelectionTimeoutMS=2000)
            client.server_info()
            self.is_live = True
        except Exception:
            self.is_live = False

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.LABORATORIO_CLINICO

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.MONGODB

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        status = "online" if self.is_live else "simulated_active"
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "institucion": "Laboratorio Clínico",
            "motor": "MongoDB (Documental NoSQL)",
            "base_datos": "laboratorio_clinico",
            "modo": "LIVE (Conexión Real)" if self.is_live else "SIMULATED (Motor Documental en Memoria)",
            "estado": status,
            "latencia_ms": latency_ms,
            "total_pacientes": len(self.simulated.collections["pacientes"]),
            "total_ordenes": len(self.simulated.collections["ordenes"]),
            "total_resultados_dinamicos": len(self.simulated.collections["resultados"]),
            "modelo_documental": "Pacientes referenciados + Parámetros analíticos embebidos"
        }

    def create_patient(self, patient_data: Dict[str, Any]) -> Patient:
        raw = self.simulated.insert_patient(patient_data)
        return self._to_patient_domain(raw)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        for p in self.simulated.collections["pacientes"]:
            if p["id_paciente"] == patient_id:
                return self._to_patient_domain(p)
        return None

    def search_patients(self, query: str) -> List[Patient]:
        q = query.lower().strip()
        results = []
        for p in self.simulated.collections["pacientes"]:
            nombre = f"{p['nombres']} {p['apellidos']}".lower()
            dpi = p["dpi"].lower()
            if q in nombre or q in dpi or q == str(p["id_paciente"]):
                results.append(self._to_patient_domain(p))
        return results

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        for p in self.simulated.collections["pacientes"]:
            if p["id_paciente"] == patient_id:
                for k, v in updates.items():
                    if k in p and k != "id_paciente":
                        p[k] = v
                return self._to_patient_domain(p)
        raise ValueError(f"Paciente con id {patient_id} no encontrado en MongoDB")

    def deactivate_patient(self, patient_id: int, motivo_baja: str) -> Dict[str, Any]:
        found = False
        for p in self.simulated.collections["pacientes"]:
            if p["id_paciente"] == patient_id:
                p["estado"] = "dado_de_baja"
                found = True
                break
        if not found:
            raise ValueError(f"Paciente con id {patient_id} no existe")

        for h in self.simulated.collections["historiales_clinicos"]:
            if h["id_paciente"] == patient_id:
                h["estado"] = "archivado"
                h["motivo_baja"] = motivo_baja
                h["fecha_ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()

        return {
            "id_paciente": patient_id,
            "estado": "archivado",
            "motivo_baja": motivo_baja,
            "motor": "MongoDB",
            "mensaje": "Expediente de laboratorio archivado exitosamente."
        }

    def create_appointment(self, appointment_data: Dict[str, Any]) -> Appointment:
        new_id = self.simulated._next_id("ordenes")
        cita_dict = {
            "id_cita": new_id,
            "id_paciente": appointment_data["id_paciente"],
            "id_profesional": 1,
            "fecha_hora_programada": appointment_data.get("fecha_hora_programada", datetime.now(timezone.utc).isoformat()),
            "motivo_consulta": appointment_data.get("motivo_consulta", "Toma de muestras clínicas"),
            "estado_cita": "programada",
            "fecha_creacion": datetime.now(timezone.utc).isoformat()
        }
        return self._to_appointment_domain(cita_dict)

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        res = []
        for o in self.simulated.collections["ordenes"]:
            if patient_id is None or o["id_paciente"] == patient_id:
                res.append(Appointment(
                    id_cita=o["id_orden"],
                    id_paciente=o["id_paciente"],
                    id_profesional=1,
                    profesional_nombre="Laboratorio Central",
                    fecha_hora_programada=o["fecha_hora_ingreso"],
                    motivo_consulta=o["diagnostico_presuntivo"],
                    estado_cita=o["estado_orden"],
                    fecha_creacion=o["fecha_hora_ingreso"]
                ))
        return res

    def register_consultation(self, consultation_data: Dict[str, Any]) -> Consultation:
        """
        En Laboratorio Clínico, una 'consulta' equivale al procesamiento analítico
        de una orden de laboratorio, generando trazabilidad de muestra y resultados dinámicos.
        """
        res = self.simulated.insert_lab_order_and_results(consultation_data)
        r_doc = res["resultado"]

        param_objects = [
            LabParameter(
                nombre_parametro=p["nombre_parametro"],
                valor_resultado=p["valor_resultado"],
                unidad_medida=p["unidad_medida"],
                rango_referencia_min=p.get("rango_referencia_min"),
                rango_referencia_max=p.get("rango_referencia_max"),
                interpretacion_alerta=p.get("interpretacion_alerta", "NORMAL")
            )
            for p in r_doc["parametros"]
        ]

        lab_exam = LabExamResult(
            id_resultado=r_doc["id_resultado"],
            id_orden=r_doc["id_orden"],
            codigo_examen=r_doc["codigo_examen"],
            nombre_examen=r_doc["nombre_examen"],
            fecha_hora_analisis=r_doc["fecha_hora_analisis"],
            fecha_hora_validacion=r_doc.get("fecha_hora_validacion"),
            estado=r_doc["estado"],
            alertas_criticas=r_doc["alertas_criticas"],
            observaciones_tecnicas=r_doc["observaciones_tecnicas"],
            conclusiones_diagnosticas=r_doc["conclusiones_diagnosticas"],
            parametros=param_objects
        )

        diag = Diagnosis(
            id_diagnostico=r_doc["id_resultado"],
            codigo_cie10="Z01.7",
            descripcion=f"Informe de Laboratorio: {r_doc['nombre_examen']} - {r_doc['conclusiones_diagnosticas']}",
            tipo="principal",
            fecha_diagnostico=r_doc["fecha_hora_analisis"][:10]
        )

        return Consultation(
            id_consulta=r_doc["id_resultado"],
            id_cita=r_doc["id_orden"],
            fecha_hora_atencion=r_doc["fecha_hora_analisis"],
            motivo=r_doc["nombre_examen"],
            notas_clinicas=r_doc["conclusiones_diagnosticas"],
            tipo_consulta="laboratorio_analitico",
            diagnosticos=[diag],
            examenes_laboratorio=[lab_exam]
        )

    def get_clinical_history(
        self, patient_id: int, user_role: UserRole = UserRole.LABORATORISTA
    ) -> Optional[UnifiedClinicalRecord]:
        patient = self.get_patient(patient_id)
        if not patient:
            return None

        hist_doc = None
        for h in self.simulated.collections["historiales_clinicos"]:
            if h["id_paciente"] == patient_id:
                hist_doc = h
                break

        if not hist_doc:
            hist_doc = {
                "id_historial": 1,
                "fecha_apertura": patient.fecha_registro,
                "fecha_ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
                "estado": "activo",
                "motivo_baja": None
            }

        citas_list = self.get_appointments(patient_id)

        # Buscar todos los resultados de este paciente
        consultas_list = []
        for r in self.simulated.collections["resultados"]:
            if r["id_paciente"] == patient_id:
                params = [
                    LabParameter(
                        nombre_parametro=p["nombre_parametro"],
                        valor_resultado=p["valor_resultado"],
                        unidad_medida=p["unidad_medida"],
                        rango_referencia_min=p.get("rango_referencia_min"),
                        rango_referencia_max=p.get("rango_referencia_max"),
                        interpretacion_alerta=p.get("interpretacion_alerta", "NORMAL")
                    )
                    for p in r["parametros"]
                ]

                lab_exam = LabExamResult(
                    id_resultado=r["id_resultado"],
                    id_orden=r["id_orden"],
                    codigo_examen=r["codigo_examen"],
                    nombre_examen=r["nombre_examen"],
                    fecha_hora_analisis=r["fecha_hora_analisis"],
                    fecha_hora_validacion=r.get("fecha_hora_validacion"),
                    estado=r["estado"],
                    alertas_criticas=r["alertas_criticas"],
                    observaciones_tecnicas=r["observaciones_tecnicas"],
                    conclusiones_diagnosticas=r["conclusiones_diagnosticas"],
                    parametros=params
                )

                diag = Diagnosis(
                    id_diagnostico=r["id_resultado"],
                    codigo_cie10="Z01.7",
                    descripcion=f"Resultado: {r['nombre_examen']}",
                    tipo="principal",
                    fecha_diagnostico=r["fecha_hora_analisis"][:10]
                )

                consultas_list.append(Consultation(
                    id_consulta=r["id_resultado"],
                    id_cita=r["id_orden"],
                    fecha_hora_atencion=r["fecha_hora_analisis"],
                    motivo=r["nombre_examen"],
                    notas_clinicas=r["conclusiones_diagnosticas"],
                    tipo_consulta="laboratorio_analitico",
                    diagnosticos=[diag],
                    examenes_laboratorio=[lab_exam]
                ))

        history = UnifiedClinicalRecord(
            id_historial=hist_doc["id_historial"],
            id_paciente=patient_id,
            paciente=patient,
            fecha_apertura=hist_doc["fecha_apertura"],
            fecha_ultima_actualizacion=hist_doc["fecha_ultima_actualizacion"],
            estado=hist_doc["estado"],
            motivo_baja=hist_doc.get("motivo_baja"),
            institucion=InstitutionType.LABORATORIO_CLINICO,
            motor=DatabaseEngine.MONGODB,
            consultas=consultas_list,
            citas=citas_list,
            datos_adicionales={
                "alertas_criticas_activas": sum(1 for c in consultas_list for e in c.examenes_laboratorio if e.alertas_criticas)
            }
        )

        return self.apply_security_filter(history, user_role)

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        resultados = [r for r in self.simulated.collections["resultados"] if r["id_paciente"] == patient_id]
        muestras = [m for m in self.simulated.collections["muestras"]]
        return {
            "institucion": "Laboratorio Clínico",
            "motor": "MongoDB",
            "examenes_realizados": resultados,
            "muestras": muestras
        }

    # Helpers
    def _to_patient_domain(self, d: Dict[str, Any]) -> Patient:
        ce = d.get("contacto_emergencia", {})
        return Patient(
            id_paciente=d["id_paciente"],
            nombres=d["nombres"],
            apellidos=d["apellidos"],
            fecha_nacimiento=d["fecha_nacimiento"],
            sexo=d["sexo"],
            dpi=d["dpi"],
            direccion=d.get("direccion", ""),
            telefono=d.get("telefono", ""),
            correo_electronico=d.get("correo_electronico", ""),
            tipo_sangre=d.get("tipo_sangre", "O+"),
            contacto_emergencia_nombre=ce.get("nombre", "") if isinstance(ce, dict) else "",
            contacto_emergencia_telefono=ce.get("telefono", "") if isinstance(ce, dict) else "",
            fecha_registro=d.get("fecha_registro", date.today().isoformat()),
            estado=d.get("estado", "activo")
        )

    def _to_appointment_domain(self, d: Dict[str, Any]) -> Appointment:
        return Appointment(
            id_cita=d["id_cita"],
            id_paciente=d["id_paciente"],
            id_profesional=d.get("id_profesional", 1),
            profesional_nombre="Laboratorio Central",
            fecha_hora_programada=d["fecha_hora_programada"],
            motivo_consulta=d["motivo_consulta"],
            estado_cita=d["estado_cita"],
            fecha_creacion=d["fecha_creacion"]
        )
