"""
Simulated High-Fidelity In-Memory Storage Engines.
Provides resilient, fully operational implementations of the 4 database models
when external DB servers are not active on the host machine.
Strictly replicates the relational constraints, document embedding, and collections
of PostgreSQL, MySQL, MongoDB, and Firebase.
"""

import copy
import re
from datetime import datetime, date, timezone
from typing import Dict, List, Any, Optional


# ============================================================================
# 1. MOTOR POSTGRESQL SIMULADO (Hospital General)
# Schema: 'hospital', ACID transactions, foreign keys, hospitalizations.
# ============================================================================
class SimulatedPostgreSQLEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tables = {
            "hospital.Paciente": [
                {
                    "id_paciente": 1,
                    "nombres": "Manuel Antonio",
                    "apellidos": "Pérez Morales",
                    "fecha_nacimiento": "1982-05-14",
                    "sexo": "M",
                    "dpi": "2456789010101",
                    "direccion": "Zona 1, Quetzaltenango",
                    "telefono": "4123-8899",
                    "correo_electronico": "mperez@gmail.com",
                    "tipo_sangre": "O+",
                    "contacto_emergencia_nombre": "Ana Gómez de Pérez",
                    "contacto_emergencia_telefono": "4988-7711",
                    "fecha_registro": "2026-01-10",
                    "estado_salud": "hospitalizado"
                }
            ],
            "hospital.Historial_Clinico": [
                {
                    "id_historial": 1,
                    "id_paciente": 1,
                    "fecha_apertura": "2026-01-10",
                    "fecha_ultima_actualizacion": "2026-03-01 09:30:00",
                    "estado": "activo",
                    "motivo_baja": None
                }
            ],
            "hospital.Medico": [
                {
                    "id_medico": 1,
                    "nombre": "Dr. Carlos Roberto Mendoza",
                    "numero_colegiado": "COL-12450",
                    "telefono": "5551-0101",
                    "correo_electronico": "cmendoza@hospitalgeneral.gob.gt",
                    "estado": "activo"
                },
                {
                    "id_medico": 2,
                    "nombre": "Dra. Laura Sofía Estrada",
                    "numero_colegiado": "COL-14820",
                    "telefono": "5551-0102",
                    "correo_electronico": "lestrada@hospitalgeneral.gob.gt",
                    "estado": "activo"
                }
            ],
            "hospital.Cita": [
                {
                    "id_cita": 1,
                    "id_paciente": 1,
                    "id_medico": 2,
                    "fecha_hora_programada": "2026-03-01 08:30:00",
                    "motivo_consulta": "Dolor abdominal agudo e ictericia",
                    "estado_cita": "atendida",
                    "fecha_creacion": "2026-03-01 08:00:00"
                }
            ],
            "hospital.Consulta": [
                {
                    "id_consulta": 1,
                    "id_cita": 1,
                    "fecha_hora_atencion": "2026-03-01 08:45:00",
                    "motivo": "Dolor intenso en hipocondrio derecho Murphy positivo",
                    "presion_arterial": "135/85",
                    "temperatura": 38.4,
                    "pulso": 92,
                    "notas_clinicas": "Paciente requiere manejo quirúrgico e internamiento inmediato.",
                    "tipo_consulta": "emergencia"
                }
            ],
            "hospital.Diagnostico": [
                {
                    "id_diagnostico": 1,
                    "id_consulta": 1,
                    "codigo_cie10": "K80.0",
                    "descripcion": "Cálculo de la vesícula biliar con colecistitis aguda",
                    "tipo": "principal",
                    "fecha_diagnostico": "2026-03-01"
                }
            ],
            "hospital.Tratamiento": [
                {
                    "id_tratamiento": 1,
                    "id_diagnostico": 1,
                    "descripcion": "Antibioticoterapia prequirúrgica y laparoscopía",
                    "fecha_inicio": "2026-03-01",
                    "fecha_fin": "2026-03-08",
                    "estado": "activo",
                    "indicaciones": "Nada por vía oral, canalizar vía periférica y control horario."
                }
            ],
            "hospital.Receta": [
                {
                    "id_receta": 1,
                    "id_tratamiento": 1,
                    "id_medicamento": 1,
                    "medicamento": "Amoxicilina + Ácido Clavulánico 875/125mg",
                    "dosis": "1 tableta",
                    "frecuencia": "Cada 8 horas",
                    "duracion_dias": 7,
                    "via_administracion": "Oral",
                    "fecha_emision": "2026-03-01"
                }
            ],
            "hospital.Hospitalizacion": [
                {
                    "id_hospitalizacion": 1,
                    "id_paciente": 1,
                    "id_consulta": 1,
                    "fecha_ingreso": "2026-03-01 09:30:00",
                    "fecha_egreso": None,
                    "numero_habitacion": "HAB-304",
                    "motivo_ingreso": "Monitoreo pre y post operatorio de colecistectomía",
                    "estado": "ingresado"
                }
            ]
        }
        self.sequences = {tbl: len(rows) for tbl, rows in self.tables.items()}

    def _next_id(self, table_name: str) -> int:
        self.sequences[table_name] = self.sequences.get(table_name, 0) + 1
        return self.sequences[table_name]

    def insert_patient(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Validar DPI único
        for p in self.tables["hospital.Paciente"]:
            if p["dpi"] == data["dpi"]:
                raise ValueError(f"Violación de restricción UNIQUE en hospital.Paciente(dpi): {data['dpi']}")
        
        new_id = self._next_id("hospital.Paciente")
        record = {
            "id_paciente": new_id,
            "nombres": data["nombres"],
            "apellidos": data["apellidos"],
            "fecha_nacimiento": str(data["fecha_nacimiento"]),
            "sexo": data.get("sexo", "M"),
            "dpi": data["dpi"],
            "direccion": data.get("direccion", ""),
            "telefono": data.get("telefono", ""),
            "correo_electronico": data.get("correo_electronico", ""),
            "tipo_sangre": data.get("tipo_sangre", "O+"),
            "contacto_emergencia_nombre": data.get("contacto_emergencia_nombre", ""),
            "contacto_emergencia_telefono": data.get("contacto_emergencia_telefono", ""),
            "fecha_registro": data.get("fecha_registro", date.today().isoformat()),
            "estado_salud": data.get("estado_salud", "activo")
        }
        self.tables["hospital.Paciente"].append(record)

        # Crear automáticamente historial clínico
        hist_id = self._next_id("hospital.Historial_Clinico")
        self.tables["hospital.Historial_Clinico"].append({
            "id_historial": hist_id,
            "id_paciente": new_id,
            "fecha_apertura": date.today().isoformat(),
            "fecha_ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": "activo",
            "motivo_baja": None
        })
        return copy.deepcopy(record)

    def execute_transaction_consultation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta una transacción ACID completa:
        Cita -> Consulta -> Diagnostico -> Tratamiento -> Receta -> (Hospitalizacion opcional)
        Si algún paso falla, se revierte toda la transacción.
        """
        snapshot = copy.deepcopy(self.tables)
        try:
            paciente_id = data["id_paciente"]
            # 1. Cita
            id_cita = data.get("id_cita")
            if not id_cita:
                id_cita = self._next_id("hospital.Cita")
                cita = {
                    "id_cita": id_cita,
                    "id_paciente": paciente_id,
                    "id_medico": data.get("id_medico", 1),
                    "fecha_hora_programada": data.get("fecha_hora_atencion", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "motivo_consulta": data["motivo"],
                    "estado_cita": "atendida",
                    "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.tables["hospital.Cita"].append(cita)

            # 2. Consulta
            id_consulta = self._next_id("hospital.Consulta")
            consulta = {
                "id_consulta": id_consulta,
                "id_cita": id_cita,
                "fecha_hora_atencion": data.get("fecha_hora_atencion", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "motivo": data["motivo"],
                "presion_arterial": data.get("presion_arterial", "120/80"),
                "temperatura": float(data.get("temperatura", 37.0)),
                "pulso": int(data.get("pulso", 75)),
                "notas_clinicas": data.get("notas_clinicas", ""),
                "tipo_consulta": data.get("tipo_consulta", "ordinaria")
            }
            self.tables["hospital.Consulta"].append(consulta)

            # 3. Diagnostico
            id_diag = self._next_id("hospital.Diagnostico")
            diag = {
                "id_diagnostico": id_diag,
                "id_consulta": id_consulta,
                "codigo_cie10": data.get("codigo_cie10", "Z00.0"),
                "descripcion": data.get("descripcion_diagnostico", "Evaluación clínica general"),
                "tipo": data.get("tipo_diagnostico", "principal"),
                "fecha_diagnostico": date.today().isoformat()
            }
            self.tables["hospital.Diagnostico"].append(diag)

            # 4. Tratamiento
            id_trat = self._next_id("hospital.Tratamiento")
            trat = {
                "id_tratamiento": id_trat,
                "id_diagnostico": id_diag,
                "descripcion": data.get("descripcion_tratamiento", "Tratamiento ambulatorio estándar"),
                "fecha_inicio": date.today().isoformat(),
                "fecha_fin": data.get("fecha_fin_tratamiento"),
                "estado": "activo",
                "indicaciones": data.get("indicaciones_tratamiento", "Reposo e hidratación")
            }
            self.tables["hospital.Tratamiento"].append(trat)

            # 5. Receta
            receta = None
            if data.get("medicamento"):
                id_receta = self._next_id("hospital.Receta")
                receta = {
                    "id_receta": id_receta,
                    "id_tratamiento": id_trat,
                    "id_medicamento": 1,
                    "medicamento": data["medicamento"],
                    "dosis": data.get("dosis", "1 cada 8h"),
                    "frecuencia": data.get("frecuencia", "Cada 8 horas"),
                    "duracion_dias": int(data.get("duracion_dias", 5)),
                    "via_administracion": data.get("via_administracion", "Oral"),
                    "fecha_emision": date.today().isoformat()
                }
                self.tables["hospital.Receta"].append(receta)

            # 6. Hospitalización opcional
            hosp = None
            if data.get("requiere_hospitalizacion"):
                id_hosp = self._next_id("hospital.Hospitalizacion")
                hosp = {
                    "id_hospitalizacion": id_hosp,
                    "id_paciente": paciente_id,
                    "id_consulta": id_consulta,
                    "fecha_ingreso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fecha_egreso": None,
                    "numero_habitacion": data.get("numero_habitacion", "HAB-101"),
                    "motivo_ingreso": data.get("motivo_hospitalizacion", "Observación clínica"),
                    "estado": "ingresado"
                }
                self.tables["hospital.Hospitalizacion"].append(hosp)
                # Actualizar estado del paciente a hospitalizado
                for p in self.tables["hospital.Paciente"]:
                    if p["id_paciente"] == paciente_id:
                        p["estado_salud"] = "hospitalizado"

            # Actualizar timestamp en historial
            for h in self.tables["hospital.Historial_Clinico"]:
                if h["id_paciente"] == paciente_id:
                    h["fecha_ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return {
                "id_consulta": id_consulta,
                "id_cita": id_cita,
                "consulta": consulta,
                "diagnostico": diag,
                "tratamiento": trat,
                "receta": receta,
                "hospitalizacion": hosp
            }
        except Exception as e:
            # Rollback en caso de excepción
            self.tables = snapshot
            raise RuntimeError(f"PostgreSQL Transaction ROLLBACK. Error: {str(e)}")


# ============================================================================
# 2. MOTOR MYSQL SIMULADO (Centro Médico Pediátrico)
# Database: 'centro_pediatrico', InnoDB, Somatometría, Vacunación, Dosificación
# ============================================================================
class SimulatedMySQLEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tables = {
            "paciente_pediatrico": [
                {
                    "id_paciente": 1,
                    "nombres": "Mateo Alejandro",
                    "apellidos": "Ríos Castillo",
                    "fecha_nacimiento": "2024-02-15",
                    "sexo": "M",
                    "cui_nacimiento": "3024881920101",
                    "direccion": "Zona 3, Quetzaltenango",
                    "nombre_tutor": "Andrea Castillo de Ríos",
                    "parentesco_tutor": "Madre",
                    "dpi_tutor": "1987543210101",
                    "telefono_tutor": "4211-0022",
                    "semanas_gestacion": 39,
                    "peso_nacer_kg": 3.25,
                    "talla_nacer_cm": 49.50,
                    "fecha_registro": "2024-02-20",
                    "estado": "activo"
                }
            ],
            "historial_pediatrico": [
                {
                    "id_historial": 1,
                    "id_paciente": 1,
                    "fecha_apertura": "2024-02-20",
                    "fecha_ultima_actualizacion": "2026-02-15 10:15:00",
                    "estado": "activo",
                    "motivo_baja": None
                }
            ],
            "pediatra": [
                {
                    "id_pediatra": 1,
                    "nombre_completo": "Dra. Mariana Lucía Batres",
                    "numero_colegiado": "PED-08912",
                    "telefono": "5552-0101",
                    "correo_electronico": "mbatres@centropediatrico.com",
                    "estado": "activo"
                }
            ],
            "cita": [
                {
                    "id_cita": 1,
                    "id_paciente": 1,
                    "id_pediatra": 1,
                    "fecha_hora_programada": "2026-02-15 10:00:00",
                    "motivo_consulta": "Control de niño sano - 2 años de edad y vacuna",
                    "estado_cita": "atendida",
                    "fecha_creacion": "2026-02-10 09:00:00"
                }
            ],
            "consulta": [
                {
                    "id_consulta": 1,
                    "id_cita": 1,
                    "fecha_hora_atencion": "2026-02-15 10:15:00",
                    "motivo": "Evaluación integral de 2 años",
                    "temperatura": 36.6,
                    "frecuencia_cardiaca": 98,
                    "peso_kg": 12.40,
                    "talla_cm": 86.50,
                    "perimetro_cefalico_cm": 48.20,
                    "percentil_crecimiento": 50.0,
                    "diagnostico_cie10": "Z00.1",
                    "descripcion_diagnostico": "Control de salud de rutina del niño",
                    "notas_clinicas": "Desarrollo psicomotor adecuado, lenguaje bisilábico fluido.",
                    "tipo_consulta": "control_sano"
                }
            ],
            "vacunacion": [
                {
                    "id_vacunacion": 1,
                    "id_paciente": 1,
                    "id_consulta": 1,
                    "nombre_vacuna": "Triple Viral (SPR - Sarampión, Paperas, Rubéola)",
                    "dosis": "2da Dosis (Refuerzo)",
                    "lote": "SPR-2026-99A",
                    "fecha_aplicacion": "2026-02-15",
                    "proxima_fecha_refuerzo": "2028-02-15"
                }
            ],
            "receta": [
                {
                    "id_receta": 1,
                    "id_consulta": 1,
                    "medicamento": "Multivitamínico Pediátrico con Zinc",
                    "presentacion": "Jarabe 120ml",
                    "dosis_mg_kg": 5.00,
                    "dosis_calculada_ml": 2.50,
                    "frecuencia": "Cada 24 horas por la mañana",
                    "duracion_dias": 30,
                    "indicaciones": "Administrar con el desayuno durante 1 mes para suplementación preventiva",
                    "fecha_emision": "2026-02-15"
                }
            ],
            # Tablas expandidas del Modelo Relacional 3FN (+20 tablas)
            "tutor_legal": [
                {
                    "id_tutor": 1,
                    "dpi": "1987543210101",
                    "nombres": "Andrea",
                    "apellidos": "Castillo de Ríos",
                    "telefono_principal": "4211-0022",
                    "direccion": "Zona 3, Quetzaltenango"
                }
            ],
            "tutor_paciente": [
                {"id_tutor_paciente": 1, "id_tutor": 1, "id_paciente": 1, "parentesco": "Madre", "es_tutor_principal": True}
            ],
            "antecedente_perinatal": [
                {
                    "id_antecedente": 1,
                    "id_paciente": 1,
                    "semanas_gestacion": 39,
                    "peso_nacer_kg": 3.25,
                    "talla_nacer_cm": 49.50,
                    "perimetro_cefalico_nacer_cm": 34.50,
                    "tipo_parto": "Eutócico vaginal",
                    "apgar_1min": 9,
                    "apgar_5min": 10
                }
            ],
            "especialidad_pediatrica": [
                {"id_especialidad": 1, "nombre_especialidad": "Pediatría general"},
                {"id_especialidad": 2, "nombre_especialidad": "Neonatología"}
            ],
            "pediatra_especialidad": [
                {"id_pediatra_especialidad": 1, "id_pediatra": 1, "id_especialidad": 1, "fecha_certificacion": "2020-01-15"}
            ],
            "horario_atencion": [
                {"id_horario": 1, "id_pediatra": 1, "dia_semana": "Lunes", "hora_inicio": "08:00", "hora_fin": "12:00", "consultorio_numero": "C-101"}
            ],
            "antropometria_somatometria": [
                {
                    "id_somatometria": 1,
                    "id_consulta": 1,
                    "id_paciente": 1,
                    "edad_meses_atencion": 24,
                    "peso_kg": 12.40,
                    "talla_cm": 86.50,
                    "perimetro_cefalico_cm": 48.20,
                    "imc_calculado": 16.57,
                    "percentil_peso_edad": 50.0,
                    "percentil_talla_edad": 50.0,
                    "percentil_pc_edad": 50.0
                }
            ],
            "normativa_percentil_oms": [
                {"id_normativa": 1, "sexo": "M", "edad_meses": 0, "parametro_antropometrico": "peso_edad", "p3": 2.5, "p15": 2.9, "p50": 3.3, "p85": 3.9, "p97": 4.4},
                {"id_normativa": 2, "sexo": "M", "edad_meses": 6, "parametro_antropometrico": "peso_edad", "p3": 6.4, "p15": 7.1, "p50": 7.9, "p85": 8.8, "p97": 9.8},
                {"id_normativa": 3, "sexo": "M", "edad_meses": 12, "parametro_antropometrico": "peso_edad", "p3": 7.7, "p15": 8.6, "p50": 9.6, "p85": 10.8, "p97": 12.0},
                {"id_normativa": 4, "sexo": "M", "edad_meses": 24, "parametro_antropometrico": "peso_edad", "p3": 9.7, "p15": 10.8, "p50": 12.2, "p85": 13.6, "p97": 15.3},
                {"id_normativa": 5, "sexo": "M", "edad_meses": 36, "parametro_antropometrico": "peso_edad", "p3": 11.3, "p15": 12.7, "p50": 14.3, "p85": 16.2, "p97": 18.3},
                {"id_normativa": 6, "sexo": "F", "edad_meses": 24, "parametro_antropometrico": "peso_edad", "p3": 9.0, "p15": 10.2, "p50": 11.5, "p85": 13.0, "p97": 14.8},
                {"id_normativa": 7, "sexo": "M", "edad_meses": 24, "parametro_antropometrico": "talla_edad", "p3": 81.0, "p15": 84.1, "p50": 87.8, "p85": 90.9, "p97": 93.9},
                {"id_normativa": 8, "sexo": "M", "edad_meses": 24, "parametro_antropometrico": "perimetro_cefalico", "p3": 46.2, "p15": 47.3, "p50": 48.3, "p85": 49.5, "p97": 50.5}
            ],
            "evaluacion_desarrollo": [
                {"id_evaluacion": 1, "id_consulta": 1, "id_paciente": 1, "area_desarrollo": "Lenguaje", "hito_evaluado": "Frases de 2 palabras con sentido", "cumple_hito": True, "observaciones": "Comunica deseos claramente"},
                {"id_evaluacion": 2, "id_consulta": 1, "id_paciente": 1, "area_desarrollo": "Motricidad Fina", "hito_evaluado": "Construye torre de 6 cubos", "cumple_hito": True, "observaciones": "Buena prensión palmar y pinza"},
                {"id_evaluacion": 3, "id_consulta": 1, "id_paciente": 1, "area_desarrollo": "Motricidad Gruesa", "hito_evaluado": "Corre con estabilidad y patea pelota", "cumple_hito": True, "observaciones": "Marcha firme"},
                {"id_evaluacion": 4, "id_consulta": 1, "id_paciente": 1, "area_desarrollo": "Personal-Social", "hito_evaluado": "Usa cuchara y avisa necesidades", "cumple_hito": True, "observaciones": "Adecuada interacción con la madre"}
            ],
            "catalogo_cie10_pediatrico": [
                {"codigo_cie10": "Z00.1", "descripcion_diagnostico": "Control de salud de rutina del niño sano", "categoria_morbilidad": "Preventiva"},
                {"codigo_cie10": "Z23", "descripcion_diagnostico": "Necesidad de inmunización", "categoria_morbilidad": "Preventiva"},
                {"codigo_cie10": "J06.9", "descripcion_diagnostico": "Infección aguda de vías respiratorias superiores", "categoria_morbilidad": "Respiratoria"},
                {"codigo_cie10": "A09", "descripcion_diagnostico": "Gastroenteritis y diarrea de presunto origen infeccioso", "categoria_morbilidad": "Gastrointestinal"},
                {"codigo_cie10": "E44.1", "descripcion_diagnostico": "Desnutrición proteicocalórica leve", "categoria_morbilidad": "Nutricional"}
            ],
            "diagnostico_consulta": [
                {"id_diagnostico_consulta": 1, "id_consulta": 1, "codigo_cie10": "Z00.1", "tipo_diagnostico": "principal"}
            ],
            "vacuna_catalogo": [
                {"id_vacuna": 1, "nombre_vacuna": "Triple Viral (SPR - Sarampión, Paperas, Rubeola)", "codigo_biologico": "BIO-SPR-01", "via_administracion": "Subcutánea", "edad_meses_sugerida": 12, "dosis_recomendada_ml": 0.5},
                {"id_vacuna": 2, "nombre_vacuna": "Pentavalente Acelular (DPT + HepB + Hib)", "codigo_biologico": "BIO-PENT-02", "via_administracion": "Intramuscular", "edad_meses_sugerida": 2, "dosis_recomendada_ml": 0.5},
                {"id_vacuna": 3, "nombre_vacuna": "Neumococo Conjugada 13-valente", "codigo_biologico": "BIO-NEU-03", "via_administracion": "Intramuscular", "edad_meses_sugerida": 2, "dosis_recomendada_ml": 0.5},
                {"id_vacuna": 4, "nombre_vacuna": "Rotavirus Monovalente Oral", "codigo_biologico": "BIO-ROTA-04", "via_administracion": "Oral", "edad_meses_sugerida": 2, "dosis_recomendada_ml": 1.5},
                {"id_vacuna": 5, "nombre_vacuna": "BCG (Tuberculosis)", "codigo_biologico": "BIO-BCG-05", "via_administracion": "Intradérmica", "edad_meses_sugerida": 0, "dosis_recomendada_ml": 0.05},
                {"id_vacuna": 6, "nombre_vacuna": "Hepatitis B Pediátrica", "codigo_biologico": "BIO-HEPB-06", "via_administracion": "Intramuscular", "edad_meses_sugerida": 0, "dosis_recomendada_ml": 0.5},
                {"id_vacuna": 7, "nombre_vacuna": "DPT Refuerzo Pediátrico", "codigo_biologico": "BIO-DPT-07", "via_administracion": "Intramuscular", "edad_meses_sugerida": 18, "dosis_recomendada_ml": 0.5}
            ],
            "lote_vacuna": [
                {"id_lote": 1, "id_vacuna": 1, "numero_lote": "SPR-2026-99A", "fabricante": "Serum Institute", "fecha_fabricacion": "2025-10-01", "fecha_vencimiento": "2027-10-01", "stock_disponible": 45, "temp_min_celsius": 2.0, "temp_max_celsius": 8.0},
                {"id_lote": 2, "id_vacuna": 2, "numero_lote": "PENT-2026-03", "fabricante": "Sanofi Pasteur", "fecha_fabricacion": "2025-11-15", "fecha_vencimiento": "2027-11-15", "stock_disponible": 60, "temp_min_celsius": 2.0, "temp_max_celsius": 8.0},
                {"id_lote": 3, "id_vacuna": 3, "numero_lote": "NEU-2026-11", "fabricante": "Pfizer Pediátrica", "fecha_fabricacion": "2025-09-20", "fecha_vencimiento": "2027-09-20", "stock_disponible": 30, "temp_min_celsius": 2.0, "temp_max_celsius": 8.0},
                {"id_lote": 4, "id_vacuna": 5, "numero_lote": "BCG-2026-01", "fabricante": "Statens Serum Institut", "fecha_fabricacion": "2025-08-10", "fecha_vencimiento": "2027-08-10", "stock_disponible": 25, "temp_min_celsius": 2.0, "temp_max_celsius": 8.0}
            ],
            "registro_vacunacion": [
                {"id_registro_vac": 1, "id_vacunacion": 1, "id_paciente": 1, "id_consulta": 1, "id_lote": 1, "numero_dosis": 2, "fecha_aplicacion": "2026-02-15", "profesional_aplico": "Enfermería Pediátrica", "proxima_fecha_refuerzo": "2028-02-15", "reaccion_adversa": "Ninguna observada"}
            ],
            "catalogo_alergeno": [
                {"id_alergeno": 1, "nombre_alergeno": "Amoxicilina / Penicilinas", "tipo_alergeno": "Medicamento", "riesgo_anafilaxia": True},
                {"id_alergeno": 2, "nombre_alergeno": "Proteína de Leche de Vaca (APLV)", "tipo_alergeno": "Alimento", "riesgo_anafilaxia": True},
                {"id_alergeno": 3, "nombre_alergeno": "Huevo (Albúmina)", "tipo_alergeno": "Alimento", "riesgo_anafilaxia": False},
                {"id_alergeno": 4, "nombre_alergeno": "Ácaros del Polvo Doméstico", "tipo_alergeno": "Ambiental", "riesgo_anafilaxia": False},
                {"id_alergeno": 5, "nombre_alergeno": "Látex Natural", "tipo_alergeno": "Contacto", "riesgo_anafilaxia": True},
                {"id_alergeno": 6, "nombre_alergeno": "Maní y Frutos Secos", "tipo_alergeno": "Alimento", "riesgo_anafilaxia": True}
            ],
            "alergia_paciente": [
                {"id_alergia_paciente": 1, "id_paciente": 1, "id_alergeno": 1, "fecha_deteccion": "2025-06-10", "severidad": "Severa / Anafiláctica", "sintomas_observados": "Exantema generalizado y broncoespasmo leve tras administración previa"}
            ],
            "medicamento_pediatrico": [
                {"id_medicamento": 1, "nombre_generico": "Paracetamol Pediátrico", "presentacion": "Gotas orales", "concentracion_mg_ml": 100.0, "dosis_min_mg_kg_dia": 10.0, "dosis_max_mg_kg_dia": 15.0},
                {"id_medicamento": 2, "nombre_generico": "Ibuprofeno Suspensión", "presentacion": "Suspensión 100mg/5ml", "concentracion_mg_ml": 20.0, "dosis_min_mg_kg_dia": 5.0, "dosis_max_mg_kg_dia": 10.0},
                {"id_medicamento": 3, "nombre_generico": "Amoxicilina Suspensión", "presentacion": "Suspensión 250mg/5ml", "concentracion_mg_ml": 50.0, "dosis_min_mg_kg_dia": 25.0, "dosis_max_mg_kg_dia": 50.0},
                {"id_medicamento": 4, "nombre_generico": "Sales de Rehidratación Oral (SRO)", "presentacion": "Sobre para 1 litro", "concentracion_mg_ml": 1.0, "dosis_min_mg_kg_dia": 10.0, "dosis_max_mg_kg_dia": 20.0}
            ],
            "detalle_receta_pediatrica": [
                {"id_detalle_receta": 1, "id_receta": 1, "id_medicamento": 1, "dosis_mg_kg": 5.0, "dosis_calculada_ml": 2.5, "duracion_dias": 30}
            ],
            "auditoria_acceso_menor": []
        }
        self.sequences = {tbl: len(rows) for tbl, rows in self.tables.items()}

    def _next_id(self, table_name: str) -> int:
        self.sequences[table_name] = self.sequences.get(table_name, 0) + 1
        return self.sequences[table_name]

    def insert_patient(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cui = data.get("cui_nacimiento") or data.get("dpi")
        for p in self.tables["paciente_pediatrico"]:
            if p["cui_nacimiento"] == cui:
                raise ValueError(f"Violación de clave UNIQUE en paciente_pediatrico(cui_nacimiento): {cui}")

        new_id = self._next_id("paciente_pediatrico")
        record = {
            "id_paciente": new_id,
            "nombres": data["nombres"],
            "apellidos": data["apellidos"],
            "fecha_nacimiento": str(data["fecha_nacimiento"]),
            "sexo": data.get("sexo", "M"),
            "cui_nacimiento": cui,
            "direccion": data.get("direccion", ""),
            "nombre_tutor": data.get("nombre_tutor", data.get("contacto_emergencia_nombre", "Tutor Responsable")),
            "parentesco_tutor": data.get("parentesco_tutor", "Padre/Madre"),
            "dpi_tutor": data.get("dpi_tutor", "0000000000101"),
            "telefono_tutor": data.get("telefono_tutor", data.get("telefono", "")),
            "semanas_gestacion": int(data.get("semanas_gestacion", 39)),
            "peso_nacer_kg": float(data.get("peso_nacer_kg", 3.2)),
            "talla_nacer_cm": float(data.get("talla_nacer_cm", 50.0)),
            "fecha_registro": data.get("fecha_registro", date.today().isoformat()),
            "estado": data.get("estado", "activo")
        }
        self.tables["paciente_pediatrico"].append(record)

        hist_id = self._next_id("historial_pediatrico")
        self.tables["historial_pediatrico"].append({
            "id_historial": hist_id,
            "id_paciente": new_id,
            "fecha_apertura": date.today().isoformat(),
            "fecha_ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": "activo",
            "motivo_baja": None
        })

        # Sincronización automática a las tablas 3FN normalizadas (+20 tablas)
        id_tutor = self._next_id("tutor_legal")
        self.tables["tutor_legal"].append({
            "id_tutor": id_tutor,
            "dpi": record["dpi_tutor"],
            "nombres": record["nombre_tutor"],
            "apellidos": "Responsable",
            "telefono_principal": record["telefono_tutor"],
            "direccion": record["direccion"]
        })
        self.tables["tutor_paciente"].append({
            "id_tutor_paciente": self._next_id("tutor_paciente"),
            "id_tutor": id_tutor,
            "id_paciente": new_id,
            "parentesco": record["parentesco_tutor"],
            "es_tutor_principal": True
        })
        self.tables["antecedente_perinatal"].append({
            "id_antecedente": self._next_id("antecedente_perinatal"),
            "id_paciente": new_id,
            "semanas_gestacion": record["semanas_gestacion"],
            "peso_nacer_kg": record["peso_nacer_kg"],
            "talla_nacer_cm": record["talla_nacer_cm"],
            "perimetro_cefalico_nacer_cm": 34.50,
            "tipo_parto": "Eutócico vaginal",
            "apgar_1min": 9,
            "apgar_5min": 10
        })

        return copy.deepcopy(record)

    def execute_transaction_consultation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = copy.deepcopy(self.tables)
        try:
            paciente_id = data["id_paciente"]

            # 1. Cita
            id_cita = data.get("id_cita")
            if not id_cita:
                id_cita = self._next_id("cita")
                cita = {
                    "id_cita": id_cita,
                    "id_paciente": paciente_id,
                    "id_pediatra": data.get("id_pediatra", 1),
                    "fecha_hora_programada": data.get("fecha_hora_atencion", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "motivo_consulta": data["motivo"],
                    "estado_cita": "atendida",
                    "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.tables["cita"].append(cita)

            # 2. Somatometría y Consulta rápida
            peso_kg = float(data.get("peso_kg", 10.0))
            talla_cm = float(data.get("talla_cm", 75.0))
            perimetro = float(data.get("perimetro_cefalico_cm", 46.0)) if data.get("perimetro_cefalico_cm") else None
            percentil = float(data.get("percentil_crecimiento", 50.0))

            id_consulta = self._next_id("consulta")
            consulta = {
                "id_consulta": id_consulta,
                "id_cita": id_cita,
                "fecha_hora_atencion": data.get("fecha_hora_atencion", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "motivo": data["motivo"],
                "temperatura": float(data.get("temperatura", 36.8)),
                "frecuencia_cardiaca": int(data.get("pulso", data.get("frecuencia_cardiaca", 100))),
                "peso_kg": peso_kg,
                "talla_cm": talla_cm,
                "perimetro_cefalico_cm": perimetro,
                "percentil_crecimiento": percentil,
                "diagnostico_cie10": data.get("codigo_cie10", "Z00.1"),
                "descripcion_diagnostico": data.get("descripcion_diagnostico", "Control pediátrico"),
                "notas_clinicas": data.get("notas_clinicas", ""),
                "tipo_consulta": data.get("tipo_consulta", "control_sano")
            }
            self.tables["consulta"].append(consulta)

            # 3. Vacunación opcional
            vac = None
            if data.get("nombre_vacuna"):
                id_vac = self._next_id("vacunacion")
                vac = {
                    "id_vacunacion": id_vac,
                    "id_paciente": paciente_id,
                    "id_consulta": id_consulta,
                    "nombre_vacuna": data["nombre_vacuna"],
                    "dosis": data.get("dosis_vacuna", "Dosis única"),
                    "lote": data.get("lote_vacuna", "LOTE-2026-X"),
                    "fecha_aplicacion": date.today().isoformat(),
                    "proxima_fecha_refuerzo": data.get("proxima_fecha_refuerzo")
                }
                self.tables["vacunacion"].append(vac)

            # 4. Receta pediátrica con dosificación por peso (mg/kg)
            receta = None
            if data.get("medicamento"):
                id_receta = self._next_id("receta")
                dosis_mg_kg = float(data.get("dosis_mg_kg", 10.0))
                # Cálculo de ml: (dosis_mg_kg * peso_kg) / concentracion estándar (ej. 50mg/ml)
                dosis_calculada_ml = round((dosis_mg_kg * peso_kg) / 50.0, 2)
                receta = {
                    "id_receta": id_receta,
                    "id_consulta": id_consulta,
                    "medicamento": data["medicamento"],
                    "presentacion": data.get("presentacion", "Suspensión oral"),
                    "dosis_mg_kg": dosis_mg_kg,
                    "dosis_calculada_ml": dosis_calculada_ml,
                    "frecuencia": data.get("frecuencia", "Cada 8 horas"),
                    "duracion_dias": int(data.get("duracion_dias", 5)),
                    "indicaciones": data.get("indicaciones", f"Tomar {dosis_calculada_ml} ml cada {data.get('frecuencia', '8 horas')}"),
                    "fecha_emision": date.today().isoformat()
                }
                self.tables["receta"].append(receta)

            for h in self.tables["historial_pediatrico"]:
                if h["id_paciente"] == paciente_id:
                    h["fecha_ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Sincronización automática a tablas 3FN (antropometría, diagnóstico y detalle de receta)
            id_som = self._next_id("antropometria_somatometria")
            imc = round(peso_kg / ((talla_cm / 100) ** 2), 2)
            self.tables["antropometria_somatometria"].append({
                "id_somatometria": id_som,
                "id_consulta": id_consulta,
                "id_paciente": paciente_id,
                "edad_meses_atencion": 24,
                "peso_kg": peso_kg,
                "talla_cm": talla_cm,
                "perimetro_cefalico_cm": perimetro or 48.0,
                "imc_calculado": imc,
                "percentil_peso_edad": percentil,
                "percentil_talla_edad": percentil,
                "percentil_pc_edad": percentil
            })

            id_dc = self._next_id("diagnostico_consulta")
            self.tables["diagnostico_consulta"].append({
                "id_diagnostico_consulta": id_dc,
                "id_consulta": id_consulta,
                "codigo_cie10": consulta["diagnostico_cie10"],
                "tipo_diagnostico": "principal"
            })

            if receta:
                id_dr = self._next_id("detalle_receta_pediatrica")
                self.tables["detalle_receta_pediatrica"].append({
                    "id_detalle_receta": id_dr,
                    "id_receta": receta["id_receta"],
                    "id_medicamento": 1,
                    "dosis_mg_kg": receta["dosis_mg_kg"],
                    "dosis_calculada_ml": receta["dosis_calculada_ml"],
                    "duracion_dias": receta["duracion_dias"]
                })

            return {
                "id_consulta": id_consulta,
                "id_cita": id_cita,
                "consulta": consulta,
                "vacunacion": vac,
                "receta": receta
            }
        except Exception as e:
            self.tables = snapshot
            raise RuntimeError(f"MySQL InnoDB Transaction ROLLBACK. Error: {str(e)}")

    # ------------------------------------------------------------------------
    # Módulo Centro Pediátrico: Operaciones Clínicas Especializadas
    # ------------------------------------------------------------------------
    def get_pediatric_details(self, patient_id: int) -> Dict[str, Any]:
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado en Centro Pediátrico")

        # Perinatal
        peri = next((x for x in self.tables["antecedente_perinatal"] if x["id_paciente"] == patient_id), None)
        if not peri:
            peri = {
                "id_antecedente": 0,
                "id_paciente": patient_id,
                "semanas_gestacion": p.get("semanas_gestacion") or 39,
                "peso_nacer_kg": p.get("peso_nacer_kg") or 3.2,
                "talla_nacer_cm": p.get("talla_nacer_cm") or 50.0,
                "perimetro_cefalico_nacer_cm": 34.5,
                "tipo_parto": "Eutócico vaginal",
                "apgar_1min": 9,
                "apgar_5min": 10,
                "complicaciones_neonatales": "Sin complicaciones registradas"
            }

        # Tutor
        tp = next((x for x in self.tables["tutor_paciente"] if x["id_paciente"] == patient_id), None)
        tutor = None
        if tp:
            tutor = next((x for x in self.tables["tutor_legal"] if x["id_tutor"] == tp["id_tutor"]), None)
        if not tutor:
            tutor = {
                "id_tutor": 0,
                "dpi": p.get("dpi_tutor") or "0000000000101",
                "nombres": p.get("nombre_tutor") or "Tutor Legal",
                "apellidos": "",
                "telefono_principal": p.get("telefono_tutor") or "",
                "direccion": p.get("direccion") or "",
                "parentesco": p.get("parentesco_tutor") or "Madre",
                "es_tutor_principal": True
            }
        else:
            tutor = {**tutor, "parentesco": tp.get("parentesco", p.get("parentesco_tutor", "Tutor")), "es_tutor_principal": tp.get("es_tutor_principal", True)}

        # Somatometría
        somatometrias = [
            copy.deepcopy(s) for s in self.tables["antropometria_somatometria"] if s["id_paciente"] == patient_id
        ]
        somatometrias.sort(key=lambda s: s.get("id_somatometria", 0), reverse=True)

        # Vacunas aplicadas
        vacunas = [
            copy.deepcopy(v) for v in self.tables["vacunacion"] if v["id_paciente"] == patient_id
        ]

        # Hitos psicomotores (Denver II)
        hitos = [
            copy.deepcopy(h) for h in self.tables["evaluacion_desarrollo"] if h["id_paciente"] == patient_id
        ]

        # Alergias
        alergias_raw = [
            a for a in self.tables["alergia_paciente"] if a["id_paciente"] == patient_id
        ]
        alergias = []
        for a in alergias_raw:
            cat = next((c for c in self.tables["catalogo_alergeno"] if c["id_alergeno"] == a["id_alergeno"]), None)
            alergias.append({
                "id_alergia_paciente": a["id_alergia_paciente"],
                "id_alergeno": a["id_alergeno"],
                "nombre_alergeno": cat["nombre_alergeno"] if cat else f"Alérgeno #{a['id_alergeno']}",
                "tipo_alergeno": cat["tipo_alergeno"] if cat else "General",
                "riesgo_anafilaxia": cat["riesgo_anafilaxia"] if cat else False,
                "fecha_deteccion": a["fecha_deteccion"],
                "severidad": a["severidad"],
                "sintomas_observados": a.get("sintomas_observados", "")
            })

        return {
            "paciente": copy.deepcopy(p),
            "perinatal": peri,
            "antecedente_perinatal": peri,
            "tutor": tutor,
            "tutores": [tutor] if tutor else [],
            "somatometrias": somatometrias,
            "somatometria": somatometrias,
            "vacunas": vacunas,
            "vacunaciones": vacunas,
            "hitos": hitos,
            "hitos_desarrollo": hitos,
            "alergias": alergias
        }

    def update_perinatal(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        peri = next((x for x in self.tables["antecedente_perinatal"] if x["id_paciente"] == patient_id), None)
        if not peri:
            peri = {
                "id_antecedente": self._next_id("antecedente_perinatal"),
                "id_paciente": patient_id
            }
            self.tables["antecedente_perinatal"].append(peri)

        peri["semanas_gestacion"] = int(data.get("semanas_gestacion", peri.get("semanas_gestacion", 39)))
        peri["peso_nacer_kg"] = float(data.get("peso_nacer_kg", peri.get("peso_nacer_kg", 3.2)))
        peri["talla_nacer_cm"] = float(data.get("talla_nacer_cm", peri.get("talla_nacer_cm", 50.0)))
        peri["perimetro_cefalico_nacer_cm"] = float(data.get("perimetro_cefalico_nacer_cm", peri.get("perimetro_cefalico_nacer_cm", 34.5)))
        peri["tipo_parto"] = data.get("tipo_parto", peri.get("tipo_parto", "Eutócico vaginal"))
        peri["apgar_1min"] = int(data.get("apgar_1min", peri.get("apgar_1min", 9)))
        peri["apgar_5min"] = int(data.get("apgar_5min", peri.get("apgar_5min", 10)))
        peri["complicaciones_neonatales"] = data.get("complicaciones_neonatales", peri.get("complicaciones_neonatales", ""))

        # Reflejar en paciente
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if p:
            p["semanas_gestacion"] = peri["semanas_gestacion"]
            p["peso_nacer_kg"] = peri["peso_nacer_kg"]
            p["talla_nacer_cm"] = peri["talla_nacer_cm"]

        return copy.deepcopy(peri)

    def update_guardian(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado")

        p["nombre_tutor"] = data.get("nombres") or data.get("nombre_tutor", p.get("nombre_tutor"))
        p["parentesco_tutor"] = data.get("parentesco", p.get("parentesco_tutor"))
        p["dpi_tutor"] = data.get("dpi", p.get("dpi_tutor"))
        p["telefono_tutor"] = data.get("telefono_principal") or data.get("telefono", p.get("telefono_tutor"))

        tp = next((x for x in self.tables["tutor_paciente"] if x["id_paciente"] == patient_id), None)
        if tp:
            tp["parentesco"] = p["parentesco_tutor"]
            tutor = next((x for x in self.tables["tutor_legal"] if x["id_tutor"] == tp["id_tutor"]), None)
            if tutor:
                tutor["dpi"] = p["dpi_tutor"]
                tutor["nombres"] = p["nombre_tutor"]
                tutor["telefono_principal"] = p["telefono_tutor"]
                if data.get("direccion"):
                    tutor["direccion"] = data["direccion"]
        return {"ok": True, "paciente_id": patient_id, "nombre_tutor": p["nombre_tutor"]}

    def add_somatometry(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado")

        peso_kg = float(data["peso_kg"])
        talla_cm = float(data["talla_cm"])
        perimetro = float(data.get("perimetro_cefalico_cm", 48.0))
        edad_meses = int(data.get("edad_meses", 24))
        imc = round(peso_kg / ((talla_cm / 100) ** 2), 2)
        percentil = float(data.get("percentil_crecimiento", 50.0))

        id_som = self._next_id("antropometria_somatometria")
        rec = {
            "id_somatometria": id_som,
            "id_consulta": data.get("id_consulta", 0),
            "id_paciente": patient_id,
            "fecha": data.get("fecha", date.today().isoformat()),
            "edad_meses_atencion": edad_meses,
            "peso_kg": peso_kg,
            "talla_cm": talla_cm,
            "perimetro_cefalico_cm": perimetro,
            "imc_calculado": imc,
            "percentil_peso_edad": percentil,
            "percentil_talla_edad": percentil,
            "percentil_pc_edad": percentil
        }
        self.tables["antropometria_somatometria"].append(rec)
        return copy.deepcopy(rec)

    def list_vaccines_catalog(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.tables["vacuna_catalogo"])

    def list_vaccine_batches(self) -> List[Dict[str, Any]]:
        res = []
        for l in self.tables["lote_vacuna"]:
            v = next((x for x in self.tables["vacuna_catalogo"] if x["id_vacuna"] == l["id_vacuna"]), None)
            res.append({
                **l,
                "nombre_vacuna": v["nombre_vacuna"] if v else f"Vacuna #{l['id_vacuna']}",
                "via_administracion": v["via_administracion"] if v else "Intramuscular"
            })
        return res

    def create_vaccine_batch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        new_id = self._next_id("lote_vacuna")
        lote = {
            "id_lote": new_id,
            "id_vacuna": int(data["id_vacuna"]),
            "numero_lote": data["numero_lote"].strip().upper(),
            "fabricante": data["fabricante"].strip(),
            "fecha_fabricacion": str(data["fecha_fabricacion"]),
            "fecha_vencimiento": str(data["fecha_vencimiento"]),
            "stock_disponible": int(data["stock_disponible"]),
            "temp_min_celsius": float(data.get("temp_min_celsius", 2.0)),
            "temp_max_celsius": float(data.get("temp_max_celsius", 8.0))
        }
        self.tables["lote_vacuna"].append(lote)
        v = next((x for x in self.tables["vacuna_catalogo"] if x["id_vacuna"] == lote["id_vacuna"]), None)
        return {**lote, "nombre_vacuna": v["nombre_vacuna"] if v else "Biológico"}

    def add_vaccination(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado")

        new_id = self._next_id("vacunacion")
        nombre_vac = data.get("nombre_vacuna")
        id_lote = data.get("id_lote")
        lote_num = data.get("lote") or "LOTE-2026"

        if id_lote:
            lote_obj = next((l for l in self.tables["lote_vacuna"] if l["id_lote"] == int(id_lote)), None)
            if lote_obj:
                lote_num = lote_obj["numero_lote"]
                if lote_obj["stock_disponible"] > 0:
                    lote_obj["stock_disponible"] -= 1
                v = next((x for x in self.tables["vacuna_catalogo"] if x["id_vacuna"] == lote_obj["id_vacuna"]), None)
                if v and not nombre_vac:
                    nombre_vac = v["nombre_vacuna"]

        nombre_vac = nombre_vac or "Vacuna Pediátrica"
        rec = {
            "id_vacunacion": new_id,
            "id_paciente": patient_id,
            "id_consulta": int(data.get("id_consulta", 0)),
            "nombre_vacuna": nombre_vac,
            "dosis": data.get("dosis", "Dosis recomendada"),
            "lote": lote_num,
            "fecha_aplicacion": data.get("fecha_aplicacion", date.today().isoformat()),
            "proxima_fecha_refuerzo": data.get("proxima_fecha_refuerzo")
        }
        self.tables["vacunacion"].append(rec)

        id_reg = self._next_id("registro_vacunacion")
        self.tables["registro_vacunacion"].append({
            "id_registro_vac": id_reg,
            "id_vacunacion": new_id,
            "id_paciente": patient_id,
            "id_consulta": rec["id_consulta"],
            "id_lote": int(id_lote) if id_lote else None,
            "numero_dosis": int(data.get("numero_dosis", 1)),
            "fecha_aplicacion": rec["fecha_aplicacion"],
            "profesional_aplico": data.get("profesional_aplico", "Enfermería Pediátrica"),
            "proxima_fecha_refuerzo": rec["proxima_fecha_refuerzo"],
            "reaccion_adversa": data.get("reaccion_adversa", "Sin reacciones adversas")
        })

        return copy.deepcopy(rec)

    def list_somatometry(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = self.tables["antropometria_somatometria"]
        if patient_id is not None:
            rows = [s for s in rows if s["id_paciente"] == patient_id]
        res = []
        for s in rows:
            p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == s["id_paciente"]), None)
            res.append({
                **copy.deepcopy(s),
                "paciente_nombre": f"{p['nombres']} {p['apellidos']}" if p else f"Paciente #{s['id_paciente']}"
            })
        res.sort(key=lambda x: x.get("id_somatometria", 0), reverse=True)
        return res

    def list_vaccinations(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = self.tables["vacunacion"]
        if patient_id is not None:
            rows = [v for v in rows if v["id_paciente"] == patient_id]
        res = []
        for v in rows:
            p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == v["id_paciente"]), None)
            res.append({
                **copy.deepcopy(v),
                "paciente_nombre": f"{p['nombres']} {p['apellidos']}" if p else f"Paciente #{v['id_paciente']}"
            })
        res.sort(key=lambda x: str(x.get("fecha_aplicacion", "")), reverse=True)
        return res

    def list_development_milestones(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = self.tables["evaluacion_desarrollo"]
        if patient_id is not None:
            rows = [h for h in rows if h["id_paciente"] == patient_id]
        res = []
        for h in rows:
            p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == h["id_paciente"]), None)
            res.append({
                **copy.deepcopy(h),
                "paciente_nombre": f"{p['nombres']} {p['apellidos']}" if p else f"Paciente #{h['id_paciente']}"
            })
        return res

    def add_development_milestone(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado")

        new_id = self._next_id("evaluacion_desarrollo")
        rec = {
            "id_evaluacion": new_id,
            "id_consulta": int(data.get("id_consulta", 0)),
            "id_paciente": patient_id,
            "area_desarrollo": data["area_desarrollo"],
            "hito_evaluado": data["hito_evaluado"].strip(),
            "cumple_hito": bool(data.get("cumple_hito", True)),
            "observaciones": data.get("observaciones", "")
        }
        self.tables["evaluacion_desarrollo"].append(rec)
        return copy.deepcopy(rec)

    def list_patient_allergies(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        raw = self.tables["alergia_paciente"]
        if patient_id is not None:
            raw = [a for a in raw if a["id_paciente"] == patient_id]
        res = []
        for a in raw:
            cat = next((c for c in self.tables["catalogo_alergeno"] if c["id_alergeno"] == a["id_alergeno"]), None)
            p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == a["id_paciente"]), None)
            res.append({
                "id_alergia_paciente": a["id_alergia_paciente"],
                "id_paciente": a["id_paciente"],
                "paciente_nombre": f"{p['nombres']} {p['apellidos']}" if p else f"Paciente #{a['id_paciente']}",
                "id_alergeno": a["id_alergeno"],
                "nombre_alergeno": cat["nombre_alergeno"] if cat else f"Alérgeno #{a['id_alergeno']}",
                "tipo_alergeno": cat["tipo_alergeno"] if cat else "General",
                "riesgo_anafilaxia": cat["riesgo_anafilaxia"] if cat else False,
                "fecha_deteccion": a["fecha_deteccion"],
                "severidad": a["severidad"],
                "sintomas_observados": a.get("sintomas_observados", "")
            })
        return res

    def add_patient_allergy(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        p = next((x for x in self.tables["paciente_pediatrico"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado")

        id_alergeno = int(data["id_alergeno"])
        # Verificar duplicado
        for a in self.tables["alergia_paciente"]:
            if a["id_paciente"] == patient_id and a["id_alergeno"] == id_alergeno:
                raise ValueError("El paciente ya tiene registrada esta alergia")

        new_id = self._next_id("alergia_paciente")
        rec = {
            "id_alergia_paciente": new_id,
            "id_paciente": patient_id,
            "id_alergeno": id_alergeno,
            "fecha_deteccion": data.get("fecha_deteccion", date.today().isoformat()),
            "severidad": data.get("severidad", "Moderada"),
            "sintomas_observados": data.get("sintomas_observados", "")
        }
        self.tables["alergia_paciente"].append(rec)
        cat = next((c for c in self.tables["catalogo_alergeno"] if c["id_alergeno"] == id_alergeno), None)
        return {
            **rec,
            "nombre_alergeno": cat["nombre_alergeno"] if cat else "Alérgeno",
            "riesgo_anafilaxia": cat["riesgo_anafilaxia"] if cat else False
        }

    def list_allergens_catalog(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.tables["catalogo_alergeno"])

    def list_growth_percentiles(self, sexo: Optional[str] = None, parametro: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.tables["normativa_percentil_oms"]
        if sexo:
            rows = [r for r in rows if r["sexo"] == sexo.upper()]
        if parametro:
            rows = [r for r in rows if r["parametro_antropometrico"] == parametro]
        return copy.deepcopy(rows)


# ============================================================================
# 3. MOTOR MONGODB SIMULADO (Laboratorio Clínico)
# Database: 'laboratorio_clinico', NoSQL Documental, Colecciones referenciadas
# con parámetros analíticos dinámicos embebidos y alertas críticas.
# ============================================================================
class SimulatedMongoDBEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.collections = {
            "pacientes": [
                {
                    "id_paciente": 1,
                    "nombres": "Estuardo René",
                    "apellidos": "Guzmán Barrios",
                    "fecha_nacimiento": "1988-11-23",
                    "sexo": "M",
                    "dpi": "2389104520101",
                    "direccion": "Zona 9, Quetzaltenango",
                    "telefono": "4811-2299",
                    "correo_electronico": "eguzman@gmail.com",
                    "tipo_sangre": "A+",
                    "contacto_emergencia": {"nombre": "Claudia de Guzmán", "telefono": "4811-2200"},
                    "fecha_registro": "2026-02-10",
                    "estado": "activo"
                },
                {
                    "id_paciente": 2,
                    "nombres": "Marta Alicia",
                    "apellidos": "Hernández de León",
                    "fecha_nacimiento": "1965-04-18",
                    "sexo": "F",
                    "dpi": "1890334410101",
                    "direccion": "Zona 1, Quetzaltenango",
                    "telefono": "5901-4433",
                    "correo_electronico": "mhernandez@hotmail.com",
                    "tipo_sangre": "O+",
                    "contacto_emergencia": {"nombre": "Jorge Hernández (Hijo)", "telefono": "5901-4434"},
                    "fecha_registro": "2026-03-01",
                    "estado": "activo"
                }
            ],
            "historiales_clinicos": [
                {
                    "id_historial": 1,
                    "id_paciente": 1,
                    "fecha_apertura": "2026-02-10",
                    "fecha_ultima_actualizacion": "2026-03-01T10:15:00Z",
                    "estado": "activo",
                    "motivo_baja": None
                },
                {
                    "id_historial": 2,
                    "id_paciente": 2,
                    "fecha_apertura": "2026-03-01",
                    "fecha_ultima_actualizacion": "2026-03-01T09:15:00Z",
                    "estado": "activo",
                    "motivo_baja": None
                }
            ],
            "tipos_examen": [
                {
                    "codigo": "HEM-01",
                    "nombre_examen": "Hematología Completa Automatizada",
                    "area_laboratorio": "Hematología",
                    "costo": 120.0
                },
                {
                    "codigo": "QUI-01",
                    "nombre_examen": "Perfil Glucémico y Renal (Glucosa + Creatinina)",
                    "area_laboratorio": "Química Clínica",
                    "costo": 95.0
                }
            ],
            "ordenes": [
                {
                    "id_orden": 1,
                    "id_paciente": 1,
                    "fecha_hora_ingreso": "2026-03-01T07:15:00Z",
                    "prioridad": "normal",
                    "diagnostico_presuntivo": "Chequeo médico de rutina",
                    "estado_orden": "completada"
                },
                {
                    "id_orden": 2,
                    "id_paciente": 2,
                    "fecha_hora_ingreso": "2026-03-01T08:00:00Z",
                    "prioridad": "emergencia",
                    "diagnostico_presuntivo": "Descompensación diabética",
                    "estado_orden": "completada"
                }
            ],
            "muestras": [
                {
                    "id_muestra": 1,
                    "id_orden": 1,
                    "tipo_muestra": "Sangre total EDTA",
                    "codigo_etiqueta_barras": "LAB-2026-000101",
                    "estado": "procesada"
                },
                {
                    "id_muestra": 2,
                    "id_orden": 2,
                    "tipo_muestra": "Suero sanguíneo",
                    "codigo_etiqueta_barras": "LAB-2026-000102",
                    "estado": "procesada"
                }
            ],
            "resultados": [
                {
                    "id_resultado": 1,
                    "id_orden": 1,
                    "id_paciente": 1,
                    "codigo_examen": "HEM-01",
                    "nombre_examen": "Hematología Completa Automatizada",
                    "fecha_hora_analisis": "2026-03-01T09:30:00Z",
                    "fecha_hora_validacion": "2026-03-01T10:15:00Z",
                    "estado": "validado",
                    "alertas_criticas": False,
                    "observaciones_tecnicas": "Curvas citométricas normales",
                    "conclusiones_diagnosticas": "Serie roja y blanca normales.",
                    "parametros": [
                        {"nombre_parametro": "Leucocitos Totales", "valor_resultado": 7.2, "unidad_medida": "10^3/uL", "rango_referencia_min": 4.5, "rango_referencia_max": 11.0, "interpretacion_alerta": "NORMAL"},
                        {"nombre_parametro": "Hemoglobina", "valor_resultado": 15.1, "unidad_medida": "g/dL", "rango_referencia_min": 13.5, "rango_referencia_max": 17.5, "interpretacion_alerta": "NORMAL"},
                        {"nombre_parametro": "Hematocrito", "valor_resultado": 45.3, "unidad_medida": "%", "rango_referencia_min": 41.0, "rango_referencia_max": 50.0, "interpretacion_alerta": "NORMAL"},
                        {"nombre_parametro": "Plaquetas", "valor_resultado": 245.0, "unidad_medida": "10^3/uL", "rango_referencia_min": 150.0, "rango_referencia_max": 450.0, "interpretacion_alerta": "NORMAL"}
                    ]
                },
                {
                    "id_resultado": 2,
                    "id_orden": 2,
                    "id_paciente": 2,
                    "codigo_examen": "QUI-01",
                    "nombre_examen": "Perfil Glucémico y Renal",
                    "fecha_hora_analisis": "2026-03-01T09:00:00Z",
                    "fecha_hora_validacion": "2026-03-01T09:15:00Z",
                    "estado": "validado",
                    "alertas_criticas": True,
                    "observaciones_tecnicas": "Alerta crítica notificada vía telefónica a médico.",
                    "conclusiones_diagnosticas": "Hiperglucemia severa descompensada.",
                    "parametros": [
                        {"nombre_parametro": "Glucosa Sérica Basal", "valor_resultado": 348.0, "unidad_medida": "mg/dL", "rango_referencia_min": 70.0, "rango_referencia_max": 100.0, "interpretacion_alerta": "CRITICO_ALTO"},
                        {"nombre_parametro": "Creatinina Sérica", "valor_resultado": 1.85, "unidad_medida": "mg/dL", "rango_referencia_min": 0.5, "rango_referencia_max": 1.1, "interpretacion_alerta": "ALTO"}
                    ]
                }
            ]
        }
        self.sequences = {col: len(docs) for col, docs in self.collections.items()}

    def _next_id(self, col: str) -> int:
        self.sequences[col] = self.sequences.get(col, 0) + 1
        return self.sequences[col]

    def insert_patient(self, data: Dict[str, Any]) -> Dict[str, Any]:
        dpi = data["dpi"]
        for p in self.collections["pacientes"]:
            if p["dpi"] == dpi:
                raise ValueError(f"MongoDB Duplicate Key Error: {dpi}")

        new_id = self._next_id("pacientes")
        doc = {
            "id_paciente": new_id,
            "nombres": data["nombres"],
            "apellidos": data["apellidos"],
            "fecha_nacimiento": str(data["fecha_nacimiento"]),
            "sexo": data.get("sexo", "M"),
            "dpi": dpi,
            "direccion": data.get("direccion", ""),
            "telefono": data.get("telefono", ""),
            "correo_electronico": data.get("correo_electronico", ""),
            "tipo_sangre": data.get("tipo_sangre", "O+"),
            "contacto_emergencia": {
                "nombre": data.get("contacto_emergencia_nombre", ""),
                "telefono": data.get("contacto_emergencia_telefono", "")
            },
            "fecha_registro": data.get("fecha_registro", date.today().isoformat()),
            "estado": data.get("estado", "activo")
        }
        self.collections["pacientes"].append(doc)

        hist_id = self._next_id("historiales_clinicos")
        self.collections["historiales_clinicos"].append({
            "id_historial": hist_id,
            "id_paciente": new_id,
            "fecha_apertura": date.today().isoformat(),
            "fecha_ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            "estado": "activo",
            "motivo_baja": None
        })
        return copy.deepcopy(doc)

    def insert_lab_order_and_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Inserta orden, muestra y resultado dinámico con parámetros embebidos."""
        paciente_id = data["id_paciente"]
        id_orden = self._next_id("ordenes")
        orden_doc = {
            "id_orden": id_orden,
            "id_paciente": paciente_id,
            "fecha_hora_ingreso": datetime.now(timezone.utc).isoformat(),
            "prioridad": data.get("prioridad", "normal"),
            "diagnostico_presuntivo": data.get("motivo", "Examen de laboratorio"),
            "estado_orden": "completada"
        }
        self.collections["ordenes"].append(orden_doc)

        id_muestra = self._next_id("muestras")
        muestra_doc = {
            "id_muestra": id_muestra,
            "id_orden": id_orden,
            "tipo_muestra": data.get("tipo_muestra", "Muestra biológica"),
            "codigo_etiqueta_barras": f"LAB-2026-{id_orden:06d}",
            "estado": "procesada"
        }
        self.collections["muestras"].append(muestra_doc)

        # Generar o parsear parámetros analíticos
        parametros = data.get("parametros")
        if not parametros:
            # Parámetro estándar según tipo
            valor_glucosa = float(data.get("valor_analitico", 95.0))
            alerta = "CRITICO_ALTO" if valor_glucosa > 200 else ("ALTO" if valor_glucosa > 105 else "NORMAL")
            parametros = [
                {
                    "nombre_parametro": data.get("nombre_parametro", "Glucosa en Ayunas"),
                    "valor_resultado": valor_glucosa,
                    "unidad_medida": data.get("unidad_medida", "mg/dL"),
                    "rango_referencia_min": 70.0,
                    "rango_referencia_max": 100.0,
                    "interpretacion_alerta": alerta
                }
            ]

        tiene_alertas = any("CRITICO" in p.get("interpretacion_alerta", "") for p in parametros)
        id_res = self._next_id("resultados")
        res_doc = {
            "id_resultado": id_res,
            "id_orden": id_orden,
            "id_paciente": paciente_id,
            "codigo_examen": data.get("codigo_examen", "LAB-GEN"),
            "nombre_examen": data.get("nombre_examen", data.get("motivo", "Análisis Clínico")),
            "fecha_hora_analisis": datetime.now(timezone.utc).isoformat(),
            "fecha_hora_validacion": datetime.now(timezone.utc).isoformat(),
            "estado": "validado",
            "alertas_criticas": tiene_alertas,
            "observaciones_tecnicas": data.get("observaciones_tecnicas", "Procesado en analizador automatizado."),
            "conclusiones_diagnosticas": data.get("conclusiones_diagnosticas", data.get("notas_clinicas", "Resultados validados.")),
            "parametros": parametros
        }
        self.collections["resultados"].append(res_doc)

        # Actualizar historial
        for h in self.collections["historiales_clinicos"]:
            if h["id_paciente"] == paciente_id:
                h["fecha_ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()

        return {
            "id_consulta": id_res, # Mapeo polimórfico a consulta clínica
            "id_orden": id_orden,
            "orden": orden_doc,
            "muestra": muestra_doc,
            "resultado": res_doc
        }


# ============================================================================
# 4. MOTOR FIREBASE SIMULADO (Clínica Odontológica)
# Database: 'clinica-odontologica-landivar', Cloud Firestore Document Model
# Colecciones: pacientes, odontologos, secretarias, citas, procedimientos
# ============================================================================
class SimulatedFirebaseEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.collections = {
            "pacientes": [
                {
                    "id_paciente": 1,
                    "nombre_completo": "Sofía Valentina Morales Díaz",
                    "nombres": "Sofía Valentina",
                    "apellidos": "Morales Díaz",
                    "fecha_nacimiento": "1999-07-22",
                    "sexo": "F",
                    "dpi": "2589012340101",
                    "direccion": "Zona 10, Quetzaltenango",
                    "telefono": "5512-3344",
                    "correo_electronico": "sofia.morales@gmail.com",
                    "contacto_emergencia": {"nombre": "Carmen Díaz de Morales", "telefono": "5512-3300"},
                    "fecha_registro": "2026-01-15",
                    "estado": "activo"
                }
            ],
            "odontologos": [
                {
                    "id_odontologo": 1,
                    "nombre_completo": "Dr. Rodrigo Andrés Molina",
                    "numero_colegiado": "ODONT-3210",
                    "especialidad": "Ortodoncia y Rehabilitación Oral",
                    "telefono": "5554-0101",
                    "correo_electronico": "rmolina@clinicadental.gt",
                    "estado": "activo"
                }
            ],
            "secretarias": [
                {
                    "id_secretaria": 1,
                    "nombre_completo": "Claudia Maricela Fuentes",
                    "usuario": "sec_claudia",
                    "telefono": "5554-0110",
                    "estado": "activo"
                }
            ],
            "procedimientos_catalogo": [
                {"id_procedimiento": 1, "nombre_procedimiento": "Profilaxis y Limpieza Dental con Ultrasonido", "costo": 250.0},
                {"id_procedimiento": 2, "nombre_procedimiento": "Restauración con Resina Fotocurable (Calza)", "costo": 350.0},
                {"id_procedimiento": 3, "nombre_procedimiento": "Extracción Dental Simple", "costo": 300.0},
                {"id_procedimiento": 4, "nombre_procedimiento": "Endodoncia Unirradicular", "costo": 800.0}
            ],
            "citas": [
                {
                    "id_cita": 1,
                    "id_paciente": 1,
                    "id_odontologo": 1,
                    "id_secretaria": 1,
                    "fecha_hora_programada": "2026-03-01T09:00:00Z",
                    "motivo_consulta": "Sensibilidad y revisión de molar",
                    "estado_cita": "atendida",
                    "fecha_creacion": "2026-02-25T14:30:00Z"
                }
            ],
            "consultas_procedimientos": [
                {
                    "id_consulta_procedimiento": 1,
                    "id_cita": 1,
                    "id_paciente": 1,
                    "id_odontologo": 1,
                    "id_procedimiento": 2,
                    "nombre_procedimiento": "Restauración con Resina Fotocurable (Calza)",
                    "pieza_dental": "46 (Primer molar inferior derecho)",
                    "observaciones": "Caries oclusal Grado II. Se realizó grabado ácido y resina A2.",
                    "fecha_realizacion": "2026-03-01T09:45:00Z",
                    "costo": 350.0,
                    "estado": "completado"
                }
            ],
            "historiales": [
                {
                    "id_historial": 1,
                    "id_paciente": 1,
                    "fecha_apertura": "2026-01-15",
                    "fecha_ultima_actualizacion": "2026-03-01T10:00:00Z",
                    "estado": "activo",
                    "motivo_baja": None
                }
            ],
            # Colecciones y tablas del Modelo Relacional / Documental Expandido (+20)
            "piezas_dentales": [
                {"codigo_fdi": 11, "nombre": "Incisivo Central Superior Derecho", "cuadrante": 1},
                {"codigo_fdi": 16, "nombre": "Primer Molar Superior Derecho", "cuadrante": 1},
                {"codigo_fdi": 21, "nombre": "Incisivo Central Superior Izquierdo", "cuadrante": 2},
                {"codigo_fdi": 36, "nombre": "Primer Molar Inferior Izquierdo", "cuadrante": 3},
                {"codigo_fdi": 46, "nombre": "Primer Molar Inferior Derecho", "cuadrante": 4}
            ],
            "odontogramas": [
                {
                    "id_odontograma": 1,
                    "id_paciente": 1,
                    "fecha": "2026-01-15",
                    "hallazgos": [
                        {"pieza_fdi": 46, "cara": "O", "hallazgo": "Caries activa", "color_hex": "#E53935"},
                        {"pieza_fdi": 16, "cara": "O", "hallazgo": "Restauración resina", "color_hex": "#43A047"}
                    ]
                }
            ],
            "odontogramas_detalles": [
                {"id_detalle": 1, "id_paciente": 1, "codigo_fdi": 46, "cara": "O", "hallazgo": "Caries activa", "color_hex": "#E53935", "notas": "Caries oclusal Grado II profunda", "fecha": "2026-03-01"},
                {"id_detalle": 2, "id_paciente": 1, "codigo_fdi": 16, "cara": "O", "hallazgo": "Restauración resina", "color_hex": "#43A047", "notas": "Resina en buen estado", "fecha": "2026-03-01"},
                {"id_detalle": 3, "id_paciente": 1, "codigo_fdi": 21, "cara": "O/I", "hallazgo": "Fractura dental", "color_hex": "#FB8C00", "notas": "Borde incisal con fractura leve", "fecha": "2026-03-01"},
                {"id_detalle": 4, "id_paciente": 1, "codigo_fdi": 36, "cara": "O", "hallazgo": "Sellante de fisuras", "color_hex": "#00ACC1", "notas": "Sellante preventivo intacto", "fecha": "2026-03-01"}
            ],
            "antecedentes_medicos_dentales": [
                {
                    "id_antecedente": 1,
                    "id_paciente": 1,
                    "padece_diabetes": False,
                    "padece_hipertension": True,
                    "padece_coagulopatia": False,
                    "es_alergico_anestesia": True,
                    "es_alergico_latex": False,
                    "esta_embarazada": False,
                    "medicamentos_actuales": "Losartán 50mg/día",
                    "observaciones_medicas": "Alerta clínica: Paciente hipertensa controlada y reacción adversa previa a lidocaína (usar mepivacaína)."
                }
            ],
            "planes_tratamiento": [
                {
                    "id_plan": 1,
                    "id_paciente": 1,
                    "id_odontologo": 1,
                    "titulo": "Rehabilitación oclusal y profilaxis",
                    "costo_total_estimado": 1200.0,
                    "estado_aprobacion": "en_curso",
                    "fecha_propuesta": "2026-02-25",
                    "etapas": [
                        {"id_etapa": 1, "numero_etapa": 1, "descripcion_fase": "Profilaxis y limpieza ultrasónica", "costo_fase": 250.0, "estado_fase": "completada"},
                        {"id_etapa": 2, "numero_etapa": 2, "descripcion_fase": "Restauración con resina pieza 46", "costo_fase": 350.0, "estado_fase": "completada"},
                        {"id_etapa": 3, "numero_etapa": 3, "descripcion_fase": "Reconstrucción estética borde incisal pieza 21", "costo_fase": 600.0, "estado_fase": "en_curso"}
                    ]
                }
            ],
            "facturas_cobro": [
                {
                    "id_factura": 1,
                    "id_paciente": 1,
                    "id_plan": 1,
                    "fecha_emision": "2026-03-01",
                    "monto_total": 1200.0,
                    "monto_pagado": 600.0,
                    "saldo_pendiente": 600.0,
                    "estado_factura": "parcial"
                }
            ],
            "pagos_abono": [
                {"id_pago": 1, "id_factura": 1, "id_paciente": 1, "fecha_pago": "2026-03-01 10:15", "monto_abonado": 350.0, "metodo_pago": "Efectivo", "numero_recibo": "REC-2026-0041", "secretaria": "Claudia Fuentes"},
                {"id_pago": 2, "id_factura": 1, "id_paciente": 1, "fecha_pago": "2026-03-05 11:30", "monto_abonado": 250.0, "metodo_pago": "Tarjeta de Crédito/Débito", "numero_recibo": "REC-2026-0089", "secretaria": "Claudia Fuentes"}
            ],
            "catalogo_hallazgos": [
                {"id_hallazgo": 1, "codigo": "caries", "nombre": "Caries activa", "color_hex": "#E53935"},
                {"id_hallazgo": 2, "codigo": "resina", "nombre": "Restauración resina", "color_hex": "#43A047"},
                {"id_hallazgo": 3, "codigo": "amalgama", "nombre": "Obturación amalgama", "color_hex": "#1E88E5"},
                {"id_hallazgo": 4, "codigo": "corona", "nombre": "Corona protésica", "color_hex": "#FDD835"},
                {"id_hallazgo": 5, "codigo": "endodoncia", "nombre": "Conducto / Endodoncia", "color_hex": "#8E24AA"},
                {"id_hallazgo": 6, "codigo": "ausente", "nombre": "Pieza ausente / extracción", "color_hex": "#757575"},
                {"id_hallazgo": 7, "codigo": "sellante", "nombre": "Sellante de fisuras", "color_hex": "#00ACC1"},
                {"id_hallazgo": 8, "codigo": "fractura", "nombre": "Fractura dental", "color_hex": "#FB8C00"}
            ],
            "insumos_dentales": [
                {"id_insumo": 1, "nombre": "Resina Fotocurable A2", "unidad": "Jeringa 4g", "stock": 25, "stock_minimo": 5, "costo_unitario": 120.0},
                {"id_insumo": 2, "nombre": "Anestubo Lidocaína 2% con Epinefrina", "unidad": "Caja 50 un.", "stock": 180, "stock_minimo": 20, "costo_unitario": 4.5},
                {"id_insumo": 3, "nombre": "Anestubo Mepivacaína 3% (Sin vasoconstrictor)", "unidad": "Caja 50 un.", "stock": 60, "stock_minimo": 10, "costo_unitario": 5.2},
                {"id_insumo": 4, "nombre": "Conos de Gutapercha Endodóntica", "unidad": "Caja", "stock": 40, "stock_minimo": 8, "costo_unitario": 65.0},
                {"id_insumo": 5, "nombre": "Diques de Goma para Aislamiento", "unidad": "Caja 36 un.", "stock": 50, "stock_minimo": 10, "costo_unitario": 80.0}
            ]
        }
        self.sequences = {col: len(docs) for col, docs in self.collections.items()}

    def _next_id(self, col: str) -> int:
        self.sequences[col] = self.sequences.get(col, 0) + 1
        return self.sequences[col]

    def insert_patient(self, data: Dict[str, Any]) -> Dict[str, Any]:
        dpi = data["dpi"]
        for p in self.collections["pacientes"]:
            if p["dpi"] == dpi:
                raise ValueError(f"Firestore Document Key Error: {dpi}")

        new_id = self._next_id("pacientes")
        nombres = data.get("nombres", "")
        apellidos = data.get("apellidos", "")
        doc = {
            "id_paciente": new_id,
            "nombres": nombres,
            "apellidos": apellidos,
            "nombre_completo": f"{nombres} {apellidos}".strip(),
            "fecha_nacimiento": str(data["fecha_nacimiento"]),
            "sexo": data.get("sexo", "M"),
            "dpi": dpi,
            "direccion": data.get("direccion", ""),
            "telefono": data.get("telefono", ""),
            "correo_electronico": data.get("correo_electronico", ""),
            "contacto_emergencia": {
                "nombre": data.get("contacto_emergencia_nombre", ""),
                "telefono": data.get("contacto_emergencia_telefono", "")
            },
            "fecha_registro": data.get("fecha_registro", date.today().isoformat()),
            "estado": data.get("estado", "activo")
        }
        self.collections["pacientes"].append(doc)

        hist_id = self._next_id("historiales")
        self.collections["historiales"].append({
            "id_historial": hist_id,
            "id_paciente": new_id,
            "fecha_apertura": date.today().isoformat(),
            "fecha_ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            "estado": "activo",
            "motivo_baja": None
        })
        return copy.deepcopy(doc)

    def insert_dental_procedure_consultation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        paciente_id = data["id_paciente"]
        id_cita = data.get("id_cita")
        if not id_cita:
            id_cita = self._next_id("citas")
            cita_doc = {
                "id_cita": id_cita,
                "id_paciente": paciente_id,
                "id_odontologo": data.get("id_odontologo", 1),
                "id_secretaria": data.get("id_secretaria", 1),
                "fecha_hora_programada": datetime.now(timezone.utc).isoformat(),
                "motivo_consulta": data.get("motivo", "Consulta odontológica"),
                "estado_cita": "atendida",
                "fecha_creacion": datetime.now(timezone.utc).isoformat()
            }
            self.collections["citas"].append(cita_doc)

        id_proc_reg = self._next_id("consultas_procedimientos")
        costo = float(data.get("costo", 350.0))
        proc_doc = {
            "id_consulta_procedimiento": id_proc_reg,
            "id_cita": id_cita,
            "id_paciente": paciente_id,
            "id_odontologo": data.get("id_odontologo", 1),
            "id_procedimiento": data.get("id_procedimiento", 2),
            "nombre_procedimiento": data.get("nombre_procedimiento", "Procedimiento Odontológico"),
            "pieza_dental": data.get("pieza_dental", "Pieza General"),
            "observaciones": data.get("observaciones", data.get("notas_clinicas", "Procedimiento realizado sin complicaciones.")),
            "fecha_realizacion": datetime.now(timezone.utc).isoformat(),
            "costo": costo,
            "estado": "completado"
        }
        self.collections["consultas_procedimientos"].append(proc_doc)

        for h in self.collections["historiales"]:
            if h["id_paciente"] == paciente_id:
                h["fecha_ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()

        return {
            "id_consulta": id_proc_reg,
            "id_cita": id_cita,
            "procedimiento": proc_doc
        }

    # ------------------------------------------------------------------------
    # Módulo Clínica Odontológica: Operaciones Especializadas
    # ------------------------------------------------------------------------
    def get_dental_details(self, patient_id: int) -> Dict[str, Any]:
        p = next((x for x in self.collections["pacientes"] if x["id_paciente"] == patient_id), None)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado en Clínica Odontológica")

        # Anamnesis sistémica médica
        antecedente = next((x for x in self.collections["antecedentes_medicos_dentales"] if x["id_paciente"] == patient_id), None)
        if not antecedente:
            antecedente = {
                "id_antecedente": 0,
                "id_paciente": patient_id,
                "padece_diabetes": False,
                "padece_hipertension": False,
                "padece_coagulopatia": False,
                "es_alergico_anestesia": False,
                "es_alergico_latex": False,
                "esta_embarazada": False,
                "medicamentos_actuales": "",
                "observaciones_medicas": "Sin antecedentes sistémicos patológicos."
            }

        # Odontograma detallado
        hallazgos = [
            copy.deepcopy(h) for h in self.collections["odontogramas_detalles"] if h["id_paciente"] == patient_id
        ]

        # Procedimientos realizados
        procs = [
            copy.deepcopy(pr) for pr in self.collections["consultas_procedimientos"] if pr["id_paciente"] == patient_id
        ]

        # Piezas tratadas (FDI codes con hallazgos o procedimientos)
        piezas_tratadas = set()
        for h in hallazgos:
            piezas_tratadas.add(str(h["codigo_fdi"]))
        for pr in procs:
            pd = str(pr.get("pieza_dental", ""))
            # Extraer los primeros 2 dígitos si los hay
            m = re.search(r"\b(\d{2})\b", pd)
            if m:
                piezas_tratadas.add(m.group(1))

        # Planes de tratamiento
        planes = [
            copy.deepcopy(pl) for pl in self.collections["planes_tratamiento"] if pl["id_paciente"] == patient_id
        ]

        # Facturas y cobros
        facturas = [
            copy.deepcopy(f) for f in self.collections["facturas_cobro"] if f["id_paciente"] == patient_id
        ]
        pagos = [
            copy.deepcopy(pg) for pg in self.collections["pagos_abono"] if pg["id_paciente"] == patient_id
        ]
        total_facturado = sum(f.get("monto_total", 0.0) for f in facturas)
        total_pagado = sum(pg.get("monto_abonado", 0.0) for pg in pagos)
        saldo_pendiente = max(0.0, total_facturado - total_pagado)

        return {
            "paciente": copy.deepcopy(p),
            "antecedentes": antecedente,
            "antecedentes_sistemicos": antecedente,
            "odontograma": {"hallazgos": hallazgos, "piezas": {str(h["codigo_fdi"]): [h] for h in hallazgos}},
            "hallazgos_odontograma": hallazgos,
            "piezas_tratadas": sorted(list(piezas_tratadas)),
            "procedimientos": procs,
            "planes_tratamiento": planes,
            "facturacion": {
                "facturas": facturas,
                "pagos": pagos,
                "total_facturado": total_facturado,
                "total_pagado": total_pagado,
                "saldo_pendiente": saldo_pendiente
            }
        }

    def update_systemic_background(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        ant = next((x for x in self.collections["antecedentes_medicos_dentales"] if x["id_paciente"] == patient_id), None)
        if not ant:
            ant = {
                "id_antecedente": self._next_id("antecedentes_medicos_dentales"),
                "id_paciente": patient_id
            }
            self.collections["antecedentes_medicos_dentales"].append(ant)

        ant["padece_diabetes"] = ant["diabetes"] = bool(data.get("padece_diabetes", data.get("diabetes", ant.get("padece_diabetes", False))))
        ant["padece_hipertension"] = ant["hipertension"] = bool(data.get("padece_hipertension", data.get("hipertension", ant.get("padece_hipertension", False))))
        ant["padece_coagulopatia"] = ant["trastornos_hemorragicos"] = bool(data.get("padece_coagulopatia", data.get("trastornos_hemorragicos", ant.get("padece_coagulopatia", False))))
        ant["es_alergico_anestesia"] = ant["alergia_anestesia_local"] = bool(data.get("es_alergico_anestesia", data.get("alergia_anestesia_local", ant.get("es_alergico_anestesia", False))))
        ant["es_alergico_latex"] = ant["alergia_latex"] = bool(data.get("es_alergico_latex", data.get("alergia_latex", ant.get("es_alergico_latex", False))))
        ant["esta_embarazada"] = ant["embarazo"] = bool(data.get("esta_embarazada", data.get("embarazo", ant.get("esta_embarazada", False))))
        ant["medicamentos_actuales"] = data.get("medicamentos_actuales", ant.get("medicamentos_actuales", ""))
        ant["observaciones_medicas"] = data.get("observaciones_medicas", ant.get("observaciones_medicas", ""))
        ant["observaciones_medicas"] = data.get("observaciones_medicas", ant.get("observaciones_medicas", ""))

        return copy.deepcopy(ant)

    def get_odontogram(self, patient_id: Optional[int] = None) -> Dict[str, Any]:
        raw = self.collections["odontogramas_detalles"]
        if patient_id is not None:
            hallazgos = [copy.deepcopy(h) for h in raw if h["id_paciente"] == patient_id]
        else:
            hallazgos = [copy.deepcopy(h) for h in raw]
        # Decorar con nombre de paciente si está disponible
        for h in hallazgos:
            pid = h.get("id_paciente")
            p = next((x for x in self.collections["pacientes"] if x["id_paciente"] == pid), None)
            if p:
                h["paciente_nombre"] = f"{p['nombres']} {p['apellidos']}"
        # Agrupar por pieza FDI
        piezas_map: Dict[str, List[Dict[str, Any]]] = {}
        for h in hallazgos:
            piezas_map.setdefault(str(h["codigo_fdi"]), []).append(h)
        return {
            "id_paciente": patient_id,
            "hallazgos": hallazgos,
            "piezas": piezas_map
        }

    def save_odontogram_finding(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        fdi = int(data["codigo_fdi"])
        cara = str(data.get("cara", "O")).upper()
        hallazgo = str(data["hallazgo"]).strip()
        color_hex = str(data.get("color_hex", "#E53935"))
        notas = str(data.get("notas", ""))

        # Buscar si ya existe para esa cara y diente
        existente = next((h for h in self.collections["odontogramas_detalles"]
                          if h["id_paciente"] == patient_id and h["codigo_fdi"] == fdi and h["cara"] == cara), None)
        if existente:
            existente["hallazgo"] = hallazgo
            existente["color_hex"] = color_hex
            existente["notas"] = notas
            existente["fecha"] = date.today().isoformat()
            return copy.deepcopy(existente)

        new_id = self._next_id("odontogramas_detalles")
        item = {
            "id_detalle": new_id,
            "id_paciente": patient_id,
            "codigo_fdi": fdi,
            "cara": cara,
            "hallazgo": hallazgo,
            "color_hex": color_hex,
            "notas": notas,
            "fecha": date.today().isoformat()
        }
        self.collections["odontogramas_detalles"].append(item)
        return copy.deepcopy(item)

    def list_treatment_plans(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        res = []
        for pl in self.collections["planes_tratamiento"]:
            if patient_id is None or pl["id_paciente"] == patient_id:
                p = next((x for x in self.collections["pacientes"] if x["id_paciente"] == pl["id_paciente"]), None)
                res.append({
                    **pl,
                    "paciente_nombre": p.get("nombre_completo") or f"{p.get('nombres','')} {p.get('apellidos','')}" if p else "Paciente"
                })
        return res

    def create_treatment_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        new_id = self._next_id("planes_tratamiento")
        etapas_raw = data.get("etapas") or []
        etapas = []
        for i, e in enumerate(etapas_raw, 1):
            etapas.append({
                "id_etapa": i,
                "numero_etapa": i,
                "descripcion_fase": e.get("descripcion_fase") or e.get("descripcion", f"Fase {i}"),
                "costo_fase": float(e.get("costo_fase", e.get("costo", 0.0))),
                "estado_fase": e.get("estado_fase", "pendiente")
            })
        if not etapas:
            etapas = [{"id_etapa": 1, "numero_etapa": 1, "descripcion_fase": "Fase inicial de tratamiento", "costo_fase": float(data.get("costo_total_estimado", 0.0)), "estado_fase": "pendiente"}]

        costo_total = float(data.get("costo_total_estimado", sum(e["costo_fase"] for e in etapas)))
        plan = {
            "id_plan": new_id,
            "id_paciente": int(data["id_paciente"]),
            "id_odontologo": int(data.get("id_odontologo", 1)),
            "titulo": data.get("titulo", "Plan de Rehabilitación Dental"),
            "costo_total_estimado": costo_total,
            "estado_aprobacion": data.get("estado_aprobacion", "pendiente"),
            "fecha_propuesta": data.get("fecha_propuesta", date.today().isoformat()),
            "etapas": etapas
        }
        self.collections["planes_tratamiento"].append(plan)

        # Crear factura inicial asociada al plan
        id_fac = self._next_id("facturas_cobro")
        self.collections["facturas_cobro"].append({
            "id_factura": id_fac,
            "id_paciente": plan["id_paciente"],
            "id_plan": new_id,
            "fecha_emision": date.today().isoformat(),
            "monto_total": costo_total,
            "monto_pagado": 0.0,
            "saldo_pendiente": costo_total,
            "estado_factura": "pendiente"
        })

        return copy.deepcopy(plan)

    def update_treatment_plan_stage(self, plan_id: int, etapa_id: int, estado: str) -> Dict[str, Any]:
        plan = next((p for p in self.collections["planes_tratamiento"] if p["id_plan"] == plan_id), None)
        if not plan:
            raise ValueError(f"Plan de tratamiento {plan_id} no encontrado")

        etapa = next((e for e in plan["etapas"] if e["id_etapa"] == etapa_id), None)
        if not etapa:
            raise ValueError(f"Etapa {etapa_id} no encontrada en el plan")

        etapa["estado_fase"] = estado
        # Si todas las etapas están completadas, finalizar el plan
        if all(e["estado_fase"] == "completada" for e in plan["etapas"]):
            plan["estado_aprobacion"] = "finalizado"
        elif any(e["estado_fase"] == "completada" for e in plan["etapas"]):
            plan["estado_aprobacion"] = "en_curso"

        return copy.deepcopy(plan)

    def list_dental_procedures_catalog(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.collections["procedimientos_catalogo"])

    def create_dental_procedure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        new_id = self._next_id("procedimientos_catalogo")
        proc = {
            "id_procedimiento": new_id,
            "nombre_procedimiento": data["nombre_procedimiento"].strip(),
            "categoria": data.get("categoria", "Operatoria Dental"),
            "descripcion": data.get("descripcion", ""),
            "duracion_estimada_min": int(data.get("duracion_estimada_min", 45)),
            "costo": float(data["costo"])
        }
        self.collections["procedimientos_catalogo"].append(proc)
        return copy.deepcopy(proc)

    def list_billing_and_payments(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        facturas = self.collections["facturas_cobro"]
        if patient_id is not None:
            facturas = [f for f in facturas if f["id_paciente"] == patient_id]

        res = []
        for f in facturas:
            p = next((x for x in self.collections["pacientes"] if x["id_paciente"] == f["id_paciente"]), None)
            pl = next((x for x in self.collections["planes_tratamiento"] if x["id_plan"] == f.get("id_plan")), None)
            pagos = [pg for pg in self.collections["pagos_abono"] if pg["id_factura"] == f["id_factura"]]
            res.append({
                **f,
                "paciente_nombre": p.get("nombre_completo") or f"{p.get('nombres','')} {p.get('apellidos','')}" if p else "Paciente",
                "plan_titulo": pl.get("titulo") if pl else "Consulta/Procedimiento directo",
                "abonos": copy.deepcopy(pagos)
            })
        return res

    def register_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        id_factura = int(data["id_factura"])
        monto = float(data["monto_abonado"])
        fac = next((f for f in self.collections["facturas_cobro"] if f["id_factura"] == id_factura), None)
        if not fac:
            raise ValueError(f"Factura {id_factura} no encontrada")

        new_id = self._next_id("pagos_abono")
        pago = {
            "id_pago": new_id,
            "id_factura": id_factura,
            "id_paciente": fac["id_paciente"],
            "fecha_pago": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "monto_abonado": monto,
            "metodo_pago": data.get("metodo_pago", "Efectivo"),
            "numero_recibo": data["numero_recibo"].strip().upper(),
            "secretaria": data.get("secretaria", "Secretaría de Recepción")
        }
        self.collections["pagos_abono"].append(pago)

        fac["monto_pagado"] = round(fac["monto_pagado"] + monto, 2)
        fac["saldo_pendiente"] = max(0.0, round(fac["monto_total"] - fac["monto_pagado"], 2))
        if fac["saldo_pendiente"] == 0:
            fac["estado_factura"] = "cancelada"
        else:
            fac["estado_factura"] = "parcial"

        return {
            **copy.deepcopy(pago),
            "monto": monto,
            "monto_abonado": monto,
            "pago": copy.deepcopy(pago),
            "factura": copy.deepcopy(fac)
        }

    def list_dental_findings_catalog(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.collections["catalogo_hallazgos"])

    def list_dental_supplies(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.collections["insumos_dentales"])
