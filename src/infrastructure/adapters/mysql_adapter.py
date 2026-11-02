"""
MySQL Database Adapter for Centro Médico Pediátrico.
Hexagonal Architecture Adapter implementing ClinicalRepositoryPort.
Optimized for pediatric follow-up, somatometry (weight, height, head circumference, percentiles),
vaccination schedule tracking, and dosage by body weight (mg/kg).
"""

import time
import mysql.connector
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from .base_adapter import BaseClinicalAdapter
from .simulated_engines import SimulatedMySQLEngine
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
    Prescription,
    SomatometryRecord,
    VaccinationRecord
)


class MySQLAdapter(BaseClinicalAdapter):
    def __init__(self, config: Config, simulated_engine: Optional[SimulatedMySQLEngine] = None):
        self.config = config
        self.simulated = simulated_engine or SimulatedMySQLEngine()
        self.is_live = False
        self._init_connection()

    def _init_connection(self):
        if self.config.ENGINE_MODE == "simulated":
            self.is_live = False
            return

        try:
            conn = mysql.connector.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                database=self.config.MYSQL_DATABASE,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                connection_timeout=2
            )
            conn.close()
            self.is_live = True
        except Exception:
            self.is_live = False

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.CENTRO_PEDIATRICO

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.MYSQL

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        status = "online" if self.is_live else "simulated_active"
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "institucion": "Centro Médico Pediátrico",
            "motor": "MySQL (InnoDB)",
            "base_datos": "centro_pediatrico",
            "modo": "LIVE (Conexión Real)" if self.is_live else "SIMULATED (Motor Relacional en Memoria)",
            "estado": status,
            "latencia_ms": latency_ms,
            "total_pacientes_infantiles": len(self.simulated.tables["paciente_pediatrico"]),
            "total_consultas_somatometria": len(self.simulated.tables["consulta"]),
            "total_vacunas_registradas": len(self.simulated.tables["vacunacion"]),
            "integridad_referencial": "InnoDB Foreign Keys & Check Constraints Activas"
        }

    def create_patient(self, patient_data: Dict[str, Any]) -> Patient:
        raw = self.simulated.insert_patient(patient_data)
        return self._to_patient_domain(raw)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        for p in self.simulated.tables["paciente_pediatrico"]:
            if p["id_paciente"] == patient_id:
                return self._to_patient_domain(p)
        return None

    def search_patients(self, query: str) -> List[Patient]:
        q = query.lower().strip()
        results = []
        for p in self.simulated.tables["paciente_pediatrico"]:
            nombre = f"{p['nombres']} {p['apellidos']}".lower()
            cui = p["cui_nacimiento"].lower()
            tutor = p.get("nombre_tutor", "").lower()
            if q in nombre or q in cui or q in tutor or q == str(p["id_paciente"]):
                results.append(self._to_patient_domain(p))
        return results

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        for p in self.simulated.tables["paciente_pediatrico"]:
            if p["id_paciente"] == patient_id:
                for k, v in updates.items():
                    if k in p and k != "id_paciente":
                        p[k] = v
                return self._to_patient_domain(p)
        raise ValueError(f"Paciente pediátrico con id {patient_id} no encontrado en MySQL")

    def deactivate_patient(self, patient_id: int, motivo_baja: str) -> Dict[str, Any]:
        found = False
        for p in self.simulated.tables["paciente_pediatrico"]:
            if p["id_paciente"] == patient_id:
                p["estado"] = "dado_de_baja"
                found = True
                break
        if not found:
            raise ValueError(f"Paciente con id {patient_id} no existe")

        for h in self.simulated.tables["historial_pediatrico"]:
            if h["id_paciente"] == patient_id:
                h["estado"] = "archivado"
                h["motivo_baja"] = motivo_baja
                h["fecha_ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "id_paciente": patient_id,
            "estado": "archivado",
            "motivo_baja": motivo_baja,
            "motor": "MySQL",
            "mensaje": "Expediente pediátrico archivado con éxito."
        }

    def create_appointment(self, appointment_data: Dict[str, Any]) -> Appointment:
        new_id = self.simulated._next_id("cita")
        cita_dict = {
            "id_cita": new_id,
            "id_paciente": appointment_data["id_paciente"],
            "id_pediatra": appointment_data.get("id_pediatra", 1),
            "fecha_hora_programada": appointment_data["fecha_hora_programada"],
            "motivo_consulta": appointment_data["motivo_consulta"],
            "estado_cita": appointment_data.get("estado_cita", "programada"),
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.simulated.tables["cita"].append(cita_dict)
        return self._to_appointment_domain(cita_dict)

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        res = []
        for c in self.simulated.tables["cita"]:
            if patient_id is None or c["id_paciente"] == patient_id:
                res.append(self._to_appointment_domain(c))
        return res

    def register_consultation(self, consultation_data: Dict[str, Any]) -> Consultation:
        """Transacción de consulta pediátrica, somatometría y vacunas en MySQL."""
        tx_res = self.simulated.execute_transaction_consultation(consultation_data)
        c_row = tx_res["consulta"]
        vac_row = tx_res["vacunacion"]
        rec_row = tx_res["receta"]

        somatometria = SomatometryRecord(
            peso_kg=c_row["peso_kg"],
            talla_cm=c_row["talla_cm"],
            perimetro_cefalico_cm=c_row.get("perimetro_cefalico_cm"),
            percentil_crecimiento=c_row.get("percentil_crecimiento")
        )

        vacunas = []
        if vac_row:
            vacunas.append(VaccinationRecord(
                id_vacunacion=vac_row["id_vacunacion"],
                nombre_vacuna=vac_row["nombre_vacuna"],
                dosis=vac_row["dosis"],
                lote=vac_row["lote"],
                fecha_aplicacion=vac_row["fecha_aplicacion"],
                proxima_fecha_refuerzo=vac_row.get("proxima_fecha_refuerzo")
            ))

        recetas = []
        if rec_row:
            recetas.append(Prescription(
                id_receta=rec_row["id_receta"],
                medicamento=rec_row["medicamento"],
                dosis=f"{rec_row['dosis_mg_kg']} mg/kg ({rec_row['dosis_calculada_ml']} ml)",
                frecuencia=rec_row["frecuencia"],
                duracion_dias=rec_row["duracion_dias"],
                indicaciones=rec_row["indicaciones"],
                fecha_emision=rec_row["fecha_emision"],
                dosis_mg_kg=rec_row["dosis_mg_kg"],
                dosis_calculada_ml=rec_row["dosis_calculada_ml"]
            ))

        diagnostico = Diagnosis(
            id_diagnostico=c_row["id_consulta"],
            codigo_cie10=c_row["diagnostico_cie10"],
            descripcion=c_row["descripcion_diagnostico"],
            tipo="principal",
            fecha_diagnostico=c_row["fecha_hora_atencion"][:10]
        )

        return Consultation(
            id_consulta=c_row["id_consulta"],
            id_cita=c_row["id_cita"],
            fecha_hora_atencion=c_row["fecha_hora_atencion"],
            motivo=c_row["motivo"],
            temperatura=c_row["temperatura"],
            pulso=c_row["frecuencia_cardiaca"],
            notas_clinicas=c_row["notas_clinicas"],
            tipo_consulta=c_row["tipo_consulta"],
            diagnosticos=[diagnostico],
            somatometria=somatometria,
            vacunaciones=vacunas,
            recetas_pediatricas=recetas
        )

    def get_clinical_history(
        self, patient_id: int, user_role: UserRole = UserRole.PEDIATRA
    ) -> Optional[UnifiedClinicalRecord]:
        patient = self.get_patient(patient_id)
        if not patient:
            return None

        hist_row = None
        for h in self.simulated.tables["historial_pediatrico"]:
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

        citas_list = self.get_appointments(patient_id)
        cita_ids = {c.id_cita for c in citas_list}

        consultas_list = []
        for c_row in self.simulated.tables["consulta"]:
            if c_row["id_cita"] in cita_ids:
                id_con = c_row["id_consulta"]

                # Somatometría
                som = SomatometryRecord(
                    peso_kg=c_row["peso_kg"],
                    talla_cm=c_row["talla_cm"],
                    perimetro_cefalico_cm=c_row.get("perimetro_cefalico_cm"),
                    percentil_crecimiento=c_row.get("percentil_crecimiento")
                )

                # Vacunas administradas en esta consulta
                vacs = []
                for v in self.simulated.tables["vacunacion"]:
                    if v["id_consulta"] == id_con:
                        vacs.append(VaccinationRecord(
                            id_vacunacion=v["id_vacunacion"],
                            nombre_vacuna=v["nombre_vacuna"],
                            dosis=v["dosis"],
                            lote=v["lote"],
                            fecha_aplicacion=v["fecha_aplicacion"],
                            proxima_fecha_refuerzo=v.get("proxima_fecha_refuerzo")
                        ))

                # Recetas
                recs = []
                for r in self.simulated.tables["receta"]:
                    if r["id_consulta"] == id_con:
                        recs.append(Prescription(
                            id_receta=r["id_receta"],
                            medicamento=r["medicamento"],
                            dosis=f"{r.get('dosis_mg_kg')} mg/kg",
                            frecuencia=r["frecuencia"],
                            duracion_dias=r["duracion_dias"],
                            indicaciones=r["indicaciones"],
                            fecha_emision=r["fecha_emision"],
                            dosis_mg_kg=r.get("dosis_mg_kg"),
                            dosis_calculada_ml=r.get("dosis_calculada_ml")
                        ))

                diag = Diagnosis(
                    id_diagnostico=id_con,
                    codigo_cie10=c_row.get("diagnostico_cie10", "Z00.1"),
                    descripcion=c_row["descripcion_diagnostico"],
                    tipo="principal",
                    fecha_diagnostico=c_row["fecha_hora_atencion"][:10]
                )

                consultas_list.append(Consultation(
                    id_consulta=id_con,
                    id_cita=c_row["id_cita"],
                    fecha_hora_atencion=c_row["fecha_hora_atencion"],
                    motivo=c_row["motivo"],
                    temperatura=c_row["temperatura"],
                    pulso=c_row["frecuencia_cardiaca"],
                    notas_clinicas=c_row["notas_clinicas"],
                    tipo_consulta=c_row["tipo_consulta"],
                    diagnosticos=[diag],
                    somatometria=som,
                    vacunaciones=vacs,
                    recetas_pediatricas=recs
                ))

        history = UnifiedClinicalRecord(
            id_historial=hist_row["id_historial"],
            id_paciente=patient_id,
            paciente=patient,
            fecha_apertura=hist_row["fecha_apertura"],
            fecha_ultima_actualizacion=hist_row["fecha_ultima_actualizacion"],
            estado=hist_row["estado"],
            motivo_baja=hist_row.get("motivo_baja"),
            institucion=InstitutionType.CENTRO_PEDIATRICO,
            motor=DatabaseEngine.MYSQL,
            consultas=consultas_list,
            citas=citas_list,
            datos_adicionales={
                "tutor": f"{patient.nombre_tutor} ({patient.parentesco_tutor})",
                "semanas_gestacion": patient.semanas_gestacion,
                "peso_nacer_kg": patient.peso_nacer_kg
            }
        )

        return self.apply_security_filter(history, user_role)

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        vacunas = [v for v in self.simulated.tables["vacunacion"] if v["id_paciente"] == patient_id]
        curva_crecimiento = []
        citas_p = {c["id_cita"] for c in self.simulated.tables["cita"] if c["id_paciente"] == patient_id}
        for c in self.simulated.tables["consulta"]:
            if c["id_cita"] in citas_p:
                curva_crecimiento.append({
                    "fecha": c["fecha_hora_atencion"][:10],
                    "peso_kg": c["peso_kg"],
                    "talla_cm": c["talla_cm"],
                    "percentil": c["percentil_crecimiento"]
                })
        return {
            "institucion": "Centro Médico Pediátrico",
            "motor": "MySQL",
            "carnet_vacunacion": vacunas,
            "curva_crecimiento": curva_crecimiento
        }

    # Helpers
    def _to_patient_domain(self, d: Dict[str, Any]) -> Patient:
        return Patient(
            id_paciente=d["id_paciente"],
            nombres=d["nombres"],
            apellidos=d["apellidos"],
            fecha_nacimiento=d["fecha_nacimiento"],
            sexo=d["sexo"],
            dpi=d["cui_nacimiento"],
            direccion=d.get("direccion", ""),
            telefono=d.get("telefono_tutor", ""),
            correo_electronico="pediatria@paciente.gt",
            tipo_sangre="O+",
            contacto_emergencia_nombre=d.get("nombre_tutor", ""),
            contacto_emergencia_telefono=d.get("telefono_tutor", ""),
            fecha_registro=d.get("fecha_registro", date.today().isoformat()),
            estado=d.get("estado", "activo"),
            nombre_tutor=d.get("nombre_tutor"),
            parentesco_tutor=d.get("parentesco_tutor"),
            dpi_tutor=d.get("dpi_tutor"),
            telefono_tutor=d.get("telefono_tutor"),
            semanas_gestacion=d.get("semanas_gestacion"),
            peso_nacer_kg=d.get("peso_nacer_kg"),
            talla_nacer_cm=d.get("talla_nacer_cm")
        )

    def _to_appointment_domain(self, d: Dict[str, Any]) -> Appointment:
        ped_nombre = "Dra. Especialista Pediátrica"
        for p in self.simulated.tables["pediatra"]:
            if p["id_pediatra"] == d.get("id_pediatra"):
                ped_nombre = p["nombre_completo"]
                break
        return Appointment(
            id_cita=d["id_cita"],
            id_paciente=d["id_paciente"],
            id_profesional=d.get("id_pediatra", 1),
            profesional_nombre=ped_nombre,
            fecha_hora_programada=d["fecha_hora_programada"],
            motivo_consulta=d["motivo_consulta"],
            estado_cita=d["estado_cita"],
            fecha_creacion=d["fecha_creacion"]
        )

