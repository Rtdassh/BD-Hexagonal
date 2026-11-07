"""
Adaptador PostgreSQL - Hospital General.

Modelo relacional normalizado (esquema `hospital`). Cada operación que toca
varias tablas corre dentro de UNA transacción: si cualquier INSERT falla,
PostgreSQL hace ROLLBACK y no queda un diagnóstico "a medias".
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .base_adapter import BaseClinicalAdapter
from ..config import Config
from ...domain.ports import HospitalOperationsPort
from ...domain.entities import (
    Appointment,
    Consultation,
    DatabaseEngine,
    Diagnosis,
    HospitalizationRecord,
    InstitutionType,
    Patient,
    Prescription,
    Professional,
    ShiftAssignment,
    Surgery,
    Treatment,
    UnifiedClinicalRecord,
    UserRole,
)

CAMPOS_EDITABLES = {
    "nombres", "apellidos", "fecha_nacimiento", "sexo", "direccion", "telefono",
    "correo_electronico", "tipo_sangre", "contacto_emergencia_nombre",
    "contacto_emergencia_telefono",
}


class PostgreSQLAdapter(BaseClinicalAdapter, HospitalOperationsPort):
    is_live = True

    def __init__(self, config: Config):
        self.config = config
        # Lanza excepción si el servidor no responde: el router decide qué hacer.
        self.pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD,
            connect_timeout=3,
            options="-c search_path=hospital,public",
        )

    # ------------------------------------------------------------------
    # Conexión / transacción
    # ------------------------------------------------------------------
    @contextmanager
    def _tx(self):
        """Abre una transacción: COMMIT si todo sale bien, ROLLBACK si hay error."""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.HOSPITAL_GENERAL

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.POSTGRESQL

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        with self._tx() as cur:
            cur.execute("SELECT version() AS v")
            version = cur.fetchone()["v"].split(" on ")[0]
            cur.execute("""
                SELECT (SELECT COUNT(*) FROM Paciente) AS pacientes,
                       (SELECT COUNT(*) FROM Consulta) AS consultas,
                       (SELECT COUNT(*) FROM Hospitalizacion WHERE estado = 'ingresado') AS ingresados
            """)
            counts = cur.fetchone()
        return {
            "institucion": "Hospital General",
            "motor": "PostgreSQL",
            "modo": "real",
            "estado": "online",
            "version": version,
            "base_datos": f"{self.config.PG_DATABASE} (esquema hospital)",
            "latencia_ms": round((time.time() - start) * 1000, 1),
            "conteos": {
                "pacientes": counts["pacientes"],
                "consultas": counts["consultas"],
                "hospitalizados": counts["ingresados"],
            },
            "consistencia": "Transacciones ACID (BEGIN / COMMIT / ROLLBACK)",
        }

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------
    def create_patient(self, data: Dict[str, Any]) -> Patient:
        self.requerido(data, "nombres", "apellidos", "fecha_nacimiento", "sexo", "dpi")
        try:
            with self._tx() as cur:
                cur.execute(
                    """
                    INSERT INTO Paciente (nombres, apellidos, fecha_nacimiento, sexo, dpi, direccion,
                        telefono, correo_electronico, tipo_sangre, contacto_emergencia_nombre,
                        contacto_emergencia_telefono)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_paciente
                    """,
                    (
                        data["nombres"].strip(), data["apellidos"].strip(), data["fecha_nacimiento"],
                        data["sexo"], data["dpi"].strip(), data.get("direccion"), data.get("telefono"),
                        data.get("correo_electronico"), data.get("tipo_sangre") or None,
                        data.get("contacto_emergencia_nombre"), data.get("contacto_emergencia_telefono"),
                    ),
                )
                pid = cur.fetchone()["id_paciente"]
                # El historial se abre en la MISMA transacción que el paciente.
                cur.execute("INSERT INTO Historial_Clinico (id_paciente) VALUES (%s)", (pid,))
        except psycopg2.errors.UniqueViolation:
            raise ValueError(f"Ya existe un paciente con DPI {data['dpi']}")
        return self.get_patient(pid)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        with self._tx() as cur:
            cur.execute("SELECT * FROM Paciente WHERE id_paciente = %s", (patient_id,))
            row = cur.fetchone()
        return self._to_patient(row) if row else None

    def search_patients(self, query: str) -> List[Patient]:
        q = (query or "").strip()
        with self._tx() as cur:
            if not q:
                cur.execute("SELECT * FROM Paciente ORDER BY apellidos, nombres LIMIT 200")
            else:
                cur.execute(
                    """
                    SELECT * FROM Paciente
                    WHERE (nombres || ' ' || apellidos) ILIKE %s OR dpi LIKE %s
                       OR id_paciente::text = %s
                    ORDER BY apellidos, nombres LIMIT 200
                    """,
                    (f"%{q}%", f"{q}%", q),
                )
            rows = cur.fetchall()
        return [self._to_patient(r) for r in rows]

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        campos = {k: v for k, v in updates.items() if k in CAMPOS_EDITABLES}
        if not campos:
            raise ValueError("No hay campos válidos para actualizar")
        sets = ", ".join(f"{k} = %s" for k in campos)
        with self._tx() as cur:
            cur.execute(
                f"UPDATE Paciente SET {sets} WHERE id_paciente = %s", (*campos.values(), patient_id)
            )
            if cur.rowcount == 0:
                raise ValueError(f"Paciente {patient_id} no encontrado")
            cur.execute(
                "UPDATE Historial_Clinico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s",
                (patient_id,),
            )
        return self.get_patient(patient_id)

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
        estado = self.estado_por_motivo(categoria)
        with self._tx() as cur:
            cur.execute(
                "SELECT estado FROM Historial_Clinico WHERE id_paciente = %s FOR UPDATE", (patient_id,)
            )
            hist = cur.fetchone()
            if not hist:
                raise ValueError(f"Paciente {patient_id} no encontrado")
            if hist["estado"] != "activo":
                raise ValueError("El historial ya está dado de baja")
            cur.execute(
                """UPDATE Historial_Clinico SET estado = %s, motivo_baja = %s,
                       fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s""",
                (estado, motivo_baja[:150], patient_id),
            )
            cur.execute("SELECT 1 FROM Cirugia WHERE id_paciente = %s AND estado = 'en_curso'", (patient_id,))
            if cur.fetchone():
                raise ValueError("El paciente está en cirugía; no se puede dar de baja hasta que termine")
            cur.execute(
                """UPDATE Cirugia SET estado = 'cancelada', motivo_cancelacion = 'Baja del historial'
                   WHERE id_paciente = %s AND estado = 'programada'""", (patient_id,))
            cur.execute(
                """UPDATE Asignacion_Turno t SET estado = 'anulada' FROM Hospitalizacion h
                   WHERE h.id_hospitalizacion = t.id_hospitalizacion AND h.id_paciente = %s
                     AND t.estado = 'activa' AND t.fecha > CURRENT_DATE""", (patient_id,))
            cur.execute("UPDATE Paciente SET estado_salud = 'dado_de_baja' WHERE id_paciente = %s", (patient_id,))
            cur.execute(
                "UPDATE Cita SET estado_cita = 'cancelada' WHERE id_paciente = %s AND estado_cita = 'programada'",
                (patient_id,),
            )
            citas_canceladas = cur.rowcount
            cur.execute(
                """UPDATE Hospitalizacion SET estado = %s, fecha_egreso = NOW()
                   WHERE id_paciente = %s AND estado = 'ingresado'""",
                ("referido" if estado == "trasladado" else "alta", patient_id),
            )
        return {
            "id_paciente": patient_id,
            "estado": estado,
            "motivo_baja": motivo_baja,
            "citas_canceladas": citas_canceladas,
            "motor": "PostgreSQL",
            "mensaje": "Historial archivado en una sola transacción.",
        }

    # ------------------------------------------------------------------
    # Citas
    # ------------------------------------------------------------------
    def create_appointment(self, data: Dict[str, Any]) -> Appointment:
        self.requerido(data, "id_paciente", "fecha_hora_programada", "motivo_consulta")
        with self._tx() as cur:
            self._exigir_activo(cur, data["id_paciente"])
            cur.execute(
                """INSERT INTO Cita (id_paciente, id_medico, fecha_hora_programada, motivo_consulta)
                   VALUES (%s, %s, %s, %s) RETURNING id_cita""",
                (data["id_paciente"], data["id_profesional"],
                 data["fecha_hora_programada"], data["motivo_consulta"]),
            )
            cid = cur.fetchone()["id_cita"]
            return self._citas(cur, "c.id_cita = %s", (cid,))[0]

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        with self._tx() as cur:
            if patient_id:
                return self._citas(cur, "c.id_paciente = %s", (patient_id,))
            return self._citas(cur, "c.estado_cita = 'programada'", ())

    def _citas(self, cur, where: str, params) -> List[Appointment]:
        cur.execute(
            f"""SELECT c.*, m.nombre AS profesional FROM Cita c
                JOIN Medico m ON m.id_medico = c.id_medico
                WHERE {where} ORDER BY c.fecha_hora_programada DESC""",
            params,
        )
        return [
            Appointment(
                id_cita=r["id_cita"], id_paciente=r["id_paciente"], id_profesional=r["id_medico"],
                profesional_nombre=r["profesional"], fecha_hora_programada=self._s(r["fecha_hora_programada"]),
                motivo_consulta=r["motivo_consulta"], estado_cita=r["estado_cita"],
                fecha_creacion=self._s(r["fecha_creacion"]),
            )
            for r in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    # Consulta + diagnóstico + tratamiento + recetas (transacción ACID)
    # ------------------------------------------------------------------
    def register_consultation(self, data: Dict[str, Any]) -> Consultation:
        self.requerido(data, "id_paciente", "motivo")
        pid = int(data["id_paciente"])
        recetas = self.recetas_del_payload(data)

        with self._tx() as cur:
            self._exigir_activo(cur, pid, bloquear=True)

            # 1. Cita: se usa la programada o se crea una cita "atendida" en el momento.
            id_cita = data.get("id_cita")
            if id_cita:
                cur.execute(
                    "SELECT id_paciente, estado_cita FROM Cita WHERE id_cita = %s FOR UPDATE", (id_cita,)
                )
                cita = cur.fetchone()
                if not cita or cita["id_paciente"] != pid:
                    raise ValueError("La cita no pertenece a este paciente")
                if cita["estado_cita"] != "programada":
                    raise ValueError(f"La cita ya está '{cita['estado_cita']}'")
                # La cita queda a nombre del médico que realmente atendió.
                cur.execute("UPDATE Cita SET estado_cita = 'atendida', id_medico = %s WHERE id_cita = %s",
                            (data["id_profesional"], id_cita))
            else:
                cur.execute(
                    """INSERT INTO Cita (id_paciente, id_medico, fecha_hora_programada, motivo_consulta, estado_cita)
                       VALUES (%s, %s, NOW(), %s, 'atendida') RETURNING id_cita""",
                    (pid, data["id_profesional"], data["motivo"][:200]),
                )
                id_cita = cur.fetchone()["id_cita"]

            # 2. Consulta
            cur.execute(
                """INSERT INTO Consulta (id_cita, motivo, presion_arterial, temperatura, pulso,
                       notas_clinicas, tipo_consulta)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_consulta""",
                (id_cita, data["motivo"][:200], data.get("presion_arterial") or None,
                 self._f(data.get("temperatura")), self._i(data.get("pulso")),
                 data.get("notas_clinicas"), data.get("tipo_consulta") or "ordinaria"),
            )
            id_consulta = cur.fetchone()["id_consulta"]

            # 3. Diagnóstico
            id_diag = None
            if data.get("codigo_cie10") or data.get("descripcion_diagnostico"):
                cur.execute(
                    """INSERT INTO Diagnostico (id_consulta, codigo_cie10, descripcion, tipo)
                       VALUES (%s, %s, %s, %s) RETURNING id_diagnostico""",
                    (id_consulta, (data.get("codigo_cie10") or "R69").upper(),
                     data.get("descripcion_diagnostico") or "Sin descripción",
                     data.get("tipo_diagnostico") or "principal"),
                )
                id_diag = cur.fetchone()["id_diagnostico"]

            # 4. Tratamiento (obligatorio si hay recetas: Receta -> Tratamiento -> Diagnóstico)
            if id_diag and (data.get("descripcion_tratamiento") or recetas):
                cur.execute(
                    """INSERT INTO Tratamiento (id_diagnostico, descripcion, fecha_fin, indicaciones)
                       VALUES (%s, %s, %s, %s) RETURNING id_tratamiento""",
                    (id_diag, data.get("descripcion_tratamiento") or "Tratamiento farmacológico",
                     data.get("fecha_fin_tratamiento") or None, data.get("indicaciones_tratamiento")),
                )
                id_trat = cur.fetchone()["id_tratamiento"]

                # 5. Recetas (el medicamento se busca en el catálogo o se registra)
                for r in recetas:
                    cur.execute(
                        "SELECT id_medicamento FROM Medicamento WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
                        (r["medicamento"].strip(),),
                    )
                    med = cur.fetchone()
                    if med:
                        id_med = med["id_medicamento"]
                    else:
                        cur.execute(
                            """INSERT INTO Medicamento (nombre, presentacion, unidad_medida)
                               VALUES (%s, %s, %s) RETURNING id_medicamento""",
                            (r["medicamento"].strip(), r.get("presentacion") or "No especificada", "unidad"),
                        )
                        id_med = cur.fetchone()["id_medicamento"]
                    cur.execute(
                        """INSERT INTO Receta (id_tratamiento, id_medicamento, dosis, frecuencia,
                               duracion_dias, via_administracion)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (id_trat, id_med, r.get("dosis") or "Según indicación",
                         r.get("frecuencia") or "Cada 8 horas", self._i(r.get("duracion_dias")) or 1,
                         r.get("via_administracion") or "Oral"),
                    )
            elif recetas:
                raise ValueError("Para recetar se necesita un diagnóstico")

            # 6. Hospitalización (opcional)
            if data.get("requiere_hospitalizacion"):
                cur.execute("""SELECT numero_habitacion FROM Hospitalizacion
                               WHERE id_paciente = %s AND estado = 'ingresado'""", (pid,))
                ya = cur.fetchone()
                if ya:
                    raise ValueError(f"El paciente ya está ingresado en {ya['numero_habitacion']}")
                cur.execute(
                    """INSERT INTO Hospitalizacion (id_paciente, id_consulta, numero_habitacion, motivo_ingreso)
                       VALUES (%s, %s, %s, %s)""",
                    (pid, id_consulta, data.get("numero_habitacion") or "POR-ASIGNAR",
                     data.get("motivo_hospitalizacion") or data["motivo"][:200]),
                )
                cur.execute("UPDATE Paciente SET estado_salud = 'hospitalizado' WHERE id_paciente = %s", (pid,))

            cur.execute(
                "UPDATE Historial_Clinico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s", (pid,)
            )
            return self._consultas(cur, "co.id_consulta = %s", (id_consulta,))[0]

    def _exigir_activo(self, cur, patient_id: int, bloquear: bool = False) -> None:
        cur.execute(
            "SELECT estado FROM Historial_Clinico WHERE id_paciente = %s" + (" FOR UPDATE" if bloquear else ""),
            (patient_id,),
        )
        h = cur.fetchone()
        if not h:
            raise ValueError(f"Paciente {patient_id} no encontrado")
        if h["estado"] != "activo":
            raise ValueError(f"El historial está '{h['estado']}' y no admite nuevos registros")

    # ------------------------------------------------------------------
    # Historial clínico
    # ------------------------------------------------------------------
    def get_clinical_history(self, patient_id: int, user_role: UserRole = UserRole.MEDICO) -> Optional[UnifiedClinicalRecord]:
        with self._tx() as cur:
            cur.execute("SELECT * FROM Paciente WHERE id_paciente = %s", (patient_id,))
            prow = cur.fetchone()
            if not prow:
                return None
            cur.execute("SELECT * FROM Historial_Clinico WHERE id_paciente = %s", (patient_id,))
            h = cur.fetchone() or {}
            consultas = self._consultas(cur, "ci.id_paciente = %s", (patient_id,))
            citas = self._citas(cur, "c.id_paciente = %s", (patient_id,))

        record = UnifiedClinicalRecord(
            id_historial=h.get("id_historial", 0), id_paciente=patient_id, paciente=self._to_patient(prow),
            fecha_apertura=self._s(h.get("fecha_apertura")),
            fecha_ultima_actualizacion=self._s(h.get("fecha_ultima_actualizacion")),
            estado=h.get("estado", "activo"), motivo_baja=h.get("motivo_baja"),
            institucion=InstitutionType.HOSPITAL_GENERAL, motor=DatabaseEngine.POSTGRESQL,
            consultas=consultas, citas=citas,
            datos_adicionales={"hospitalizaciones": sum(1 for c in consultas if c.hospitalizacion)},
        )
        return self.apply_security_filter(record, user_role)

    def _consultas(self, cur, where: str, params) -> List[Consultation]:
        cur.execute(
            f"""SELECT co.*, m.nombre AS profesional FROM Consulta co
                JOIN Cita ci ON ci.id_cita = co.id_cita
                JOIN Medico m ON m.id_medico = ci.id_medico
                WHERE {where} ORDER BY co.fecha_hora_atencion DESC""",
            params,
        )
        filas = cur.fetchall()
        if not filas:
            return []
        ids = tuple(f["id_consulta"] for f in filas)

        cur.execute("SELECT * FROM Diagnostico WHERE id_consulta IN %s ORDER BY id_diagnostico", (ids,))
        diags = cur.fetchall()
        diag_ids = tuple(d["id_diagnostico"] for d in diags) or (0,)
        cur.execute("SELECT * FROM Tratamiento WHERE id_diagnostico IN %s ORDER BY id_tratamiento", (diag_ids,))
        trats = cur.fetchall()
        trat_ids = tuple(t["id_tratamiento"] for t in trats) or (0,)
        cur.execute(
            """SELECT r.*, m.nombre AS medicamento, m.presentacion FROM Receta r
               JOIN Medicamento m ON m.id_medicamento = r.id_medicamento
               WHERE r.id_tratamiento IN %s ORDER BY r.id_receta""",
            (trat_ids,),
        )
        recs = cur.fetchall()
        cur.execute("SELECT * FROM Hospitalizacion WHERE id_consulta IN %s", (ids,))
        hosps = {h["id_consulta"]: h for h in cur.fetchall()}

        def receta(r):
            return Prescription(
                id_receta=r["id_receta"], medicamento=r["medicamento"], dosis=r["dosis"],
                frecuencia=r["frecuencia"], duracion_dias=r["duracion_dias"],
                via_administracion=r["via_administracion"], fecha_emision=self._s(r["fecha_emision"]),
                presentacion=r["presentacion"],
            )

        resultado = []
        for f in filas:
            todas_recetas: List[Prescription] = []
            diagnosticos = []
            for d in (x for x in diags if x["id_consulta"] == f["id_consulta"]):
                tratamientos = []
                for t in (x for x in trats if x["id_diagnostico"] == d["id_diagnostico"]):
                    rs = [receta(r) for r in recs if r["id_tratamiento"] == t["id_tratamiento"]]
                    todas_recetas.extend(rs)
                    tratamientos.append(Treatment(
                        id_tratamiento=t["id_tratamiento"], descripcion=t["descripcion"],
                        fecha_inicio=self._s(t["fecha_inicio"]), fecha_fin=self._s(t["fecha_fin"]),
                        estado=t["estado"], indicaciones=t["indicaciones"], recetas=rs,
                    ))
                diagnosticos.append(Diagnosis(
                    id_diagnostico=d["id_diagnostico"], codigo_cie10=d["codigo_cie10"],
                    descripcion=d["descripcion"], tipo=d["tipo"],
                    fecha_diagnostico=self._s(d["fecha_diagnostico"]), tratamientos=tratamientos,
                ))
            hr = hosps.get(f["id_consulta"])
            resultado.append(Consultation(
                id_consulta=f["id_consulta"], id_cita=f["id_cita"],
                fecha_hora_atencion=self._s(f["fecha_hora_atencion"]), motivo=f["motivo"],
                presion_arterial=f["presion_arterial"], temperatura=self._f(f["temperatura"]),
                pulso=f["pulso"], notas_clinicas=f["notas_clinicas"], tipo_consulta=f["tipo_consulta"],
                profesional_nombre=f["profesional"], diagnosticos=diagnosticos, recetas=todas_recetas,
                hospitalizacion=HospitalizationRecord(
                    id_hospitalizacion=hr["id_hospitalizacion"], id_consulta=hr["id_consulta"],
                    fecha_ingreso=self._s(hr["fecha_ingreso"]), fecha_egreso=self._s(hr["fecha_egreso"]),
                    numero_habitacion=hr["numero_habitacion"], motivo_ingreso=hr["motivo_ingreso"],
                    estado=hr["estado"],
                ) if hr else None,
            ))
        return resultado

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        with self._tx() as cur:
            cur.execute(
                "SELECT * FROM Hospitalizacion WHERE id_paciente = %s ORDER BY fecha_ingreso DESC", (patient_id,)
            )
            filas = [{k: self._s(v) if not isinstance(v, (int, str)) else v for k, v in r.items()} for r in cur.fetchall()]
        return {"institucion": "Hospital General", "motor": "PostgreSQL", "hospitalizaciones": filas}

    # ------------------------------------------------------------------
    # Personal médico: Medico + Medico_Especialidad (N:M) + Especialidad
    # ------------------------------------------------------------------
    def _medicos(self, cur, where: str = "TRUE", params=()) -> List[Professional]:
        cur.execute(
            f"""SELECT m.*, COALESCE(string_agg(e.nombre_especialidad, ', ' ORDER BY e.nombre_especialidad), '') AS esp
                FROM Medico m
                LEFT JOIN Medico_Especialidad me ON me.id_medico = m.id_medico
                LEFT JOIN Especialidad e ON e.id_especialidad = me.id_especialidad
                WHERE {where} GROUP BY m.id_medico ORDER BY m.estado, m.nombre""",
            params,
        )
        return [Professional(r["id_medico"], r["nombre"], r["numero_colegiado"], r["esp"], r["telefono"] or "",
                             r["correo_electronico"] or "", r["estado"]) for r in cur.fetchall()]

    def _asignar_especialidad(self, cur, id_medico: int, especialidad: str) -> None:
        cur.execute("DELETE FROM Medico_Especialidad WHERE id_medico = %s", (id_medico,))
        nombre = (especialidad or "").strip()
        if not nombre:
            return
        cur.execute("SELECT id_especialidad FROM Especialidad WHERE LOWER(nombre_especialidad) = LOWER(%s)", (nombre,))
        fila = cur.fetchone()
        if fila:
            id_esp = fila["id_especialidad"]
        else:
            cur.execute("INSERT INTO Especialidad (nombre_especialidad) VALUES (%s) RETURNING id_especialidad", (nombre,))
            id_esp = cur.fetchone()["id_especialidad"]
        cur.execute("INSERT INTO Medico_Especialidad (id_medico, id_especialidad) VALUES (%s, %s)", (id_medico, id_esp))

    def list_professionals(self) -> List[Professional]:
        with self._tx() as cur:
            return self._medicos(cur)

    def create_professional(self, data: Dict[str, Any]) -> Professional:
        self.requerido(data, "nombre_completo", "numero_colegiado")
        try:
            with self._tx() as cur:
                cur.execute(
                    """INSERT INTO Medico (nombre, numero_colegiado, telefono, correo_electronico)
                       VALUES (%s, %s, %s, %s) RETURNING id_medico""",
                    (data["nombre_completo"].strip(), data["numero_colegiado"].strip(),
                     data.get("telefono") or None, data.get("correo_electronico") or None),
                )
                mid = cur.fetchone()["id_medico"]
                self._asignar_especialidad(cur, mid, data.get("especialidad"))
                return self._medicos(cur, "m.id_medico = %s", (mid,))[0]
        except psycopg2.errors.UniqueViolation:
            raise ValueError(f"Ya existe un médico con colegiado {data['numero_colegiado']}")

    def update_professional(self, professional_id: int, data: Dict[str, Any]) -> Professional:
        self.validar_profesional(data)
        campos = {"nombre": data.get("nombre_completo"), "telefono": data.get("telefono"),
                  "correo_electronico": data.get("correo_electronico"), "estado": data.get("estado")}
        campos = {k: v for k, v in campos.items() if v not in (None, "")}
        with self._tx() as cur:
            if campos:
                cur.execute(f"UPDATE Medico SET {', '.join(f'{k} = %s' for k in campos)} WHERE id_medico = %s",
                            (*campos.values(), professional_id))
                if cur.rowcount == 0:
                    raise ValueError(f"Médico {professional_id} no encontrado")
            if "especialidad" in data:
                self._asignar_especialidad(cur, professional_id, data.get("especialidad"))
            r = self._medicos(cur, "m.id_medico = %s", (professional_id,))
            if not r:
                raise ValueError(f"Médico {professional_id} no encontrado")
            return r[0]

    # ==================================================================
    # HOSPITAL: quirófanos, cirugías, enfermería y altas
    # ==================================================================
    @contextmanager
    def _tx_hosp(self):
        """Transacción que traduce los rechazos de la base de datos a mensajes claros."""
        try:
            with self._tx() as cur:
                yield cur
        except psycopg2.errors.ExclusionViolation as e:
            if e.diag.constraint_name == "excl_quirofano_ocupado":
                raise ValueError("El quirófano ya tiene otra cirugía en ese horario")
            if e.diag.constraint_name == "excl_cirujano_ocupado":
                raise ValueError("El cirujano ya tiene otra cirugía en ese horario")
            raise ValueError("Conflicto de horario")
        except psycopg2.errors.UniqueViolation as e:
            if e.diag.constraint_name == "uq_turno_activo":
                raise ValueError("Ese enfermero ya está asignado a este paciente en ese turno")
            raise ValueError("Registro duplicado")
        except psycopg2.errors.CheckViolation as e:
            # Mensajes del trigger validar_asignacion_turno() o de los CHECK
            raise ValueError(e.diag.message_primary)

    _SQL_CIRUGIA = """SELECT c.*, p.nombres || ' ' || p.apellidos AS paciente, m.nombre AS cirujano
                      FROM Cirugia c JOIN Paciente p ON p.id_paciente = c.id_paciente
                      JOIN Medico m ON m.id_medico = c.id_medico"""

    def _cirugias(self, cur, where="TRUE", params=()) -> List[Surgery]:
        cur.execute(f"{self._SQL_CIRUGIA} WHERE {where} ORDER BY c.fecha_hora_programada", params)
        return [
            Surgery(
                id_cirugia=r["id_cirugia"], id_paciente=r["id_paciente"], paciente_nombre=r["paciente"],
                id_medico=r["id_medico"], cirujano_nombre=r["cirujano"], procedimiento=r["procedimiento"],
                codigo_quirofano=r["codigo_quirofano"], tipo=r["tipo"],
                fecha_hora_programada=self._s(r["fecha_hora_programada"]),
                duracion_estimada_min=r["duracion_estimada_min"], estado=r["estado"],
                fecha_hora_inicio=self._s(r["fecha_hora_inicio"]), fecha_hora_fin=self._s(r["fecha_hora_fin"]),
                id_hospitalizacion=r["id_hospitalizacion"], notas_operatorias=r["notas_operatorias"],
                motivo_cancelacion=r["motivo_cancelacion"],
            )
            for r in cur.fetchall()
        ]

    def list_operating_rooms(self) -> List[Dict[str, Any]]:
        with self._tx() as cur:
            cur.execute("SELECT * FROM Quirofano ORDER BY codigo")
            return [dict(r) for r in cur.fetchall()]

    def list_surgeries(self, fecha=None, patient_id=None, solo_pendientes=False) -> List[Surgery]:
        cond, params = [], []
        if fecha:
            cond.append("c.fecha_hora_programada::date = %s")
            params.append(fecha)
        if patient_id:
            cond.append("c.id_paciente = %s")
            params.append(patient_id)
        if solo_pendientes:
            cond.append("(c.estado = 'en_curso' OR (c.estado = 'programada' AND c.fecha_hora_programada >= CURRENT_DATE))")
        with self._tx() as cur:
            return self._cirugias(cur, " AND ".join(cond) or "TRUE", tuple(params))

    def schedule_surgery(self, data: Dict[str, Any]) -> Surgery:
        self.requerido(data, "id_paciente", "id_medico", "procedimiento", "codigo_quirofano",
                       "fecha_hora_programada", "duracion_estimada_min")
        pid = int(data["id_paciente"])
        tipo = data.get("tipo") or "electiva"
        with self._tx_hosp() as cur:
            self._exigir_activo(cur, pid)
            cur.execute("SELECT estado FROM Quirofano WHERE codigo = %s", (data["codigo_quirofano"],))
            q = cur.fetchone()
            if not q:
                raise ValueError("Quirófano inexistente")
            if q["estado"] != "disponible":
                raise ValueError(f"El quirófano {data['codigo_quirofano']} está en mantenimiento")
            cur.execute("SELECT %s::timestamp < NOW() - INTERVAL '10 minutes' AS pasado",
                        (str(data["fecha_hora_programada"]).replace("T", " "),))
            if cur.fetchone()["pasado"] and tipo == "electiva":
                raise ValueError("Una cirugía electiva no se puede programar en el pasado")
            # Si el paciente está internado, la cirugía queda ligada a esa hospitalización
            cur.execute("""SELECT id_hospitalizacion FROM Hospitalizacion
                           WHERE id_paciente = %s AND estado = 'ingresado'
                           ORDER BY fecha_ingreso DESC LIMIT 1""", (pid,))
            h = cur.fetchone()
            cur.execute(
                """INSERT INTO Cirugia (id_paciente, id_medico, id_hospitalizacion, procedimiento, codigo_quirofano,
                       tipo, fecha_hora_programada, duracion_estimada_min, notas_operatorias)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_cirugia""",
                (pid, int(data["id_medico"]), h["id_hospitalizacion"] if h else None, data["procedimiento"].strip(),
                 data["codigo_quirofano"], tipo, str(data["fecha_hora_programada"]).replace("T", " "),
                 int(data["duracion_estimada_min"]), data.get("notas_operatorias") or None),
            )
            cid = cur.fetchone()["id_cirugia"]
            cur.execute("UPDATE Historial_Clinico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s", (pid,))
            return self._cirugias(cur, "c.id_cirugia = %s", (cid,))[0]

    def _cirugia_bloqueada(self, cur, surgery_id: int) -> Dict[str, Any]:
        cur.execute("SELECT * FROM Cirugia WHERE id_cirugia = %s FOR UPDATE", (surgery_id,))
        c = cur.fetchone()
        if not c:
            raise ValueError(f"Cirugía {surgery_id} no encontrada")
        return c

    def start_surgery(self, surgery_id: int) -> Surgery:
        with self._tx_hosp() as cur:
            c = self._cirugia_bloqueada(cur, surgery_id)
            if c["estado"] != "programada":
                raise ValueError(f"Solo se inicia una cirugía programada (esta está '{c['estado']}')")
            cur.execute("SELECT 1 FROM Cirugia WHERE id_paciente = %s AND estado = 'en_curso'", (c["id_paciente"],))
            if cur.fetchone():
                raise ValueError("El paciente ya está en otra cirugía")
            cur.execute("SELECT 1 FROM Cirugia WHERE codigo_quirofano = %s AND estado = 'en_curso'", (c["codigo_quirofano"],))
            if cur.fetchone():
                raise ValueError(f"El quirófano {c['codigo_quirofano']} está ocupado ahora mismo")
            cur.execute("UPDATE Cirugia SET estado = 'en_curso', fecha_hora_inicio = NOW() WHERE id_cirugia = %s",
                        (surgery_id,))
            return self._cirugias(cur, "c.id_cirugia = %s", (surgery_id,))[0]

    def finish_surgery(self, surgery_id: int, notas: Optional[str] = None) -> Surgery:
        with self._tx_hosp() as cur:
            c = self._cirugia_bloqueada(cur, surgery_id)
            if c["estado"] != "en_curso":
                raise ValueError("Solo se finaliza una cirugía que está en curso")
            cur.execute(
                """UPDATE Cirugia SET estado = 'realizada', fecha_hora_fin = NOW(),
                       notas_operatorias = COALESCE(NULLIF(%s, ''), notas_operatorias)
                   WHERE id_cirugia = %s""", (notas or "", surgery_id))
            cur.execute("UPDATE Historial_Clinico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s",
                        (c["id_paciente"],))
            return self._cirugias(cur, "c.id_cirugia = %s", (surgery_id,))[0]

    def cancel_surgery(self, surgery_id: int, motivo: str) -> Surgery:
        with self._tx_hosp() as cur:
            c = self._cirugia_bloqueada(cur, surgery_id)
            if c["estado"] != "programada":
                raise ValueError("Solo se cancela una cirugía programada")
            cur.execute("UPDATE Cirugia SET estado = 'cancelada', motivo_cancelacion = %s WHERE id_cirugia = %s",
                        ((motivo or "Sin motivo")[:200], surgery_id))
            return self._cirugias(cur, "c.id_cirugia = %s", (surgery_id,))[0]

    # ---- Enfermería ----------------------------------------------------
    def _enfermeros(self, cur, where="TRUE", params=()) -> List[Professional]:
        cur.execute(f"SELECT * FROM Enfermero WHERE {where} ORDER BY estado, nombre", params)
        return [Professional(r["id_enfermero"], r["nombre"], r["numero_colegiado"], r["area"] or "",
                             r["telefono"] or "", r["correo_electronico"] or "", r["estado"]) for r in cur.fetchall()]

    def list_nurses(self) -> List[Professional]:
        with self._tx() as cur:
            return self._enfermeros(cur)

    def create_nurse(self, data: Dict[str, Any]) -> Professional:
        self.requerido(data, "nombre_completo", "numero_colegiado")
        try:
            with self._tx() as cur:
                cur.execute(
                    """INSERT INTO Enfermero (nombre, numero_colegiado, area, telefono, correo_electronico)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id_enfermero""",
                    (data["nombre_completo"].strip(), data["numero_colegiado"].strip(), data.get("especialidad") or None,
                     data.get("telefono") or None, data.get("correo_electronico") or None))
                return self._enfermeros(cur, "id_enfermero = %s", (cur.fetchone()["id_enfermero"],))[0]
        except psycopg2.errors.UniqueViolation:
            raise ValueError(f"Ya existe un enfermero con colegiado {data['numero_colegiado']}")

    def update_nurse(self, nurse_id: int, data: Dict[str, Any]) -> Professional:
        self.validar_profesional(data)
        campos = {"nombre": data.get("nombre_completo"), "area": data.get("especialidad"), "telefono": data.get("telefono"),
                  "correo_electronico": data.get("correo_electronico"), "estado": data.get("estado")}
        campos = {k: v for k, v in campos.items() if v not in (None, "")}
        with self._tx() as cur:
            if campos:
                cur.execute(f"UPDATE Enfermero SET {', '.join(f'{k} = %s' for k in campos)} WHERE id_enfermero = %s",
                            (*campos.values(), nurse_id))
            if data.get("estado") == "inactivo":
                # Al desactivar, se anulan sus turnos futuros
                cur.execute("""UPDATE Asignacion_Turno SET estado = 'anulada'
                               WHERE id_enfermero = %s AND estado = 'activa' AND fecha > CURRENT_DATE""", (nurse_id,))
            r = self._enfermeros(cur, "id_enfermero = %s", (nurse_id,))
            if not r:
                raise ValueError(f"Enfermero {nurse_id} no encontrado")
            return r[0]

    _SQL_TURNO = """SELECT t.*, e.nombre AS enfermero, h.id_paciente, h.numero_habitacion,
                           p.nombres || ' ' || p.apellidos AS paciente
                    FROM Asignacion_Turno t
                    JOIN Enfermero e ON e.id_enfermero = t.id_enfermero
                    JOIN Hospitalizacion h ON h.id_hospitalizacion = t.id_hospitalizacion
                    JOIN Paciente p ON p.id_paciente = h.id_paciente"""

    def _turnos(self, cur, where, params) -> List[ShiftAssignment]:
        cur.execute(f"""{self._SQL_TURNO} WHERE {where}
                        ORDER BY t.fecha DESC, CASE t.turno WHEN 'manana' THEN 1 WHEN 'tarde' THEN 2 ELSE 3 END, e.nombre""",
                    params)
        return [
            ShiftAssignment(
                id_asignacion=r["id_asignacion"], id_enfermero=r["id_enfermero"], enfermero_nombre=r["enfermero"],
                id_hospitalizacion=r["id_hospitalizacion"], id_paciente=r["id_paciente"], paciente_nombre=r["paciente"],
                numero_habitacion=r["numero_habitacion"], fecha=self._s(r["fecha"]), turno=r["turno"],
                observaciones=r["observaciones"], estado=r["estado"],
            )
            for r in cur.fetchall()
        ]

    def list_shift_assignments(self, fecha=None, patient_id=None) -> List[ShiftAssignment]:
        cond, params = ["t.estado = 'activa'"], []
        if fecha:
            cond.append("t.fecha = %s")
            params.append(fecha)
        if patient_id:
            cond.append("h.id_paciente = %s")
            params.append(patient_id)
        with self._tx() as cur:
            return self._turnos(cur, " AND ".join(cond), tuple(params))

    def assign_shift(self, data: Dict[str, Any]) -> ShiftAssignment:
        self.requerido(data, "id_enfermero", "id_hospitalizacion", "fecha", "turno")
        with self._tx_hosp() as cur:
            # El turno de noche empieza un día y termina el siguiente: a las 2 a. m. aún vale el de ayer.
            cur.execute("""SELECT (%s::date < CURRENT_DATE - 1)
                                  OR (%s::date < CURRENT_DATE AND (%s <> 'noche' OR LOCALTIME >= TIME '07:00')) AS pasado""",
                        (data["fecha"], data["fecha"], data["turno"]))
            if cur.fetchone()["pasado"]:
                raise ValueError("No se asignan turnos en fechas pasadas")
            cur.execute(
                """INSERT INTO Asignacion_Turno (id_enfermero, id_hospitalizacion, fecha, turno, observaciones)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id_asignacion""",
                (int(data["id_enfermero"]), int(data["id_hospitalizacion"]), data["fecha"], data["turno"],
                 data.get("observaciones") or None))
            aid = cur.fetchone()["id_asignacion"]
            return self._turnos(cur, "t.id_asignacion = %s", (aid,))[0]

    def annul_shift(self, assignment_id: int) -> ShiftAssignment:
        with self._tx_hosp() as cur:
            cur.execute("UPDATE Asignacion_Turno SET estado = 'anulada' WHERE id_asignacion = %s AND estado = 'activa'",
                        (assignment_id,))
            if cur.rowcount == 0:
                raise ValueError("La asignación no existe o ya estaba anulada")
            return self._turnos(cur, "t.id_asignacion = %s", (assignment_id,))[0]

    # ---- Hospitalizaciones y altas --------------------------------------
    def list_hospitalizations(self, solo_ingresados: bool = True) -> List[Dict[str, Any]]:
        with self._tx() as cur:
            cur.execute(
                f"""SELECT h.*, p.nombres || ' ' || p.apellidos AS paciente,
                           EXISTS (SELECT 1 FROM Cirugia c WHERE c.id_paciente = h.id_paciente AND c.estado = 'en_curso') AS en_cirugia
                    FROM Hospitalizacion h JOIN Paciente p ON p.id_paciente = h.id_paciente
                    {"WHERE h.estado = 'ingresado'" if solo_ingresados else ""}
                    ORDER BY h.numero_habitacion""")
            return [{**{k: (self._s(v) if k.startswith("fecha") else v) for k, v in r.items()}} for r in cur.fetchall()]

    def discharge(self, hospitalization_id: int, tipo: str = "alta") -> Dict[str, Any]:
        if tipo not in ("alta", "referido"):
            raise ValueError("Tipo de egreso inválido: use alta o referido")
        with self._tx_hosp() as cur:
            cur.execute("SELECT * FROM Hospitalizacion WHERE id_hospitalizacion = %s FOR UPDATE", (hospitalization_id,))
            h = cur.fetchone()
            if not h:
                raise ValueError("Hospitalización no encontrada")
            if h["estado"] != "ingresado":
                raise ValueError("El paciente ya no está ingresado")
            cur.execute("SELECT 1 FROM Cirugia WHERE id_paciente = %s AND estado = 'en_curso'", (h["id_paciente"],))
            if cur.fetchone():
                raise ValueError("El paciente está en cirugía; no se puede dar de alta todavía")
            cur.execute("UPDATE Hospitalizacion SET estado = %s, fecha_egreso = NOW() WHERE id_hospitalizacion = %s",
                        (tipo, hospitalization_id))
            cur.execute("""UPDATE Cirugia SET estado = 'cancelada', motivo_cancelacion = 'Egreso del paciente'
                           WHERE id_hospitalizacion = %s AND estado = 'programada'""", (hospitalization_id,))
            canceladas = cur.rowcount
            cur.execute("""UPDATE Asignacion_Turno SET estado = 'anulada'
                           WHERE id_hospitalizacion = %s AND estado = 'activa' AND fecha > CURRENT_DATE""",
                        (hospitalization_id,))
            cur.execute("""UPDATE Paciente SET estado_salud = 'activo'
                           WHERE id_paciente = %s AND estado_salud = 'hospitalizado'
                             AND NOT EXISTS (SELECT 1 FROM Hospitalizacion WHERE id_paciente = %s AND estado = 'ingresado')""",
                        (h["id_paciente"], h["id_paciente"]))
            cur.execute("UPDATE Historial_Clinico SET fecha_ultima_actualizacion = NOW() WHERE id_paciente = %s",
                        (h["id_paciente"],))
        return {"id_hospitalizacion": hospitalization_id, "estado": tipo, "cirugias_canceladas": canceladas}

    # ------------------------------------------------------------------
    def _to_patient(self, r: Dict[str, Any]) -> Patient:
        return Patient(
            id_paciente=r["id_paciente"], nombres=r["nombres"], apellidos=r["apellidos"],
            fecha_nacimiento=self._s(r["fecha_nacimiento"]), sexo=r["sexo"], dpi=r["dpi"],
            direccion=r["direccion"] or "", telefono=r["telefono"] or "",
            correo_electronico=r["correo_electronico"] or "",
            contacto_emergencia_nombre=r["contacto_emergencia_nombre"] or "",
            contacto_emergencia_telefono=r["contacto_emergencia_telefono"] or "",
            fecha_registro=self._s(r["fecha_registro"]), estado=r["estado_salud"],
            tipo_sangre=r["tipo_sangre"],
        )
