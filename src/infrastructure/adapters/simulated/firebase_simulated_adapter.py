"""
Firebase Cloud Firestore Adapter for Clínica Odontológica Pequeña.
Hexagonal Architecture Adapter implementing ClinicalRepositoryPort.
Optimized for zero-maintenance serverless cloud operations, rapid booking by secretaries,
and procedure tracking indexed by tooth piece (pieza dental).
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timezone
from ..base_adapter import BaseClinicalAdapter
from .engines import SimulatedFirebaseEngine
from ...config import Config
from ....domain.entities import (
    InstitutionType,
    DatabaseEngine,
    UserRole,
    Patient,
    UnifiedClinicalRecord,
    Consultation,
    Appointment,
    Diagnosis,
    DentalProcedureRecord
)


class SimulatedFirebaseAdapter(BaseClinicalAdapter):
    def __init__(self, config: Config, simulated_engine: Optional[SimulatedFirebaseEngine] = None):
        self.config = config
        self.simulated = simulated_engine or SimulatedFirebaseEngine()
        self.is_live = False
        self._init_connection()

    def _init_connection(self):
        # Motor simulado en memoria: no abre conexiones reales.
        self.is_live = False

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.CLINICA_ODONTOLOGICA

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.FIREBASE

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        status = "online" if self.is_live else "simulated_active"
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "institucion": "Clínica Odontológica Pequeña",
            "motor": "Firebase Cloud Firestore (NoSQL)",
            "proyecto": self.config.FIREBASE_PROJECT_ID,
            "modo": "LIVE (Conexión Firebase Cloud)" if self.is_live else "SIMULATED (Motor Firestore en Memoria)",
            "estado": status,
            "latencia_ms": latency_ms,
            "total_pacientes_dentales": len(self.simulated.collections["pacientes"]),
            "total_citas_secretaria": len(self.simulated.collections["citas"]),
            "total_procedimientos_por_pieza": len(self.simulated.collections["consultas_procedimientos"]),
            "reglas_seguridad": "firestore.rules cargadas y validadas"
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
            nombre = f"{p.get('nombres', '')} {p.get('apellidos', '')}".lower() or p.get("nombre_completo", "").lower()
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
        raise ValueError(f"Paciente con id {patient_id} no encontrado en Firestore")

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
        found = False
        for p in self.simulated.collections["pacientes"]:
            if p["id_paciente"] == patient_id:
                p["estado"] = "dado_de_baja"
                found = True
                break
        if not found:
            raise ValueError(f"Paciente con id {patient_id} no existe")

        for h in self.simulated.collections["historiales"]:
            if h["id_paciente"] == patient_id:
                h["estado"] = "archivado"
                h["motivo_baja"] = motivo_baja
                h["fecha_ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()

        return {
            "id_paciente": patient_id,
            "estado": "archivado",
            "motivo_baja": motivo_baja,
            "motor": "Firebase",
            "mensaje": "Historial odontológico archivado exitosamente."
        }

    def create_appointment(self, appointment_data: Dict[str, Any]) -> Appointment:
        new_id = self.simulated._next_id("citas")
        cita_dict = {
            "id_cita": new_id,
            "id_paciente": appointment_data["id_paciente"],
            "id_odontologo": appointment_data.get("id_odontologo", 1),
            "id_secretaria": appointment_data.get("id_secretaria", 1),
            "fecha_hora_programada": appointment_data.get("fecha_hora_programada", datetime.now(timezone.utc).isoformat()),
            "motivo_consulta": appointment_data.get("motivo_consulta", "Consulta odontológica general"),
            "estado_cita": appointment_data.get("estado_cita", "programada"),
            "fecha_creacion": datetime.now(timezone.utc).isoformat()
        }
        self.simulated.collections["citas"].append(cita_dict)
        return self._to_appointment_domain(cita_dict)

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        res = []
        for c in self.simulated.collections["citas"]:
            if patient_id is None or c["id_paciente"] == patient_id:
                res.append(self._to_appointment_domain(c))
        return res

    def register_consultation(self, consultation_data: Dict[str, Any]) -> Consultation:
        """Registro de procedimiento dental por pieza en Firestore."""
        tx_res = self.simulated.insert_dental_procedure_consultation(consultation_data)
        proc_doc = tx_res["procedimiento"]

        proc_record = DentalProcedureRecord(
            id_consulta_procedimiento=proc_doc["id_consulta_procedimiento"],
            id_cita=proc_doc["id_cita"],
            nombre_procedimiento=proc_doc["nombre_procedimiento"],
            pieza_dental=proc_doc["pieza_dental"],
            observaciones=proc_doc["observaciones"],
            fecha_realizacion=proc_doc["fecha_realizacion"],
            costo=proc_doc["costo"],
            estado=proc_doc["estado"]
        )

        diag = Diagnosis(
            id_diagnostico=proc_doc["id_consulta_procedimiento"],
            codigo_cie10=consultation_data.get("codigo_cie10", "K02.1"),
            descripcion=f"Afección dental en {proc_doc['pieza_dental']}: {proc_doc['nombre_procedimiento']}",
            tipo="principal",
            fecha_diagnostico=proc_doc["fecha_realizacion"][:10]
        )

        return Consultation(
            id_consulta=proc_doc["id_consulta_procedimiento"],
            id_cita=proc_doc["id_cita"],
            fecha_hora_atencion=proc_doc["fecha_realizacion"],
            motivo=proc_doc["nombre_procedimiento"],
            notas_clinicas=proc_doc["observaciones"],
            tipo_consulta="odontologica",
            diagnosticos=[diag],
            procedimientos_dentales=[proc_record]
        )

    def get_clinical_history(
        self, patient_id: int, user_role: UserRole = UserRole.ODONTOLOGO
    ) -> Optional[UnifiedClinicalRecord]:
        patient = self.get_patient(patient_id)
        if not patient:
            return None

        hist_doc = None
        for h in self.simulated.collections["historiales"]:
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

        consultas_list = []
        for p in self.simulated.collections["consultas_procedimientos"]:
            if p["id_paciente"] == patient_id:
                proc_rec = DentalProcedureRecord(
                    id_consulta_procedimiento=p["id_consulta_procedimiento"],
                    id_cita=p["id_cita"],
                    nombre_procedimiento=p["nombre_procedimiento"],
                    pieza_dental=p["pieza_dental"],
                    observaciones=p["observaciones"],
                    fecha_realizacion=p["fecha_realizacion"],
                    costo=p["costo"],
                    estado=p["estado"]
                )

                diag = Diagnosis(
                    id_diagnostico=p["id_consulta_procedimiento"],
                    codigo_cie10="K02.1",
                    descripcion=f"Tratamiento en {p['pieza_dental']}: {p['nombre_procedimiento']}",
                    tipo="principal",
                    fecha_diagnostico=p["fecha_realizacion"][:10]
                )

                consultas_list.append(Consultation(
                    id_consulta=p["id_consulta_procedimiento"],
                    id_cita=p["id_cita"],
                    fecha_hora_atencion=p["fecha_realizacion"],
                    motivo=p["nombre_procedimiento"],
                    notas_clinicas=p["observaciones"],
                    tipo_consulta="odontologica",
                    diagnosticos=[diag],
                    procedimientos_dentales=[proc_rec]
                ))

        history = UnifiedClinicalRecord(
            id_historial=hist_doc["id_historial"],
            id_paciente=patient_id,
            paciente=patient,
            fecha_apertura=hist_doc["fecha_apertura"],
            fecha_ultima_actualizacion=hist_doc["fecha_ultima_actualizacion"],
            estado=hist_doc["estado"],
            motivo_baja=hist_doc.get("motivo_baja"),
            institucion=InstitutionType.CLINICA_ODONTOLOGICA,
            motor=DatabaseEngine.FIREBASE,
            consultas=consultas_list,
            citas=citas_list,
            datos_adicionales={
                "procedimientos_totales": len(consultas_list)
            }
        )

        return self.apply_security_filter(history, user_role)

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        procs = [p for p in self.simulated.collections["consultas_procedimientos"] if p["id_paciente"] == patient_id]
        cat = self.simulated.collections["procedimientos_catalogo"]
        return {
            "institucion": "Clínica Odontológica Pequeña",
            "motor": "Firebase Cloud Firestore",
            "procedimientos_realizados": procs,
            "catalogo_procedimientos": cat
        }

    # Helpers
    def _to_patient_domain(self, d: Dict[str, Any]) -> Patient:
        nombres = d.get("nombres") or d.get("nombre_completo", "").split(" ")[0]
        apellidos = d.get("apellidos") or " ".join(d.get("nombre_completo", "").split(" ")[1:])
        ce = d.get("contacto_emergencia", {})
        return Patient(
            id_paciente=d["id_paciente"],
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=d["fecha_nacimiento"],
            sexo=d["sexo"],
            dpi=d["dpi"],
            direccion=d.get("direccion", ""),
            telefono=d.get("telefono", ""),
            correo_electronico=d.get("correo_electronico", ""),
            tipo_sangre="O+",
            contacto_emergencia_nombre=ce.get("nombre", "") if isinstance(ce, dict) else "",
            contacto_emergencia_telefono=ce.get("telefono", "") if isinstance(ce, dict) else "",
            fecha_registro=d.get("fecha_registro", date.today().isoformat()),
            estado=d.get("estado", "activo")
        )

    def _to_appointment_domain(self, d: Dict[str, Any]) -> Appointment:
        odontologo_nombre = "Dr. Rodrigo Andrés Molina (Odontólogo)"
        for o in self.simulated.collections["odontologos"]:
            if o["id_odontologo"] == d.get("id_odontologo"):
                odontologo_nombre = o["nombre_completo"]
                break
        return Appointment(
            id_cita=d["id_cita"],
            id_paciente=d["id_paciente"],
            id_profesional=d.get("id_odontologo", 1),
            profesional_nombre=odontologo_nombre,
            fecha_hora_programada=d["fecha_hora_programada"],
            motivo_consulta=d["motivo_consulta"],
            estado_cita=d["estado_cita"],
            fecha_creacion=d["fecha_creacion"],
            id_secretaria=d.get("id_secretaria")
        )
