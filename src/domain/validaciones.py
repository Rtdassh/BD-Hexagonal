"""
Reglas de formato de los datos (dominio).

Son las mismas para los cuatro motores: los servicios las aplican antes de llamar
al adaptador, así PostgreSQL, MySQL, MongoDB y Firestore reciben datos ya limpios.
Las bases de datos repiten las más importantes como restricciones propias
(CHECK, $jsonSchema, reglas de Firestore) por si alguien escribe sin pasar por la app.

Cada función:
  * normaliza (recorta espacios, mayúsculas en códigos, teléfono como ####-####)
  * y lanza ValueError con un mensaje que el usuario entiende.
"""

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

LETRAS = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .\-]+$")
DPI = re.compile(r"^\d{13}$")
TELEFONO = re.compile(r"^([2-7]\d{3})-?(\d{4})$")
CORREO = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
CIE10 = re.compile(r"^[A-Z]\d{2}(\.[0-9A-Z]{1,4})?$")
PRESION = re.compile(r"^(\d{2,3})/(\d{2,3})$")
COLEGIADO = re.compile(r"^[A-Z0-9\-]{3,20}$")
LOTE = re.compile(r"^[A-Za-z0-9\-]{3,30}$")
DOSIS = re.compile(r"^\d+([.,]\d+)?\s?[A-Za-zµÁÉÍÓÚáéíóúñ/%]+(\s[A-Za-zÁÉÍÓÚáéíóúñ/]+)*$")

# Piezas dentales válidas (notación FDI): permanentes 11-48 y temporales 51-85
PIEZAS_FDI = {c * 10 + n for c in (1, 2, 3, 4) for n in range(1, 9)} | {c * 10 + n for c in (5, 6, 7, 8) for n in range(1, 6)}


def _txt(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def texto(data: Dict[str, Any], campo: str, etiqueta: str, maximo: int, minimo: int = 0,
          req: bool = False, patron: Optional[re.Pattern] = None, msg_patron: str = "") -> Optional[str]:
    """Valida un campo de texto y lo deja normalizado en data."""
    if campo not in data:
        if req:
            raise ValueError(f"{etiqueta} es obligatorio")
        return None
    v = _txt(data[campo])
    if not v:
        if req:
            raise ValueError(f"{etiqueta} es obligatorio")
        data[campo] = None   # vacío se guarda como NULL, no como texto vacío
        return None
    if len(v) < minimo:
        raise ValueError(f"{etiqueta} debe tener al menos {minimo} caracteres")
    if len(v) > maximo:
        raise ValueError(f"{etiqueta} admite como máximo {maximo} caracteres")
    if patron and not patron.match(v):
        raise ValueError(f"{etiqueta}: {msg_patron}")
    data[campo] = v
    return v


def numero(data: Dict[str, Any], campo: str, etiqueta: str, minimo: float, maximo: float,
           req: bool = False, entero: bool = False) -> Optional[float]:
    v = data.get(campo)
    if v in (None, ""):
        if req:
            raise ValueError(f"{etiqueta} es obligatorio")
        if campo in data:
            data.pop(campo)      # vacío = no informado (cada adaptador usa su valor por defecto)
        return None
    try:
        n = float(str(v).replace(",", "."))
    except ValueError:
        raise ValueError(f"{etiqueta} debe ser un número")
    if entero and n != int(n):
        raise ValueError(f"{etiqueta} debe ser un número entero")
    if not minimo <= n <= maximo:
        raise ValueError(f"{etiqueta} debe estar entre {_fmt(minimo)} y {_fmt(maximo)}")
    data[campo] = int(n) if entero else n
    return n


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else str(n)


def nombre(data, campo, etiqueta, maximo=50, req=False):
    return texto(data, campo, etiqueta, maximo, 2, req, LETRAS, "use solo letras, espacios, punto, apóstrofo o guion")


def dpi(data, campo, etiqueta="DPI", req=False):
    v = texto(data, campo, etiqueta, 20, 0, req)
    if v is None:
        return None
    v = v.replace(" ", "").replace("-", "")
    if not DPI.match(v):
        raise ValueError(f"{etiqueta} debe tener exactamente 13 dígitos")
    depto, muni = int(v[9:11]), int(v[11:13])
    if not 1 <= depto <= 22:
        raise ValueError(f"{etiqueta}: los dígitos 10 y 11 son el departamento (01 a 22)")
    if not 1 <= muni <= 35:
        raise ValueError(f"{etiqueta}: los dos últimos dígitos son el municipio (01 en adelante)")
    data[campo] = v
    return v


def telefono(data, campo, etiqueta="Teléfono", req=False):
    v = texto(data, campo, etiqueta, 9, 0, req)
    if v is None:
        return None
    m = TELEFONO.match(v.replace(" ", ""))
    if not m:
        raise ValueError(f"{etiqueta}: 8 dígitos de Guatemala, empieza con 2 a 7 (ej. 5841-7501)")
    data[campo] = f"{m.group(1)}-{m.group(2)}"
    return data[campo]


def correo(data, campo="correo_electronico"):
    v = texto(data, campo, "Correo", 80, 6, False, CORREO, "escriba un correo válido (ej. nombre@dominio.com)")
    if v:
        data[campo] = v.lower()
    return v


def fecha(data, campo, etiqueta, req=False, pasada=False, futura=False, max_anios=None) -> Optional[date]:
    v = data.get(campo)
    if v in (None, ""):
        if req:
            raise ValueError(f"{etiqueta} es obligatoria")
        return None
    try:
        f = date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ValueError(f"{etiqueta} no es una fecha válida")
    hoy = date.today()
    if pasada and f > hoy:
        raise ValueError(f"{etiqueta} no puede ser una fecha futura")
    if futura and f < hoy:
        raise ValueError(f"{etiqueta} no puede ser una fecha pasada")
    if max_anios and f < hoy.replace(year=hoy.year - max_anios):
        raise ValueError(f"{etiqueta} no puede ser de hace más de {max_anios} años")
    return f


def fecha_hora(data, campo, etiqueta, req=True, tolerancia_min=0, max_dias=None) -> Optional[datetime]:
    """Fecha y hora que no puede quedar en el pasado (con tolerancia en minutos)."""
    v = data.get(campo)
    if v in (None, ""):
        if req:
            raise ValueError(f"{etiqueta} es obligatoria")
        return None
    try:
        f = datetime.fromisoformat(str(v).replace("T", " ")[:16])
    except ValueError:
        raise ValueError(f"{etiqueta} no es una fecha y hora válida")
    ahora = datetime.now()
    if f < ahora - timedelta(minutes=tolerancia_min):
        raise ValueError(f"{etiqueta} no puede quedar en el pasado")
    if max_dias and f > ahora + timedelta(days=max_dias):
        raise ValueError(f"{etiqueta} no puede ser a más de {max_dias} días")
    return f


# ---------------------------------------------------------------------------
# Reglas por formulario
# ---------------------------------------------------------------------------
def validar_paciente(data: Dict[str, Any], institucion: str, nuevo: bool = True) -> Dict[str, Any]:
    ped = institucion == "pediatrico"
    oblig = lambda c: nuevo or c in data   # al editar, lo obligatorio que se envía no puede quedar vacío
    nombre(data, "nombres", "Nombres", 50, req=oblig("nombres"))
    nombre(data, "apellidos", "Apellidos", 50, req=oblig("apellidos"))
    if nuevo or "dpi" in data:
        dpi(data, "dpi", "CUI" if ped else "DPI", req=nuevo)
    nac = fecha(data, "fecha_nacimiento", "Fecha de nacimiento", req=oblig("fecha_nacimiento"), pasada=True, max_anios=120)
    if ped and nac and nac < date.today().replace(year=date.today().year - 18):
        raise ValueError("El Centro Pediátrico atiende a menores de 18 años")
    if "sexo" in data and data["sexo"] not in ("M", "F"):
        raise ValueError("Sexo inválido: use M o F")
    if data.get("tipo_sangre") and data["tipo_sangre"] not in ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"):
        raise ValueError("Tipo de sangre inválido")
    texto(data, "direccion", "Dirección", 200, 5)
    telefono(data, "telefono")
    correo(data)
    nombre(data, "contacto_emergencia_nombre", "Nombre del contacto de emergencia", 100)
    telefono(data, "contacto_emergencia_telefono", "Teléfono de emergencia")
    if data.get("contacto_emergencia_nombre") and not data.get("contacto_emergencia_telefono"):
        raise ValueError("Indique el teléfono del contacto de emergencia")
    if ped:
        nombre(data, "nombre_tutor", "Nombre del tutor", 100, req=oblig("nombre_tutor"))
        nombre(data, "parentesco_tutor", "Parentesco", 30, req=oblig("parentesco_tutor"))
        dpi(data, "dpi_tutor", "DPI del tutor", req=oblig("dpi_tutor"))
        telefono(data, "telefono_tutor", "Teléfono del tutor", req=oblig("telefono_tutor"))
        numero(data, "semanas_gestacion", "Semanas de gestación", 20, 45, entero=True)
        numero(data, "peso_nacer_kg", "Peso al nacer", 0.3, 7)
        numero(data, "talla_nacer_cm", "Talla al nacer", 20, 65)
    return data


def validar_cita(data: Dict[str, Any]) -> Dict[str, Any]:
    fecha_hora(data, "fecha_hora_programada", "La fecha de la cita", tolerancia_min=5, max_dias=365)
    texto(data, "motivo_consulta", "Motivo", 200, 3, req=True)
    return data


def validar_consulta(data: Dict[str, Any], institucion: str) -> Dict[str, Any]:
    texto(data, "motivo", "Motivo", 200, 3, req=True)
    pa = texto(data, "presion_arterial", "Presión arterial", 7, 0, False, PRESION, "use el formato 120/80")
    if pa:
        s, d = (int(x) for x in PRESION.match(pa).groups())
        if not (60 <= s <= 260 and 30 <= d <= 160 and s > d):
            raise ValueError("Presión arterial fuera de rango: sistólica 60–260, diastólica 30–160 y mayor la sistólica")
    numero(data, "temperatura", "Temperatura", 30, 45)
    numero(data, "pulso", "Pulso", 20, 250, entero=True)
    if institucion == "pediatrico":
        numero(data, "peso_kg", "Peso", 0.3, 150, req=True)
        numero(data, "talla_cm", "Talla", 20, 200, req=True)
        numero(data, "perimetro_cefalico_cm", "Perímetro cefálico", 20, 70)
        numero(data, "percentil_crecimiento", "Percentil", 0, 100)
        texto(data, "nombre_vacuna", "Vacuna", 100, 2)
        if data.get("nombre_vacuna"):
            texto(data, "dosis_vacuna", "Dosis de la vacuna", 30, 1, req=True)
            texto(data, "lote_vacuna", "Lote", 30, 3, True, LOTE, "use letras, números o guion")
            fecha(data, "proxima_fecha_refuerzo", "Próximo refuerzo", futura=True)
    cie = data.get("codigo_cie10")
    if cie:
        data["codigo_cie10"] = str(cie).strip().upper()
    texto(data, "codigo_cie10", "Código CIE-10", 8, 0, False, CIE10, "use letra + 2 números y decimal opcional (ej. K80.0)")
    texto(data, "descripcion_diagnostico", "Descripción del diagnóstico", 300, 3)
    texto(data, "descripcion_tratamiento", "Tratamiento", 300, 3)
    texto(data, "indicaciones_tratamiento", "Indicaciones", 500)
    texto(data, "notas_clinicas", "Notas clínicas", 2000)
    texto(data, "motivo_hospitalizacion", "Motivo de ingreso", 200, 3)

    for i, r in enumerate(data.get("recetas") or [], 1):
        e = f"Medicamento {i}"
        texto(r, "medicamento", f"{e}: nombre", 100, 2, req=True)
        texto(r, "presentacion", f"{e}: presentación", 50)
        texto(r, "dosis", f"{e}: dosis", 50)
        texto(r, "frecuencia", f"{e}: frecuencia", 50)
        numero(r, "duracion_dias", f"{e}: días", 1, 90, entero=True)
        numero(r, "dosis_mg_kg", f"{e}: dosis mg/kg", 0.01, 100)
        numero(r, "concentracion_mg_ml", f"{e}: concentración", 0.1, 1000)

    for i, p in enumerate(data.get("procedimientos") or [], 1):
        e = f"Procedimiento {i}"
        pieza = p.get("pieza_dental")
        if pieza not in (None, ""):
            try:
                pieza = int(pieza)
            except ValueError:
                raise ValueError(f"{e}: la pieza debe ser un número FDI (11–48 o 51–85)")
            if pieza not in PIEZAS_FDI:
                raise ValueError(f"{e}: la pieza {pieza} no existe en la notación FDI (11–48 o 51–85)")
            p["pieza_dental"] = pieza
        numero(p, "costo", f"{e}: costo", 0, 50000)
        texto(p, "observaciones", f"{e}: observaciones", 200)

    for i, p in enumerate(data.get("parametros") or [], 1):
        e = f"Parámetro {i}"
        texto(p, "nombre_parametro", f"{e}: nombre", 60, 2, req=True)
        texto(p, "valor_resultado", f"{e}: resultado", 40)
        texto(p, "unidad_medida", f"{e}: unidad", 20)
        mn = numero(p, "rango_referencia_min", f"{e}: mínimo", -1e6, 1e6)
        mx = numero(p, "rango_referencia_max", f"{e}: máximo", -1e6, 1e6)
        if mn is not None and mx is not None and mn > mx:
            raise ValueError(f"{e}: el mínimo de referencia no puede ser mayor que el máximo")
    texto(data, "tipo_muestra", "Muestra", 60)
    texto(data, "conclusiones_diagnosticas", "Conclusiones", 1000)
    texto(data, "observaciones_tecnicas", "Observaciones técnicas", 300)
    return data


def validar_profesional(data: Dict[str, Any], nuevo: bool = True) -> Dict[str, Any]:
    nombre(data, "nombre_completo", "Nombre completo", 100, req=nuevo or "nombre_completo" in data)
    if data.get("numero_colegiado"):
        data["numero_colegiado"] = str(data["numero_colegiado"]).strip().upper()
    texto(data, "numero_colegiado", "Número de colegiado", 20, 3, nuevo, COLEGIADO, "use letras, números o guion (ej. COL-12450)")
    nombre(data, "especialidad", "Especialidad", 80)
    telefono(data, "telefono")
    correo(data)
    return data


def validar_cirugia(data: Dict[str, Any]) -> Dict[str, Any]:
    texto(data, "procedimiento", "Procedimiento", 200, 3, req=True)
    tolerancia = 30 if data.get("tipo") == "urgencia" else 0
    fecha_hora(data, "fecha_hora_programada", "La fecha de la cirugía", tolerancia_min=tolerancia, max_dias=365)
    numero(data, "duracion_estimada_min", "Duración", 15, 720, req=True, entero=True)
    texto(data, "notas_operatorias", "Indicaciones prequirúrgicas", 1000)
    return data


def validar_orden_medicacion(data: Dict[str, Any]) -> Dict[str, Any]:
    texto(data, "dosis", "Dosis", 50, 2, True, DOSIS, "cantidad y unidad (ej. 500 mg, 1 g, 2 tabletas)")
    numero(data, "frecuencia_horas", "Frecuencia", 1, 72, req=True, entero=True)
    numero(data, "duracion_dias", "Duración", 1, 30, entero=True)
    if data.get("fecha_inicio"):
        fecha_hora(data, "fecha_inicio", "La primera dosis", tolerancia_min=60, max_dias=30)
    texto(data, "indicaciones", "Indicaciones", 200)
    return data


def motivo(valor: Any, etiqueta: str = "El motivo", maximo: int = 200) -> str:
    v = _txt(valor)
    if len(v) < 5:
        raise ValueError(f"{etiqueta} debe tener al menos 5 caracteres")
    if len(v) > maximo:
        raise ValueError(f"{etiqueta} admite como máximo {maximo} caracteres")
    return v


HABITACION = re.compile(r"^[A-Z]{2,4}-\d{2,3}$")
TIPOS_HABITACION = ("individual", "compartida", "aislamiento", "intensivo")


def validar_departamento(data: Dict[str, Any]) -> Dict[str, Any]:
    texto(data, "nombre", "Nombre del departamento", 80, 3, True, LETRAS, "use solo letras y espacios")
    numero(data, "piso", "Piso", 0, 20, req=True, entero=True)
    texto(data, "extension", "Extensión", 5, 2, False, re.compile(r"^\d{2,5}$"), "de 2 a 5 dígitos")
    return data


def validar_habitacion(data: Dict[str, Any], nueva: bool = True) -> Dict[str, Any]:
    if nueva:
        data["codigo"] = _txt(data.get("codigo")).upper()
        texto(data, "codigo", "Código", 8, 5, True, HABITACION, "2 a 4 letras, guion y 2 o 3 números (ej. MI-104)")
    numero(data, "camas", "Camas", 1, 6, req=nueva, entero=True)
    if data.get("tipo") and data["tipo"] not in TIPOS_HABITACION:
        raise ValueError("Tipo de habitación inválido")
    if data.get("estado") and data["estado"] not in ("disponible", "mantenimiento"):
        raise ValueError("Estado inválido: disponible o mantenimiento")
    return data


def validar_orden_laboratorio(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("examenes"):
        raise ValueError("Elija al menos un examen")
    if len(data["examenes"]) > 15:
        raise ValueError("Una orden admite como máximo 15 exámenes")
    texto(data, "medico_solicitante", "Médico solicitante", 100, 3)
    if data.get("prioridad") and data["prioridad"] not in ("normal", "urgente"):
        raise ValueError("Prioridad inválida: normal o urgente")
    texto(data, "diagnostico_presuntivo", "Diagnóstico presuntivo", 200, 3)
    if data.get("codigo_cie10"):
        data["codigo_cie10"] = str(data["codigo_cie10"]).strip().upper()
    texto(data, "codigo_cie10", "Código CIE-10", 8, 0, False, CIE10, "use letra + 2 números y decimal opcional (ej. E11.9)")
    texto(data, "observaciones", "Observaciones", 300)
    if data.get("fecha_toma"):
        fecha_hora(data, "fecha_toma", "La toma de muestra", tolerancia_min=5, max_dias=90)
    return data


# ----------------------------------------------------------------------------
# Validaciones específicas Centro Médico Pediátrico
# ----------------------------------------------------------------------------
def validar_antecedente_perinatal(data: Dict[str, Any]) -> Dict[str, Any]:
    numero(data, "semanas_gestacion", "Semanas de gestación", 20, 45, req=True, entero=True)
    numero(data, "peso_nacer_kg", "Peso al nacer", 0.3, 7.0, req=True)
    numero(data, "talla_nacer_cm", "Talla al nacer", 20.0, 65.0, req=True)
    numero(data, "perimetro_cefalico_nacer_cm", "Perímetro cefálico al nacer", 20.0, 55.0, req=False)
    numero(data, "apgar_1min", "Apgar a 1 min", 0, 10, req=False, entero=True)
    numero(data, "apgar_5min", "Apgar a 5 min", 0, 10, req=False, entero=True)
    texto(data, "complicaciones_neonatales", "Complicaciones", 500, 0, False)
    return data


def validar_somatometria_pediatrica(data: Dict[str, Any]) -> Dict[str, Any]:
    numero(data, "peso_kg", "Peso", 0.3, 150.0, req=True)
    numero(data, "talla_cm", "Talla", 20.0, 200.0, req=True)
    numero(data, "perimetro_cefalico_cm", "Perímetro cefálico", 20.0, 70.0, req=False)
    numero(data, "percentil_crecimiento", "Percentil", 0.0, 100.0, req=False)
    return data


def validar_lote_vacuna(data: Dict[str, Any]) -> Dict[str, Any]:
    if "fecha_fabricacion" not in data or not data["fecha_fabricacion"]:
        data["fecha_fabricacion"] = date.today().isoformat()
    if "stock_disponible" not in data and "dosis_disponibles" in data:
        data["stock_disponible"] = data["dosis_disponibles"]
    if "dosis_disponibles" not in data and "stock_disponible" in data:
        data["dosis_disponibles"] = data["stock_disponible"]
    texto(data, "numero_lote", "Número de lote", 40, 2, True)
    texto(data, "fabricante", "Fabricante", 100, 2, True)
    fecha(data, "fecha_fabricacion", "Fecha de fabricación", req=True, pasada=True)
    fecha(data, "fecha_vencimiento", "Fecha de vencimiento", req=True, futura=True)
    numero(data, "stock_disponible", "Stock disponible", 0, 100000, req=True, entero=True)
    t_min = numero(data, "temp_min_celsius", "Temperatura mínima", -50.0, 50.0, req=True)
    t_max = numero(data, "temp_max_celsius", "Temperatura máxima", -50.0, 50.0, req=True)
    if t_min >= t_max:
        raise ValueError("La temperatura mínima de conservación debe ser menor que la máxima")
    return data


# ----------------------------------------------------------------------------
# Validaciones específicas Clínica Odontológica
# ----------------------------------------------------------------------------
CARAS_DENTALES_VALIDAS = {"O", "M", "D", "V", "L", "P", "O/I", "GENERAL"}


def validar_antecedente_sistemico_dental(data: Dict[str, Any]) -> Dict[str, Any]:
    texto(data, "medicamentos_actuales", "Medicamentos actuales", 500, 0, False)
    texto(data, "observaciones_medicas", "Observaciones médicas", 500, 0, False)
    return data


def validar_hallazgo_odontograma(data: Dict[str, Any]) -> Dict[str, Any]:
    fdi = numero(data, "codigo_fdi", "Pieza dental (FDI)", 11, 85, req=True, entero=True)
    if int(fdi) not in PIEZAS_FDI:
        raise ValueError(f"Pieza dental {int(fdi)} no es válida en notación FDI (11-48 permanentes, 51-85 temporales)")
    data["cara"] = validar_cara_dental(data.get("cara", "O"))
    texto(data, "hallazgo", "Hallazgo o diagnóstico", 80, 2, True)
    color = _txt(data.get("color_hex"))
    if color and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        raise ValueError("Color de simbología inválido (use el formato #RRGGBB)")
    validar_estado_hallazgo(data.get("estado") or "activo")
    data["estado"] = data.get("estado") or "activo"
    sev = _txt(data.get("severidad")).lower()
    if sev and sev not in SEVERIDADES_HALLAZGO:
        raise ValueError(f"Severidad inválida. Use: {', '.join(SEVERIDADES_HALLAZGO)}")
    data["severidad"] = sev or None
    texto(data, "notas", "Notas específicas", 255, 0, False)
    return data


ESTADOS_HALLAZGO = ("activo", "tratado", "en_observacion")
SEVERIDADES_HALLAZGO = ("leve", "moderada", "severa")
_ALIAS_CARAS = {"GENERAL": "G", "O/I": "O", "I": "O", "P": "L"}


def validar_cara_dental(valor: Any) -> str:
    cara = _ALIAS_CARAS.get(_txt(valor).upper(), _txt(valor).upper())
    if cara not in ("O", "V", "L", "M", "D", "G"):
        raise ValueError(f"Cara dental inválida ({valor}). Use O, V, L, M, D o G (toda la pieza)")
    return cara


def validar_estado_hallazgo(estado: Any) -> str:
    if estado not in ESTADOS_HALLAZGO:
        raise ValueError(f"Estado del hallazgo inválido. Use: {', '.join(ESTADOS_HALLAZGO)}")
    return estado


def validar_plan_tratamiento(data: Dict[str, Any]) -> Dict[str, Any]:
    if "titulo" not in data and "diagnostico_general" in data:
        data["titulo"] = data["diagnostico_general"]
    if "diagnostico_general" not in data and "titulo" in data:
        data["diagnostico_general"] = data["titulo"]
    texto(data, "titulo", "Título del plan de tratamiento", 120, 3, True)
    numero(data, "costo_total_estimado", "Costo total estimado", 0.0, 500000.0, req=True)
    return data


def validar_pago_dental(data: Dict[str, Any]) -> Dict[str, Any]:
    if "monto_abonado" not in data and "monto" in data:
        data["monto_abonado"] = data["monto"]
    if "monto" not in data and "monto_abonado" in data:
        data["monto"] = data["monto_abonado"]
    numero(data, "monto_abonado", "Monto abonado", 0.5, 100000.0, req=True)
    texto(data, "numero_recibo", "Número de recibo", 30, 2, True)
    metodos_map = {
        "efectivo": "Efectivo",
        "tarjeta": "Tarjeta de Crédito/Débito",
        "tarjeta_credito": "Tarjeta de Crédito/Débito",
        "tarjeta_debito": "Tarjeta de Crédito/Débito",
        "transferencia": "Transferencia bancaria",
        "transferencia_bancaria": "Transferencia bancaria"
    }
    raw_m = str(data.get("metodo_pago", "Efectivo")).strip()
    metodo = metodos_map.get(raw_m.lower(), raw_m)
    data["metodo_pago"] = metodo
    return data


# ----------------------------------------------------------------------------
# Caja
# ----------------------------------------------------------------------------
METODOS_PAGO = ("efectivo", "tarjeta", "transferencia", "cheque")
CATEGORIAS_ARANCEL = ("consulta", "hospitalizacion", "cirugia", "medicamento", "procedimiento", "vacunacion", "examen", "otro")


def nit_valido(nit: str) -> bool:
    """NIT de Guatemala: números + dígito verificador (módulo 11; 10 se escribe K)."""
    n = nit.replace("-", "").upper()
    if not re.match(r"^\d{1,12}[\dK]$", n):
        return False
    cuerpo, dv = n[:-1], n[-1]
    suma = sum(int(d) * peso for d, peso in zip(reversed(cuerpo), range(2, 2 + len(cuerpo))))
    esperado = (11 - suma % 11) % 11
    return dv == ("K" if esperado == 10 else str(esperado))


def validar_nit(data: Dict[str, Any]) -> None:
    nit = _txt(data.get("nit")).upper().replace(" ", "") or "CF"
    if nit not in ("CF", "C/F") and not nit_valido(nit):
        raise ValueError("NIT inválido: el dígito verificador no coincide (use CF si es consumidor final)")
    data["nit"] = "CF" if nit in ("CF", "C/F") else nit


def validar_factura(data: Dict[str, Any]) -> Dict[str, Any]:
    validar_nit(data)
    texto(data, "nombre_facturacion", "Nombre de facturación", 120, 3)
    lineas = [dict(l) for l in (data.get("lineas") or []) if (l or {}).get("concepto")]
    if not lineas:
        raise ValueError("Agregue al menos un cargo a la factura")
    if len(lineas) > 30:
        raise ValueError("Una factura admite como máximo 30 líneas")
    for i, l in enumerate(lineas, 1):
        texto(l, "concepto", f"Línea {i}: concepto", 150, 2, req=True)
        numero(l, "cantidad", f"Línea {i}: cantidad", 0.01, 1000, req=True)
        numero(l, "precio_unitario", f"Línea {i}: precio", 0, 100000, req=True)
        l["precio_unitario"] = round(l["precio_unitario"], 2)
    data["lineas"] = lineas
    if sum(l["cantidad"] * l["precio_unitario"] for l in lineas) <= 0:
        raise ValueError("El total de la factura debe ser mayor que cero")
    return data


def validar_pago(data: Dict[str, Any]) -> Dict[str, Any]:
    numero(data, "monto", "Monto", 0.01, 1000000, req=True)
    data["monto"] = round(data["monto"], 2)
    metodo = _txt(data.get("metodo_pago")).lower()
    if metodo not in METODOS_PAGO:
        raise ValueError("Método de pago inválido: efectivo, tarjeta, transferencia o cheque")
    data["metodo_pago"] = metodo
    texto(data, "referencia", "Referencia", 40, 3, req=metodo != "efectivo")
    return data


def validar_arancel(data: Dict[str, Any]) -> Dict[str, Any]:
    data["codigo"] = _txt(data.get("codigo")).upper()
    texto(data, "codigo", "Código", 15, 3, True, re.compile(r"^[A-Z0-9-]{3,15}$"), "mayúsculas, números y guion")
    texto(data, "descripcion", "Descripción", 120, 3, req=True)
    if data.get("categoria") not in CATEGORIAS_ARANCEL:
        raise ValueError("Categoría inválida")
    numero(data, "precio", "Precio", 0, 100000, req=True)
    data["precio"] = round(data["precio"], 2)
    data["activo"] = data.get("activo") not in (False, "0", "false", 0)
    return data
