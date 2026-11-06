"""
Adaptador MongoDB - Laboratorio Clínico.

Modelo documental:
  * pacientes            -> datos personales; el contacto de emergencia va EMBEBIDO (1:1).
  * historiales_clinicos -> 1 documento por paciente (referencia por id_paciente).
  * ordenes              -> la "consulta" del laboratorio: diagnóstico presuntivo CIE-10, prioridad.
  * muestras             -> trazabilidad de cada tubo/frasco (referencia a la orden).
  * resultados           -> REFERENCIADOS (un paciente acumula cientos), pero sus parámetros van
                            EMBEBIDOS porque cada examen tiene una estructura distinta y siempre se
                            leen juntos.
  * tipos_examen         -> catálogo público con la plantilla de parámetros de cada examen.
  * citas                -> agenda de toma de muestras.

Consistencia: orden + muestra + resultado + historial se graban en una transacción
multi-documento (requiere replica set; docker-compose lo levanta como rs0).
"""

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from .base_adapter import BaseClinicalAdapter
from ..config import Config
from ...domain.entities import (
    Appointment,
    Consultation,
    DatabaseEngine,
    Diagnosis,
    InstitutionType,
    LabExamResult,
    LabParameter,
    Patient,
    UnifiedClinicalRecord,
    UserRole,
)

CAMPOS_EDITABLES = {
    "nombres", "apellidos", "fecha_nacimiento", "sexo", "direccion", "telefono",
    "correo_electronico", "tipo_sangre",
}


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class MongoDBAdapter(BaseClinicalAdapter):
    is_live = True

    def __init__(self, config: Config, client: Optional[MongoClient] = None):
        self.config = config
        self.client = client or MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)
        self.db = self.client[config.MONGO_DATABASE]
        self.db.command("ping")  # lanza excepción si el servidor no responde
        # Las transacciones multi-documento solo existen en replica set / sharded cluster.
        try:
            hello = self.client.admin.command("hello")
            self.transacciones = bool(hello.get("setName")) or hello.get("msg") == "isdbgrid"
        except Exception:
            self.transacciones = False

    # ------------------------------------------------------------------
    @contextmanager
    def _tx(self):
        """Sesión con transacción (commit al salir, abort si hay excepción)."""
        if not self.transacciones:
            yield None
            return
        with self.client.start_session() as session:
            with session.start_transaction():
                yield session

    def _next_id(self, nombre: str, session=None) -> int:
        doc = self.db.contadores.find_one_and_update(
            {"_id": nombre}, {"$inc": {"seq": 1}}, upsert=True,
            return_document=ReturnDocument.AFTER, session=session,
        )
        return int(doc["seq"])

    @property
    def institution_type(self) -> InstitutionType:
        return InstitutionType.LABORATORIO_CLINICO

    @property
    def database_engine(self) -> DatabaseEngine:
        return DatabaseEngine.MONGODB

    def health_check(self) -> Dict[str, Any]:
        start = time.time()
        info = self.client.server_info()
        return {
            "institucion": "Laboratorio Clínico",
            "motor": "MongoDB",
            "modo": "real",
            "estado": "online",
            "version": f"MongoDB {info.get('version')}",
            "base_datos": self.config.MONGO_DATABASE,
            "latencia_ms": round((time.time() - start) * 1000, 1),
            "conteos": {
                "pacientes": self.db.pacientes.count_documents({}),
                "ordenes": self.db.ordenes.count_documents({}),
                "resultados": self.db.resultados.count_documents({}),
            },
            "consistencia": (
                "Transacciones multi-documento (replica set)" if self.transacciones
                else "Sin replica set: escrituras atómicas por documento (sin transacción multi-documento)"
            ),
        }

    # ------------------------------------------------------------------
    # Pacientes
    # ------------------------------------------------------------------
    def create_patient(self, data: Dict[str, Any]) -> Patient:
        self.requerido(data, "nombres", "apellidos", "fecha_nacimiento", "sexo", "dpi")
        if self.db.pacientes.find_one({"dpi": data["dpi"].strip()}):
            raise ValueError(f"Ya existe un paciente con DPI {data['dpi']}")
        try:
            with self._tx() as s:
                pid = self._next_id("pacientes", s)
                doc = {
                    "id_paciente": pid,
                    "nombres": data["nombres"].strip(),
                    "apellidos": data["apellidos"].strip(),
                    "fecha_nacimiento": str(data["fecha_nacimiento"]),
                    "sexo": data["sexo"],
                    "dpi": data["dpi"].strip(),
                    "direccion": data.get("direccion") or "",
                    "telefono": data.get("telefono") or "",
                    "correo_electronico": data.get("correo_electronico") or "",
                    "tipo_sangre": data.get("tipo_sangre") or "",
                    "contacto_emergencia": {
                        "nombre": data.get("contacto_emergencia_nombre") or "",
                        "telefono": data.get("contacto_emergencia_telefono") or "",
                    },
                    "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                    "estado": "activo",
                }
                self.db.pacientes.insert_one(doc, session=s)
                self.db.historiales_clinicos.insert_one({
                    "id_historial": self._next_id("historiales_clinicos", s),
                    "id_paciente": pid,
                    "fecha_apertura": doc["fecha_registro"],
                    "fecha_ultima_actualizacion": _ahora(),
                    "estado": "activo",
                    "motivo_baja": None,
                    "total_examenes_realizados": 0,
                }, session=s)
        except DuplicateKeyError:
            raise ValueError(f"Ya existe un paciente con DPI {data['dpi']}")
        return self.get_patient(pid)

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        doc = self.db.pacientes.find_one({"id_paciente": int(patient_id)})
        return self._to_patient(doc) if doc else None

    def search_patients(self, query: str) -> List[Patient]:
        q = (query or "").strip()
        filtro: Dict[str, Any] = {}
        if q:
            import re
            patron = re.escape(q)
            ors: List[Dict[str, Any]] = [
                {"nombres": {"$regex": patron, "$options": "i"}},
                {"apellidos": {"$regex": patron, "$options": "i"}},
                {"dpi": {"$regex": f"^{patron}"}},
            ]
            if q.isdigit():
                ors.append({"id_paciente": int(q)})
            filtro = {"$or": ors}
        cursor = self.db.pacientes.find(filtro).sort([("apellidos", 1), ("nombres", 1)]).limit(200)
        return [self._to_patient(d) for d in cursor]

    def update_patient(self, patient_id: int, updates: Dict[str, Any]) -> Patient:
        cambios = {k: v for k, v in updates.items() if k in CAMPOS_EDITABLES}
        if "contacto_emergencia_nombre" in updates:
            cambios["contacto_emergencia.nombre"] = updates["contacto_emergencia_nombre"]
        if "contacto_emergencia_telefono" in updates:
            cambios["contacto_emergencia.telefono"] = updates["contacto_emergencia_telefono"]
        if not cambios:
            raise ValueError("No hay campos válidos para actualizar")
        res = self.db.pacientes.update_one({"id_paciente": int(patient_id)}, {"$set": cambios})
        if res.matched_count == 0:
            raise ValueError(f"Paciente {patient_id} no encontrado")
        self.db.historiales_clinicos.update_one(
            {"id_paciente": int(patient_id)}, {"$set": {"fecha_ultima_actualizacion": _ahora()}}
        )
        return self.get_patient(patient_id)

    def deactivate_patient(self, patient_id: int, motivo_baja: str, categoria: str = "administrativa") -> Dict[str, Any]:
        pid = int(patient_id)
        estado = self.estado_por_motivo(categoria)
        with self._tx() as s:
            # Filtro condicional: solo cambia si sigue activo (evita doble baja concurrente).
            h = self.db.historiales_clinicos.find_one_and_update(
                {"id_paciente": pid, "estado": "activo"},
                {"$set": {"estado": estado, "motivo_baja": motivo_baja, "fecha_ultima_actualizacion": _ahora()}},
                session=s,
            )
            if not h:
                if not self.db.pacientes.find_one({"id_paciente": pid}, session=s):
                    raise ValueError(f"Paciente {pid} no encontrado")
                raise ValueError("El historial ya está dado de baja")
            self.db.pacientes.update_one({"id_paciente": pid}, {"$set": {"estado": "dado_de_baja"}}, session=s)
            res = self.db.citas.update_many(
                {"id_paciente": pid, "estado_cita": "programada"}, {"$set": {"estado_cita": "cancelada"}}, session=s
            )
        return {
            "id_paciente": pid, "estado": estado, "motivo_baja": motivo_baja,
            "citas_canceladas": res.modified_count, "motor": "MongoDB",
            "mensaje": "Historial archivado" + (" en una transacción multi-documento." if self.transacciones else "."),
        }

    # ------------------------------------------------------------------
    # Citas (toma de muestra)
    # ------------------------------------------------------------------
    def create_appointment(self, data: Dict[str, Any]) -> Appointment:
        self.requerido(data, "id_paciente", "fecha_hora_programada", "motivo_consulta")
        pid = int(data["id_paciente"])
        self._exigir_activo(pid)
        with self._tx() as s:
            doc = {
                "id_cita": self._next_id("citas", s),
                "id_paciente": pid,
                "id_laboratorista": int(data.get("id_profesional") or 1),
                "fecha_hora_programada": str(data["fecha_hora_programada"]).replace("T", " "),
                "motivo_consulta": data["motivo_consulta"],
                "estado_cita": "programada",
                "fecha_creacion": _ahora(),
            }
            self.db.citas.insert_one(doc, session=s)
        return self._to_cita(doc)

    def get_appointments(self, patient_id: Optional[int] = None) -> List[Appointment]:
        filtro = {"id_paciente": int(patient_id)} if patient_id else {"estado_cita": "programada"}
        return [self._to_cita(d) for d in self.db.citas.find(filtro).sort("fecha_hora_programada", -1)]

    def _to_cita(self, d) -> Appointment:
        return Appointment(
            id_cita=d["id_cita"], id_paciente=d["id_paciente"], id_profesional=d.get("id_laboratorista", 1),
            profesional_nombre=self._laboratorista(d.get("id_laboratorista", 1)),
            fecha_hora_programada=d["fecha_hora_programada"], motivo_consulta=d["motivo_consulta"],
            estado_cita=d["estado_cita"], fecha_creacion=d.get("fecha_creacion", ""),
        )

    def _laboratorista(self, id_lab) -> str:
        doc = self.db.laboratoristas.find_one({"id_laboratorista": id_lab}, {"nombre_completo": 1})
        return doc["nombre_completo"] if doc else "Laboratorio Clínico"

    # ------------------------------------------------------------------
    # Orden de laboratorio + muestra + resultado (transacción multi-documento)
    # ------------------------------------------------------------------
    @staticmethod
    def _interpretar(p: Dict[str, Any]) -> str:
        if p.get("interpretacion_alerta"):
            return p["interpretacion_alerta"]
        valor = p.get("valor_resultado")
        vmin, vmax = p.get("rango_referencia_min"), p.get("rango_referencia_max")
        if isinstance(valor, (int, float)) and (vmin is not None or vmax is not None):
            if vmax is not None and valor > vmax:
                return "CRITICO_ALTO" if vmax and valor >= vmax * 2 else "ALTO"
            if vmin is not None and valor < vmin:
                return "CRITICO_BAJO" if vmin and valor <= vmin * 0.5 else "BAJO"
            return "NORMAL"
        ref = (p.get("valor_referencia_cualitativo") or "").strip().lower()
        if ref and str(valor).strip().lower() != ref:
            return "POSITIVO" if ref in ("negativo", "ninguno") else "ALTO"
        return "NEGATIVO" if ref == "negativo" else "NORMAL"

    def _parametros(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        salida = []
        for p in data.get("parametros") or []:
            if not p.get("nombre_parametro") or p.get("valor_resultado") in (None, ""):
                continue
            valor = p["valor_resultado"]
            try:
                valor = float(valor)
            except (TypeError, ValueError):
                valor = str(valor)
            par = {
                "nombre_parametro": p["nombre_parametro"],
                "valor_resultado": valor,
                "unidad_medida": p.get("unidad_medida") or "",
                "rango_referencia_min": self._f(p.get("rango_referencia_min")),
                "rango_referencia_max": self._f(p.get("rango_referencia_max")),
                "valor_referencia_cualitativo": p.get("valor_referencia_cualitativo") or None,
            }
            par["interpretacion_alerta"] = self._interpretar({**par, "interpretacion_alerta": p.get("interpretacion_alerta")})
            salida.append(par)
        return salida

    def register_consultation(self, data: Dict[str, Any]) -> Consultation:
        self.requerido(data, "id_paciente", "motivo", "codigo_examen")
        if self.recetas_del_payload(data):
            raise ValueError("El laboratorio clínico no emite recetas")
        pid = int(data["id_paciente"])
        tipo = self.db.tipos_examen.find_one({"codigo": data["codigo_examen"]})
        if not tipo:
            raise ValueError(f"Tipo de examen desconocido: {data['codigo_examen']}")
        parametros = self._parametros(data)
        if not parametros:
            raise ValueError("Ingrese al menos un parámetro con su resultado")
        id_lab = int(data.get("id_profesional") or 1)

        with self._tx() as s:
            h = self.db.historiales_clinicos.find_one({"id_paciente": pid}, session=s)
            if not h:
                raise ValueError(f"Paciente {pid} no encontrado")
            if h["estado"] != "activo":
                raise ValueError(f"El historial está '{h['estado']}' y no admite nuevos registros")

            id_cita = data.get("id_cita")
            if id_cita:
                upd = self.db.citas.update_one(
                    {"id_cita": int(id_cita), "id_paciente": pid, "estado_cita": "programada"},
                    {"$set": {"estado_cita": "atendida"}}, session=s,
                )
                if upd.modified_count == 0:
                    raise ValueError("La cita no existe, no es de este paciente o ya fue atendida")

            id_orden = self._next_id("ordenes", s)
            orden = {
                "id_orden": id_orden,
                "id_paciente": pid,
                "id_cita": int(id_cita) if id_cita else None,
                "id_medico_solicitante": int(data.get("id_medico_solicitante") or 1),
                "id_laboratorista": id_lab,
                "fecha_hora_ingreso": _ahora(),
                "prioridad": data.get("tipo_consulta") if data.get("tipo_consulta") in ("normal", "urgente", "emergencia") else "normal",
                "motivo": data["motivo"],
                "codigo_cie10": (data.get("codigo_cie10") or "").upper() or None,
                "diagnostico_presuntivo": data.get("descripcion_diagnostico") or data["motivo"],
                "estado_orden": "completada",
                "observaciones": data.get("notas_clinicas") or "",
            }
            self.db.ordenes.insert_one(orden, session=s)

            id_muestra = self._next_id("muestras", s)
            self.db.muestras.insert_one({
                "id_muestra": id_muestra,
                "id_orden": id_orden,
                "tipo_muestra": data.get("tipo_muestra") or "No especificada",
                "codigo_etiqueta_barras": f"LAB-{datetime.now().year}-{id_orden:06d}",
                "fecha_hora_toma": _ahora(),
                "condicion_muestra": data.get("condicion_muestra") or "Adecuada",
                "estado": "procesada",
            }, session=s)

            self.db.resultados.insert_one({
                "id_resultado": self._next_id("resultados", s),
                "id_orden": id_orden,
                "id_paciente": pid,
                "codigo_examen": tipo["codigo"],
                "nombre_examen": tipo["nombre_examen"],
                "id_laboratorista_analista": id_lab,
                "id_laboratorista_validador": id_lab,
                "fecha_hora_analisis": _ahora(),
                "fecha_hora_validacion": _ahora(),
                "estado": "validado",
                "alertas_criticas": any(p["interpretacion_alerta"].startswith("CRITICO") for p in parametros),
                "observaciones_tecnicas": data.get("observaciones_tecnicas") or "",
                "conclusiones_diagnosticas": data.get("conclusiones_diagnosticas") or "",
                "parametros": parametros,
            }, session=s)

            self.db.historiales_clinicos.update_one(
                {"id_paciente": pid},
                {"$set": {"fecha_ultima_actualizacion": _ahora()}, "$inc": {"total_examenes_realizados": 1}},
                session=s,
            )

        return self._consultas({"id_orden": id_orden})[0]

    def _exigir_activo(self, pid: int) -> None:
        h = self.db.historiales_clinicos.find_one({"id_paciente": pid})
        if not h:
            raise ValueError(f"Paciente {pid} no encontrado")
        if h["estado"] != "activo":
            raise ValueError(f"El historial está '{h['estado']}' y no admite nuevos registros")

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    def get_clinical_history(self, patient_id: int, user_role: UserRole = UserRole.MEDICO) -> Optional[UnifiedClinicalRecord]:
        pid = int(patient_id)
        doc = self.db.pacientes.find_one({"id_paciente": pid})
        if not doc:
            return None
        h = self.db.historiales_clinicos.find_one({"id_paciente": pid}) or {}
        consultas = self._consultas({"id_paciente": pid})
        record = UnifiedClinicalRecord(
            id_historial=h.get("id_historial", 0), id_paciente=pid, paciente=self._to_patient(doc),
            fecha_apertura=h.get("fecha_apertura"), fecha_ultima_actualizacion=h.get("fecha_ultima_actualizacion"),
            estado=h.get("estado", "activo"), motivo_baja=h.get("motivo_baja"),
            institucion=InstitutionType.LABORATORIO_CLINICO, motor=DatabaseEngine.MONGODB,
            consultas=consultas, citas=self.get_appointments(pid),
            datos_adicionales={
                "total_examenes": h.get("total_examenes_realizados", 0),
                "alertas_criticas": sum(1 for c in consultas for e in c.examenes_laboratorio if e.alertas_criticas),
            },
        )
        return self.apply_security_filter(record, user_role)

    def _consultas(self, filtro: Dict[str, Any]) -> List[Consultation]:
        ordenes = list(self.db.ordenes.find(filtro).sort("fecha_hora_ingreso", -1))
        if not ordenes:
            return []
        ids = [o["id_orden"] for o in ordenes]
        resultados: Dict[int, List[Dict[str, Any]]] = {}
        for r in self.db.resultados.find({"id_orden": {"$in": ids}}):
            resultados.setdefault(r["id_orden"], []).append(r)
        nombres = {d["id_laboratorista"]: d["nombre_completo"] for d in self.db.laboratoristas.find()}

        salida = []
        for o in ordenes:
            examenes = [
                LabExamResult(
                    id_resultado=r["id_resultado"], id_orden=r["id_orden"], codigo_examen=r["codigo_examen"],
                    nombre_examen=r.get("nombre_examen", r["codigo_examen"]),
                    fecha_hora_analisis=r.get("fecha_hora_analisis", ""),
                    fecha_hora_validacion=r.get("fecha_hora_validacion"), estado=r["estado"],
                    alertas_criticas=r.get("alertas_criticas", False),
                    observaciones_tecnicas=r.get("observaciones_tecnicas", ""),
                    conclusiones_diagnosticas=r.get("conclusiones_diagnosticas", ""),
                    parametros=[
                        LabParameter(
                            nombre_parametro=p["nombre_parametro"], valor_resultado=p["valor_resultado"],
                            unidad_medida=p.get("unidad_medida", ""),
                            rango_referencia_min=p.get("rango_referencia_min"),
                            rango_referencia_max=p.get("rango_referencia_max"),
                            valor_referencia_cualitativo=p.get("valor_referencia_cualitativo"),
                            interpretacion_alerta=p.get("interpretacion_alerta", "NORMAL"),
                        )
                        for p in r.get("parametros", [])
                    ],
                )
                for r in resultados.get(o["id_orden"], [])
            ]
            salida.append(Consultation(
                id_consulta=o["id_orden"], id_cita=o.get("id_cita") or 0,
                fecha_hora_atencion=str(o.get("fecha_hora_ingreso", "")).replace("T", " ").replace("Z", "")[:16],
                motivo=o.get("motivo") or o.get("diagnostico_presuntivo", "Orden de laboratorio"),
                notas_clinicas=o.get("observaciones"), tipo_consulta=o.get("prioridad", "normal"),
                profesional_nombre=nombres.get(o.get("id_laboratorista", 1), "Laboratorio Clínico"),
                diagnosticos=[Diagnosis(
                    id_diagnostico=o["id_orden"], codigo_cie10=o.get("codigo_cie10") or "",
                    descripcion=o.get("diagnostico_presuntivo", ""), tipo="presuntivo",
                )] if o.get("diagnostico_presuntivo") else [],
                examenes_laboratorio=examenes,
            ))
        return salida

    def get_specialized_records(self, patient_id: int) -> Dict[str, Any]:
        resultados = list(self.db.resultados.find(
            {"id_paciente": int(patient_id)}, {"_id": 0}
        ).sort("fecha_hora_analisis", -1))
        return {"institucion": "Laboratorio Clínico", "motor": "MongoDB", "resultados": resultados}

    def get_catalogs(self) -> Dict[str, Any]:
        return {"tipos_examen": list(self.db.tipos_examen.find({}, {"_id": 0}).sort("codigo", 1))}

    def _to_patient(self, d) -> Patient:
        ce = d.get("contacto_emergencia") or {}
        return Patient(
            id_paciente=d["id_paciente"], nombres=d["nombres"], apellidos=d["apellidos"],
            fecha_nacimiento=d["fecha_nacimiento"], sexo=d["sexo"], dpi=d["dpi"],
            direccion=d.get("direccion", ""), telefono=d.get("telefono", ""),
            correo_electronico=d.get("correo_electronico", ""),
            contacto_emergencia_nombre=ce.get("nombre", ""), contacto_emergencia_telefono=ce.get("telefono", ""),
            fecha_registro=d.get("fecha_registro", ""), estado=d.get("estado", "activo"),
            tipo_sangre=d.get("tipo_sangre") or None,
        )
