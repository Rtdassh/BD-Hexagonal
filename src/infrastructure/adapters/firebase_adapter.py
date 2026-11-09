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
  * facturas/{id}                  -> Caja: factura con su detalle EMBEBIDO (CO-000001). Se
                                      genera sola al registrar una consulta con procedimientos
                                      o al proponer un plan de tratamiento.
  * pagos/{id}                     -> abonos y pagos (R-CO-000001), referencian la factura.
  * facturas_origen/{tipo}-{id}    -> índice que impide facturar dos veces la misma consulta
                                      o el mismo plan (se lee dentro de la transacción).

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
from ...domain.ports import BillingPort, DentalOperationsPort

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


class FirebaseAdapter(BaseClinicalAdapter, DentalOperationsPort, BillingPort):
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

    def _siguiente_id(self, nombre: str) -> int:
        """Reserva el siguiente id de una colección en su propia transacción."""
        def tx_fn(tx):
            return self._next_id(tx, nombre, self._leer_contador(tx, nombre))
        return self._run_tx(tx_fn)

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
                "codigo_arancel": self._codigo_proc(cat) if cat else None,
            })
        cobrar = any(p["costo"] > 0 for p in procedimientos)

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
            # Los procedimientos con costo generan su factura pendiente en Caja (misma transacción)
            ctx_fac = self._leer_para_factura(tx, {"id_paciente": pid}) if cobrar else None

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
            if ctx_fac is not None:
                fac = self._escribir_factura(tx, ctx_fac, {
                    "id_paciente": pid, "origen_tipo": "consulta", "origen_id": id_consulta,
                    "lineas": [{"codigo_arancel": p["codigo_arancel"], "cantidad": 1, "precio_unitario": p["costo"],
                                "concepto": p["nombre_procedimiento"] + (f" (pieza {p['pieza_dental']})"
                                                                         if p["pieza_dental"] != "General" else "")}
                               for p in procedimientos if p["costo"] > 0]})
                doc["id_factura"], doc["numero_factura"] = fac["id_factura"], fac["numero_factura"]
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

        planes = self.list_treatment_plans(patient_id)
        facturas = [f for f in self.list_invoices(patient_id=patient_id) if f["estado"] != "anulada"]
        pagos = [s.to_dict() for s in self.db.collection("pagos").where("id_paciente", "==", int(patient_id)).stream()]

        tot_fac = round(sum(f["monto_total"] for f in facturas), 2)
        tot_pag = round(sum(f["monto_pagado"] for f in facturas), 2)

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

    # ------------------------------------------------------------------
    # Planes de tratamiento
    # ------------------------------------------------------------------
    @staticmethod
    def _etapa(i: int, e: Dict[str, Any]) -> Dict[str, Any]:
        """Una fase del plan. Guarda los dos juegos de nombres (pantalla y documento)."""
        nombre = (e.get("nombre_etapa") or e.get("descripcion_fase") or f"Fase {i}").strip()
        costo = round(float(e.get("costo_estimado") or e.get("costo_fase") or 0.0), 2)
        est = e.get("estado") or e.get("estado_fase") or "pendiente"
        return {"id_etapa": i, "numero_etapa": i, "nombre_etapa": nombre, "descripcion_fase": nombre,
                "procedimientos_planificados": e.get("procedimientos_planificados") or "",
                "costo_estimado": costo, "costo_fase": costo, "estado": est, "estado_fase": est}

    def list_treatment_plans(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        q = self.db.collection("planes_tratamiento")
        if patient_id:
            q = q.where("id_paciente", "==", int(patient_id))
        return sorted((s.to_dict() for s in q.stream()), key=lambda p: p["id_plan"], reverse=True)

    def create_treatment_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(data["id_paciente"])
        etapas = [self._etapa(i, e) for i, e in enumerate(data.get("etapas") or [], 1)]
        suma = round(sum(e["costo_estimado"] for e in etapas), 2)
        total = round(float(data.get("costo_total_estimado") or suma), 2)
        if total < suma:
            raise ValueError(f"El costo total (Q{total:.2f}) es menor que la suma de las fases (Q{suma:.2f})")
        id_od = int(data.get("id_odontologo") or data.get("id_profesional") or 1)
        od = self.db.collection("odontologos").document(str(id_od)).get()
        od_nombre = od.to_dict().get("nombre_completo", "Odontólogo") if od.exists else "Odontólogo"
        titulo = data.get("titulo") or data.get("diagnostico_general") or "Plan odontológico"

        def tx_fn(tx):
            # 1) LECTURAS
            seq_plan = self._leer_contador(tx, "planes_tratamiento")
            # el id del plan aún no existe, así que no hace falta revisar si ya se facturó
            ctx = self._leer_para_factura(tx, {"id_paciente": pid})
            # 2) ESCRITURAS
            plan_id = self._next_id(tx, "planes_tratamiento", seq_plan)
            pac = ctx["paciente"]
            lineas = [{"codigo_arancel": None, "concepto": f"Plan #{plan_id}: {e['nombre_etapa']}",
                       "cantidad": 1, "precio_unitario": e["costo_estimado"]} for e in etapas if e["costo_estimado"] > 0]
            if total > suma:
                lineas.append({"codigo_arancel": None, "cantidad": 1, "precio_unitario": round(total - suma, 2),
                               "concepto": f"Plan #{plan_id}: fases restantes" if etapas else f"Plan #{plan_id}: {titulo}"})
            factura = self._escribir_factura(tx, ctx, {
                "id_paciente": pid, "lineas": lineas, "origen_tipo": "plan", "origen_id": plan_id}) if lineas else None
            plan = {
                "id_plan": plan_id, "id_paciente": pid, "paciente_nombre": f"{pac['nombres']} {pac['apellidos']}",
                "id_odontologo": id_od, "odontologo_nombre": od_nombre,
                "titulo": titulo, "diagnostico_general": data.get("diagnostico_general") or titulo,
                "costo_total_estimado": total, "estado": "propuesto", "estado_aprobacion": "pendiente",
                "fecha_propuesta": _ahora()[:10], "etapas": etapas,
                "id_factura": factura["id_factura"] if factura else None,
                "numero_factura": factura["numero_factura"] if factura else None,
            }
            tx.set(self.db.collection("planes_tratamiento").document(str(plan_id)), plan)
            return plan

        return self._run_tx(tx_fn)

    def update_treatment_plan_stage(self, plan_id: int, etapa_id: int, estado: str) -> Dict[str, Any]:
        ref = self.db.collection("planes_tratamiento").document(str(int(plan_id)))

        def tx_fn(tx):
            snap = ref.get(transaction=tx)
            if not snap.exists:
                raise ValueError(f"Plan {plan_id} no encontrado")
            p = snap.to_dict()
            etapas = p.get("etapas") or []
            if not any(int(e["id_etapa"]) == int(etapa_id) for e in etapas):
                raise ValueError(f"El plan {plan_id} no tiene la fase {etapa_id}")
            for e in etapas:
                if int(e["id_etapa"]) == int(etapa_id):
                    e["estado"] = e["estado_fase"] = estado
            if all(e.get("estado") == "completada" for e in etapas):
                p["estado"], p["estado_aprobacion"] = "finalizado", "finalizado"
            elif any(e.get("estado") in ("en_curso", "completada") for e in etapas):
                p["estado"], p["estado_aprobacion"] = "en_curso", "en_curso"
            tx.set(ref, p)
            return p

        return self._run_tx(tx_fn)

    # ------------------------------------------------------------------
    # Catálogo de procedimientos = aranceles de la Caja
    # ------------------------------------------------------------------
    @staticmethod
    def _codigo_proc(p: Dict[str, Any]) -> str:
        return p.get("codigo") or f"OD-{int(p['id_procedimiento']):02d}"

    def list_dental_procedures_catalog(self) -> List[Dict[str, Any]]:
        return sorted(({**s.to_dict(), "codigo": self._codigo_proc(s.to_dict())}
                       for s in self.db.collection("procedimientos_catalogo").stream()),
                      key=lambda p: p["id_procedimiento"])

    def create_dental_procedure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        def tx_fn(tx):
            new_id = self._next_id(tx, "procedimientos_catalogo", self._leer_contador(tx, "procedimientos_catalogo"))
            proc = {
                "id_procedimiento": new_id,
                "codigo": (data.get("codigo") or f"OD-{new_id:02d}").strip().upper(),
                "nombre_procedimiento": data["nombre_procedimiento"].strip(),
                "descripcion": data.get("descripcion") or "",
                "categoria": data.get("categoria") or data.get("especialidad") or "Operatoria",
                "duracion_estimada_min": int(data.get("duracion_estimada_min") or data.get("duracion_minutos") or 45),
                "costo": round(float(data["costo"]), 2),
                "activo": True,
            }
            tx.set(self.db.collection("procedimientos_catalogo").document(str(new_id)), proc)
            return proc

        return self._run_tx(tx_fn)

    def list_tariffs(self) -> List[Dict[str, Any]]:
        return [{"codigo": p["codigo"], "descripcion": p["nombre_procedimiento"], "categoria": "procedimiento",
                 "precio": float(p.get("costo") or 0), "activo": p.get("activo", True)}
                for p in self.list_dental_procedures_catalog()]

    def save_tariff(self, data: Dict[str, Any]) -> Dict[str, Any]:
        actual = next((p for p in self.list_dental_procedures_catalog() if p["codigo"] == data["codigo"]), None)
        if actual is None:
            self.create_dental_procedure({"codigo": data["codigo"], "nombre_procedimiento": data["descripcion"],
                                          "costo": data["precio"]})
        else:
            self.db.collection("procedimientos_catalogo").document(str(actual["id_procedimiento"])).update({
                "codigo": data["codigo"], "nombre_procedimiento": data["descripcion"],
                "costo": round(float(data["precio"]), 2), "activo": bool(data.get("activo", True))})
        return next(t for t in self.list_tariffs() if t["codigo"] == data["codigo"])

    # ------------------------------------------------------------------
    # Caja (BillingPort)
    # ------------------------------------------------------------------
    def _leer_para_factura(self, tx, data: Dict[str, Any]) -> Dict[str, Any]:
        """Fase de LECTURA de una factura nueva: paciente, contador y que el origen no esté facturado."""
        pid = int(data["id_paciente"])
        snap = self._paciente_ref(pid).get(transaction=tx)
        if not snap.exists:
            raise ValueError(f"Paciente {pid} no encontrado")
        if data.get("origen_id"):
            origen_ref = self.db.collection("facturas_origen").document(f"{data.get('origen_tipo') or 'manual'}-{int(data['origen_id'])}")
            ya = origen_ref.get(transaction=tx)
            if ya.exists:
                raise ValueError(f"Eso ya está facturado en la factura {ya.to_dict().get('numero_factura')}")
        return {"paciente": snap.to_dict(), "seq": self._leer_contador(tx, "facturas")}

    def _escribir_factura(self, tx, ctx: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Fase de ESCRITURA: la factura con su detalle embebido."""
        pac = ctx["paciente"]
        fid = self._next_id(tx, "facturas", ctx["seq"])
        detalle = [{"codigo_arancel": l.get("codigo_arancel") or None, "concepto": l["concepto"],
                    "cantidad": float(l["cantidad"]), "precio_unitario": round(float(l["precio_unitario"]), 2),
                    "subtotal": round(float(l["cantidad"]) * float(l["precio_unitario"]), 2)} for l in data["lineas"]]
        total = round(sum(d["subtotal"] for d in detalle), 2)
        est = "pendiente" if total > 0 else "pagada"
        origen_tipo, origen_id = data.get("origen_tipo") or "manual", data.get("origen_id")
        doc = {
            "id_factura": fid, "numero_factura": f"CO-{fid:06d}", "id_paciente": int(pac["id_paciente"]),
            "paciente": f"{pac['nombres']} {pac['apellidos']}",
            "nit": data.get("nit") or "CF",
            "nombre_facturacion": data.get("nombre_facturacion") or f"{pac['nombres']} {pac['apellidos']}",
            "fecha_emision": _ahora(), "detalle": detalle,
            "monto_total": total, "monto_pagado": 0.0, "saldo_pendiente": total,
            "estado": est, "estado_factura": est,
            "origen_tipo": origen_tipo, "origen_id": int(origen_id) if origen_id else None,
            "id_plan": int(origen_id) if origen_tipo == "plan" and origen_id else None,
            "motivo_anulacion": None,
        }
        tx.set(self.db.collection("facturas").document(str(fid)), doc)
        if origen_id:   # índice para no facturar dos veces el mismo plan o consulta
            tx.set(self.db.collection("facturas_origen").document(f"{origen_tipo}-{int(origen_id)}"),
                   {"id_factura": fid, "numero_factura": doc["numero_factura"]})
        return doc

    @staticmethod
    def _con_saldo(f: Dict[str, Any]) -> Dict[str, Any]:
        f["saldo"] = f["saldo_pendiente"] = round(f["monto_total"] - f["monto_pagado"], 2)
        return f

    def list_invoices(self, estado: Optional[str] = None, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        q = self.db.collection("facturas")
        if patient_id:
            q = q.where("id_paciente", "==", int(patient_id))
        facturas = [self._con_saldo(s.to_dict()) for s in q.stream()]
        if estado:
            facturas = [f for f in facturas if f["estado"] == estado]
        return sorted(facturas, key=lambda f: (f["fecha_emision"], f["id_factura"]), reverse=True)

    def _pagos_de(self, invoice_id: int) -> List[Dict[str, Any]]:
        return sorted((s.to_dict() for s in self.db.collection("pagos").where("id_factura", "==", int(invoice_id)).stream()),
                      key=lambda p: p["id_pago"])

    def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        snap = self.db.collection("facturas").document(str(int(invoice_id))).get()
        if not snap.exists:
            raise ValueError("Factura no encontrada")
        f = self._con_saldo(snap.to_dict())
        f["pagos"] = self._pagos_de(f["id_factura"])
        return f

    def create_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        def tx_fn(tx):
            ctx = self._leer_para_factura(tx, data)
            return self._escribir_factura(tx, ctx, data)["id_factura"]

        return self.get_invoice(self._run_tx(tx_fn))

    def register_invoice_payment(self, invoice_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        self._cobrar(invoice_id, data)
        return self.get_invoice(invoice_id)

    def _cobrar(self, invoice_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra el pago y devuelve el recibo."""
        monto = round(float(data["monto"]), 2)
        fref = self.db.collection("facturas").document(str(int(invoice_id)))

        def tx_fn(tx):
            # 1) LECTURAS: si otro cajero cobra al mismo tiempo, Firestore reintenta y vuelve a validar el saldo
            snap = fref.get(transaction=tx)
            if not snap.exists:
                raise ValueError("Factura no encontrada")
            f = snap.to_dict()
            if f["estado"] == "anulada":
                raise ValueError(f"La factura {f['numero_factura']} está anulada")
            if f["estado"] == "pagada":
                raise ValueError(f"La factura {f['numero_factura']} ya está pagada")
            saldo = round(f["monto_total"] - f["monto_pagado"], 2)
            if monto > saldo:
                raise ValueError(f"El pago (Q{monto:.2f}) supera el saldo de la factura (Q{saldo:.2f})")
            seq = self._leer_contador(tx, "pagos")
            # 2) ESCRITURAS
            pago_id = self._next_id(tx, "pagos", seq)
            quien = data.get("recibido_por") or "Caja"
            pago = {
                "id_pago": pago_id, "id_factura": f["id_factura"], "id_paciente": f["id_paciente"],
                "numero_recibo": f"R-CO-{pago_id:06d}", "fecha_pago": _ahora(),
                "monto": monto, "monto_abonado": monto, "metodo_pago": data["metodo_pago"],
                "referencia": data.get("referencia") or None, "recibido_por": quien, "secretaria": quien,
            }
            tx.set(self.db.collection("pagos").document(str(pago_id)), pago)
            pagado = round(f["monto_pagado"] + monto, 2)
            est = "pagada" if pagado >= f["monto_total"] else "parcial"
            tx.update(fref, {"monto_pagado": pagado, "saldo_pendiente": round(f["monto_total"] - pagado, 2),
                             "estado": est, "estado_factura": est})
            return pago

        return self._run_tx(tx_fn)

    def void_invoice(self, invoice_id: int, motivo: str) -> Dict[str, Any]:
        fref = self.db.collection("facturas").document(str(int(invoice_id)))

        def tx_fn(tx):
            snap = fref.get(transaction=tx)
            if not snap.exists:
                raise ValueError("Factura no encontrada")
            f = snap.to_dict()
            if f["estado"] == "anulada":
                raise ValueError("La factura ya está anulada")
            if f["monto_pagado"] > 0:
                raise ValueError(f"La factura {f['numero_factura']} tiene pagos por Q{f['monto_pagado']:.2f}; no se puede anular")
            tx.update(fref, {"estado": "anulada", "estado_factura": "anulada", "motivo_anulacion": motivo})
            if f.get("origen_id"):   # el plan o la consulta se puede volver a facturar
                tx.delete(self.db.collection("facturas_origen").document(f"{f['origen_tipo']}-{f['origen_id']}"))

        self._run_tx(tx_fn)
        return self.get_invoice(invoice_id)

    def suggested_charges(self, origen_tipo: str, origen_id: int) -> List[Dict[str, Any]]:
        return []

    # Rutas antiguas /api/dental/billing y /api/dental/payments: usan la misma Caja
    def list_billing_and_payments(self, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return [{**f, "abonos": self._pagos_de(f["id_factura"])} for f in self.list_invoices(patient_id=patient_id)]

    _METODOS = {"efectivo": "efectivo", "tarjeta de crédito/débito": "tarjeta", "transferencia bancaria": "transferencia",
                "tarjeta": "tarjeta", "transferencia": "transferencia", "cheque": "cheque"}

    def register_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        metodo = self._METODOS.get(str(data.get("metodo_pago") or "efectivo").strip().lower(), "efectivo")
        pago = self._cobrar(int(data["id_factura"]), {
            "monto": data.get("monto_abonado") or data.get("monto"), "metodo_pago": metodo,
            "referencia": data.get("referencia") or data.get("numero_recibo"),
            "recibido_por": data.get("secretaria") or data.get("recibido_por")})
        return {**pago, "pago": pago, "factura": self.get_invoice(int(data["id_factura"]))}

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
