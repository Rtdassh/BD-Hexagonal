"""
Adaptador MySQL (InnoDB) - Centro Médico Pediátrico.

Consultas cortas y frecuentes: el diagnóstico va en la misma fila de la consulta
(una consulta pediátrica tiene un diagnóstico principal), junto con la
somatometría. Vacunas y recetas son tablas hijas. Todo se graba dentro de una
transacción InnoDB (START TRANSACTION / COMMIT / ROLLBACK).
"""

import re
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import mysql.connector
from mysql.connector import errorcode, pooling

from .base_adapter import BaseClinicalAdapter
from ..config import Config
from ...domain.entities import (
    Appointment,
    Consultation,
    DatabaseEngine,
    Diagnosis,
    InstitutionType,
    Patient,
    Prescription,
    Professional,
    SomatometryRecord,
    UnifiedClinicalRecord,
    UserRole,
    VaccinationRecord,
)

# Campos de la API -> columnas de paciente_pediatrico
CAMPOS_EDITABLES = {
    "nombres": "nombres", "apellidos": "apellidos", "fecha_nacimiento": "fecha_nacimiento",
    "sexo": "sexo", "direccion": "direccion", "nombre_tutor": "nombre_tutor",
    "parentesco_tutor": "parentesco_tutor", "dpi_tutor": "dpi_tutor",
    "telefono_tutor": "telefono_tutor", "telefono": "telefono_tutor",
    "semanas_gestacion": "semanas_gestacion", "peso_nacer_kg": "peso_nacer_kg",
    "talla_nacer_cm": "talla_nacer_cm",
}

TIPO_CONSULTA = {"ordinaria": "control_sano", "emergencia": "urgencia"}


# Mensajes para las restricciones CHECK (database/mysql/01_init_pediatrico.sql)
MENSAJES_CHECK = {
    "chk_ped_cui": "El CUI debe tener exactamente 13 dígitos",
    "chk_ped_dpi_tutor": "El DPI del tutor debe tener exactamente 13 dígitos",
    "chk_ped_tel_tutor": "El teléfono del tutor debe tener el formato ####-#### y empezar con 2 a 7",
    "chk_ped_nombres": "Nombres y apellidos deben tener al menos 2 caracteres",
    "chk_ped_gestacion": "Las semanas de gestación deben estar entre 20 y 45",
    "chk_ped_peso_nacer": "El peso al nacer debe estar entre 0.3 y 7 kg",
    "chk_ped_talla_nacer": "La talla al nacer debe estar entre 20 y 65 cm",
    "chk_pediatra_colegiado": "El número de colegiado solo admite letras mayúsculas, números y guion (3 a 20)",
    "chk_pediatra_telefono": "El teléfono debe tener el formato ####-####",
    "chk_ped_temperatura": "La temperatura debe estar entre 30 y 45 °C",
    "chk_ped_frecuencia": "La frecuencia cardiaca debe estar entre 20 y 250 lpm",
    "chk_ped_peso": "El peso debe estar entre 0.3 y 150 kg",
    "chk_ped_talla": "La talla debe estar entre 20 y 200 cm",
    "chk_ped_perimetro": "El perímetro cefálico debe estar entre 20 y 70 cm",
    "chk_ped_percentil": "El percentil debe estar entre 0 y 100",
    "chk_ped_cie10": "El código CIE-10 no tiene un formato válido (ej. Z00.1)",
    "chk_ped_receta_duracion": "La duración de la receta debe estar entre 1 y 90 días",
}


class MySQLAdapter(BaseClinicalAdapter):
    is_live = True

    def __init__(self, config: Config):
        self.config = config
        self.pool = pooling.MySQLConnectionPool(
            pool_name="pediatrico",
            pool_size=5,
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            database=config.MYSQL_DATABASE,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            connection_timeout=3,
            autocommit=False,
        )

    @contextmanager
    def _tx(self):
        conn = self.pool.get_connection()
        cur = None
        try:
            conn.start_transaction(isolation_level="READ COMMITTED")
            cur = conn.cursor(dictionary=True)
            yield cur
            conn.commit()
        except mysql.connector.Error as e:
            conn.rollback()
            # 3819 = CHECK violado; 1644 = SIGNAL de un trigger
            if e.errno == 3819:
                nombre = (re.search(r"'([^']+)'", e.msg or "") or [None, None])[1]
                raise ValueError(MENSAJES_CHECK.get(nombre, f"Dato no válido ({nombre})"))
            if e.errno == 1644:
                raise ValueError(e.msg)
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            conn.close()  # devuelve la conexión al pool

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.CENTRO_PEDIATRICO

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.MYSQL

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        with self._tx() as cur:
            cur.execute("SELECT VERSION() AS v")
            version = cur.fetchone()["v"]
            cur.execute("""
                SELECT (SELECT COUNT(*) FROM paciente_pediatrico) AS pacientes,
                       (SELECT COUNT(*) FROM consulta) AS consultas,
                       (SELECT COUNT(*) FROM vacunacion) AS vacunas
            """)
            c = cur.fetchone()
        return {
            "institucion": "Centro Médico Pediátrico",
            "motor": "MySQL",
            "modo": "real",
            "estado": "online",
            "version": f"MySQL {version}",
            "base_datos": self.config.MYSQL_DATABASE,
            "latencia_ms": round((time.time() - start) * 1000, 1),
            "conteos": {"pacientes": c["pacientes"], "consultas": c["consultas"], "vacunas": c["vacunas"]},
            "consistencia": "Transacciones InnoDB + llaves foráneas y CHECK",
        }

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------
    def create_patient(self, data: Dict[str, Any]) -> Patient:
        cui = data.get("cui_nacimiento") or data.get("dpi")
        data = {**data, "cui_nacimiento": cui}
        self.requerido(data, "nombres", "apellidos", "fecha_nacimiento", "sexo", "cui_nacimiento",
                       "nombre_tutor", "parentesco_tutor", "dpi_tutor", "telefono_tutor")
        try:
            with self._tx() as cur:
                cur.execute(
                    """INSERT INTO paciente_pediatrico (nombres, apellidos, fecha_nacimiento, sexo,
                           cui_nacimiento, direccion, nombre_tutor, parentesco_tutor, dpi_tutor,
                           telefono_tutor, semanas_gestacion, peso_nacer_kg, talla_nacer_cm)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (data["nombres"].strip(), data["apellidos"].strip(), data["fecha_nacimiento"],
                     data["sexo"], cui.strip(), data.get("direccion"), data["nombre_tutor"],
                     data["parentesco_tutor"], data["dpi_tutor"], data["telefono_tutor"],
                     self._i(data.get("semanas_gestacion")), self._f(data.get("peso_nacer_kg")),
                     self._f(data.get("talla_nacer_cm"))),
                )
                pid = cur.lastrowid
                cur.execute("INSERT INTO historial_pediatrico (id_paciente) VALUES (%s)", (pid,))
        except mysql.connector.IntegrityError as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                raise ValueError(f"Ya existe un paciente con CUI {cui}")
            raise
        return self.get_patient(pid)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        with self._tx() as cur:
            cur.execute("SELECT * FROM paciente_pediatrico WHERE id_paciente = %s", (patient_id,))
            row = cur.fetchone()
        return self._to_patient(row) if row else None

    def search_patients(self, query: str) -> List[Patient]:
        q = (query or "").strip()
        with self._tx() as cur:
            if not q:
                cur.execute("SELECT * FROM paciente_pediatrico ORDER BY apellidos, nombres LIMIT 200")
            else:
                cur.execute(
                    """SELECT * FROM paciente_pediatrico
                       WHERE CONCAT(nombres, ' ', apellidos) LIKE %s OR cui_nacimiento LIKE %s
                          OR nombre_tutor LIKE %s OR CAST(id_paciente AS CHAR) = %s
                       ORDER BY apellidos, nombres LIMIT 200""",
                    (f"%{q}%", f"{q}%", f"%{q}%", q),
                )
            rows = cur.fetchall()
        return [self._to_patient(r) for r in rows]

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        campos = {CAMPOS_EDITABLES[k]: v for k, v in updates.items() if k in CAMPOS_EDITABLES and v not in (None, "")}
        if not campos:
            raise ValueError("No hay campos válidos para actualizar")
        sets = ", ".join(f"{k} = %s" for k in campos)
        with self._tx() as cur:
            cur.execute(f"UPDATE paciente_pediatrico SET {sets} WHERE id_paciente = %s", (*campos.values(), patient_id))
            cur.execute(
                "UPDATE historial_pediatrico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s",
                (patient_id,),
            )
        p = self.get_patient(patient_id)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado")
        return p

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
        estado = self.estado_por_motivo(categoria)
        with self._tx() as cur:
            cur.execute("SELECT estado FROM historial_pediatrico WHERE id_paciente = %s FOR UPDATE", (patient_id,))
            h = cur.fetchone()
            if not h:
                raise ValueError(f"Paciente {patient_id} no encontrado")
            if h["estado"] != "activo":
                raise ValueError("El historial ya está dado de baja")
            cur.execute(
                "UPDATE historial_pediatrico SET estado = %s, motivo_baja = %s WHERE id_paciente = %s",
                (estado, motivo_baja[:150], patient_id),
            )
            cur.execute("UPDATE paciente_pediatrico SET estado = 'dado_de_baja' WHERE id_paciente = %s", (patient_id,))
            cur.execute(
                "UPDATE cita SET estado_cita = 'cancelada' WHERE id_paciente = %s AND estado_cita = 'programada'",
                (patient_id,),
            )
            canceladas = cur.rowcount
        return {
            "id_paciente": patient_id, "estado": estado, "motivo_baja": motivo_baja,
            "citas_canceladas": canceladas, "motor": "MySQL",
            "mensaje": "Historial archivado en una sola transacción InnoDB.",
        }

    # ------------------------------------------------------------------
    # Citas
    # ------------------------------------------------------------------
    def create_appointment(self, data: Dict[str, Any]) -> Appointment:
        self.requerido(data, "id_paciente", "fecha_hora_programada", "motivo_consulta")
        with self._tx() as cur:
            self._exigir_activo(cur, data["id_paciente"])
            cur.execute(
                """INSERT INTO cita (id_paciente, id_pediatra, fecha_hora_programada, motivo_consulta)
                   VALUES (%s, %s, %s, %s)""",
                (data["id_paciente"], data["id_profesional"],
                 str(data["fecha_hora_programada"]).replace("T", " "), data["motivo_consulta"]),
            )
            return self._citas(cur, "c.id_cita = %s", (cur.lastrowid,))[0]

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        with self._tx() as cur:
            if patient_id:
                return self._citas(cur, "c.id_paciente = %s", (patient_id,))
            return self._citas(cur, "c.estado_cita = 'programada'", ())

    def _citas(self, cur, where, params) -> List[Appointment]:
        cur.execute(
            f"""SELECT c.*, p.nombre_completo AS profesional FROM cita c
                JOIN pediatra p ON p.id_pediatra = c.id_pediatra
                WHERE {where} ORDER BY c.fecha_hora_programada DESC""",
            params,
        )
        return [
            Appointment(
                id_cita=r["id_cita"], id_paciente=r["id_paciente"], id_profesional=r["id_pediatra"],
                profesional_nombre=r["profesional"], fecha_hora_programada=self._s(r["fecha_hora_programada"]),
                motivo_consulta=r["motivo_consulta"], estado_cita=r["estado_cita"],
                fecha_creacion=self._s(r["fecha_creacion"]),
            )
            for r in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    # Consulta pediátrica (transacción InnoDB)
    # ------------------------------------------------------------------
    def register_consultation(self, data: Dict[str, Any]) -> Consultation:
        self.requerido(data, "id_paciente", "motivo", "peso_kg", "talla_cm")
        pid = int(data["id_paciente"])
        recetas = self.recetas_del_payload(data)
        if recetas and not data.get("descripcion_diagnostico"):
            raise ValueError("Para recetar se necesita un diagnóstico")
        peso = self._f(data["peso_kg"])

        with self._tx() as cur:
            self._exigir_activo(cur, pid, bloquear=True)

            id_cita = data.get("id_cita")
            if id_cita:
                cur.execute("SELECT id_paciente, estado_cita FROM cita WHERE id_cita = %s FOR UPDATE", (id_cita,))
                cita = cur.fetchone()
                if not cita or cita["id_paciente"] != pid:
                    raise ValueError("La cita no pertenece a este paciente")
                if cita["estado_cita"] != "programada":
                    raise ValueError(f"La cita ya está '{cita['estado_cita']}'")
                cur.execute("UPDATE cita SET estado_cita = 'atendida', id_pediatra = %s WHERE id_cita = %s",
                            (data["id_profesional"], id_cita))
            else:
                cur.execute(
                    """INSERT INTO cita (id_paciente, id_pediatra, fecha_hora_programada, motivo_consulta, estado_cita)
                       VALUES (%s, %s, NOW(), %s, 'atendida')""",
                    (pid, data["id_profesional"], data["motivo"][:200]),
                )
                id_cita = cur.lastrowid

            tipo = data.get("tipo_consulta") or "control_sano"
            tipo = TIPO_CONSULTA.get(tipo, tipo)
            cur.execute(
                """INSERT INTO consulta (id_cita, motivo, temperatura, frecuencia_cardiaca, peso_kg, talla_cm,
                       perimetro_cefalico_cm, percentil_crecimiento, diagnostico_cie10,
                       descripcion_diagnostico, notas_clinicas, tipo_consulta)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (id_cita, data["motivo"][:200], self._f(data.get("temperatura")),
                 self._i(data.get("pulso") or data.get("frecuencia_cardiaca")), peso,
                 self._f(data["talla_cm"]), self._f(data.get("perimetro_cefalico_cm")),
                 self._f(data.get("percentil_crecimiento")),
                 (data.get("codigo_cie10") or "Z00.1").upper(),
                 data.get("descripcion_diagnostico") or "Control de salud de rutina del niño",
                 data.get("notas_clinicas"), tipo),
            )
            id_consulta = cur.lastrowid

            if data.get("nombre_vacuna"):
                cur.execute(
                    """INSERT INTO vacunacion (id_paciente, id_consulta, nombre_vacuna, dosis, lote,
                           fecha_aplicacion, proxima_fecha_refuerzo)
                       VALUES (%s, %s, %s, %s, %s, CURDATE(), %s)""",
                    (pid, id_consulta, data["nombre_vacuna"], data.get("dosis_vacuna") or "Dosis única",
                     data.get("lote_vacuna") or "SIN-LOTE", data.get("proxima_fecha_refuerzo") or None),
                )

            for r in recetas:
                mg_kg = self._f(r.get("dosis_mg_kg"))
                conc = self._f(r.get("concentracion_mg_ml"))
                ml = round(mg_kg * peso / conc, 2) if (mg_kg and conc) else None
                indic = r.get("indicaciones") or (
                    f"{r.get('dosis') or ''} {r.get('via_administracion') or ''}".strip() or None
                )
                cur.execute(
                    """INSERT INTO receta (id_consulta, medicamento, presentacion, dosis_mg_kg,
                           dosis_calculada_ml, frecuencia, duracion_dias, indicaciones)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (id_consulta, r["medicamento"].strip(), r.get("presentacion") or "Suspensión oral",
                     mg_kg, ml, r.get("frecuencia") or "Cada 8 horas",
                     self._i(r.get("duracion_dias")) or 1, indic),
                )

            cur.execute(
                "UPDATE historial_pediatrico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s", (pid,)
            )
            return self._consultas(cur, "co.id_consulta = %s", (id_consulta,))[0]

    def _exigir_activo(self, cur, patient_id, bloquear=False):
        cur.execute(
            "SELECT estado FROM historial_pediatrico WHERE id_paciente = %s" + (" FOR UPDATE" if bloquear else ""),
            (patient_id,),
        )
        h = cur.fetchone()
        if not h:
            raise ValueError(f"Paciente {patient_id} no encontrado")
        if h["estado"] != "activo":
            raise ValueError(f"El historial está '{h['estado']}' y no admite nuevos registros")

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    def get_clinical_history(self, patient_id: int, user_role: UserRole = UserRole.MEDICO) -> Optional[UnifiedClinicalRecord]:
        with self._tx() as cur:
            cur.execute("SELECT * FROM paciente_pediatrico WHERE id_paciente = %s", (patient_id,))
            prow = cur.fetchone()
            if not prow:
                return None
            cur.execute("SELECT * FROM historial_pediatrico WHERE id_paciente = %s", (patient_id,))
            h = cur.fetchone() or {}
            consultas = self._consultas(cur, "ci.id_paciente = %s", (patient_id,))
            citas = self._citas(cur, "c.id_paciente = %s", (patient_id,))

        record = UnifiedClinicalRecord(
            id_historial=h.get("id_historial", 0), id_paciente=patient_id, paciente=self._to_patient(prow),
            fecha_apertura=self._s(h.get("fecha_apertura")),
            fecha_ultima_actualizacion=self._s(h.get("fecha_ultima_actualizacion")),
            estado=h.get("estado", "activo"), motivo_baja=h.get("motivo_baja"),
            institucion=InstitutionType.CENTRO_PEDIATRICO, motor=DatabaseEngine.MYSQL,
            consultas=consultas, citas=citas,
            datos_adicionales={"vacunas_aplicadas": sum(len(c.vacunaciones) for c in consultas)},
        )
        return self.apply_security_filter(record, user_role)

    def _consultas(self, cur, where, params) -> List[Consultation]:
        cur.execute(
            f"""SELECT co.*, p.nombre_completo AS profesional FROM consulta co
                JOIN cita ci ON ci.id_cita = co.id_cita
                JOIN pediatra p ON p.id_pediatra = ci.id_pediatra
                WHERE {where} ORDER BY co.fecha_hora_atencion DESC""",
            params,
        )
        filas = cur.fetchall()
        if not filas:
            return []
        ids = [f["id_consulta"] for f in filas]
        marcas = ", ".join(["%s"] * len(ids))
        cur.execute(f"SELECT * FROM vacunacion WHERE id_consulta IN ({marcas})", ids)
        vacunas = cur.fetchall()
        cur.execute(f"SELECT * FROM receta WHERE id_consulta IN ({marcas}) ORDER BY id_receta", ids)
        recetas = cur.fetchall()

        resultado = []
        for f in filas:
            rs = [
                Prescription(
                    id_receta=r["id_receta"], medicamento=r["medicamento"],
                    dosis=(f"{self._f(r['dosis_calculada_ml'])} ml" if r["dosis_calculada_ml"] is not None
                           else (f"{self._f(r['dosis_mg_kg'])} mg/kg" if r["dosis_mg_kg"] is not None
                                 else (r["indicaciones"] or "Según indicación"))),
                    frecuencia=r["frecuencia"], duracion_dias=r["duracion_dias"], via_administracion="Oral",
                    indicaciones=r["indicaciones"], fecha_emision=self._s(r["fecha_emision"]),
                    dosis_mg_kg=self._f(r["dosis_mg_kg"]), dosis_calculada_ml=self._f(r["dosis_calculada_ml"]),
                    presentacion=r["presentacion"],
                )
                for r in recetas if r["id_consulta"] == f["id_consulta"]
            ]
            resultado.append(Consultation(
                id_consulta=f["id_consulta"], id_cita=f["id_cita"],
                fecha_hora_atencion=self._s(f["fecha_hora_atencion"]), motivo=f["motivo"],
                temperatura=self._f(f["temperatura"]), pulso=f["frecuencia_cardiaca"],
                notas_clinicas=f["notas_clinicas"], tipo_consulta=f["tipo_consulta"],
                profesional_nombre=f["profesional"],
                diagnosticos=[Diagnosis(
                    id_diagnostico=f["id_consulta"], codigo_cie10=f["diagnostico_cie10"] or "",
                    descripcion=f["descripcion_diagnostico"], tipo="principal",
                    fecha_diagnostico=self._s(f["fecha_hora_atencion"])[:10],
                )],
                recetas=rs, recetas_pediatricas=[],
                somatometria=SomatometryRecord(
                    peso_kg=self._f(f["peso_kg"]), talla_cm=self._f(f["talla_cm"]),
                    perimetro_cefalico_cm=self._f(f["perimetro_cefalico_cm"]),
                    percentil_crecimiento=self._f(f["percentil_crecimiento"]),
                ),
                vacunaciones=[
                    VaccinationRecord(
                        id_vacunacion=v["id_vacunacion"], nombre_vacuna=v["nombre_vacuna"], dosis=v["dosis"],
                        lote=v["lote"], fecha_aplicacion=self._s(v["fecha_aplicacion"]),
                        proxima_fecha_refuerzo=self._s(v["proxima_fecha_refuerzo"]),
                    )
                    for v in vacunas if v["id_consulta"] == f["id_consulta"]
                ],
            ))
        return resultado

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        with self._tx() as cur:
            cur.execute(
                """SELECT DATE(co.fecha_hora_atencion) AS fecha, co.peso_kg, co.talla_cm,
                          co.perimetro_cefalico_cm, co.percentil_crecimiento
                   FROM consulta co JOIN cita ci ON ci.id_cita = co.id_cita
                   WHERE ci.id_paciente = %s ORDER BY co.fecha_hora_atencion""",
                (patient_id,),
            )
            crecimiento = [
                {"fecha": self._s(r["fecha"]), "peso_kg": self._f(r["peso_kg"]), "talla_cm": self._f(r["talla_cm"]),
                 "perimetro_cefalico_cm": self._f(r["perimetro_cefalico_cm"]),
                 "percentil": self._f(r["percentil_crecimiento"])}
                for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT * FROM vacunacion WHERE id_paciente = %s ORDER BY fecha_aplicacion DESC", (patient_id,)
            )
            vacunas = [
                {"nombre_vacuna": v["nombre_vacuna"], "dosis": v["dosis"], "lote": v["lote"],
                 "fecha_aplicacion": self._s(v["fecha_aplicacion"]),
                 "proxima_fecha_refuerzo": self._s(v["proxima_fecha_refuerzo"])}
                for v in cur.fetchall()
            ]
        return {"institucion": "Centro Médico Pediátrico", "motor": "MySQL",
                "control_crecimiento": crecimiento, "esquema_vacunacion": vacunas}

    # ------------------------------------------------------------------
    # Personal médico: tabla pediatra
    # ------------------------------------------------------------------
    @staticmethod
    def _to_prof(r) -> Professional:
        return Professional(r["id_pediatra"], r["nombre_completo"], r["numero_colegiado"],
                            r.get("especialidad") or "", r["telefono"] or "", r["correo_electronico"] or "", r["estado"])

    def list_professionals(self) -> List[Professional]:
        with self._tx() as cur:
            cur.execute("SELECT * FROM pediatra ORDER BY estado, nombre_completo")
            return [self._to_prof(r) for r in cur.fetchall()]

    def create_professional(self, data: Dict[str, Any]) -> Professional:
        self.requerido(data, "nombre_completo", "numero_colegiado")
        try:
            with self._tx() as cur:
                cur.execute(
                    """INSERT INTO pediatra (nombre_completo, numero_colegiado, especialidad, telefono, correo_electronico)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (data["nombre_completo"].strip(), data["numero_colegiado"].strip(),
                     data.get("especialidad") or "Pediatría general", data.get("telefono") or None,
                     data.get("correo_electronico") or None),
                )
                cur.execute("SELECT * FROM pediatra WHERE id_pediatra = %s", (cur.lastrowid,))
                return self._to_prof(cur.fetchone())
        except mysql.connector.IntegrityError as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                raise ValueError(f"Ya existe un pediatra con colegiado {data['numero_colegiado']}")
            raise

    def update_professional(self, professional_id: int, data: Dict[str, Any]) -> Professional:
        self.validar_profesional(data)
        campos = {k: data.get(k) for k in ("nombre_completo", "especialidad", "telefono", "correo_electronico", "estado")}
        campos = {k: v for k, v in campos.items() if v not in (None, "")}
        with self._tx() as cur:
            if campos:
                cur.execute(f"UPDATE pediatra SET {', '.join(f'{k} = %s' for k in campos)} WHERE id_pediatra = %s",
                            (*campos.values(), professional_id))
            cur.execute("SELECT * FROM pediatra WHERE id_pediatra = %s", (professional_id,))
            r = cur.fetchone()
            if not r:
                raise ValueError(f"Pediatra {professional_id} no encontrado")
            return self._to_prof(r)

    def _to_patient(self, r) -> Patient:
        return Patient(
            id_paciente=r["id_paciente"], nombres=r["nombres"], apellidos=r["apellidos"],
            fecha_nacimiento=self._s(r["fecha_nacimiento"]), sexo=r["sexo"], dpi=r["cui_nacimiento"],
            direccion=r["direccion"] or "", telefono=r["telefono_tutor"] or "", correo_electronico="",
            contacto_emergencia_nombre=r["nombre_tutor"], contacto_emergencia_telefono=r["telefono_tutor"],
            fecha_registro=self._s(r["fecha_registro"]), estado=r["estado"],
            nombre_tutor=r["nombre_tutor"], parentesco_tutor=r["parentesco_tutor"], dpi_tutor=r["dpi_tutor"],
            telefono_tutor=r["telefono_tutor"], semanas_gestacion=r["semanas_gestacion"],
            peso_nacer_kg=self._f(r["peso_nacer_kg"]), talla_nacer_cm=self._f(r["talla_nacer_cm"]),
        )
