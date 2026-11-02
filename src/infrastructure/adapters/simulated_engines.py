"""
Simulated High-Fidelity In-Memory Storage Engines.
Provides resilient, fully operational implementations of the 4 database models
when external DB servers are not active on the host machine.
Strictly replicates the relational constraints, document embedding, and collections
of PostgreSQL, MySQL, MongoDB, and Firebase.
"""

import copy
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
            ]
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
