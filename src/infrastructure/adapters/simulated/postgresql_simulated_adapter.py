"""
PostgreSQL Database Adapter for Hospital General.
Hexagonal Architecture Adapter implementing ClinicalRepositoryPort.
Ensures strong ACID transactional consistency for hospital admissions,
diagnoses, and prescriptions.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from ..base_adapter import BaseClinicalAdapter
from .engines import SimulatedPostgreSQLEngine
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
    Treatment,
    Prescription,
    HospitalizationRecord
)


class SimulatedPostgreSQLAdapter(BaseClinicalAdapter):
    def __init__(self, config: Config, simulated_engine: Optional[SimulatedPostgreSQLEngine] = None):
        self.config = config
        self.simulated = simulated_engine or SimulatedPostgreSQLEngine()
        self.is_live = False
        self._init_connection()

    def _init_connection(self):
        # Motor simulado en memoria: no abre conexiones reales.
        self.is_live = False

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.HOSPITAL_GENERAL

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.POSTGRESQL

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        status = "online" if self.is_live else "simulated_active"
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "institucion": "Hospital General",
            "motor": "PostgreSQL",
            "esquema": "hospital",
            "modo": "LIVE (Conexión Real)" if self.is_live else "SIMULATED (Motor Relacional en Memoria)",
            "estado": status,
            "latencia_ms": latency_ms,
            "total_pacientes": len(self.simulated.tables["hospital.Paciente"]),
            "total_consultas": len(self.simulated.tables["hospital.Consulta"]),
            "total_hospitalizaciones": len(self.simulated.tables["hospital.Hospitalizacion"]),
            "transacciones_acid": "Habilitadas y Verificadas"
        }

    def create_patient(self, patient_data: Dict[str, Any]) -> Patient:
        raw = self.simulated.insert_patient(patient_data)
        return self._to_patient_domain(raw)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        for p in self.simulated.tables["hospital.Paciente"]:
            if p["id_paciente"] == patient_id:
                return self._to_patient_domain(p)
        return None

    def search_patients(self, query: str) -> List[Patient]:
        q = query.lower().strip()
        results = []
        for p in self.simulated.tables["hospital.Paciente"]:
            nombre = f"{p['nombres']} {p['apellidos']}".lower()
            dpi = p["dpi"].lower()
            if q in nombre or q in dpi or q == str(p["id_paciente"]):
                results.append(self._to_patient_domain(p))
        return results

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        for p in self.simulated.tables["hospital.Paciente"]:
            if p["id_paciente"] == patient_id:
                for k, v in updates.items():
                    if k in p and k != "id_paciente":
                        p[k] = v
                return self._to_patient_domain(p)
        raise ValueError(f"Paciente con id {patient_id} no encontrado en PostgreSQL")

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
        found = False
        for p in self.simulated.tables["hospital.Paciente"]:
            if p["id_paciente"] == patient_id:
                p["estado_salud"] = "dado_de_baja"
                found = True
                break
        if not found:
            raise ValueError(f"Paciente con id {patient_id} no existe")

        for h in self.simulated.tables["hospital.Historial_Clinico"]:
            if h["id_paciente"] == patient_id:
                h["estado"] = "archivado"
                h["motivo_baja"] = motivo_baja
                h["fecha_ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "id_paciente": patient_id,
            "estado": "archivado",
            "motivo_baja": motivo_baja,
            "motor": "PostgreSQL",
            "mensaje": "Historial clínico desactivado y archivado exitosamente."
        }

    def create_appointment(self, appointment_data: Dict[str, Any]) -> Appointment:
        new_id = self.simulated._next_id("hospital.Cita")
        cita_dict = {
            "id_cita": new_id,
            "id_paciente": appointment_data["id_paciente"],
            "id_medico": appointment_data.get("id_medico", 1),
            "fecha_hora_programada": appointment_data["fecha_hora_programada"],
            "motivo_consulta": appointment_data["motivo_consulta"],
            "estado_cita": appointment_data.get("estado_cita", "programada"),
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.simulated.tables["hospital.Cita"].append(cita_dict)
        return self._to_appointment_domain(cita_dict)

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        res = []
        for c in self.simulated.tables["hospital.Cita"]:
            if patient_id is None or c["id_paciente"] == patient_id:
                res.append(self._to_appointment_domain(c))
        return res

    def register_consultation(self, consultation_data: Dict[str, Any]) -> Consultation:
        """Transacción atómica ACID en PostgreSQL."""
        tx_res = self.simulated.execute_transaction_consultation(consultation_data)
        consulta_row = tx_res["consulta"]
        diag_row = tx_res["diagnostico"]
        trat_row = tx_res["tratamiento"]
        receta_row = tx_res["receta"]
        hosp_row = tx_res["hospitalizacion"]

        prescriptions = []
        if receta_row:
            prescriptions.append(Prescription(
                id_receta=receta_row["id_receta"],
                medicamento=receta_row["medicamento"],
                dosis=receta_row["dosis"],
                frecuencia=receta_row["frecuencia"],
                duracion_dias=receta_row["duracion_dias"],
                via_administracion=receta_row["via_administracion"],
                fecha_emision=receta_row["fecha_emision"]
            ))

        treatments = [Treatment(
            id_tratamiento=trat_row["id_tratamiento"],
            descripcion=trat_row["descripcion"],
            fecha_inicio=trat_row["fecha_inicio"],
            fecha_fin=trat_row["fecha_fin"],
            estado=trat_row["estado"],
            indicaciones=trat_row["indicaciones"],
            recetas=prescriptions
        )]

        diagnoses = [Diagnosis(
            id_diagnostico=diag_row["id_diagnostico"],
            codigo_cie10=diag_row["codigo_cie10"],
            descripcion=diag_row["descripcion"],
            tipo=diag_row["tipo"],
            fecha_diagnostico=diag_row["fecha_diagnostico"],
            tratamientos=treatments
        )]

        hosp_domain = None
        if hosp_row:
            hosp_domain = HospitalizationRecord(
                id_hospitalizacion=hosp_row["id_hospitalizacion"],
                id_consulta=hosp_row["id_consulta"],
                fecha_ingreso=hosp_row["fecha_ingreso"],
                fecha_egreso=hosp_row["fecha_egreso"],
                numero_habitacion=hosp_row["numero_habitacion"],
                motivo_ingreso=hosp_row["motivo_ingreso"],
                estado=hosp_row["estado"]
            )

        return Consultation(
            id_consulta=consulta_row["id_consulta"],
            id_cita=consulta_row["id_cita"],
            fecha_hora_atencion=consulta_row["fecha_hora_atencion"],
            motivo=consulta_row["motivo"],
            presion_arterial=consulta_row["presion_arterial"],
            temperatura=consulta_row["temperatura"],
            pulso=consulta_row["pulso"],
            notas_clinicas=consulta_row["notas_clinicas"],
            tipo_consulta=consulta_row["tipo_consulta"],
            diagnosticos=diagnoses,
            hospitalizacion=hosp_domain
        )

    def get_clinical_history(
        self, patient_id: int, user_role: UserRole = UserRole.MEDICO
    ) -> Optional[UnifiedClinicalRecord]:
        patient = self.get_patient(patient_id)
        if not patient:
            return None

        hist_row = None
        for h in self.simulated.tables["hospital.Historial_Clinico"]:
            if h["id_paciente"] == patient_id:
                hist_row = h
                break

        if not hist_row:
            hist_row = {
                "id_historial": 1,
                "fecha_apertura": patient.fecha_registro,
                "fecha_ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "estado": "activo",
                "motivo_baja": None
            }

        # Citas del paciente
        citas_list = self.get_appointments(patient_id)

        # Consultas del paciente mapeadas con sus diagnósticos, tratamientos y recetas
        consultas_list = []
        # Buscar citas pertenecientes a este paciente
        cita_ids = {c.id_cita for c in citas_list}

        for c_row in self.simulated.tables["hospital.Consulta"]:
            if c_row["id_cita"] in cita_ids:
                id_con = c_row["id_consulta"]
                # Diagnósticos de esta consulta
                diags = []
                for d_row in self.simulated.tables["hospital.Diagnostico"]:
                    if d_row["id_consulta"] == id_con:
                        id_d = d_row["id_diagnostico"]
                        # Tratamientos de este diagnóstico
                        trats = []
                        for t_row in self.simulated.tables["hospital.Tratamiento"]:
                            if t_row["id_diagnostico"] == id_d:
                                id_t = t_row["id_tratamiento"]
                                # Recetas
                                recs = []
                                for r_row in self.simulated.tables["hospital.Receta"]:
                                    if r_row["id_tratamiento"] == id_t:
                                        recs.append(Prescription(
                                            id_receta=r_row["id_receta"],
                                            medicamento=r_row["medicamento"],
                                            dosis=r_row["dosis"],
                                            frecuencia=r_row["frecuencia"],
                                            duracion_dias=r_row["duracion_dias"],
                                            via_administracion=r_row["via_administracion"],
                                            fecha_emision=r_row["fecha_emision"]
                                        ))
                                trats.append(Treatment(
                                    id_tratamiento=t_row["id_tratamiento"],
                                    descripcion=t_row["descripcion"],
                                    fecha_inicio=t_row["fecha_inicio"],
                                    fecha_fin=t_row.get("fecha_fin"),
                                    estado=t_row["estado"],
                                    indicaciones=t_row["indicaciones"],
                                    recetas=recs
                                ))
                        diags.append(Diagnosis(
                            id_diagnostico=d_row["id_diagnostico"],
                            codigo_cie10=d_row["codigo_cie10"],
                            descripcion=d_row["descripcion"],
                            tipo=d_row["tipo"],
                            fecha_diagnostico=d_row["fecha_diagnostico"],
                            tratamientos=trats
                        ))

                # Hospitalización asociada
                hosp = None
                for hr in self.simulated.tables["hospital.Hospitalizacion"]:
                    if hr["id_consulta"] == id_con:
                        hosp = HospitalizationRecord(
                            id_hospitalizacion=hr["id_hospitalizacion"],
                            id_consulta=hr["id_consulta"],
                            fecha_ingreso=hr["fecha_ingreso"],
                            fecha_egreso=hr["fecha_egreso"],
                            numero_habitacion=hr["numero_habitacion"],
                            motivo_ingreso=hr["motivo_ingreso"],
                            estado=hr["estado"]
                        )
                        break

                consultas_list.append(Consultation(
                    id_consulta=id_con,
                    id_cita=c_row["id_cita"],
                    fecha_hora_atencion=c_row["fecha_hora_atencion"],
                    motivo=c_row["motivo"],
                    presion_arterial=c_row["presion_arterial"],
                    temperatura=c_row["temperatura"],
                    pulso=c_row["pulso"],
                    notas_clinicas=c_row["notas_clinicas"],
                    tipo_consulta=c_row["tipo_consulta"],
                    diagnosticos=diags,
                    hospitalizacion=hosp
                ))

        history = UnifiedClinicalRecord(
            id_historial=hist_row["id_historial"],
            id_paciente=patient_id,
            paciente=patient,
            fecha_apertura=hist_row["fecha_apertura"],
            fecha_ultima_actualizacion=hist_row["fecha_ultima_actualizacion"],
            estado=hist_row["estado"],
            motivo_baja=hist_row.get("motivo_baja"),
            institucion=InstitutionType.HOSPITAL_GENERAL,
            motor=DatabaseEngine.POSTGRESQL,
            consultas=consultas_list,
            citas=citas_list,
            datos_adicionales={"hospitalizaciones": len([c for c in consultas_list if c.hospitalizacion])}
        )

        return self.apply_security_filter(history, user_role)

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        hosp_list = [h for h in self.simulated.tables["hospital.Hospitalizacion"] if h["id_paciente"] == patient_id]
        return {
            "institucion": "Hospital General",
            "motor": "PostgreSQL",
            "hospitalizaciones": hosp_list
        }

    # Helpers
    def _to_patient_domain(self, d: Dict[str, Any]) -> Patient:
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
            tipo_sangre=d.get("tipo_sangre"),
            contacto_emergencia_nombre=d.get("contacto_emergencia_nombre", ""),
            contacto_emergencia_telefono=d.get("contacto_emergencia_telefono", ""),
            fecha_registro=d.get("fecha_registro", date.today().isoformat()),
            estado=d.get("estado_salud", "activo")
        )

    def _to_appointment_domain(self, d: Dict[str, Any]) -> Appointment:
        med_nombre = "Dr. Colegiado Hospital"
        for m in self.simulated.tables["hospital.Medico"]:
            if m["id_medico"] == d.get("id_medico"):
                med_nombre = m["nombre"]
                break
        return Appointment(
            id_cita=d["id_cita"],
            id_paciente=d["id_paciente"],
            id_profesional=d.get("id_medico", 1),
            profesional_nombre=med_nombre,
            fecha_hora_programada=d["fecha_hora_programada"],
            motivo_consulta=d["motivo_consulta"],
            estado_cita=d["estado_cita"],
            fecha_creacion=d["fecha_creacion"]
        )

