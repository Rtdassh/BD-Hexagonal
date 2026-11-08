"""
MySQL Database Adapter for Centro Médico Pediátrico.
Hexagonal Architecture Adapter implementing ClinicalRepositoryPort.
Optimized for pediatric follow-up, somatometry (weight, height, head circumference, percentiles),
vaccination schedule tracking, and dosage by body weight (mg/kg).
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from ..base_adapter import BaseClinicalAdapter
from .engines import SimulatedMySQLEngine
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
    Prescription,
    Professional,
    SomatometryRecord,
    VaccinationRecord
)
from ....domain.ports import PediatricOperationsPort


class SimulatedMySQLAdapter(BaseClinicalAdapter, PediatricOperationsPort):
    def __init__(self, config: Config, simulated_engine: Optional[SimulatedMySQLEngine] = None):
        self.config = config
        self.simulated = simulated_engine or SimulatedMySQLEngine()
        self.is_live = False
        self._init_connection()

    def _init_connection(self):
        # Motor simulado en memoria: no abre conexiones reales.
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

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
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
            "control_crecimiento": curva_crecimiento,
            "curva_crecimiento": curva_crecimiento,
            "esquema_vacunacion": vacunas,
            "carnet_vacunacion": vacunas
        }

    # ------------------------------------------------------------------------
    # Implementación de PediatricOperationsPort
    # ------------------------------------------------------------------------
    def get_pediatric_details(self, patient_id: int) -> Dict[str, Any]:
        return self.simulated.get_pediatric_details(patient_id)

    def update_perinatal(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.update_perinatal(patient_id, data)

    def update_guardian(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.update_guardian(patient_id, data)

    def add_somatometry(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.add_somatometry(patient_id, data)

    def list_somatometry(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.simulated.list_somatometry(patient_id)

    def list_vaccines_catalog(self) -> List[Dict[str, Any]]:
        return self.simulated.list_vaccines_catalog()

    def list_vaccine_batches(self) -> List[Dict[str, Any]]:
        return self.simulated.list_vaccine_batches()

    def create_vaccine_batch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.create_vaccine_batch(data)

    def add_vaccination(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.add_vaccination(patient_id, data)

    def list_vaccinations(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.simulated.list_vaccinations(patient_id)

    def list_development_milestones(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.simulated.list_development_milestones(patient_id)

    def add_development_milestone(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.add_development_milestone(patient_id, data)

    def list_patient_allergies(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.simulated.list_patient_allergies(patient_id)

    def add_patient_allergy(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.simulated.add_patient_allergy(patient_id, data)

    def list_allergens_catalog(self) -> List[Dict[str, Any]]:
        return self.simulated.list_allergens_catalog()

    def list_growth_percentiles(self, sexo: Optional[str] = None, parametro: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.simulated.list_growth_percentiles(sexo, parametro)

    # Personal médico
    def list_professionals(self) -> List[Professional]:
        return [
            Professional(
                id_profesional=p["id_pediatra"],
                nombre_completo=p["nombre_completo"],
                numero_colegiado=p["numero_colegiado"],
                especialidad=p.get("especialidad", "Pediatría general"),
                telefono=p.get("telefono", ""),
                correo_electronico=p.get("correo_electronico", ""),
                estado=p.get("estado", "activo")
            )
            for p in self.simulated.tables["pediatra"]
        ]

    def create_professional(self, data: Dict[str, Any]) -> Professional:
        self.requerido(data, "nombre_completo", "numero_colegiado")
        col = data["numero_colegiado"].strip()
        for p in self.simulated.tables["pediatra"]:
            if p["numero_colegiado"] == col:
                raise ValueError(f"Ya existe un pediatra con colegiado {col}")
        new_id = self.simulated._next_id("pediatra")
        rec = {
            "id_pediatra": new_id,
            "nombre_completo": data["nombre_completo"].strip(),
            "numero_colegiado": col,
            "especialidad": data.get("especialidad") or "Pediatría general",
            "telefono": data.get("telefono") or "",
            "correo_electronico": data.get("correo_electronico") or "",
            "estado": data.get("estado", "activo")
        }
        self.simulated.tables["pediatra"].append(rec)
        return Professional(
            id_profesional=new_id,
            nombre_completo=rec["nombre_completo"],
            numero_colegiado=rec["numero_colegiado"],
            especialidad=rec["especialidad"],
            telefono=rec["telefono"],
            correo_electronico=rec["correo_electronico"],
            estado=rec["estado"]
        )

    def update_professional(self, professional_id: int, data: Dict[str, Any]) -> Professional:
        for p in self.simulated.tables["pediatra"]:
            if p["id_pediatra"] == int(professional_id):
                for k in ("nombre_completo", "especialidad", "telefono", "correo_electronico", "estado"):
                    if data.get(k) not in (None, ""):
                        p[k] = data[k]
                return Professional(
                    id_profesional=p["id_pediatra"],
                    nombre_completo=p["nombre_completo"],
                    numero_colegiado=p["numero_colegiado"],
                    especialidad=p.get("especialidad", ""),
                    telefono=p.get("telefono", ""),
                    correo_electronico=p.get("correo_electronico", ""),
                    estado=p.get("estado", "activo")
                )
        raise ValueError(f"Pediatra {professional_id} no encontrado")

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

