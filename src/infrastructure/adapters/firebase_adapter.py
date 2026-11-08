"""
Adaptador Firebase Cloud Firestore - Clínica Odontológica.

Modelo documental:
  * pacientes/{id}                 -> datos del paciente + historial EMBEBIDO (relación 1:1,
                                      se lee siempre junto con el paciente).
  * pacientes/{id}/consultas/{id}  -> SUBCOLECCIÓN (referenciada): un paciente acumula
                                      consultas sin límite. Cada consulta EMBEBE sus diagnósticos,
                                      tratamiento, recetas y procedimientos por pieza (son pocos y
                                      se leen juntos).
  * citas/{id}                     -> colección raíz para la agenda de la secretaria. Guarda el
                                      nombre del paciente DUPLICADO (desnormalizado) para listar la
                                      agenda con una sola lectura.
  * odontologos, secretarias, procedimientos_catalogo -> catálogos.
  * contadores/{coleccion}         -> ids enteros secuenciales.

Consistencia: las escrituras que tocan varios documentos usan transacciones de
Firestore (todas las lecturas primero, luego las escrituras; si otro cliente
modifica un documento leído, Firestore reintenta la transacción).
"""

import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseClinicalAdapter
from ..config import Config
from ...domain.entities import (
    Appointment,
    Consultation,
    DatabaseEngine,
    DentalProcedureRecord,
    Diagnosis,
    InstitutionType,
    Patient,
    Prescription,
    Professional,
    Treatment,
    UnifiedClinicalRecord,
    UserRole,
)
from ...domain.ports import DentalOperationsPort

CAMPOS_EDITABLES = {
    "nombres", "apellidos", "fecha_nacimiento", "sexo", "direccion", "telefono", "correo_electronico",
}


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def crear_cliente_firestore(config: Config):
    """Crea el cliente de Firestore: emulador local o proyecto real de Firebase."""
    from google.cloud import firestore

    if config.FIRESTORE_EMULATOR_HOST:
        from google.auth.credentials import AnonymousCredentials

        os.environ["FIRESTORE_EMULATOR_HOST"] = config.FIRESTORE_EMULATOR_HOST
        return firestore.Client(project=config.FIREBASE_PROJECT_ID, credentials=AnonymousCredentials())

    if config.FIREBASE_CREDENTIALS_PATH:
        import firebase_admin
        from firebase_admin import credentials, firestore as admin_firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {"projectId": config.FIREBASE_PROJECT_ID})
        return admin_firestore.client()

    raise RuntimeError("Firebase no configurado: defina FIRESTORE_EMULATOR_HOST o FIREBASE_CREDENTIALS_PATH")


class FirebaseAdapter(BaseClinicalAdapter, DentalOperationsPort):
    is_live = True

    def __init__(self, config: Config, client=None):
        self.config = config
        if config.FIRESTORE_EMULATOR_HOST and client is None:
            import socket
            try:
                host, port = config.FIRESTORE_EMULATOR_HOST.split(":")
                with socket.create_connection((host, int(port)), timeout=2):
                    pass
            except Exception as e:
                raise ConnectionRefusedError(f"Emulador de Firestore no responde en {config.FIRESTORE_EMULATOR_HOST}: {e}") from e
        self.db = client if client is not None else crear_cliente_firestore(config)
        # Verificar que el servidor responde (falla rápido si no está disponible).
        self.db.collection("contadores").document("pacientes").get(timeout=5)

    # ------------------------------------------------------------------
    def _run_tx(self, fn: Callable):
        """Ejecuta fn(transaction) dentro de una transacción de Firestore."""
        from google.cloud import firestore

        return firestore.transactional(fn)(self.db.transaction())

    def _next_id(self, tx, nombre: str, actual: Optional[int] = None) -> int:
        """Debe llamarse DESPUÉS de leer el contador (lecturas antes que escrituras)."""
        nuevo = (actual or 0) + 1
        tx.set(self.db.collection("contadores").document(nombre), {"seq": nuevo})
        return nuevo

    def _leer_contador(self, tx, nombre: str) -> int:
        snap = self.db.collection("contadores").document(nombre).get(transaction=tx)
        return int(snap.to_dict().get("seq", 0)) if snap.exists else 0

    def _paciente_ref(self, pid: int):
        return self.db.collection("pacientes").document(str(int(pid)))

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.CLINICA_ODONTOLOGICA

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.FIREBASE

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        pacientes = self._leer_contador_simple("pacientes")
        consultas = self._leer_contador_simple("consultas")
        citas = self._leer_contador_simple("citas")
        return {
            "institucion": "Clínica Odontológica",
            "motor": "Firebase Cloud Firestore",
            "modo": "real",
            "estado": "online",
            "version": "Emulador local de Firestore" if self.config.FIRESTORE_EMULATOR_HOST else "Firestore (nube)",
            "base_datos": f"proyecto {self.config.FIREBASE_PROJECT_ID}",
            "latencia_ms": round((time.time() - start) * 1000, 1),
            "conteos": {"pacientes": pacientes, "consultas": consultas, "citas": citas},
            "consistencia": "Transacciones de Firestore (lecturas y escrituras atómicas con reintento)",
        }

    def _leer_contador_simple(self, nombre: str) -> int:
        snap = self.db.collection("contadores").document(nombre).get()
        return int(snap.to_dict().get("seq", 0)) if snap.exists else 0

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------
    def create_patient(self, data: Dict[str, Any]) -> Patient:
        self.requerido(data, "nombres", "apellidos", "fecha_nacimiento", "sexo", "dpi")
        dpi = data["dpi"].strip()
        # El índice del DPI se guarda como documento: dpi_index/{dpi}. Leerlo dentro de la
        # transacción garantiza unicidad incluso con dos secretarias registrando a la vez.
        dpi_ref = self.db.collection("dpi_index").document(dpi)

        def tx_fn(tx):
            if dpi_ref.get(transaction=tx).exists:
                raise ValueError(f"Ya existe un paciente con DPI {dpi}")
            seq_p = self._leer_contador(tx, "pacientes")
            seq_h = self._leer_contador(tx, "historiales")
            pid = self._next_id(tx, "pacientes", seq_p)
            hid = self._next_id(tx, "historiales", seq_h)
            hoy = datetime.now().strftime("%Y-%m-%d")
            tx.set(self._paciente_ref(pid), {
                "id_paciente": pid,
                "nombres": data["nombres"].strip(),
                "apellidos": data["apellidos"].strip(),
                "fecha_nacimiento": str(data["fecha_nacimiento"]),
                "sexo": data["sexo"],
                "dpi": dpi,
                "direccion": data.get("direccion") or "",
                "telefono": data.get("telefono") or "",
                "correo_electronico": data.get("correo_electronico") or "",
                "contacto_emergencia": {
                    "nombre": data.get("contacto_emergencia_nombre") or "",
                    "telefono": data.get("contacto_emergencia_telefono") or "",
                },
                "fecha_registro": hoy,
                "estado": "activo",
                "historial": {
                    "id_historial": hid, "fecha_apertura": hoy, "fecha_ultima_actualizacion": _ahora(),
                    "estado": "activo", "motivo_baja": None,
                },
            })
            tx.set(dpi_ref, {"id_paciente": pid})
            return pid

        pid = self._run_tx(tx_fn)
        return self.get_patient(pid)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        snap = self._paciente_ref(patient_id).get()
        return self._to_patient(snap.to_dict()) if snap.exists else None

    def search_patients(self, query: str) -> List[Patient]:
        # Firestore no tiene búsqueda por subcadena; la clínica es pequeña, así que se leen los
        # pacientes y se filtra en el servidor de la aplicación.
        q = (query or "").strip().lower()
        pacientes = [s.to_dict() for s in self.db.collection("pacientes").limit(500).stream()]
        if q:
            pacientes = [
                p for p in pacientes
                if q in f"{p['nombres']} {p['apellidos']}".lower() or p["dpi"].startswith(q) or str(p["id_paciente"]) == q
            ]
        pacientes.sort(key=lambda p: (p["apellidos"], p["nombres"]))
        return [self._to_patient(p) for p in pacientes]

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        # En los documentos un dato vacío se guarda como "" (el esquema exige texto)
        cambios = {k: ("" if v is None else v) for k, v in updates.items() if k in CAMPOS_EDITABLES}
        if "contacto_emergencia_nombre" in updates:
            cambios["contacto_emergencia.nombre"] = updates["contacto_emergencia_nombre"] or ""
        if "contacto_emergencia_telefono" in updates:
            cambios["contacto_emergencia.telefono"] = updates["contacto_emergencia_telefono"] or ""
        if not cambios:
            raise ValueError("No hay campos válidos para actualizar")
        ref = self._paciente_ref(patient_id)
        if not ref.get().exists:
            raise ValueError(f"Paciente {patient_id} no encontrado")
        cambios["historial.fecha_ultima_actualizacion"] = _ahora()
        ref.update(cambios)
        return self.get_patient(patient_id)

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
        pid = int(patient_id)
        estado = self.estado_por_motivo(categoria)
        ref = self._paciente_ref(pid)
        citas_q = self.db.collection("citas").where("id_paciente", "==", pid)

        def tx_fn(tx):
            snap = ref.get(transaction=tx)
            if not snap.exists:
                raise ValueError(f"Paciente {pid} no encontrado")
            if snap.to_dict()["historial"]["estado"] != "activo":
                raise ValueError("El historial ya está dado de baja")
            pendientes = [c for c in citas_q.get(transaction=tx) if c.to_dict().get("estado_cita") == "programada"]
            tx.update(ref, {
                "estado": "dado_de_baja",
                "historial.estado": estado,
                "historial.motivo_baja": motivo_baja,
                "historial.fecha_ultima_actualizacion": _ahora(),
            })
            for c in pendientes:
                tx.update(c.reference, {"estado_cita": "cancelada"})
            return len(pendientes)

        canceladas = self._run_tx(tx_fn)
        return {
            "id_paciente": pid, "estado": estado, "motivo_baja": motivo_baja,
            "citas_canceladas": canceladas, "motor": "Firebase Cloud Firestore",
            "mensaje": "Historial archivado en una transacción de Firestore.",
        }

    # ------------------------------------------------------------------
    # Citas (agenda de la secretaria)
    # ------------------------------------------------------------------
    def create_appointment(self, data: Dict[str, Any]) -> Appointment:
        self.requerido(data, "id_paciente", "fecha_hora_programada", "motivo_consulta")
        pid = int(data["id_paciente"])
        id_odont = int(data["id_profesional"])
        pac_ref = self._paciente_ref(pid)
        od_snap = self.db.collection("odontologos").document(str(id_odont)).get()
        od_nombre = od_snap.to_dict().get("nombre_completo") if od_snap.exists else "Odontólogo"

        def tx_fn(tx):
            p = pac_ref.get(transaction=tx)
            if not p.exists:
                raise ValueError(f"Paciente {pid} no encontrado")
            pd = p.to_dict()
            if pd["historial"]["estado"] != "activo":
                raise ValueError(f"El historial está '{pd['historial']['estado']}' y no admite nuevos registros")
            seq = self._leer_contador(tx, "citas")
            cid = self._next_id(tx, "citas", seq)
            doc = {
                "id_cita": cid,
                "id_paciente": pid,
                "paciente_nombre": f"{pd['nombres']} {pd['apellidos']}",
                "id_odontologo": id_odont,
                "odontologo_nombre": od_nombre,
                "id_secretaria": None,
                "fecha_hora_programada": str(data["fecha_hora_programada"]).replace("T", " ")[:16],
                "motivo_consulta": data["motivo_consulta"],
                "estado_cita": "programada",
                "fecha_creacion": _ahora(),
            }
            tx.set(self.db.collection("citas").document(str(cid)), doc)
            return doc

        return self._to_cita(self._run_tx(tx_fn))

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        col = self.db.collection("citas")
        q = col.where("id_paciente", "==", int(patient_id)) if patient_id else col.where("estado_cita", "==", "programada")
        citas = [s.to_dict() for s in q.stream()]
        citas.sort(key=lambda c: c["fecha_hora_programada"], reverse=True)
        return [self._to_cita(c) for c in citas]

    def _to_cita(self, d) -> Appointment:
        return Appointment(
            id_cita=d["id_cita"], id_paciente=d["id_paciente"], id_profesional=d.get("id_odontologo", 1),
            profesional_nombre=d.get("odontologo_nombre", ""), fecha_hora_programada=d["fecha_hora_programada"],
            motivo_consulta=d["motivo_consulta"], estado_cita=d["estado_cita"],
            fecha_creacion=d.get("fecha_creacion", ""), id_secretaria=d.get("id_secretaria"),
        )

    # ------------------------------------------------------------------
    # Consulta odontológica (transacción de Firestore)
    # ------------------------------------------------------------------
    def register_consultation(self, data: Dict[str, Any]) -> Consultation:
        self.requerido(data, "id_paciente", "motivo")
        pid = int(data["id_paciente"])
        recetas = self.recetas_del_payload(data)
        tiene_diag = bool(data.get("codigo_cie10") or data.get("descripcion_diagnostico"))
        if recetas and not tiene_diag:
            raise ValueError("Para recetar se necesita un diagnóstico")

        catalogo = {
            s.to_dict()["id_procedimiento"]: s.to_dict()
            for s in self.db.collection("procedimientos_catalogo").stream()
        }
        procedimientos = []
        for p in data.get("procedimientos") or []:
            if not p.get("id_procedimiento") and not p.get("nombre_procedimiento"):
                continue
            cat = catalogo.get(self._i(p.get("id_procedimiento")), {})
            procedimientos.append({
                "id_procedimiento": self._i(p.get("id_procedimiento")),
                "nombre_procedimiento": p.get("nombre_procedimiento") or cat.get("nombre_procedimiento", "Procedimiento"),
                "pieza_dental": str(p.get("pieza_dental") or "General"),
                "observaciones": p.get("observaciones") or "",
                "costo": self._f(p.get("costo")) if p.get("costo") not in (None, "") else float(cat.get("costo", 0.0)),
            })

        id_odont = int(data["id_profesional"])
        od_snap = self.db.collection("odontologos").document(str(id_odont)).get()
        od_nombre = od_snap.to_dict().get("nombre_completo") if od_snap.exists else "Odontólogo"
        pac_ref = self._paciente_ref(pid)
        cita_ref = self.db.collection("citas").document(str(data["id_cita"])) if data.get("id_cita") else None

        def tx_fn(tx):
            # 1) LECTURAS
            p = pac_ref.get(transaction=tx)
            if not p.exists:
                raise ValueError(f"Paciente {pid} no encontrado")
            pd = p.to_dict()
            if pd["historial"]["estado"] != "activo":
                raise ValueError(f"El historial está '{pd['historial']['estado']}' y no admite nuevos registros")
            cita = None
            if cita_ref is not None:
                cs = cita_ref.get(transaction=tx)
                cita = cs.to_dict() if cs.exists else None
                if not cita or cita["id_paciente"] != pid:
                    raise ValueError("La cita no pertenece a este paciente")
                if cita["estado_cita"] != "programada":
                    raise ValueError(f"La cita ya está '{cita['estado_cita']}'")
            seq_c = self._leer_contador(tx, "consultas")
            seq_ci = self._leer_contador(tx, "citas") if cita is None else None

            # 2) ESCRITURAS
            if cita is None:
                id_cita = self._next_id(tx, "citas", seq_ci)
                tx.set(self.db.collection("citas").document(str(id_cita)), {
                    "id_cita": id_cita, "id_paciente": pid,
                    "paciente_nombre": f"{pd['nombres']} {pd['apellidos']}",
                    "id_odontologo": id_odont, "odontologo_nombre": od_nombre, "id_secretaria": None,
                    "fecha_hora_programada": _ahora(), "motivo_consulta": data["motivo"],
                    "estado_cita": "atendida", "fecha_creacion": _ahora(),
                })
            else:
                id_cita = cita["id_cita"]
                tx.update(cita_ref, {"estado_cita": "atendida", "id_odontologo": id_odont, "odontologo_nombre": od_nombre})

            id_consulta = self._next_id(tx, "consultas", seq_c)
            hoy = datetime.now().strftime("%Y-%m-%d")
            doc = {
                "id_consulta": id_consulta,
                "id_cita": id_cita,
                "fecha_hora_atencion": _ahora(),
                "motivo": data["motivo"],
                "tipo_consulta": data.get("tipo_consulta") or "ordinaria",
                "notas_clinicas": data.get("notas_clinicas") or "",
                "id_odontologo": id_odont,
                "odontologo_nombre": od_nombre,
                "diagnosticos": [{
                    "codigo_cie10": (data.get("codigo_cie10") or "").upper(),
                    "descripcion": data.get("descripcion_diagnostico") or "",
                    "tipo": data.get("tipo_diagnostico") or "principal",
                    "fecha_diagnostico": hoy,
                }] if tiene_diag else [],
                "tratamiento": {
                    "descripcion": data.get("descripcion_tratamiento"),
                    "indicaciones": data.get("indicaciones_tratamiento"),
                } if data.get("descripcion_tratamiento") else None,
                "recetas": [{
                    "medicamento": r["medicamento"].strip(),
                    "presentacion": r.get("presentacion") or "",
                    "dosis": r.get("dosis") or "Según indicación",
                    "frecuencia": r.get("frecuencia") or "Cada 8 horas",
                    "duracion_dias": self._i(r.get("duracion_dias")) or 1,
                    "via_administracion": r.get("via_administracion") or "Oral",
                    "indicaciones": r.get("indicaciones") or "",
                    "fecha_emision": hoy,
                } for r in recetas],
                "procedimientos": procedimientos,
                "total_cobrado": round(sum(p["costo"] for p in procedimientos), 2),
            }
            tx.set(pac_ref.collection("consultas").document(str(id_consulta)), doc)
            tx.update(pac_ref, {"historial.fecha_ultima_actualizacion": _ahora()})
            return doc

        doc = self._run_tx(tx_fn)
        return self._to_consulta(doc)

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    def get_clinical_history(self, patient_id: int, user_role: UserRole = UserRole.MEDICO) -> Optional[UnifiedClinicalRecord]:
        ref = self._paciente_ref(patient_id)
        snap = ref.get()
        if not snap.exists:
            return None
        pd = snap.to_dict()
        h = pd.get("historial", {})
        consultas = [self._to_consulta(s.to_dict()) for s in ref.collection("consultas").stream()]
        consultas.sort(key=lambda c: c.fecha_hora_atencion, reverse=True)
        record = UnifiedClinicalRecord(
            id_historial=h.get("id_historial", 0), id_paciente=int(patient_id), paciente=self._to_patient(pd),
            fecha_apertura=h.get("fecha_apertura"), fecha_ultima_actualizacion=h.get("fecha_ultima_actualizacion"),
            estado=h.get("estado", "activo"), motivo_baja=h.get("motivo_baja"),
            institucion=InstitutionType.CLINICA_ODONTOLOGICA, motor=DatabaseEngine.FIREBASE,
            consultas=consultas, citas=self.get_appointments(int(patient_id)),
            datos_adicionales={
                "piezas_tratadas": sorted({p.pieza_dental for c in consultas for p in c.procedimientos_dentales}),
            },
        )
        return self.apply_security_filter(record, user_role)

    def _to_consulta(self, d: Dict[str, Any]) -> Consultation:
        recetas = [
            Prescription(
                id_receta=i + 1, medicamento=r["medicamento"], dosis=r.get("dosis", ""),
                frecuencia=r.get("frecuencia", ""), duracion_dias=r.get("duracion_dias", 0),
                via_administracion=r.get("via_administracion"), indicaciones=r.get("indicaciones"),
                fecha_emision=r.get("fecha_emision"), presentacion=r.get("presentacion"),
            )
            for i, r in enumerate(d.get("recetas") or [])
        ]
        trat = d.get("tratamiento")
        diagnosticos = []
        for i, dg in enumerate(d.get("diagnosticos") or []):
            diagnosticos.append(Diagnosis(
                id_diagnostico=i + 1, codigo_cie10=dg.get("codigo_cie10", ""), descripcion=dg.get("descripcion", ""),
                tipo=dg.get("tipo", "principal"), fecha_diagnostico=dg.get("fecha_diagnostico"),
                tratamientos=[Treatment(
                    id_tratamiento=1, descripcion=trat.get("descripcion") or "", fecha_inicio=dg.get("fecha_diagnostico"),
                    fecha_fin=None, estado="activo", indicaciones=trat.get("indicaciones"), recetas=recetas,
                )] if (trat and i == 0) else [],
            ))
        return Consultation(
            id_consulta=d["id_consulta"], id_cita=d.get("id_cita") or 0,
            fecha_hora_atencion=d.get("fecha_hora_atencion", ""), motivo=d.get("motivo", ""),
            notas_clinicas=d.get("notas_clinicas"), tipo_consulta=d.get("tipo_consulta", "ordinaria"),
            profesional_nombre=d.get("odontologo_nombre"), diagnosticos=diagnosticos, recetas=recetas,
            procedimientos_dentales=[
                DentalProcedureRecord(
                    id_consulta_procedimiento=i + 1, id_cita=d.get("id_cita") or 0,
                    nombre_procedimiento=p.get("nombre_procedimiento", ""), pieza_dental=p.get("pieza_dental", ""),
                    observaciones=p.get("observaciones", ""), fecha_realizacion=d.get("fecha_hora_atencion", ""),
                    costo=float(p.get("costo", 0.0)),
                )
                for i, p in enumerate(d.get("procedimientos") or [])
            ],
        )

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        ref = self._paciente_ref(patient_id)
        piezas: Dict[str, List[Dict[str, Any]]] = {}
        for s in ref.collection("consultas").stream():
            c = s.to_dict()
            for p in c.get("procedimientos") or []:
                piezas.setdefault(p.get("pieza_dental", "General"), []).append({
                    "procedimiento": p.get("nombre_procedimiento"), "fecha": c.get("fecha_hora_atencion"),
                })
        return {"institucion": "Clínica Odontológica", "motor": "Firebase Cloud Firestore", "odontograma": piezas}

    # ------------------------------------------------------------------
    # Personal: colección odontologos
    # ------------------------------------------------------------------
    @staticmethod
    def _to_prof(d) -> Professional:
        return Professional(d["id_odontologo"], d["nombre_completo"], d.get("numero_colegiado", ""),
                            d.get("especialidad", ""), d.get("telefono", ""), d.get("correo_electronico", ""),
                            d.get("estado", "activo"))

    def list_professionals(self) -> List[Professional]:
        docs = [s.to_dict() for s in self.db.collection("odontologos").stream()]
        docs.sort(key=lambda d: (d.get("estado", "activo"), d["nombre_completo"]))
        return [self._to_prof(d) for d in docs]

    def create_professional(self, data: Dict[str, Any]) -> Professional:
        self.requerido(data, "nombre_completo", "numero_colegiado")
        colegiado = data["numero_colegiado"].strip()
        indice = self.db.collection("colegiado_index").document(colegiado)

        def tx_fn(tx):
            if indice.get(transaction=tx).exists:
                raise ValueError(f"Ya existe un odontólogo con colegiado {colegiado}")
            seq = self._leer_contador(tx, "odontologos")
            oid = self._next_id(tx, "odontologos", seq)
            doc = {
                "id_odontologo": oid,
                "nombre_completo": data["nombre_completo"].strip(),
                "numero_colegiado": colegiado,
                "especialidad": data.get("especialidad") or "Odontología general",
                "telefono": data.get("telefono") or "",
                "correo_electronico": data.get("correo_electronico") or "",
                "horarios_atencion": data.get("horarios_atencion") or "",
                "estado": "activo",
            }
            tx.set(self.db.collection("odontologos").document(str(oid)), doc)
            tx.set(indice, {"id_odontologo": oid})
            return doc

        return self._to_prof(self._run_tx(tx_fn))

    def update_professional(self, professional_id: int, data: Dict[str, Any]) -> Professional:
        self.validar_profesional(data)
        ref = self.db.collection("odontologos").document(str(int(professional_id)))
        if not ref.get().exists:
            raise ValueError(f"Odontólogo {professional_id} no encontrado")
        cambios = {k: v for k, v in data.items()
                   if k in ("nombre_completo", "especialidad", "telefono", "correo_electronico", "estado") and v not in (None, "")}
        if cambios:
            ref.update(cambios)
        return self._to_prof(ref.get().to_dict())

    def get_catalogs(self) -> Dict[str, Any]:
        procs = sorted((s.to_dict() for s in self.db.collection("procedimientos_catalogo").stream()),
                       key=lambda p: p["id_procedimiento"])
        odont = sorted((s.to_dict() for s in self.db.collection("odontologos").stream()),
                       key=lambda o: o["id_odontologo"])
        return {"procedimientos": procs, "odontologos": odont}

    def _to_patient(self, d) -> Patient:
        ce = d.get("contacto_emergencia") or {}
        return Patient(
            id_paciente=d["id_paciente"], nombres=d["nombres"], apellidos=d["apellidos"],
            fecha_nacimiento=d["fecha_nacimiento"], sexo=d["sexo"], dpi=d["dpi"],
            direccion=d.get("direccion", ""), telefono=d.get("telefono", ""),
            correo_electronico=d.get("correo_electronico", ""),
            contacto_emergencia_nombre=ce.get("nombre", ""), contacto_emergencia_telefono=ce.get("telefono", ""),
            fecha_registro=d.get("fecha_registro", ""), estado=d.get("estado", "activo"),
        )

    # ------------------------------------------------------------------
    # Implementación de DentalOperationsPort (Cloud Firestore)
    # ------------------------------------------------------------------
    def get_dental_details(self, patient_id: int) -> Dict[str, Any]:
        p = self.get_patient(patient_id)
        if not p:
            raise ValueError(f"Paciente {patient_id} no encontrado en Firestore")
        ref = self._paciente_ref(patient_id)
        ant_snap = ref.collection("antecedente_sistemico").document("principal").get()
        ant = ant_snap.to_dict() if ant_snap.exists else {
            "padece_diabetes": False, "padece_hipertension": False, "padece_coagulopatia": False,
            "es_alergico_anestesia": False, "es_alergico_latex": False, "esta_embarazada": False,
            "medicamentos_actuales": "", "observaciones_medicas": "Sin antecedentes patológicos."
        }

        hallazgos = [s.to_dict() for s in ref.collection("odontograma").stream()]
        piezas_tratadas = {str(h["codigo_fdi"]) for h in hallazgos if "codigo_fdi" in h}

        procs = []
        for s in ref.collection("consultas").stream():
            c = s.to_dict()
            for pr in c.get("procedimientos") or []:
                procs.append({**pr, "fecha_hora_atencion": c.get("fecha_hora_atencion")})
                if pr.get("pieza_dental"):
                    piezas_tratadas.add(str(pr["pieza_dental"]).split()[0])

        planes = [s.to_dict() for s in self.db.collection("planes_tratamiento").where("id_paciente", "==", patient_id).stream()]
        facturas = [s.to_dict() for s in self.db.collection("facturas").where("id_paciente", "==", patient_id).stream()]
        pagos = [s.to_dict() for s in self.db.collection("pagos").where("id_paciente", "==", patient_id).stream()]

        tot_fac = sum(f.get("monto_total", 0.0) for f in facturas)
        tot_pag = sum(pg.get("monto_abonado", 0.0) for pg in pagos)

        return {
            "paciente": p,
            "antecedentes": ant,
            "hallazgos_odontograma": hallazgos,
            "piezas_tratadas": sorted(list(piezas_tratadas)),
            "procedimientos": procs,
            "planes_tratamiento": planes,
            "facturacion": {
                "facturas": facturas,
                "pagos": pagos,
                "total_facturado": tot_fac,
                "total_pagado": tot_pag,
                "saldo_pendiente": max(0.0, tot_fac - tot_pag)
            }
        }

    def update_systemic_background(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        ref = self._paciente_ref(patient_id).collection("antecedente_sistemico").document("principal")
        ant = {
            "padece_diabetes": bool(data.get("padece_diabetes", False)),
            "padece_hipertension": bool(data.get("padece_hipertension", False)),
            "padece_coagulopatia": bool(data.get("padece_coagulopatia", False)),
            "es_alergico_anestesia": bool(data.get("es_alergico_anestesia", False)),
            "es_alergico_latex": bool(data.get("es_alergico_latex", False)),
            "esta_embarazada": bool(data.get("esta_embarazada", False)),
            "medicamentos_actuales": data.get("medicamentos_actuales", ""),
            "observaciones_medicas": data.get("observaciones_medicas", "")
        }
        ref.set(ant)
        return ant

    def get_odontogram(self, patient_id: Optional[int] = None) -> Dict[str, Any]:
        if patient_id is not None:
            ref = self._paciente_ref(patient_id)
            hallazgos = [s.to_dict() for s in ref.collection("odontograma").stream()]
        else:
            try:
                hallazgos = [s.to_dict() for s in self.db.collection_group("odontograma").stream()]
            except Exception:
                hallazgos = []
        piezas = {}
        for h in hallazgos:
            piezas.setdefault(str(h.get("codigo_fdi")), []).append(h)
        return {"id_paciente": patient_id, "hallazgos": hallazgos, "piezas": piezas}

    def save_odontogram_finding(self, patient_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        ref = self._paciente_ref(patient_id).collection("odontograma")
        doc_id = f"{data['codigo_fdi']}_{data.get('cara', 'O')}"
        item = {
            "id_detalle": doc_id,
            "id_paciente": patient_id,
            "codigo_fdi": int(data["codigo_fdi"]),
            "cara": str(data.get("cara", "O")).upper(),
            "hallazgo": str(data["hallazgo"]).strip(),
            "color_hex": str(data.get("color_hex", "#E53935")),
            "notas": str(data.get("notas", "")),
            "fecha": _ahora()[:10]
        }
        ref.document(doc_id).set(item)
        return item

    def list_treatment_plans(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        q = self.db.collection("planes_tratamiento")
        if patient_id:
            q = q.where("id_paciente", "==", patient_id)
        return [s.to_dict() for s in q.stream()]

    def create_treatment_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        new_id = self._siguiente_id("planes_tratamiento")
        etapas_raw = data.get("etapas") or []
        etapas = []
        for i, e in enumerate(etapas_raw, 1):
            etapas.append({
                "id_etapa": i, "numero_etapa": i,
                "descripcion_fase": e.get("descripcion_fase", f"Fase {i}"),
                "costo_fase": float(e.get("costo_fase", 0.0)),
                "estado_fase": e.get("estado_fase", "pendiente")
            })
        costo_total = float(data.get("costo_total_estimado", sum(e["costo_fase"] for e in etapas)))
        plan = {
            "id_plan": new_id,
            "id_paciente": int(data["id_paciente"]),
            "id_odontologo": int(data.get("id_odontologo", 1)),
            "titulo": data.get("titulo", "Plan Odontológico"),
            "costo_total_estimado": costo_total,
            "estado_aprobacion": "pendiente",
            "fecha_propuesta": _ahora()[:10],
            "etapas": etapas
        }
        self.db.collection("planes_tratamiento").document(str(new_id)).set(plan)
        # Crear factura inicial
        id_fac = self._siguiente_id("facturas")
        self.db.collection("facturas").document(str(id_fac)).set({
            "id_factura": id_fac, "id_paciente": plan["id_paciente"], "id_plan": new_id,
            "fecha_emision": _ahora()[:10], "monto_total": costo_total, "monto_pagado": 0.0,
            "saldo_pendiente": costo_total, "estado_factura": "pendiente"
        })
        return plan

    def update_treatment_plan_stage(self, plan_id: int, etapa_id: int, estado: str) -> Dict[str, Any]:
        ref = self.db.collection("planes_tratamiento").document(str(int(plan_id)))
        snap = ref.get()
        if not snap.exists:
            raise ValueError(f"Plan {plan_id} no encontrado")
        p = snap.to_dict()
        for e in p.get("etapas") or []:
            if e["id_etapa"] == etapa_id:
                e["estado_fase"] = estado
        if all(e["estado_fase"] == "completada" for e in p.get("etapas", [])):
            p["estado_aprobacion"] = "finalizado"
        elif any(e["estado_fase"] == "completada" for e in p.get("etapas", [])):
            p["estado_aprobacion"] = "en_curso"
        ref.set(p)
        return p

    def list_dental_procedures_catalog(self) -> List[Dict[str, Any]]:
        return sorted((s.to_dict() for s in self.db.collection("procedimientos_catalogo").stream()),
                      key=lambda p: p["id_procedimiento"])

    def create_dental_procedure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        new_id = self._siguiente_id("procedimientos_catalogo")
        proc = {
            "id_procedimiento": new_id,
            "nombre_procedimiento": data["nombre_procedimiento"].strip(),
            "descripcion": data.get("descripcion", ""),
            "duracion_estimada_min": int(data.get("duracion_estimada_min", 45)),
            "costo": float(data["costo"])
        }
        self.db.collection("procedimientos_catalogo").document(str(new_id)).set(proc)
        return proc

    def list_billing_and_payments(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        q = self.db.collection("facturas")
        if patient_id:
            q = q.where("id_paciente", "==", patient_id)
        facturas = [s.to_dict() for s in q.stream()]
        res = []
        for f in facturas:
            pagos = [s.to_dict() for s in self.db.collection("pagos").where("id_factura", "==", f["id_factura"]).stream()]
            res.append({**f, "abonos": pagos})
        return res

    def register_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        id_fac = int(data["id_factura"])
        monto = float(data["monto_abonado"])
        fref = self.db.collection("facturas").document(str(id_fac))
        fsnap = fref.get()
        if not fsnap.exists:
            raise ValueError(f"Factura {id_fac} no encontrada")
        f = fsnap.to_dict()

        new_id = self._siguiente_id("pagos")
        pago = {
            "id_pago": new_id, "id_factura": id_fac, "id_paciente": f["id_paciente"],
            "fecha_pago": _ahora(), "monto_abonado": monto,
            "metodo_pago": data.get("metodo_pago", "Efectivo"),
            "numero_recibo": data["numero_recibo"].strip().upper(),
            "secretaria": data.get("secretaria", "Recepción")
        }
        self.db.collection("pagos").document(str(new_id)).set(pago)

        f["monto_pagado"] = round(f["monto_pagado"] + monto, 2)
        f["saldo_pendiente"] = max(0.0, round(f["monto_total"] - f["monto_pagado"], 2))
        f["estado_factura"] = "cancelada" if f["saldo_pendiente"] == 0 else "parcial"
        fref.set(f)
        return {
            **pago,
            "monto": monto,
            "monto_abonado": monto,
            "pago": pago,
            "factura": f
        }

    def list_dental_findings_catalog(self) -> List[Dict[str, Any]]:
        return [
            {"id_hallazgo": 1, "codigo": "caries", "nombre": "Caries activa", "color_hex": "#E53935"},
            {"id_hallazgo": 2, "codigo": "resina", "nombre": "Restauración resina", "color_hex": "#43A047"},
            {"id_hallazgo": 3, "codigo": "amalgama", "nombre": "Obturación amalgama", "color_hex": "#1E88E5"},
            {"id_hallazgo": 4, "codigo": "corona", "nombre": "Corona protésica", "color_hex": "#FDD835"},
            {"id_hallazgo": 5, "codigo": "endodoncia", "nombre": "Conducto / Endodoncia", "color_hex": "#8E24AA"},
            {"id_hallazgo": 6, "codigo": "ausente", "nombre": "Pieza ausente / extracción", "color_hex": "#757575"},
            {"id_hallazgo": 7, "codigo": "sellante", "nombre": "Sellante de fisuras", "color_hex": "#00ACC1"},
            {"id_hallazgo": 8, "codigo": "fractura", "nombre": "Fractura dental", "color_hex": "#FB8C00"}
        ]

    def list_dental_supplies(self) -> List[Dict[str, Any]]:
        return [
            {"id_insumo": 1, "nombre": "Resina Fotocurable A2", "unidad": "Jeringa 4g", "stock": 25, "stock_minimo": 5},
            {"id_insumo": 2, "nombre": "Anestubo Lidocaína 2% con Epinefrina", "unidad": "Caja 50 un.", "stock": 180, "stock_minimo": 20},
            {"id_insumo": 3, "nombre": "Anestubo Mepivacaína 3% (Sin vasoconstrictor)", "unidad": "Caja 50 un.", "stock": 60, "stock_minimo": 10}
        ]
