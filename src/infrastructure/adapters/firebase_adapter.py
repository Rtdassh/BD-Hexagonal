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
    Treatment,
    UnifiedClinicalRecord,
    UserRole,
)

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


class FirebaseAdapter(BaseClinicalAdapter):
    is_live = True

    def __init__(self, config: Config, client=None):
        self.config = config
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
        cambios = {k: v for k, v in updates.items() if k in CAMPOS_EDITABLES}
        if "contacto_emergencia_nombre" in updates:
            cambios["contacto_emergencia.nombre"] = updates["contacto_emergencia_nombre"]
        if "contacto_emergencia_telefono" in updates:
            cambios["contacto_emergencia.telefono"] = updates["contacto_emergencia_telefono"]
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
        id_odont = int(data.get("id_odontologo") or (data.get("id_profesional") if data.get("rol") == "odontologo" else 1) or 1)
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
                "id_secretaria": int(data["id_profesional"]) if data.get("rol") == "secretaria" else None,
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

        id_odont = int(data.get("id_profesional") or 1)
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
                tx.update(cita_ref, {"estado_cita": "atendida"})

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
