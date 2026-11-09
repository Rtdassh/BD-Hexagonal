/* Red de historiales clínicos — cliente web.
 * La interfaz es la misma para los 4 motores: solo consume la API REST.
 * Lo que cambia entre instituciones son los CAMPOS del dominio (somatometría, exámenes,
 * piezas dentales...), nunca el motor de base de datos. */

"use strict";

// ------------------------------------------------------------------ Constantes
const INST = {
  hospital:    { nombre: "Hospital General",         motor: "PostgreSQL",               color: "#2F5E9E", personal: ["médico", "Médicos"],
                 tipos: [["ordinaria", "Ordinaria"], ["emergencia", "Emergencia"], ["seguimiento", "Seguimiento"]] },
  pediatrico:  { nombre: "Centro Médico Pediátrico", motor: "MySQL",                    color: "#7A4FB0", personal: ["pediatra", "Pediatras"],
                 tipos: [["control_sano", "Control de niño sano"], ["urgencia", "Urgencia"], ["seguimiento", "Seguimiento"], ["vacunacion", "Vacunación"]] },
  laboratorio: { nombre: "Laboratorio Clínico",      motor: "MongoDB",                  color: "#0B7A80", personal: ["laboratorista", "Laboratoristas"],
                 tipos: [["normal", "Prioridad normal"], ["urgente", "Urgente"], ["emergencia", "Emergencia"]] },
  odontologia: { nombre: "Clínica Odontológica",     motor: "Firebase Cloud Firestore", color: "#A8436A", personal: ["odontólogo", "Odontólogos"],
                 tipos: [["ordinaria", "Ordinaria"], ["emergencia", "Emergencia"], ["seguimiento", "Seguimiento"]] },
};
const ROLES = {
  medico: "Médico", pediatra: "Pediatra", laboratorista: "Laboratorista", odontologo: "Odontólogo",
  secretaria: "Secretaria", administrador: "Administrador",
};
const CLINICOS = ["medico", "pediatra", "laboratorista", "odontologo", "administrador"];
const ESTADOS_BAJA = ["dado_de_baja", "archivado", "trasladado", "fallecido"];

// Plantillas por si el motor activo no devuelve catálogo (modo simulado)
const EXAMENES_RESPALDO = [
  { codigo: "HEM-01", nombre_examen: "Hematología completa", parametros_plantilla: [
    { nombre_parametro: "Leucocitos Totales", unidad_medida: "10^3/uL", rango_referencia_min: 4.5, rango_referencia_max: 11 },
    { nombre_parametro: "Hemoglobina", unidad_medida: "g/dL", rango_referencia_min: 13.5, rango_referencia_max: 17.5 },
    { nombre_parametro: "Plaquetas", unidad_medida: "10^3/uL", rango_referencia_min: 150, rango_referencia_max: 450 }] },
  { codigo: "QUI-01", nombre_examen: "Glucosa y creatinina", parametros_plantilla: [
    { nombre_parametro: "Glucosa Sérica Basal", unidad_medida: "mg/dL", rango_referencia_min: 70, rango_referencia_max: 100 },
    { nombre_parametro: "Creatinina Sérica", unidad_medida: "mg/dL", rango_referencia_min: 0.5, rango_referencia_max: 1.1 }] },
];
// Diagnósticos frecuentes por institución (autocompletado; se puede escribir cualquier código)
const CIE10 = {
  hospital: [["J06.9", "Infección aguda de las vías respiratorias superiores"], ["I10", "Hipertensión esencial"],
    ["E11.9", "Diabetes mellitus tipo 2 sin complicaciones"], ["K80.0", "Cálculo de la vesícula biliar con colecistitis aguda"],
    ["K35.8", "Apendicitis aguda"], ["N39.0", "Infección de vías urinarias"], ["J18.9", "Neumonía"],
    ["A09", "Diarrea y gastroenteritis de presunto origen infeccioso"], ["R51", "Cefalea"]],
  pediatrico: [["Z00.1", "Control de salud de rutina del niño"], ["Z23", "Necesidad de inmunización"],
    ["J06.9", "Infección aguda de las vías respiratorias superiores"], ["A09", "Diarrea y gastroenteritis infecciosa"],
    ["H66.9", "Otitis media"], ["J21.9", "Bronquiolitis aguda"], ["L22", "Dermatitis del pañal"],
    ["E44.1", "Desnutrición proteicocalórica leve"]],
  laboratorio: [["Z01.7", "Examen de laboratorio de rutina"], ["E11.9", "Diabetes mellitus tipo 2"], ["D64.9", "Anemia"],
    ["N39.0", "Infección de vías urinarias"], ["E78.5", "Hiperlipidemia"], ["Z34.9", "Control de embarazo normal"]],
  odontologia: [["K02.1", "Caries de la dentina"], ["K02.0", "Caries limitada al esmalte"], ["K04.0", "Pulpitis"],
    ["K05.1", "Gingivitis crónica"], ["K03.6", "Depósitos (cálculo) en los dientes"], ["K08.1", "Pérdida de dientes"],
    ["K07.3", "Anomalías de la posición dental"], ["Z01.2", "Examen odontológico"]],
};
const MEDICAMENTOS = {
  hospital: ["Paracetamol", "Ibuprofeno", "Amoxicilina", "Amoxicilina + Ácido Clavulánico", "Omeprazol", "Metformina", "Losartán", "Ceftriaxona", "Diclofenaco"],
  pediatrico: ["Acetaminofén", "Ibuprofeno", "Amoxicilina", "Sales de rehidratación oral", "Sulfato de zinc", "Salbutamol", "Multivitamínico pediátrico"],
  odontologia: ["Ibuprofeno", "Paracetamol", "Amoxicilina", "Clindamicina", "Clorhexidina 0.12% enjuague", "Ketorolaco"],
};

const PIEZAS_SUP = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
const PIEZAS_INF = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

// -------------------------------------------------------------------- Estado
const estado = {
  usuario: null,
  token: null,
  inst: null,          // institución cuyos datos se muestran
  pacientes: [],
  idSeleccionado: null,
  historial: null,
  especializado: null,
  catalogos: {},
};

// ------------------------------------------------------------------ Utilidades
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const esClinico = () => CLINICOS.includes(estado.usuario?.rol);

function guardarSesion(datos) {
  try { datos ? sessionStorage.setItem("sesion", JSON.stringify(datos)) : sessionStorage.removeItem("sesion"); } catch (_) { /* sin almacenamiento */ }
}
function leerSesion() {
  try { return JSON.parse(sessionStorage.getItem("sesion") || "null"); } catch (_) { return null; }
}

async function api(ruta, opciones = {}) {
  const res = await fetch(ruta, {
    method: opciones.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(estado.token ? { Authorization: `Bearer ${estado.token}` } : {}),
    },
    body: opciones.body ? JSON.stringify(opciones.body) : undefined,
  });
  let datos = null;
  try { datos = await res.json(); } catch (_) { /* respuesta vacía */ }
  if (res.status === 401 && estado.token) { cerrarSesion(false); throw new Error("La sesión expiró. Inicie sesión de nuevo."); }
  if (!res.ok) throw new Error(datos?.error || `Error ${res.status}`);
  return datos;
}

function avisar(texto, esError = false) {
  const el = $("#aviso");
  el.innerHTML = `<span class="aviso-ico" aria-hidden="true">${esError ? "!" : "✓"}</span><span>${esc(texto)}</span>`;
  el.classList.toggle("error-aviso", esError);
  el.hidden = false;
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => { el.hidden = true; }, esError ? 6000 : 3500);
}

function fecha(v, conHora = false) {
  if (!v) return "—";
  const s = String(v).replace("T", " ");
  const [d, h] = s.split(" ");
  const [a, m, dia] = d.split("-");
  if (!dia) return esc(s);
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const txt = `${Number(dia)} ${meses[Number(m) - 1]} ${a}`;
  return conHora && h ? `${txt}, ${h.slice(0, 5)}` : txt;
}

function edad(nacimiento) {
  if (!nacimiento) return "";
  const n = new Date(`${String(nacimiento).slice(0, 10)}T00:00:00`);
  const hoy = new Date();
  let meses = (hoy.getFullYear() - n.getFullYear()) * 12 + (hoy.getMonth() - n.getMonth());
  if (hoy.getDate() < n.getDate()) meses -= 1;
  if (meses < 24) return `${meses} ${meses === 1 ? "mes" : "meses"}`;
  return `${Math.floor(meses / 12)} años`;
}

const iniciales = (nombre) => String(nombre || "").replace(/^(Dr|Dra|Lic|Licda|Ing)\.?\s+/i, "")
  .split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
const saludo = () => { const h = new Date().getHours(); return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches"; };
const mayus = (s) => { const t = String(s ?? "").replaceAll("_", " "); return esc(t.charAt(0).toUpperCase() + t.slice(1)); };
const texto = (s) => esc(String(s ?? "").replaceAll("_", " "));

// --------------------------------------------------------------------- Login
async function iniciarLogin() {
  $("#vistaApp").hidden = true;
  $("#vistaLogin").hidden = false;

  $("#listaInstituciones").innerHTML = Object.entries(INST).map(([clave, i]) => `
    <li><span class="punto" style="background:${i.color}"></span><span>${i.nombre}</span>
    <span class="motor-nombre">${i.motor} <span class="estado-motor" data-estado-motor="${clave}"></span></span></li>`).join("");
  pintarEstadoLogin();
  actualizarIconos();

  try {
    const cuentas = await api("/api/auth/demo-users");
    $("#cuentasDemo").innerHTML = cuentas.map((c) => `
      <button type="button" class="cuenta" data-u="${esc(c.username)}" style="--c:${INST[c.institucion].color}">
        <span class="cuenta-ini" aria-hidden="true">${esc(iniciales(INST[c.institucion].nombre))}</span>
        <span class="cuenta-txt"><b>${esc(INST[c.institucion].nombre)}</b>
          <small>${esc(c.username)} · ${esc(INST[c.institucion].motor)}</small></span>
      </button>`).join("");
  } catch (e) {
    $("#cuentasDemo").textContent = "No se pudo contactar al servidor.";
  }
}

$("#cuentasDemo").addEventListener("click", (ev) => {
  const b = ev.target.closest(".cuenta");
  if (!b) return;
  $("#loginUsuario").value = b.dataset.u;
  $("#loginClave").value = "123";
  $("#formLogin").requestSubmit();
});

$("#formLogin").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const err = $("#loginError");
  err.hidden = true;
  try {
    const u = await api("/api/auth/login", {
      method: "POST",
      body: { username: $("#loginUsuario").value.trim(), password: $("#loginClave").value },
    });
    entrar(u);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
});

// ------------------------------------------------------------- Íconos del menú
const ICONO = {
  inicio: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
  pacientes: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M17 14.5c2.3.2 4 1.8 4.5 4.5"/>',
  citas: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/><path d="M8 14h3v3H8z"/>',
  personal: '<circle cx="12" cy="7" r="3.5"/><path d="M5 21c.6-4 3.3-6.5 7-6.5s6.4 2.5 7 6.5"/><path d="M12 14.5v4M10 16.5h4"/>',
  quirofanos: '<path d="M4 20h16"/><path d="M6 20v-6h12v6"/><path d="M9 14V9a3 3 0 0 1 6 0v5"/><path d="M12 3v2"/>',
  enfermeria: '<path d="M20.5 8.5c0 5-8.5 11-8.5 11S3.5 13.5 3.5 8.5A4.3 4.3 0 0 1 12 6a4.3 4.3 0 0 1 8.5 2.5z"/><path d="M6 12h3l1.5-2.5 2 5 1.5-2.5H18"/>',
  consultas: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="M9 10h6M9 14h6M9 18h3"/>',
  cama: '<path d="M3 18V7"/><path d="M3 14h18v4"/><path d="M21 14v-2a3 3 0 0 0-3-3h-7v5"/><circle cx="7" cy="11" r="2"/>',
  vacuna: '<path d="M18 2l4 4"/><path d="M17 7l3-3"/><path d="M19 9L9 19l-4 1 1-4L16 6z"/><path d="M12 10l2 2M9 13l2 2"/>',
  frasco: '<path d="M9 3h6"/><path d="M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/><path d="M7.5 15h9"/>',
  resultados: '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 16l3-4 3 2 5-6"/>',
  motores: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  buscar: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  orden: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3v2h6V3"/><path d="M9 10h6M9 14h6M9 18h3"/>',
  tubo: '<path d="M9 3h6"/><path d="M10 3v13a2 2 0 0 0 4 0V3"/><path d="M10 11h4"/>',
  salir: '<path d="M15 4h4v16h-4"/><path d="M10 8l-4 4 4 4"/><path d="M6 12h10"/>',
  grafica: '<path d="M3 3v18h18"/><path d="M7 16l4-7 4 4 5-9"/>',
  hitos: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>',
  diente: '<path d="M7 3C4.8 3 3 4.8 3 7c0 3.5 1.5 7 2.5 10.5.5 1.8 1.8 3.5 3.5 3.5 1.5 0 2-1 3-2 1 1 1.5 2 3 2 1.7 0 3-1.7 3.5-3.5C19.5 14 21 10.5 21 7c0-2.2-1.8-4-4-4-2 0-3.5 1.5-5 1.5S9 3 7 3z"/>',
  planes: '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 12l2 2 4-4"/><path d="M9 17h6"/>',
  procedimientos: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  cobros: '<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/><circle cx="7" cy="15" r="1"/><circle cx="12" cy="15" r="1"/>',
};
const svg = (n) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONO[n] || ""}</svg>`;
function actualizarIconos(raiz = document) {
  raiz.querySelectorAll("[data-icono]").forEach((el) => {
    el.innerHTML = svg(el.dataset.icono);
  });
}
actualizarIconos();

function entrar(u) {
  estado.usuario = u;
  estado.token = u.token;
  estado.inst = u.institucion;
  guardarSesion(u);
  $("#vistaLogin").hidden = true;
  $("#vistaApp").hidden = false;
  $("#nombreUsuario").textContent = u.nombre_completo;
  $("#rolUsuario").textContent = ROLES[u.rol] || u.rol;
  $("#avatarUsuario").textContent = iniciales(u.nombre_completo);
  aplicarInstitucion();
}

async function cerrarSesion(llamarApi = true) {
  if (llamarApi) { try { await api("/api/auth/logout", { method: "POST" }); } catch (_) { /* ya expiró */ } }
  Object.assign(estado, { usuario: null, token: null, inst: null, pacientes: [], idSeleccionado: null, historial: null });
  guardarSesion(null);
  $("#aviso").hidden = true;
  iniciarLogin();
}

$("#btnSalir").addEventListener("click", () => cerrarSesion(true));

async function aplicarInstitucion() {
  const i = INST[estado.inst];
  document.documentElement.style.setProperty("--inst", i.color);
  $("#nombreInst").textContent = i.nombre;
  $("#motorInst").textContent = i.motor;
  document.title = `${i.nombre} — Historiales clínicos`;
  $("#txtBuscar").value = "";
  $("#menuPersonal").textContent = `Personal médico`;
  document.querySelectorAll("[data-solo]").forEach((el) => { el.hidden = el.dataset.solo !== estado.inst; });
  document.querySelectorAll("[data-no]").forEach((el) => { el.hidden = el.dataset.no === estado.inst; });
  actualizarIconos();
  try { estado.catalogos = await api("/api/catalogs"); } catch (_) { estado.catalogos = {}; }
  await Promise.all([cargarPacientes(""), cargarPersonal(), revisarMotorReal()]);
  ir("inicio");
}

// Si la base de datos de la institución no respondió al arrancar, la API usa una copia
// en memoria: todo lo que se registre se pierde al cerrar. Se avisa en todas las páginas.
async function revisarMotorReal() {
  const caja = $("#avisoSimulado");
  try {
    const r = await api("/api/engine/status");
    const m = r.motores.find((x) => x.clave === estado.inst);
    const simulado = m && !m.real && r.modo !== "simulated";
    caja.hidden = !simulado;
    if (simulado) {
      caja.innerHTML = `<b>${esc(INST[estado.inst].motor)} no está conectado.</b>
        El sistema está usando datos de prueba en memoria y lo que registre se perderá al cerrarlo.
        Inicie los motores con <code>iniciar.ps1</code> (sin <code>-Reiniciar</code>) y vuelva a abrir el sistema.
        <button type="button" class="btn sutil chico" data-accion="ver-motores">Ver estado de motores</button>`;
    }
  } catch (_) { caja.hidden = true; }
}

// ------------------------------------------------------------------ Navegación
estado.pagina = "inicio";
estado.filtro = "activos";
estado.pestana = "historial";

function ir(pagina) {
  estado.pagina = pagina;
  if (pagina !== "paciente") estado.idSeleccionado = null;
  document.querySelectorAll(".menu-nav [data-pagina]").forEach((b) => {
    const activo = b.dataset.pagina === pagina || (pagina === "paciente" && b.dataset.pagina === "pacientes");
    b.classList.toggle("activo", activo);
    if (activo) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  $("#contenido").scrollTo?.(0, 0);
  window.scrollTo(0, 0);
  const mapa = {
    inicio: pintarInicio,
    pacientes: pintarPacientes,
    citas: pintarCitasPagina,
    personal: pintarPersonal,
    quirofanos: pintarQuirofanos,
    enfermeria: pintarEnfermeria,
    habitaciones: pintarHabitaciones,
    ordenes: pintarOrdenes,
    cobros: pintarCaja,
    agenda: pintarAgenda,
    paciente: pintarExpediente,
    "pediatrico-vacunas": pintarPediatricoVacunas,
    "pediatrico-crecimiento": pintarPediatricoCrecimiento,
    "pediatrico-desarrollo": pintarPediatricoDesarrollo,
    "dental-odontograma": pintarDentalOdontograma,
    "dental-planes": pintarDentalPlanes,
    "dental-aranceles": pintarDentalAranceles,
  };
  (mapa[pagina] || pintarInicio)();
}

function cabecera({ migas = "", titulo, acciones = "" }) {
  $("#cabecera").innerHTML = `
    <div>
      ${migas ? `<nav class="migas" aria-label="Ruta">${migas}</nav>` : ""}
      <h1>${titulo}</h1>
    </div>
    <div class="cab-acciones">${acciones}</div>`;
}

function pestanas(lista, activa, attr = "data-pestana") {
  return `<div class="pestanas" role="tablist">${lista.map(([clave, txt]) =>
    `<button type="button" role="tab" ${attr}="${clave}" aria-selected="${clave === activa}">${txt}</button>`).join("")}</div>`;
}

const btnAccion = (accion, txt, clase = "primario") => `<button type="button" class="btn ${clase}" data-accion="${accion}">${txt}</button>`;
const puedeRegistrar = () => esClinico();

document.querySelectorAll(".menu-nav [data-pagina]").forEach((b) => b.addEventListener("click", () => ir(b.dataset.pagina)));

// Búsqueda del menú lateral: filtra y lleva a la página de pacientes
let tBuscar;
$("#txtBuscar").addEventListener("input", () => {
  clearTimeout(tBuscar);
  tBuscar = setTimeout(async () => { await cargarPacientes(); if (estado.pagina !== "pacientes") ir("pacientes"); else pintarPacientes(); }, 250);
});
$("#formBuscar").addEventListener("submit", async (ev) => { ev.preventDefault(); await cargarPacientes(); ir("pacientes"); });
document.addEventListener("keydown", (ev) => {
  if (ev.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && !$("#modal").open) {
    ev.preventDefault();
    $("#txtBuscar").focus();
  }
});

// ------------------------------------------------------------------ Pacientes
async function cargarPacientes(q = $("#txtBuscar").value.trim()) {
  try {
    estado.pacientes = await api(`/api/patients?q=${encodeURIComponent(q)}`);
  } catch (e) {
    estado.pacientes = [];
    avisar(e.message, true);
  }
}

const nombreDe = (id) => {
  const p = estado.pacientes.find((x) => x.id_paciente === id);
  return p ? `${p.nombres} ${p.apellidos}` : `Paciente n.º ${id}`;
};

function pintarPacientes() {
  cabecera({ titulo: "Pacientes", acciones: btnAccion("nuevo", "+ Registrar paciente") });
  const q = $("#txtBuscar").value.trim();
  const doc = estado.inst === "pediatrico" ? "CUI" : "DPI";
  const todos = estado.pacientes;
  const lista = todos.filter((p) => estado.filtro === "todos" || (estado.filtro === "baja") === ESTADOS_BAJA.includes(p.estado));
  const nBaja = todos.filter((p) => ESTADOS_BAJA.includes(p.estado)).length;
  $("#vista").innerHTML = `
    <div class="barra-filtros">
      ${pestanas([["activos", `Activos (${todos.length - nBaja})`], ["baja", `De baja (${nBaja})`], ["todos", `Todos (${todos.length})`]], estado.filtro, "data-filtro")}
      <label class="buscar-pagina"><span class="oculto">Buscar paciente</span>
        <input type="search" id="buscarPagina" maxlength="60" value="${esc(q)}" placeholder="Buscar por nombre, DPI o n.º de historial"></label>
    </div>
    <div class="panel">
      ${lista.length ? `<table class="tabla-datos">
        <thead><tr><th>Paciente</th><th>${doc}</th><th>Edad</th><th>Sexo</th><th>Registro</th><th>Estado</th><th class="acc">Acciones</th></tr></thead>
        <tbody>${lista.map((p) => `<tr>
          <td><button type="button" class="enlace-paciente" data-id="${p.id_paciente}">
            <span class="ini" aria-hidden="true">${esc(iniciales(`${p.nombres} ${p.apellidos}`))}</span>${esc(p.apellidos)}, ${esc(p.nombres)}</button></td>
          <td>${esc(p.dpi)}</td><td>${edad(p.fecha_nacimiento)}</td><td>${p.sexo === "F" ? "F" : "M"}</td>
          <td>${fecha(p.fecha_registro)}</td>
          <td>${ESTADOS_BAJA.includes(p.estado) ? `<span class="estado baja">De baja</span>` : (p.estado === "hospitalizado" ? `<span class="estado alerta">Hospitalizado</span>` : `<span class="estado activo">Activo</span>`)}</td>
          <td class="acc"><button type="button" class="btn primario chico" data-id="${p.id_paciente}">Abrir historial</button></td>
        </tr>`).join("")}</tbody></table>`
        : `<div class="vacio-tabla"><span class="vacio-ico">${svg("pacientes")}</span><p>${q ? `Ningún paciente coincide con "${esc(q)}".` : "No hay pacientes en esta lista."}</p>
           ${btnAccion("nuevo", "+ Registrar paciente")}</div>`}
    </div>`;
}

// ------------------------------------------------------------ Personal médico
estado.personal = [];
estado.enfermeros = [];
estado.filtroPersonal = "activo";
estado.tipoPersonal = "medicos";

async function cargarPersonal() {
  try { estado.personal = await api("/api/professionals"); } catch (e) { estado.personal = []; }
  if (estado.inst === "hospital") {
    try { estado.enfermeros = await api("/api/hospital/nurses"); } catch (e) { estado.enfermeros = []; }
  } else {
    estado.enfermeros = [];
  }
}
const personalActivo = () => estado.personal.filter((p) => p.estado === "activo");
const enfermerosActivos = () => estado.enfermeros.filter((p) => p.estado === "activo");
const nombrePersonal = (plural = false) => INST[estado.inst].personal[plural ? 1 : 0];

// Qué lista se está gestionando: médicos de la institución o enfermeros (solo hospital)
function fuentePersonal() {
  if (estado.inst === "hospital" && estado.tipoPersonal === "enfermeros") {
    return { lista: estado.enfermeros, url: "/api/hospital/nurses", uno: "enfermero", varios: "Enfermeros",
             campoEsp: "Área", texto: "se asignan a los pacientes hospitalizados por turno" };
  }
  const [uno, varios] = INST[estado.inst].personal;
  return { lista: estado.personal, url: "/api/professionals", uno, varios, campoEsp: "Especialidad",
           texto: "se asignan a cada cita y consulta" };
}

function pintarPersonal() {
  const f = fuentePersonal();
  cabecera({ titulo: "Personal médico", acciones: btnAccion("nuevo-prof", `+ Registrar ${f.uno}`) });
  const todos = f.lista;
  const lista = todos.filter((p) => estado.filtroPersonal === "todos" || p.estado === estado.filtroPersonal);
  const nAct = todos.filter((p) => p.estado === "activo").length;
  $("#vista").innerHTML = `
    ${estado.inst === "hospital" ? `<div class="segmento" role="group" aria-label="Tipo de personal">
      <button type="button" data-tipo-personal="medicos" aria-pressed="${estado.tipoPersonal === "medicos"}">Médicos (${estado.personal.length})</button>
      <button type="button" data-tipo-personal="enfermeros" aria-pressed="${estado.tipoPersonal === "enfermeros"}">Enfermeros (${estado.enfermeros.length})</button>
    </div>` : ""}
    <p class="intro">Los ${f.varios.toLowerCase()} no inician sesión: aquí los registra y luego ${f.texto}.
      Solo los activos aparecen al asignar. No se borran porque su trabajo queda en los historiales; se desactivan.</p>
    ${pestanas([["activo", `Activos (${nAct})`], ["inactivo", `Inactivos (${todos.length - nAct})`], ["todos", `Todos (${todos.length})`]], estado.filtroPersonal, "data-filtro-personal")}
    <div class="panel">${lista.length ? `<table class="tabla-datos">
      <thead><tr><th>Nombre</th><th>Colegiado</th><th>${f.campoEsp}</th><th>Contacto</th><th>Estado</th><th class="acc">Acciones</th></tr></thead>
      <tbody>${lista.map((p) => `<tr>
        <td><span class="nombre-celda"><span class="ini" aria-hidden="true">${esc(iniciales(p.nombre_completo))}</span>${esc(p.nombre_completo)}</span></td>
        <td class="nowrap">${esc(p.numero_colegiado)}</td><td>${esc(p.especialidad || "—")}</td>
        <td><span class="contacto-celda"><span>${esc(p.telefono || "Sin teléfono")}</span><small>${esc(p.correo_electronico || "Sin correo")}</small></span></td>
        <td><span class="estado ${p.estado === "activo" ? "activo" : "baja"}">${p.estado === "activo" ? "Activo" : "Inactivo"}</span></td>
        <td class="acc">
          <button type="button" class="btn sutil chico" data-editar-prof="${p.id_profesional}">Editar</button>
          <button type="button" class="btn ${p.estado === "activo" ? "peligro" : "primario"} chico" data-estado-prof="${p.id_profesional}">${p.estado === "activo" ? "Desactivar" : "Activar"}</button>
        </td></tr>`).join("")}</tbody></table>`
      : `<div class="vacio-tabla"><p>No hay ${f.varios.toLowerCase()} en esta lista.</p>${btnAccion("nuevo-prof", `+ Registrar ${f.uno}`)}</div>`}</div>`;
}

function formProfesional(p = null) {
  const f = fuentePersonal();
  const v = p || {};
  const html = `<div class="rejilla">
    ${campo("nombre_completo", "Nombre completo", { req: true, valor: v.nombre_completo, clase: "doble",
      extra: `placeholder="${f.uno === "enfermero" ? "Enf. Ana Lucía Pérez" : "Dra. Ana Lucía Pérez"}"` })}
    ${p ? `<label>Número de colegiado<input value="${esc(v.numero_colegiado)}" disabled></label>`
        : campo("numero_colegiado", "Número de colegiado", { req: true })}
    ${campo("especialidad", f.campoEsp, { valor: v.especialidad })}
    ${campo("telefono", "Teléfono", { valor: v.telefono })}
    ${campo("correo_electronico", "Correo", { tipo: "email", valor: v.correo_electronico })}
  </div>`;
  abrirModal(p ? `Editar ${f.uno}` : `Registrar ${f.uno}`, html, p ? "Guardar cambios" : `Registrar ${f.uno}`, async (fd) => {
    const d = datosForm(fd);
    if (p) await api(`${f.url}/${p.id_profesional}`, { method: "PUT", body: d });
    else await api(f.url, { method: "POST", body: d });
    avisar(p ? "Datos guardados" : `${d.nombre_completo} registrado`);
    await cargarPersonal();
    if (estado.pagina === "personal") pintarPersonal();
  });
}

async function cambiarEstadoProfesional(id, confirmado = false) {
  const f = fuentePersonal();
  const p = f.lista.find((x) => x.id_profesional === id);
  const nuevo = p.estado === "activo" ? "inactivo" : "activo";
  if (nuevo === "inactivo" && !confirmado) {
    abrirModal(`Desactivar a ${p.nombre_completo}`,
      `<p>Dejará de aparecer al agendar y al asignar. Su historial de trabajo se conserva y puede activarlo de nuevo cuando quiera.</p>
       ${f.uno === "enfermero" ? "<p>Sus turnos de días siguientes se anulan.</p>" : ""}`,
      "Desactivar", async () => { await cambiarEstadoProfesional(id, true); });
    return;
  }
  try {
    await api(`${f.url}/${id}`, { method: "PUT", body: { estado: nuevo } });
    avisar(`${p.nombre_completo} ${nuevo === "activo" ? "activado" : "desactivado"}`);
    await cargarPersonal();
    pintarPersonal();
  } catch (e) { avisar(e.message, true); }
}

// Campo para elegir al profesional (citas y consultas)
function campoProfesional(etiqueta, seleccionado = null) {
  const activos = personalActivo();
  if (!activos.length) {
    return `<div class="completo aviso-sin-personal">No hay ${nombrePersonal(true).toLowerCase()} activos.
      <button type="button" class="btn sutil chico" data-ir-personal>Registrar uno en Personal médico</button></div>`;
  }
  return `<label class="doble"><span class="requerido">${etiqueta}</span><select name="id_profesional" required>
    ${activos.length > 1 && !seleccionado ? `<option value="">Seleccione…</option>` : ""}
    ${activos.map((p) => `<option value="${p.id_profesional}" ${p.id_profesional === seleccionado ? "selected" : ""}>
      ${esc(p.nombre_completo)}${p.especialidad ? ` — ${esc(p.especialidad)}` : ""}</option>`).join("")}
  </select></label>`;
}

// --------------------------------------------------------------------- Inicio
const ETIQUETAS = { ordenes: "órdenes", hospitalizados: "hospitalizados ahora", vacunas: "vacunas aplicadas" };

const ICONO_CIFRA = { pacientes: "pacientes", consultas: "consultas", hospitalizados: "cama", vacunas: "vacuna",
  ordenes: "frasco", resultados: "resultados", citas: "citas" };

const cifra = (icono, valor, etiqueta, ir = null, clase = "") =>
  `<${ir ? `button type="button" data-ir="${ir}"` : "div"} class="cifra-caja ${ir ? "cifra-boton" : ""} ${clase}">
     <span class="cifra-ico">${svg(icono)}</span>
     <span class="cifra-texto"><span class="cifra">${esc(valor)}</span><span class="cifra-etq">${esc(etiqueta)}</span></span>
   </${ir ? "button" : "div"}>`;

async function pintarInicio() {
  const inst = INST[estado.inst];
  cabecera({ titulo: "Inicio", acciones: btnAccion("nuevo", "+ Registrar paciente") });
  const hoyTxt = new Date().toLocaleDateString("es-GT", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  $("#vista").innerHTML = `
    <section class="bienvenida">
      <div>
        <p class="fecha-hoy">${esc(hoyTxt.charAt(0).toUpperCase() + hoyTxt.slice(1))}</p>
        <h2>${saludo()}</h2>
        <p>Panel de administración · ${esc(inst.nombre)}</p>
      </div>
      <div class="bienvenida-motor" id="inicioMotor">
        <span class="cifra-ico">${svg("motores")}</span>
        <span><small>Base de datos</small><b>${esc(inst.motor)}</b></span>
      </div>
    </section>
    <div class="cifras" id="inicioCifras">${'<div class="cifra-caja esqueleto"></div>'.repeat(4)}</div>
    <div class="inicio-cols">
      <section class="panel">
        <header class="panel-cab"><h2>${estado.inst === "laboratorio" ? "Próximas tomas de muestra" : "Próximas citas"}</h2><button type="button" class="btn sutil chico" data-ir="${estado.inst === "laboratorio" ? "agenda" : "citas"}">Ver todas</button></header>
        <div id="inicioCitas"><p class="tenue relleno">Cargando…</p></div>
      </section>
      <section class="panel">
        <header class="panel-cab"><h2>Pacientes recientes</h2><button type="button" class="btn sutil chico" data-ir="pacientes">Ver todos</button></header>
        <ul class="recientes">${[...estado.pacientes].sort((a, b) => String(b.fecha_registro).localeCompare(String(a.fecha_registro))).slice(0, 5).map((p) => `
          <li><button type="button" class="fila-reciente" data-id="${p.id_paciente}"><span class="ini" aria-hidden="true">${esc(iniciales(`${p.nombres} ${p.apellidos}`))}</span>
            <span><b>${esc(p.nombres)} ${esc(p.apellidos)}</b><small class="tenue">${edad(p.fecha_nacimiento)} · registrado ${fecha(p.fecha_registro)}</small></span></button></li>`).join("")
          || `<li class="tenue relleno">Aún no hay pacientes.</li>`}</ul>
      </section>
    </div>`;

  const [citas, est] = await Promise.all([
    api("/api/appointments").catch(() => []),
    api("/api/engine/status").catch(() => null),
  ]);
  if (estado.pagina !== "inicio") return;

  const m = est?.motores?.find((x) => x.clave === estado.inst);
  if (estado.inst === "hospital") {
    const t = turnoActual();
    const [cxHoy, deps, dosis, hosp, turnos] = await Promise.all([
      api(`/api/hospital/surgeries?fecha=${hoyISO()}`).catch(() => []),
      cargarDepartamentos(),
      api(`/api/hospital/doses?fecha=${t.fecha}&turno=${t.turno}`).catch(() => []),
      api("/api/hospital/hospitalizations").catch(() => []),
      api(`/api/hospital/shifts?fecha=${t.fecha}`).catch(() => []),
    ]);
    if (estado.pagina !== "inicio") return;
    const enCurso = cxHoy.filter((c) => c.estado === "en_curso").length;
    const camas = deps.reduce((s, d) => s + d.camas, 0) - deps.reduce((s, d) => s + d.ocupadas, 0);
    const pendientes = dosis.filter((d) => d.estado === "pendiente");
    const c = m?.conteos || {};
    $("#inicioCifras").innerHTML =
        cifra("pacientes", c.pacientes ?? estado.pacientes.length, "pacientes", "pacientes")
      + cifra("cama", c.hospitalizados ?? hosp.length, "hospitalizados", "habitaciones")
      + cifra("cama", camas, camas === 1 ? "cama libre" : "camas libres", "habitaciones", camas ? "" : "cifra-alerta")
      + cifra("quirofanos", enCurso, "en cirugía ahora", "quirofanos", enCurso ? "cifra-alerta" : "")
      + cifra("citas", cxHoy.filter((x) => x.estado !== "cancelada").length, "cirugías hoy", "quirofanos")
      + cifra("vacuna", pendientes.length, "dosis por aplicar", "enfermeria", pendientes.some(atrasada) ? "cifra-alerta" : "");
    guardarDosis(dosis);
    const sinEnf = hosp.filter((h) => !turnos.some((x) => x.turno === t.turno && x.id_hospitalizacion === h.id_hospitalizacion));
    const [, nombreT, horasT] = TURNOS.find((x) => x[0] === t.turno);
    $("#inicioCifras").insertAdjacentHTML("afterend", `<section class="panel turno-panel">
      <header class="panel-cab"><h2>Turno de ${nombreT.toLowerCase()} <span class="tenue">${horasT}</span></h2>
        <button type="button" class="btn sutil chico" data-ir="enfermeria">Ir a Enfermería</button></header>
      <div class="turno-cols">
        <div><h3>Medicamentos por aplicar</h3><ul class="lista-turno">${pendientes.slice(0, 6).map((d) => `<li>
            <span class="hora ${atrasada(d) ? "atrasada-txt" : ""}">${horaDe(d.fecha_hora_programada)}</span>
            <span class="txt"><b>${esc(d.medicamento)} ${esc(d.dosis)}</b>
              <small><button type="button" class="enlace-paciente" data-id="${d.id_paciente}" data-pestana-ir="especial">${esc(d.paciente)}</button> · ${esc(d.numero_habitacion)} · ${d.encargado ? esc(d.encargado) : "sin enfermero"}</small></span>
            ${tocaYa(d) ? `<button type="button" class="btn primario chico" data-aplicar-dosis="${d.id_administracion}">Aplicar</button>` : ""}
          </li>`).join("") || '<li class="vacia">No quedan dosis en este turno.</li>'}
          ${pendientes.length > 6 ? `<li class="vacia">y ${pendientes.length - 6} más en Enfermería.</li>` : ""}</ul></div>
        <div><h3>Pacientes sin enfermero en este turno</h3><ul class="lista-turno">${sinEnf.map((h) => `<li>
            <span class="txt"><button type="button" class="enlace-paciente" data-id="${h.id_paciente}" data-pestana-ir="especial">${esc(h.paciente)}</button>
              <small>${esc(h.numero_habitacion)}${h.departamento ? ` · ${esc(h.departamento)}` : ""}</small></span>
            <button type="button" class="btn sutil chico" data-asignar="${h.id_hospitalizacion}">Asignar</button></li>`).join("")
            || '<li class="vacia">Todos los pacientes ingresados tienen enfermero.</li>'}</ul></div>
      </div></section>`);
  } else if (estado.inst === "laboratorio" && m?.real) {
    const [ordenes, agenda] = await Promise.all([
      api("/api/lab/orders").catch(() => []),
      api(`/api/lab/agenda?desde=${hoyISO()}`).catch(() => []),
    ]);
    if (estado.pagina !== "inicio") return;
    const n = (e) => ordenes.filter((o) => o.estado_orden === e).length;
    const criticas = ordenes.filter((o) => o.alertas_criticas && !["entregada", "cancelada"].includes(o.estado_orden)).length;
    const tomasHoy = agenda.filter((c) => c.estado_cita === "programada" && c.fecha_hora_programada.slice(0, 10) === hoyISO()).length;
    $("#inicioCifras").innerHTML =
        cifra("orden", n("pendiente_muestra"), "esperan muestra", "ordenes")
      + cifra("tubo", n("en_analisis"), "en análisis", "ordenes")
      + cifra("consultas", n("por_validar"), "por validar", "ordenes", n("por_validar") ? "cifra-alerta" : "")
      + cifra("citas", n("lista_entrega"), "listas para entregar", "ordenes")
      + cifra("citas", tomasHoy, tomasHoy === 1 ? "toma agendada hoy" : "tomas agendadas hoy", "agenda")
      + cifra("vacuna", criticas, criticas === 1 ? "valor crítico sin entregar" : "valores críticos sin entregar", "ordenes", criticas ? "cifra-alerta" : "");
    const trabajo = ordenes.filter((o) => ACCION_ORDEN[o.estado_orden])
      .sort((x, y) => (y.prioridad === "urgente") - (x.prioridad === "urgente") || (y.alertas_criticas - x.alertas_criticas) || x.fecha_hora_ingreso.localeCompare(y.fecha_hora_ingreso));
    $("#inicioCifras").insertAdjacentHTML("afterend", `<section class="panel turno-panel">
      <header class="panel-cab"><h2>Lista de trabajo <span class="tenue">${trabajo.length} orden${trabajo.length === 1 ? "" : "es"} en curso</span></h2>
        <button type="button" class="btn sutil chico" data-ir="ordenes">Ir a Órdenes</button></header>
      <ul class="lista-turno">${trabajo.slice(0, 6).map((o) => { const acc = ACCION_ORDEN[o.estado_orden]; return `<li class="fila-clic" data-ver-orden="${o.id_orden}">
          <span class="hora">${numOrden(o.id_orden)}</span>
          <span class="txt"><b>${esc(o.paciente)}</b>
            <small>${o.examenes.map((e) => esc(e.codigo)).join(", ")} · ${ESTADOS_ORDEN[o.estado_orden][0]}${o.prioridad === "urgente" ? ' · <span class="atrasada-txt">urgente</span>' : ""}${o.alertas_criticas ? ' · <span class="atrasada-txt">valor crítico</span>' : ""}</small></span>
          <button type="button" class="btn primario chico" data-paso-orden="${acc[0]}" data-orden="${o.id_orden}">${acc[1]}</button></li>`; }).join("")
        || '<li class="vacia">No hay órdenes en curso.</li>'}</ul></section>`);
  } else {
    const conteos = Object.keys(m?.conteos || {}).length ? m.conteos : { pacientes: estado.pacientes.length };
    $("#inicioCifras").innerHTML = Object.entries(conteos).map(([k, v]) =>
        cifra(ICONO_CIFRA[k] || "consultas", v, ETIQUETAS[k] || k, k === "pacientes" ? "pacientes" : null)).join("")
      + cifra("personal", personalActivo().length, `${nombrePersonal(true).toLowerCase()} activos`, "personal");
  }
  $("#inicioMotor").insertAdjacentHTML("beforeend",
    `<span class="estado ${m?.real ? "activo" : "alerta"}">${m?.real ? "Conectado" : "Simulado"}</span>`);

  const ahora = new Date().toLocaleString("sv-SE").slice(0, 16);
  const proximas = citas.filter((c) => c.fecha_hora_programada >= ahora)
    .sort((a, b) => a.fecha_hora_programada.localeCompare(b.fecha_hora_programada)).slice(0, 5);
  const mesCorto = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  $("#inicioCitas").innerHTML = proximas.length ? `<ul class="agenda">${proximas.map((c) => {
      const [d, h] = c.fecha_hora_programada.split(" ");
      const [, mm, dd] = d.split("-");
      return `<li>
        <span class="agenda-dia"><b>${Number(dd)}</b><small>${mesCorto[Number(mm) - 1]}</small></span>
        <span class="agenda-txt"><b>${esc(nombreDe(c.id_paciente))}</b>
          <small>${esc((h || "").slice(0, 5))} · ${esc(c.motivo_consulta)} · ${esc(c.profesional_nombre)}</small></span>
        <button type="button" class="btn primario chico" data-atender="${c.id_cita}" data-paciente="${c.id_paciente}" ${c.id_orden ? `data-orden="${c.id_orden}"` : ""}>${c.id_orden ? "Tomar muestra" : "Atender"}</button>
      </li>`;
    }).join("")}</ul>`
    : `<div class="vacio-tabla compacto"><span class="vacio-ico">${svg("citas")}</span><p>No hay citas programadas.</p>
       ${btnAccion("cita-nueva", "+ Agendar cita", "sutil chico")}</div>`;
}

// ---------------------------------------------------------------------- Citas
function tablaCitas(citas, conPaciente = true) {
  const puedeAtender = puedeRegistrar();
  return `<table class="tabla-datos">
    <thead><tr><th>Fecha y hora</th>${conPaciente !== null ? "<th>Paciente</th>" : ""}<th>Motivo</th><th>Profesional</th><th>Estado</th><th class="acc">Acciones</th></tr></thead>
    <tbody>${citas.map((c) => `<tr>
      <td class="nowrap"><b>${fecha(c.fecha_hora_programada, true)}</b></td>
      ${conPaciente !== null ? `<td><button type="button" class="enlace-paciente" data-id="${c.id_paciente}">${esc(nombreDe(c.id_paciente))}</button></td>` : ""}
      <td>${esc(c.motivo_consulta)}</td>
      <td>${esc(c.profesional_nombre)}</td>
      <td><span class="estado ${c.estado_cita === "programada" ? "alerta" : (c.estado_cita === "atendida" ? "activo" : "baja")}">${texto(c.estado_cita)}</span></td>
      <td class="acc">${c.estado_cita === "programada" && puedeAtender
        ? `<button type="button" class="btn primario chico" data-atender="${c.id_cita}" data-paciente="${c.id_paciente}" ${c.id_orden ? `data-orden="${c.id_orden}"` : ""}>${c.id_orden ? "Tomar muestra" : "Atender"}</button>`
        : `<button type="button" class="btn sutil chico" data-id="${c.id_paciente}">Ver historial</button>`}</td>
    </tr>`).join("")}</tbody></table>`;
}

estado.filtroCitas = "proximas";
estado.busCitas = { q: "", prof: "", desde: "", hasta: "" };
const normalizar = (t) => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

async function pintarCitasPagina() {
  cabecera({ titulo: "Citas", acciones: btnAccion("cita-nueva", "+ Agendar cita") });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  const [citas, pacientes] = await Promise.all([
    api("/api/appointments").catch((e) => { avisar(e.message, true); return []; }),
    todosLosPacientes(),
  ]);
  if (estado.pagina !== "citas") return;
  const porId = new Map(pacientes.map((p) => [p.id_paciente, p]));
  // Texto en el que se busca: paciente, DPI, n.º de historial, motivo y profesional
  estado.citasTodas = citas.map((c) => {
    const p = porId.get(c.id_paciente);
    const nombre = p ? `${p.nombres} ${p.apellidos}` : nombreDe(c.id_paciente);
    return { ...c, _nombre: nombre, _dpi: p?.dpi || "",
      _buscar: normalizar(`${nombre} ${p?.dpi || ""} ${String(c.id_paciente).padStart(6, "0")} ${c.motivo_consulta} ${c.profesional_nombre}`) };
  });
  const b = estado.busCitas;
  const profesionales = [...new Set(citas.map((c) => c.profesional_nombre).filter(Boolean))].sort();
  $("#vista").innerHTML = `
    <div class="barra-busqueda" role="search">
      <label class="busca-texto"><span class="sr">Buscar cita</span>
        <span class="ico" aria-hidden="true">${svg("buscar")}</span>
        <input type="search" id="busCitasQ" maxlength="60" value="${esc(b.q)}" placeholder="Paciente, DPI, n.º de historial o motivo" autocomplete="off"></label>
      <label>Profesional<select id="busCitasProf"><option value="">Todos</option>${opciones(profesionales.map((n) => [n, n]), b.prof)}</select></label>
      <label>Desde<input type="date" id="busCitasDesde" value="${b.desde}"></label>
      <label>Hasta<input type="date" id="busCitasHasta" value="${b.hasta}"></label>
      <button type="button" class="btn sutil chico" id="busCitasLimpiar" ${b.q || b.prof || b.desde || b.hasta ? "" : "hidden"}>Limpiar</button>
    </div>
    <div id="pestanasCitas"></div>
    <div class="panel" id="tablaCitasPagina"></div>`;
  pintarListaCitas();
}

function pintarListaCitas() {
  const b = estado.busCitas;
  const ahora = ahoraTs();
  const q = normalizar(b.q.trim());
  const filtradas = (estado.citasTodas || []).filter((c) => {
    const f = ts(c.fecha_hora_programada).slice(0, 10);
    return (!q || q.split(/\s+/).every((p) => c._buscar.includes(p)))
      && (!b.prof || c.profesional_nombre === b.prof)
      && (!b.desde || f >= b.desde) && (!b.hasta || f <= b.hasta);
  });
  const grupos = {
    proximas: filtradas.filter((c) => c.estado_cita === "programada" && ts(c.fecha_hora_programada) >= ahora)
      .sort((x, y) => ts(x.fecha_hora_programada).localeCompare(ts(y.fecha_hora_programada))),
    atrasadas: filtradas.filter((c) => c.estado_cita === "programada" && ts(c.fecha_hora_programada) < ahora)
      .sort((x, y) => ts(x.fecha_hora_programada).localeCompare(ts(y.fecha_hora_programada))),
    historial: filtradas.filter((c) => c.estado_cita !== "programada")
      .sort((x, y) => ts(y.fecha_hora_programada).localeCompare(ts(x.fecha_hora_programada))),
  };
  grupos.todas = [...filtradas].sort((x, y) => ts(y.fecha_hora_programada).localeCompare(ts(x.fecha_hora_programada)));
  $("#pestanasCitas").innerHTML = pestanas([["proximas", `Próximas (${grupos.proximas.length})`], ["atrasadas", `Sin atender de días pasados (${grupos.atrasadas.length})`],
    ["historial", `Atendidas y canceladas (${grupos.historial.length})`], ["todas", `Todas (${grupos.todas.length})`]], estado.filtroCitas, "data-filtro-citas");
  const lista = grupos[estado.filtroCitas] || grupos.proximas;
  const buscando = b.q || b.prof || b.desde || b.hasta;
  $("#busCitasLimpiar").hidden = !buscando;
  const vacio = buscando ? "Ninguna cita coincide con la búsqueda."
    : { proximas: "No hay citas próximas.", atrasadas: "No hay citas sin atender de días pasados.", historial: "Todavía no hay citas atendidas ni canceladas.", todas: "No hay citas registradas." }[estado.filtroCitas];
  $("#tablaCitasPagina").innerHTML = lista.length ? tablaCitas(lista)
    : `<div class="vacio-tabla"><span class="vacio-ico">${svg(buscando ? "buscar" : "citas")}</span><p>${vacio}</p>
       ${buscando ? '<button type="button" class="btn sutil chico" data-limpiar-citas>Limpiar búsqueda</button>' : btnAccion("cita-nueva", "+ Agendar cita")}</div>`;
}

let tBusCitas;
$("#contenido").addEventListener("input", (ev) => {
  const id = ev.target.id;
  if (!["busCitasQ", "busCitasProf", "busCitasDesde", "busCitasHasta"].includes(id)) return;
  const k = { busCitasQ: "q", busCitasProf: "prof", busCitasDesde: "desde", busCitasHasta: "hasta" }[id];
  estado.busCitas[k] = ev.target.value;
  clearTimeout(tBusCitas);
  tBusCitas = setTimeout(pintarListaCitas, id === "busCitasQ" ? 150 : 0);
});
function limpiarBusquedaCitas() {
  estado.busCitas = { q: "", prof: "", desde: "", hasta: "" };
  ["busCitasQ", "busCitasProf", "busCitasDesde", "busCitasHasta"].forEach((id) => { $(`#${id}`).value = ""; });
  pintarListaCitas();
  $("#busCitasQ").focus();
}
$("#contenido").addEventListener("click", (ev) => {
  if (ev.target.closest("#busCitasLimpiar, [data-limpiar-citas]")) limpiarBusquedaCitas();
});


// ================================================================ Laboratorio
// Flujo: orden -> toma de muestra -> análisis -> validación -> entrega (MongoDB)
const ESTADOS_ORDEN = {
  pendiente_muestra: ["Pendiente de muestra", "alerta"],
  en_analisis: ["En análisis", "info"],
  por_validar: ["Por validar", "morado"],
  lista_entrega: ["Lista para entregar", "activo"],
  entregada: ["Entregada", "neutro"],
  cancelada: ["Cancelada", "baja"],
};
const PASOS_ORDEN = ["pendiente_muestra", "en_analisis", "por_validar", "lista_entrega", "entregada"];
const ACCION_ORDEN = {
  pendiente_muestra: ["muestra", "Tomar muestra"], en_analisis: ["resultados", "Ingresar resultados"],
  por_validar: ["validar", "Validar"], lista_entrega: ["entregar", "Entregar"],
};
const tiposExamen = () => estado.catalogos.tipos_examen || [];
const tipoExamen = (c) => tiposExamen().find((t) => t.codigo === c) || {};
const numOrden = (id) => String(id).padStart(5, "0");
const chipEstadoOrden = (e) => { const [t, c] = ESTADOS_ORDEN[e] || [e, ""]; return `<span class="estado ${c}">${t}</span>`; };
const laboratoristas = () => personalActivo();
estado.ordenesCache = {};

async function pintarOrdenes() {
  cabecera({ titulo: "Órdenes", acciones: btnAccion("nueva-orden", "+ Nueva orden") });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  const ordenes = await api("/api/lab/orders").catch((e) => { avisar(e.message, true); return []; });
  if (estado.pagina !== "ordenes") return;
  estado.ordenes = ordenes.map((o) => ({ ...o, _buscar: normalizar(`${o.paciente} ${o.dpi} ${numOrden(o.id_orden)} ${o.medico_solicitante} ${o.examenes.map((e) => `${e.codigo} ${e.nombre_examen}`).join(" ")}`) }));
  $("#vista").innerHTML = `
    <div class="barra-busqueda" role="search">
      <label class="busca-texto"><span class="sr">Buscar orden</span><span class="ico" aria-hidden="true">${svg("buscar")}</span>
        <input type="search" id="busOrdenes" maxlength="60" value="${esc(estado.busOrdenes || "")}" placeholder="Paciente, DPI, n.º de orden o examen" autocomplete="off"></label>
    </div>
    <div id="pestanasOrdenes"></div>
    <div class="panel" id="tablaOrdenes"></div>`;
  pintarListaOrdenes();
}

estado.filtroOrdenes = "pendiente_muestra";
function pintarListaOrdenes() {
  const q = normalizar((estado.busOrdenes || "").trim());
  const lista = (estado.ordenes || []).filter((o) => !q || q.split(/\s+/).every((p) => o._buscar.includes(p)));
  const cuenta = (e) => lista.filter((o) => o.estado_orden === e).length;
  const pest = [...PASOS_ORDEN.slice(0, 4).map((e) => [e, `${ESTADOS_ORDEN[e][0]} (${cuenta(e)})`]),
    ["historial", `Entregadas y canceladas (${cuenta("entregada") + cuenta("cancelada")})`]];
  $("#pestanasOrdenes").innerHTML = pestanas(pest, estado.filtroOrdenes, "data-filtro-ordenes");
  const visibles = lista.filter((o) => (estado.filtroOrdenes === "historial" ? ["entregada", "cancelada"].includes(o.estado_orden) : o.estado_orden === estado.filtroOrdenes))
    .sort((a, b) => (b.prioridad === "urgente") - (a.prioridad === "urgente") || (estado.filtroOrdenes === "historial" ? b.fecha_hora_ingreso.localeCompare(a.fecha_hora_ingreso) : a.fecha_hora_ingreso.localeCompare(b.fecha_hora_ingreso)));
  const vacio = q ? "Ninguna orden coincide con la búsqueda." : {
    pendiente_muestra: "No hay órdenes esperando muestra.", en_analisis: "No hay muestras en análisis.",
    por_validar: "No hay resultados por validar.", lista_entrega: "No hay resultados listos para entregar.",
    historial: "Todavía no hay órdenes entregadas ni canceladas." }[estado.filtroOrdenes];
  $("#tablaOrdenes").innerHTML = visibles.length ? tablaOrdenes(visibles)
    : `<div class="vacio-tabla"><span class="vacio-ico">${svg("orden")}</span><p>${vacio}</p>${q ? "" : btnAccion("nueva-orden", "+ Nueva orden")}</div>`;
}

function tablaOrdenes(lista, conPaciente = true) {
  return `<table class="tabla-datos">
    <thead><tr><th>Orden</th>${conPaciente ? "<th>Paciente</th>" : ""}<th>Exámenes</th><th>Ingreso</th><th>Estado</th><th class="acc"></th></tr></thead>
    <tbody>${lista.map((o) => {
      const acc = ACCION_ORDEN[o.estado_orden];
      return `<tr class="fila-clic" data-ver-orden="${o.id_orden}">
        <td class="nowrap"><b>${numOrden(o.id_orden)}</b>${o.prioridad === "urgente" ? '<br><span class="estado critico">Urgente</span>' : ""}</td>
        ${conPaciente ? `<td><button type="button" class="enlace-paciente" data-id="${o.id_paciente}">${esc(o.paciente)}</button><br><small class="tenue">${esc(o.medico_solicitante)}</small></td>` : ""}
        <td><span class="chips-examen">${o.examenes.map((e) => `<span class="chip-examen e-${e.estado}" title="${esc(e.nombre_examen)}">${esc(e.codigo)}</span>`).join("")}</span>
          ${o.alertas_criticas ? '<br><span class="alerta-critica">Valor crítico</span>' : ""}
          ${o.factura && o.factura.saldo > 0 && o.factura.estado !== "anulada" ? `<br><small class="saldo-pend">Por cobrar ${Q(o.factura.saldo)}</small>` : ""}</td>
        <td class="nowrap">${fecha(o.fecha_hora_ingreso, true)}${o.cita && o.estado_orden === "pendiente_muestra" ? `<br><small class="tenue">Toma: ${fecha(o.cita.fecha_hora_programada, true)}</small>` : ""}</td>
        <td>${chipEstadoOrden(o.estado_orden)}</td>
        <td class="acc">${acc ? `<button type="button" class="btn primario chico" data-paso-orden="${acc[0]}" data-orden="${o.id_orden}">${acc[1]}</button>` : ""}</td>
      </tr>`;
    }).join("")}</tbody></table>`;
}

async function cargarOrden(id) {
  const o = await api(`/api/lab/orders/${id}`);
  estado.ordenesCache[id] = o;
  return o;
}

// Panel lateral con la orden completa: línea de tiempo, exámenes, muestras y resultados
async function verOrden(id) {
  abrirCajon({ ini: "OR", sub: "Cargando…", titulo: `Orden ${numOrden(id)}`, cuerpo: '<p class="tenue">Cargando…</p>', pie: "" });
  try {
    const o = await cargarOrden(id);
    const idx = PASOS_ORDEN.indexOf(o.estado_orden);
    const pasos = PASOS_ORDEN.map((e, i) => `<li class="${o.estado_orden === "cancelada" ? "" : i < idx ? "hecho" : i === idx ? "actual" : ""}">${ESTADOS_ORDEN[e][0]}</li>`).join("");
    const resultados = o.resultados.map((r) => `<section class="cajon-bloque">
        <h3>${esc(r.nombre_examen)} <span class="tenue">· ${esc(texto(r.estado))}</span>${r.alertas_criticas ? ' <span class="alerta-critica">valor crítico</span>' : ""}</h3>
        <table class="tabla"><tbody>${r.parametros.map((p) => `<tr><td>${esc(p.nombre_parametro)}</td>
          <td class="num"><b>${esc(p.valor_resultado)}</b> ${esc(p.unidad_medida)}</td>
          <td><span class="flag ${esc(p.interpretacion_alerta)}">${texto(p.interpretacion_alerta).toLowerCase()}</span></td></tr>`).join("")}</tbody></table>
        <small class="tenue">Analizó ${esc(r.analista || "—")}${r.validador ? ` · validó ${esc(r.validador)}` : ""}</small>
        ${r.conclusiones_diagnosticas ? `<p class="notas">${esc(r.conclusiones_diagnosticas)}</p>` : ""}
      </section>`).join("");
    const acc = ACCION_ORDEN[o.estado_orden];
    abrirCajon({
      ini: "OR", sub: `${o.paciente} · ${o.prioridad === "urgente" ? "urgente" : "prioridad normal"}`, titulo: `Orden ${numOrden(o.id_orden)}`,
      cuerpo: `
        <div>${chipEstadoOrden(o.estado_orden)}${o.alertas_criticas ? ' <span class="estado critico">Valor crítico</span>' : ""}</div>
        ${o.estado_orden !== "cancelada" ? `<ol class="pasos-orden">${pasos}</ol>` : `<p class="aviso-baja">${esc(o.motivo_cancelacion || "Cancelada")}</p>`}
        <dl class="datos-cortos">
          <div><dt>Solicitó</dt><dd>${esc(o.medico_solicitante)}</dd></div>
          <div><dt>Ingreso</dt><dd>${fecha(o.fecha_hora_ingreso, true)}</dd></div>
          ${o.diagnostico_presuntivo ? `<div style="grid-column:1/-1"><dt>Diagnóstico presuntivo</dt><dd>${o.codigo_cie10 ? `${esc(o.codigo_cie10)} · ` : ""}${esc(o.diagnostico_presuntivo)}</dd></div>` : ""}
        </dl>
        <section class="cajon-bloque"><h3>Exámenes</h3>
          ${o.examenes.map((e) => { const t = tipoExamen(e.codigo); return `<p class="linea-dato"><span>${esc(e.nombre_examen)}<br><small class="tenue">${esc(t.indicaciones_preparacion || "")}</small></span><span>${esc(texto(e.estado))}</span></p>`; }).join("")}
        </section>
        ${o.factura ? `<section class="cajon-bloque"><h3>Cobro</h3><p class="linea-dato"><span>Factura ${esc(o.factura.numero_factura)}<br><small class="tenue">Total ${Q(o.factura.monto_total)}</small></span>
          <span>${chipFactura(o.factura.estado)}${o.factura.saldo > 0 && o.factura.estado !== "anulada" ? `<br><button type="button" class="btn sutil chico" data-cobrar="${o.factura.id_factura}">Cobrar ${Q(o.factura.saldo)}</button>` : ""}</span></p></section>` : ""}
        ${o.cita ? `<section class="cajon-bloque"><h3>Toma de muestra agendada</h3><p><b>${fecha(o.cita.fecha_hora_programada, true)}</b> · ${esc(texto(o.cita.estado_cita))}</p></section>` : ""}
        ${o.muestras.length ? `<section class="cajon-bloque"><h3>Muestras</h3>${o.muestras.map((m) => `<p class="linea-dato"><span>${esc(m.codigo_etiqueta_barras)}<br><small class="tenue">${esc(m.tipo_muestra)}${m.motivo_rechazo ? ` · ${esc(m.motivo_rechazo)}` : ""}</small></span><span>${esc(texto(m.estado))}</span></p>`).join("")}</section>` : ""}
        ${resultados}
        <section class="cajon-bloque"><h3>Historial de la orden</h3><ul class="historial-orden">${[...o.historial_estados].reverse().map((h) => `<li><time>${fecha(h.fecha, true)}</time><span>${esc(h.detalle)}</span></li>`).join("")}</ul></section>`,
      pie: `${acc ? `<button type="button" class="btn primario" data-paso-orden="${acc[0]}" data-orden="${o.id_orden}">${acc[1]}</button>` : `<button type="button" class="btn primario" data-cajon="historial" data-paciente="${o.id_paciente}">Ver historial del paciente</button>`}
        ${o.estado_orden === "pendiente_muestra" ? `<button type="button" class="btn sutil" data-paso-orden="agendar" data-orden="${o.id_orden}">${o.cita ? "Reagendar toma" : "Agendar toma"}</button>` : ""}
        ${["pendiente_muestra", "en_analisis"].includes(o.estado_orden) && !o.resultados.length ? `<button type="button" class="btn sutil peligro-txt" data-paso-orden="cancelar" data-orden="${o.id_orden}">Cancelar orden</button>` : ""}`,
    });
  } catch (e) {
    $("#cajonCuerpo").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function refrescarLab(id = null) {
  if (estado.pagina === "ordenes") pintarOrdenes();
  else if (estado.pagina === "agenda") pintarAgenda();
  else if (estado.pagina === "inicio") pintarInicio();
  else if (estado.pagina === "paciente") abrirPaciente(estado.historial.paciente.id_paciente, estado.pestana);
  // Si el paso se lanzó desde el panel de la orden, se vuelve a abrir con el siguiente paso
  if (id && (estado.volverAOrden === id || $("#cajon").open)) verOrden(id);
  estado.volverAOrden = null;
}

async function pasoOrden(paso, id) {
  if (paso === "cancelar") return formCancelarOrden(id);
  const o = estado.ordenesCache[id] || await cargarOrden(id);
  cerrarCajon();
  ({ muestra: formMuestra, resultados: formResultados, validar: formValidar, entregar: formEntregar, agendar: formAgendarToma })[paso](o);
}

// ---- Nueva orden
async function formOrden(idPaciente = null) {
  const pacientes = await todosLosPacientes();
  const tipos = tiposExamen();
  const medicos = estado.catalogos.medicos_solicitantes || [];
  const html = `<div id="cuerpoOrden">
    <fieldset class="paso"><legend>Paciente y solicitud</legend><div class="rejilla">
      <label class="doble"><span class="requerido">Paciente</span><select name="id_paciente" required ${idPaciente ? "disabled" : ""}>
        <option value="">Seleccione…</option>${pacientes.filter((p) => p.estado !== "dado_de_baja").map((p) => `<option value="${p.id_paciente}" ${p.id_paciente === idPaciente ? "selected" : ""}>${esc(p.nombres)} ${esc(p.apellidos)} · ${esc(p.dpi)}</option>`).join("")}
      </select></label>
      <label>Prioridad<select name="prioridad"><option value="normal">Normal</option><option value="urgente">Urgente</option></select></label>
      <label class="doble">Médico solicitante<input name="medico_solicitante" list="listaMedicos" placeholder="Vacío si lo pide el paciente"></label>
      <datalist id="listaMedicos">${medicos.map((m) => `<option value="${esc(m)}">`).join("")}</datalist>
      <label>CIE-10<input name="codigo_cie10" placeholder="E11.9"></label>
      <label class="completo">Diagnóstico presuntivo<input name="diagnostico_presuntivo" maxlength="200" placeholder="Control de diabetes"></label>
    </div></fieldset>
    <fieldset class="paso"><legend>Exámenes</legend>
      <div class="lista-examenes">${tipos.map((t) => `<label class="examen-op">
        <input type="checkbox" name="examen" value="${esc(t.codigo)}">
        <span><b>${esc(t.nombre_examen)}</b><small class="tenue">${esc(t.codigo)} · ${esc(t.area_laboratorio || "")} · resultado en ${t.tiempo_estimado_horas ?? "?"} h</small>
          ${t.indicaciones_preparacion ? `<small class="prep ${t.requiere_cita ? "prep-cita" : ""}">${esc(t.indicaciones_preparacion)}</small>` : ""}</span>
        <span class="precio">Q${Number(t.costo || 0).toFixed(2)}</span></label>`).join("")}</div>
      <p class="total-orden" id="totalOrden">Ningún examen seleccionado</p>
    </fieldset>
    <fieldset class="paso" id="secToma" hidden><legend>Toma de muestra</legend>
      <div class="aviso-prep" id="avisoPrep"></div>
      <div class="rejilla">
        <label class="completo examen-op"><input type="checkbox" name="agendar" value="1" checked>
          <span><b>Agendar la toma</b><small class="tenue">Desmarque si el paciente ya cumple la preparación y se toma la muestra ahora.</small></span></label>
        <label class="doble" data-cuando-agendar><span class="requerido">Fecha y hora</span><input name="fecha_toma" type="datetime-local"></label>
        <label class="doble" data-cuando-agendar>Laboratorista<select name="id_laboratorista">${opciones(laboratoristas().map((l) => [String(l.id_profesional), l.nombre_completo]))}</select></label>
      </div>
    </fieldset>
    <label>Observaciones<input name="observaciones" maxlength="300"></label></div>`;
  abrirModal("Nueva orden de laboratorio", html, "Registrar orden", async (fd) => {
    const d = datosForm(fd);
    const examenes = fd.getAll("examen");
    if (!examenes.length) throw new Error("Elija al menos un examen.");
    const requiere = examenes.some((c) => tipoExamen(c).requiere_cita);
    const body = { id_paciente: idPaciente || Number(d.id_paciente), examenes, prioridad: d.prioridad, medico_solicitante: d.medico_solicitante,
      codigo_cie10: d.codigo_cie10, diagnostico_presuntivo: d.diagnostico_presuntivo, observaciones: d.observaciones };
    if (requiere && fd.get("agendar") === "1") {
      if (!d.fecha_toma) throw new Error("Indique la fecha de la toma de muestra.");
      body.fecha_toma = d.fecha_toma;
      body.id_laboratorista = Number(d.id_laboratorista);
    }
    const o = await api("/api/lab/orders", { method: "POST", body });
    avisar(o.cita ? `Orden ${numOrden(o.id_orden)} registrada · toma el ${fecha(o.cita.fecha_hora_programada, true)}` : `Orden ${numOrden(o.id_orden)} registrada`);
    estado.filtroOrdenes = "pendiente_muestra";
    if (estado.pagina === "ordenes" || estado.pagina === "paciente" || estado.pagina === "inicio") refrescarLab();
    else ir("ordenes");
    if (!o.cita) setTimeout(() => verOrden(o.id_orden), 300);
  });
  const f = $("#modalForm");
  const manana = new Date(); manana.setDate(manana.getDate() + 1); manana.setHours(7, 0, 0, 0);
  f.fecha_toma.value = isoLocal(manana);
  const actualizar = () => {
    const sel = [...f.querySelectorAll('[name="examen"]:checked')].map((c) => tipoExamen(c.value));
    const total = sel.reduce((s, t) => s + Number(t.costo || 0), 0);
    $("#totalOrden").innerHTML = sel.length ? `${sel.length} examen${sel.length > 1 ? "es" : ""} · <b>Total Q${total.toFixed(2)}</b> · resultados en ${Math.max(...sel.map((t) => t.tiempo_estimado_horas || 0))} h` : "Ningún examen seleccionado";
    const conCita = sel.filter((t) => t.requiere_cita);
    $("#secToma").hidden = !conCita.length;
    $("#avisoPrep").innerHTML = conCita.length ? `<b>Requiere preparación.</b> Indique al paciente: ${conCita.map((t) => `${esc(t.indicaciones_preparacion)} (${esc(t.codigo)})`).join("; ")}.` : "";
    const ag = f.agendar.checked;
    f.querySelectorAll("[data-cuando-agendar]").forEach((el) => { el.hidden = !ag; });
  };
  $("#cuerpoOrden").addEventListener("change", actualizar);   // dentro del modal: no se acumula entre formularios
  actualizar();
}

// ---- Toma de muestra (o rechazo si no cumplió la preparación)
function formMuestra(o) {
  const tipos = o.tipos_examen || [];
  const preps = tipos.filter((t) => t.indicaciones_preparacion);
  const tipoSug = [...new Set(tipos.map((t) => t.tipo_muestra).filter(Boolean))].join(" + ");
  const html = `<div class="dosis-resumen"><b>Orden ${numOrden(o.id_orden)} · ${esc(o.paciente)}</b>
      <span class="tenue">${o.examenes.map((e) => esc(e.nombre_examen)).join(", ")}</span></div>
    ${preps.length ? `<label class="examen-op cumple-prep"><input type="checkbox" name="preparacion_cumplida" value="1" checked>
      <span><b>El paciente cumplió la preparación</b>${preps.map((t) => `<small class="prep">${esc(t.indicaciones_preparacion)}</small>`).join("")}</span></label>`
      : '<input type="hidden" name="preparacion_cumplida" value="1">'}
    <div class="rejilla">
      <label class="doble"><span class="requerido">Tipo de muestra</span><input name="tipo_muestra" required maxlength="80" value="${esc(tipoSug)}"></label>
      <label class="doble"><span class="requerido">Tomada por</span><select name="id_laboratorista" required>${opciones(laboratoristas().map((l) => [String(l.id_profesional), l.nombre_completo]))}</select></label>
      <label class="completo" data-si-cumple>Condición de la muestra<input name="condicion_muestra" maxlength="200" placeholder="Adecuada, sin hemólisis"></label>
      <label class="completo" data-si-rechaza hidden><span class="requerido">Motivo del rechazo</span><input name="motivo_rechazo" minlength="5" maxlength="200" placeholder="No vino en ayunas"></label>
    </div>
    <p class="ayuda" id="ayudaMuestra">Se genera la etiqueta de la muestra y la orden pasa a análisis.</p>`;
  abrirModal("Tomar muestra", html, "Registrar muestra", async (fd) => {
    const d = datosForm(fd);
    const cumple = fd.get("preparacion_cumplida") === "1";
    if (!cumple && (d.motivo_rechazo || "").trim().length < 5) throw new Error("Indique el motivo del rechazo (al menos 5 caracteres).");
    const r = await api(`/api/lab/orders/${o.id_orden}/sample`, { method: "POST", body: { ...d, preparacion_cumplida: cumple } });
    const m = r.muestras[r.muestras.length - 1];
    avisar(cumple ? `Muestra ${m.codigo_etiqueta_barras} registrada · orden en análisis` : "Muestra rechazada · la orden sigue pendiente", !cumple);
    refrescarLab(o.id_orden);
  });
  const f = $("#modalForm");
  const chk = f.querySelector('input[type="checkbox"][name="preparacion_cumplida"]');
  if (chk) chk.addEventListener("change", () => {
    f.querySelector("[data-si-rechaza]").hidden = chk.checked;
    f.querySelector("[data-si-cumple]").hidden = !chk.checked;
    $("#modalAceptar").textContent = chk.checked ? "Registrar muestra" : "Rechazar muestra";
    $("#ayudaMuestra").textContent = chk.checked ? "Se genera la etiqueta de la muestra y la orden pasa a análisis." : "La muestra queda rechazada y la orden sigue pendiente; puede reagendar la toma.";
  });
}

// ---- Resultados de un examen (plantilla de parámetros del catálogo)
function formResultados(o, codigo = null) {
  const pendientes = o.examenes.filter((e) => e.estado === "en_analisis");
  if (!pendientes.length) { avisar("Todos los exámenes ya tienen resultados", true); return; }
  const cod = codigo || pendientes[0].codigo;
  const t = tipoExamen(cod);
  const plantilla = t.parametros_plantilla || [];
  const html = `<div id="cuerpoResultados"><div class="dosis-resumen"><b>Orden ${numOrden(o.id_orden)} · ${esc(o.paciente)}</b>
      <span class="tenue">Muestra ${esc(o.muestras.filter((m) => m.estado !== "rechazada").map((m) => m.codigo_etiqueta_barras).join(", "))}</span></div>
    ${pendientes.length > 1 ? `<label>Examen<select name="codigo_examen" id="selExamenRes">${opciones(pendientes.map((e) => [e.codigo, e.nombre_examen]), cod)}</select></label>`
      : `<input type="hidden" name="codigo_examen" value="${esc(cod)}"><p><b>${esc(t.nombre_examen || cod)}</b></p>`}
    <table class="tabla tabla-resultados"><thead><tr><th>Parámetro</th><th>Resultado</th><th>Referencia</th><th></th></tr></thead>
      <tbody>${plantilla.map((p, i) => `<tr data-fila="parametro" data-i="${i}">
        <td>${esc(p.nombre_parametro)}<input type="hidden" data-k="nombre_parametro" value="${esc(p.nombre_parametro)}">
          <input type="hidden" data-k="unidad_medida" value="${esc(p.unidad_medida || "")}">
          <input type="hidden" data-k="rango_referencia_min" value="${p.rango_referencia_min ?? ""}"><input type="hidden" data-k="rango_referencia_max" value="${p.rango_referencia_max ?? ""}">
          <input type="hidden" data-k="valor_referencia_cualitativo" value="${esc(p.valor_referencia_cualitativo || "")}"></td>
        <td><span class="valor-con-unidad"><input data-k="valor_resultado" maxlength="40" ${p.valor_referencia_cualitativo ? `placeholder="${esc(p.valor_referencia_cualitativo)}"` : 'inputmode="decimal"'} aria-label="${esc(p.nombre_parametro)}"><span class="tenue">${esc(p.unidad_medida || "")}</span></span></td>
        <td class="tenue nowrap">${p.rango_referencia_min != null || p.rango_referencia_max != null ? `${p.rango_referencia_min ?? ""} – ${p.rango_referencia_max ?? ""}` : esc(p.valor_referencia_cualitativo || "")}</td>
        <td><span class="flag" data-flag></span></td></tr>`).join("")}</tbody></table>
    <div class="rejilla">
      <label class="doble"><span class="requerido">Analizó</span><select name="id_laboratorista" required>${opciones(laboratoristas().map((l) => [String(l.id_profesional), l.nombre_completo]))}</select></label>
      <label class="doble">Observaciones técnicas<input name="observaciones_tecnicas" maxlength="300"></label>
    </div>
    <p class="ayuda">Los resultados quedan preliminares hasta que otra persona los valide.</p></div>`;
  abrirModal(`Resultados · ${t.nombre_examen || cod}`, html, "Guardar resultados", async (fd) => {
    const d = datosForm(fd);
    const parametros = [...$("#modalCuerpo").querySelectorAll('[data-fila="parametro"]')].map((tr) =>
      Object.fromEntries([...tr.querySelectorAll("[data-k]")].map((i) => [i.dataset.k, i.value.trim()]))).filter((p) => p.valor_resultado);
    if (!parametros.length) throw new Error("Ingrese al menos un resultado.");
    const r = await api(`/api/lab/orders/${o.id_orden}/results`, { method: "POST", body: { ...d, parametros } });
    avisar(r.estado_orden === "por_validar" ? "Resultados completos · orden lista para validar" : "Resultados guardados");
    estado.ordenesCache[o.id_orden] = r;
    refrescarLab(o.id_orden);
    if (r.estado_orden === "en_analisis") setTimeout(() => formResultados(r), 250);
  });
  $("#selExamenRes")?.addEventListener("change", (ev) => { cerrarModal(); formResultados(o, ev.target.value); });
  // Interpretación en vivo, igual que la calcula el servidor
  $("#cuerpoResultados").addEventListener("input", (ev) => {
    const tr = ev.target.closest('[data-fila="parametro"]');
    if (!tr || ev.target.dataset.k !== "valor_resultado") return;
    const p = plantilla[Number(tr.dataset.i)];
    const v = ev.target.value.trim().replace(",", ".");
    const flag = tr.querySelector("[data-flag]");
    let txt = "";
    if (v !== "" && !Number.isNaN(Number(v)) && (p.rango_referencia_min != null || p.rango_referencia_max != null)) {
      const n = Number(v);
      if (p.rango_referencia_max != null && n > p.rango_referencia_max) txt = n >= p.rango_referencia_max * 2 ? "CRITICO_ALTO" : "ALTO";
      else if (p.rango_referencia_min != null && n < p.rango_referencia_min) txt = n <= p.rango_referencia_min * 0.5 ? "CRITICO_BAJO" : "BAJO";
      else txt = "NORMAL";
    } else if (v && p.valor_referencia_cualitativo) {
      txt = normalizar(v) === normalizar(p.valor_referencia_cualitativo) ? "NORMAL" : "POSITIVO";
    }
    flag.className = `flag ${txt}`;
    flag.textContent = txt ? txt.replace("_", " ").toLowerCase() : "";
  });
}

// ---- Validación (doble verificación: no puede validar quien analizó)
function formValidar(o) {
  const analistas = new Set(o.resultados.map((r) => r.id_laboratorista_analista));
  const validadores = laboratoristas().filter((l) => !analistas.has(l.id_profesional));
  const html = `<div class="dosis-resumen"><b>Orden ${numOrden(o.id_orden)} · ${esc(o.paciente)}</b>
      <span class="tenue">${o.alertas_criticas ? "Hay valores críticos: notifique al médico solicitante." : "Sin valores críticos."}</span></div>
    ${o.resultados.map((r) => `<section class="validar-examen"><h3>${esc(r.nombre_examen)} <small class="tenue">analizó ${esc(r.analista)}</small></h3>
      <table class="tabla"><tbody>${r.parametros.map((p) => `<tr><td>${esc(p.nombre_parametro)}</td><td class="num"><b>${esc(p.valor_resultado)}</b> ${esc(p.unidad_medida)}</td>
        <td><span class="flag ${esc(p.interpretacion_alerta)}">${texto(p.interpretacion_alerta).toLowerCase()}</span></td></tr>`).join("")}</tbody></table>
      <label>Conclusión<textarea name="conclusion_${esc(r.codigo_examen)}" maxlength="1000" rows="2" placeholder="Interpretación para el médico"></textarea></label></section>`).join("")}
    <label><span class="requerido">Valida</span><select name="id_laboratorista" required>
      <option value="">Seleccione…</option>${opciones(validadores.map((l) => [String(l.id_profesional), l.nombre_completo]))}</select></label>
    <p class="ayuda">${validadores.length ? "Solo aparece el personal que no hizo el análisis (doble verificación)." : "No hay otro laboratorista activo para validar: registre o active uno en Personal médico."}</p>`;
  abrirModal("Validar resultados", html, "Validar", async (fd) => {
    const d = datosForm(fd);
    const conclusiones = Object.fromEntries(o.resultados.map((r) => [r.codigo_examen, fd.get(`conclusion_${r.codigo_examen}`) || ""]));
    await api(`/api/lab/orders/${o.id_orden}/validate`, { method: "POST", body: { id_laboratorista: Number(d.id_laboratorista), conclusiones } });
    avisar(`Orden ${numOrden(o.id_orden)} validada · lista para entregar`);
    refrescarLab(o.id_orden);
  });
}

function formEntregar(o) {
  if (o.factura && o.factura.saldo > 0 && o.factura.estado !== "anulada") {
    abrirModal("Cobro pendiente", `<div class="aviso-prep"><b>La factura ${esc(o.factura.numero_factura)} tiene saldo de ${Q(o.factura.saldo)}.</b>
      Los resultados se entregan cuando la cuenta está pagada.</div>`, `Cobrar ${Q(o.factura.saldo)}`, async () => {
      estado.ordenTrasCobro = o.id_orden;   // al cobrar, se vuelve a la orden para entregar
      setTimeout(() => formCobro(o.factura.id_factura), 50);
    });
    return;
  }
  abrirModal("Entregar resultados", `<div class="dosis-resumen"><b>Orden ${numOrden(o.id_orden)} · ${esc(o.paciente)}</b>
      <span class="tenue">${o.examenes.map((e) => esc(e.nombre_examen)).join(", ")}</span></div>
    <label><span class="requerido">Entregado a</span><input name="entregado_a" required maxlength="100" value="${esc(o.paciente)}"></label>
    <p class="ayuda">Puede ser el paciente, un familiar o el médico solicitante (${esc(o.medico_solicitante)}).</p>`,
  "Registrar entrega", async (fd) => {
    await api(`/api/lab/orders/${o.id_orden}/deliver`, { method: "POST", body: datosForm(fd) });
    avisar("Resultados entregados");
    refrescarLab(o.id_orden);
  });
}

function formAgendarToma(o) {
  const preps = (o.tipos_examen || []).filter((t) => t.indicaciones_preparacion);
  const manana = new Date(); manana.setDate(manana.getDate() + 1); manana.setHours(7, 0, 0, 0);
  abrirModal(o.cita ? "Reagendar toma de muestra" : "Agendar toma de muestra", `
    ${preps.length ? `<div class="aviso-prep"><b>Indique al paciente:</b> ${preps.map((t) => esc(t.indicaciones_preparacion)).join("; ")}.</div>` : ""}
    <div class="rejilla">
      <label class="doble"><span class="requerido">Fecha y hora</span><input name="fecha_toma" type="datetime-local" required value="${isoLocal(manana)}"></label>
      <label class="doble">Laboratorista<select name="id_laboratorista">${opciones(laboratoristas().map((l) => [String(l.id_profesional), l.nombre_completo]))}</select></label>
    </div>`, o.cita ? "Reagendar" : "Agendar", async (fd) => {
    const r = await api(`/api/lab/orders/${o.id_orden}/schedule`, { method: "POST", body: datosForm(fd) });
    avisar(`Toma agendada para el ${fecha(r.cita.fecha_hora_programada, true)}`);
    refrescarLab(o.id_orden);
  });
}

function formCancelarOrden(id) {
  abrirModal("Cancelar orden", `<label><span class="requerido">Motivo</span><input name="motivo" required minlength="5" maxlength="200" placeholder="El paciente no se presentó"></label>
    <p class="ayuda">Si tenía toma agendada, también se cancela.</p>`, "Cancelar orden", async (fd) => {
    await api(`/api/lab/orders/${id}/cancel`, { method: "POST", body: datosForm(fd) });
    avisar("Orden cancelada");
    refrescarLab(id);
  });
}

// ---- Agenda de tomas
async function pintarAgenda() {
  cabecera({ titulo: "Agenda de tomas", acciones: btnAccion("nueva-orden", "+ Nueva orden") });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  const hoy = hoyISO();
  const citas = await api(`/api/lab/agenda?desde=${hoyISO(new Date(Date.now() - 7 * 86400000))}`).catch((e) => { avisar(e.message, true); return []; });
  if (estado.pagina !== "agenda") return;
  const pendientes = citas.filter((c) => c.estado_cita === "programada");
  const atrasadas = pendientes.filter((c) => c.fecha_hora_programada.slice(0, 10) < hoy);
  const proximas = pendientes.filter((c) => c.fecha_hora_programada.slice(0, 10) >= hoy);
  const porDia = {};
  proximas.forEach((c) => { (porDia[c.fecha_hora_programada.slice(0, 10)] ||= []).push(c); });
  const fila = (c) => `<li class="toma">
      <span class="hora">${horaDe(c.fecha_hora_programada)}</span>
      <span class="txt"><button type="button" class="enlace-paciente" data-id="${c.id_paciente}">${esc(c.paciente)}</button>
        <small class="tenue">Orden ${numOrden(c.id_orden)} · ${c.examenes.map((e) => esc(e.codigo)).join(", ")}${c.telefono ? ` · tel. ${esc(c.telefono)}` : ""}</small>
        ${c.preparacion ? `<small class="prep">${esc(c.preparacion)}</small>` : ""}</span>
      <span class="acc"><button type="button" class="btn sutil chico" data-ver-orden="${c.id_orden}">Ver orden</button>
        ${c.estado_orden === "pendiente_muestra" ? `<button type="button" class="btn primario chico" data-paso-orden="muestra" data-orden="${c.id_orden}">Tomar muestra</button>` : ""}</span></li>`;
  const tituloDia = (d) => {
    const f = new Date(`${d}T12:00`);
    const txt = f.toLocaleDateString("es-GT", { weekday: "long", day: "numeric", month: "long" });
    return d === hoy ? `Hoy · ${txt}` : d === hoyISO(new Date(Date.now() + 86400000)) ? `Mañana · ${txt}` : txt.charAt(0).toUpperCase() + txt.slice(1);
  };
  $("#vista").innerHTML = `
    <p class="ayuda">Solo aparecen los exámenes que requieren preparación (ayuno, primera orina, frasco estéril). Los demás se toman sin cita al registrar la orden.</p>
    ${atrasadas.length ? `<section class="panel dia-tomas atrasadas"><header class="panel-cab"><h2>No se presentaron <span class="tenue">(${atrasadas.length})</span></h2></header>
      <ul class="lista-tomas">${atrasadas.map(fila).join("")}</ul></section>` : ""}
    ${Object.keys(porDia).length ? Object.entries(porDia).map(([d, lista]) => `<section class="panel dia-tomas">
        <header class="panel-cab"><h2>${esc(tituloDia(d))}</h2><span class="tenue">${lista.length} toma${lista.length > 1 ? "s" : ""}</span></header>
        <ul class="lista-tomas">${lista.map(fila).join("")}</ul></section>`).join("")
      : `<div class="panel vacio-tabla"><span class="vacio-ico">${svg("citas")}</span><p>No hay tomas de muestra agendadas.</p>${btnAccion("nueva-orden", "+ Nueva orden")}</div>`}`;
}

let tBusOrdenes;
$("#contenido").addEventListener("input", (ev) => {
  if (ev.target.id !== "busOrdenes") return;
  estado.busOrdenes = ev.target.value;
  clearTimeout(tBusOrdenes);
  tBusOrdenes = setTimeout(pintarListaOrdenes, 150);
});


// ====================================================================== Caja
// Hospital (PostgreSQL), Pediátrico (MySQL) y Laboratorio (MongoDB) comparten esta pantalla.
// La Clínica Odontológica usa su propia facturación por planes de tratamiento.
const conCaja = () => ["hospital", "pediatrico", "laboratorio", "odontologia"].includes(estado.inst);
const Q = (n) => `Q${Number(n || 0).toLocaleString("es-GT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const ESTADO_FACTURA = { pendiente: ["Por cobrar", "alerta"], parcial: ["Abonada", "info"], pagada: ["Pagada", "activo"], anulada: ["Anulada", "baja"] };
const chipFactura = (e) => { const [t, c] = ESTADO_FACTURA[e] || [e, ""]; return `<span class="estado ${c}">${t}</span>`; };
const METODOS = [["efectivo", "Efectivo"], ["tarjeta", "Tarjeta"], ["transferencia", "Transferencia"], ["cheque", "Cheque"]];
const CATEGORIAS = { consulta: "Consulta", hospitalizacion: "Hospitalización", cirugia: "Cirugía", medicamento: "Medicamento",
  procedimiento: "Procedimiento", vacunacion: "Vacunación", examen: "Examen", otro: "Otro" };
const origenTxt = (f) => ({ consulta: "Consulta", internamiento: "Internamiento", cirugia: "Cirugía",
  orden: `Orden ${String(f.origen_id).padStart(5, "0")}`, plan: `Plan de tratamiento #${f.origen_id}` })[f.origen_tipo] || "Cargo manual";
estado.facturasCache = {};

// NIT de Guatemala: módulo 11 (10 = K). La misma regla valida el servidor.
function revisarNIT(v) {
  const n = v.replace(/[-\s]/g, "").toUpperCase();
  if (n === "CF" || n === "C/F") return null;
  if (!/^\d{1,12}[\dK]$/.test(n)) return "use CF o números con su dígito verificador (ej. 576937-K)";
  const cuerpo = n.slice(0, -1).split("").reverse();
  const suma = cuerpo.reduce((s, d, i) => s + Number(d) * (i + 2), 0);
  const esperado = (11 - (suma % 11)) % 11;
  return n.slice(-1) === (esperado === 10 ? "K" : String(esperado)) ? null : "el dígito verificador no coincide";
}

async function aranceles() {
  if (!estado.aranceles) estado.aranceles = await api("/api/billing/tariffs").catch(() => []);
  return estado.aranceles;
}

estado.filtroCaja = "por_cobrar";
async function pintarCaja() {
  cabecera({ titulo: "Caja", acciones: btnAccion("nueva-factura", "+ Nueva factura") });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  const facturas = await api("/api/billing/invoices").catch((e) => { avisar(e.message, true); return []; });
  if (estado.pagina !== "cobros") return;
  estado.facturas = facturas.map((f) => ({ ...f, _buscar: normalizar(`${f.paciente} ${f.numero_factura} ${f.nit} ${f.nombre_facturacion}`) }));
  const hoy = hoyISO();
  const vigentes = facturas.filter((f) => f.estado !== "anulada");
  const deHoy = vigentes.filter((f) => String(f.fecha_emision).slice(0, 10) === hoy);
  const porCobrar = vigentes.filter((f) => f.saldo > 0);
  $("#vista").innerHTML = `
    <div class="cifras cifras-dinero">
      ${cifra("cobros", Q(porCobrar.reduce((s, f) => s + f.saldo, 0)), `por cobrar en ${porCobrar.length} factura${porCobrar.length === 1 ? "" : "s"}`, null, porCobrar.length ? "cifra-alerta" : "")}
      ${cifra("cobros", Q(deHoy.reduce((s, f) => s + f.monto_total, 0)), `facturado hoy (${deHoy.length})`)}
      ${cifra("cobros", Q(vigentes.reduce((s, f) => s + f.monto_pagado, 0)), "cobrado en total")}
    </div>
    <div class="barra-busqueda" role="search">
      <label class="busca-texto"><span class="sr">Buscar factura</span><span class="ico" aria-hidden="true">${svg("buscar")}</span>
        <input type="search" id="busCaja" maxlength="60" value="${esc(estado.busCaja || "")}" placeholder="Paciente, n.º de factura o NIT" autocomplete="off"></label>
    </div>
    <div id="pestanasCaja"></div>
    <div class="panel" id="tablaCaja"></div>`;
  pintarListaCaja();
}

async function pintarListaCaja() {
  const f0 = estado.facturas || [];
  const q = normalizar((estado.busCaja || "").trim());
  const lista = f0.filter((f) => !q || q.split(/\s+/).every((p) => f._buscar.includes(p)));
  const grupos = {
    por_cobrar: lista.filter((f) => ["pendiente", "parcial"].includes(f.estado)),
    pagadas: lista.filter((f) => f.estado === "pagada"),
    anuladas: lista.filter((f) => f.estado === "anulada"),
  };
  $("#pestanasCaja").innerHTML = pestanas([["por_cobrar", `Por cobrar (${grupos.por_cobrar.length})`], ["pagadas", `Pagadas (${grupos.pagadas.length})`],
    ["anuladas", `Anuladas (${grupos.anuladas.length})`], ["aranceles", "Aranceles"]], estado.filtroCaja, "data-filtro-caja");
  $(".barra-busqueda").hidden = estado.filtroCaja === "aranceles";
  if (estado.filtroCaja === "aranceles") { $("#tablaCaja").innerHTML = await tablaAranceles(); return; }
  const v = grupos[estado.filtroCaja];
  $("#tablaCaja").innerHTML = v.length ? tablaFacturas(v)
    : `<div class="vacio-tabla"><span class="vacio-ico">${svg("cobros")}</span><p>${q ? "Ninguna factura coincide con la búsqueda." : { por_cobrar: "No hay cuentas por cobrar.", pagadas: "Todavía no hay facturas pagadas.", anuladas: "No hay facturas anuladas." }[estado.filtroCaja]}</p></div>`;
}

function tablaFacturas(lista, conPaciente = true) {
  return `<table class="tabla-datos">
    <thead><tr><th>Factura</th>${conPaciente ? "<th>Paciente</th>" : ""}<th>Origen</th><th class="num">Total</th><th class="num">Pagado</th><th class="num">Saldo</th><th>Estado</th><th class="acc"></th></tr></thead>
    <tbody>${lista.map((f) => `<tr class="fila-clic" data-ver-factura="${f.id_factura}">
      <td class="nowrap"><b>${esc(f.numero_factura)}</b><br><small class="tenue">${fecha(f.fecha_emision, true)}</small></td>
      ${conPaciente ? `<td><button type="button" class="enlace-paciente" data-id="${f.id_paciente}">${esc(f.paciente)}</button><br><small class="tenue">NIT ${esc(f.nit)}</small></td>` : ""}
      <td>${esc(origenTxt(f))}</td>
      <td class="num">${Q(f.monto_total)}</td><td class="num">${Q(f.monto_pagado)}</td>
      <td class="num"><b class="${f.saldo > 0 && f.estado !== "anulada" ? "saldo-pend" : ""}">${Q(f.estado === "anulada" ? 0 : f.saldo)}</b></td>
      <td>${chipFactura(f.estado)}</td>
      <td class="acc">${["pendiente", "parcial"].includes(f.estado) ? `<button type="button" class="btn primario chico" data-cobrar="${f.id_factura}">Cobrar</button>` : ""}</td>
    </tr>`).join("")}</tbody></table>`;
}

async function tablaAranceles() {
  estado.aranceles = null;
  const lista = await aranceles();
  const lab = estado.inst === "laboratorio";
  const nota = estado.inst === "odontologia" ? '<span class="tenue">Son los procedimientos del catálogo clínico.</span> ' : "";
  return `<header class="panel-cab"><h2>Aranceles <span class="tenue">${lista.length} servicios</span></h2>
      ${lab ? '<span class="tenue">Son los exámenes del catálogo; aquí se cambia su precio.</span>' : `<span>${nota}<button type="button" class="btn sutil chico" data-editar-arancel="">+ Nuevo arancel</button></span>`}</header>
    <table class="tabla-datos"><thead><tr><th>Código</th><th>Servicio</th><th>Categoría</th><th class="num">Precio</th><th>Estado</th><th class="acc"></th></tr></thead>
    <tbody>${lista.map((a) => `<tr>
      <td class="nowrap"><b>${esc(a.codigo)}</b></td><td>${esc(a.descripcion)}</td><td>${esc(CATEGORIAS[a.categoria] || a.categoria)}</td>
      <td class="num"><b>${Q(a.precio)}</b></td><td>${a.activo ? '<span class="estado activo">Activo</span>' : '<span class="estado baja">Inactivo</span>'}</td>
      <td class="acc"><button type="button" class="btn sutil chico" data-editar-arancel="${esc(a.codigo)}">Editar</button></td></tr>`).join("")}</tbody></table>`;
}

async function verFactura(id) {
  abrirCajon({ ini: "Q", sub: "Cargando…", titulo: "Factura", cuerpo: '<p class="tenue">Cargando…</p>', pie: "" });
  try {
    const f = await api(`/api/billing/invoices/${id}`);
    estado.facturasCache[id] = f;
    const cobrable = ["pendiente", "parcial"].includes(f.estado);
    abrirCajon({
      ini: "Q", sub: `${f.paciente} · ${fecha(f.fecha_emision, true)}`, titulo: `Factura ${f.numero_factura}`,
      cuerpo: `
        <div>${chipFactura(f.estado)} <span class="tenue">${esc(origenTxt(f))}</span></div>
        ${f.motivo_anulacion ? `<p class="aviso-baja">${esc(f.motivo_anulacion)}</p>` : ""}
        <dl class="datos-cortos"><div><dt>NIT</dt><dd>${esc(f.nit)}</dd></div><div><dt>Nombre</dt><dd>${esc(f.nombre_facturacion)}</dd></div></dl>
        <section class="cajon-bloque"><h3>Detalle</h3>
          <table class="tabla tabla-factura"><tbody>${f.detalle.map((d) => `<tr><td>${esc(d.concepto)}<br><small class="tenue">${Number(d.cantidad)} × ${Q(d.precio_unitario)}</small></td><td class="num">${Q(d.subtotal)}</td></tr>`).join("")}</tbody>
          <tfoot><tr><td>Total</td><td class="num">${Q(f.monto_total)}</td></tr>
            <tr><td>Pagado</td><td class="num">${Q(f.monto_pagado)}</td></tr>
            <tr class="saldo"><td>Saldo</td><td class="num">${Q(f.estado === "anulada" ? 0 : f.saldo ?? f.monto_total - f.monto_pagado)}</td></tr></tfoot></table>
        </section>
        <section class="cajon-bloque"><h3>Pagos</h3>${f.pagos.length ? f.pagos.map((p) => `<p class="linea-dato"><span>${esc(p.numero_recibo)}<br><small class="tenue">${fecha(p.fecha_pago, true)} · ${esc(texto(p.metodo_pago))}${p.referencia ? ` · ${esc(p.referencia)}` : ""} · ${esc(p.recibido_por || "")}</small></span><span>${Q(p.monto)}</span></p>`).join("")
          : '<p class="tenue">Sin pagos todavía.</p>'}</section>`,
      pie: `${cobrable ? `<button type="button" class="btn primario" data-cobrar="${f.id_factura}">Cobrar ${Q(f.saldo)}</button>` : `<button type="button" class="btn primario" data-imprimir-factura="${f.id_factura}">Imprimir comprobante</button>`}
        ${cobrable ? `<button type="button" class="btn sutil" data-imprimir-factura="${f.id_factura}">Imprimir</button>` : ""}
        ${f.estado === "pendiente" ? `<button type="button" class="btn sutil peligro-txt" data-anular-factura="${f.id_factura}">Anular</button>` : ""}`,
    });
  } catch (e) {
    $("#cajonCuerpo").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function refrescarCaja(id = null) {
  estado.aranceles = null;
  if (estado.pagina === "cobros") pintarCaja();
  else if (estado.pagina === "ordenes") pintarOrdenes();
  else if (estado.pagina === "paciente" && estado.historial) abrirPaciente(estado.historial.paciente.id_paciente, estado.pestana);
  if (estado.ordenTrasCobro) { const oid = estado.ordenTrasCobro; estado.ordenTrasCobro = null; estado.volverAFactura = null; verOrden(oid); return; }
  if (id && (estado.volverAFactura === id || $("#cajon").open)) verFactura(id);
  estado.volverAFactura = null;
}

// ---- Nueva factura (manual, o la cuenta calculada de un internamiento)
async function formFactura({ idPaciente = null, lineas = [], origenTipo = "manual", origenId = null, titulo = "Nueva factura" } = {}) {
  const [pacientes, lista] = await Promise.all([todosLosPacientes(), aranceles()]);
  const activos = lista.filter((a) => a.activo);
  const p0 = pacientes.find((p) => p.id_paciente === idPaciente);
  const fila = (l = {}) => `<tr data-fila="cargo">
      <td><input data-k="concepto" maxlength="150" required value="${esc(l.concepto || "")}" aria-label="Concepto"><input type="hidden" data-k="codigo_arancel" value="${esc(l.codigo_arancel || "")}"></td>
      <td><input data-k="cantidad" type="number" min="0.01" max="1000" step="any" required value="${l.cantidad ?? 1}" aria-label="Cantidad"></td>
      <td><input data-k="precio_unitario" type="number" min="0" max="100000" step="0.01" required value="${l.precio_unitario ?? ""}" aria-label="Precio"></td>
      <td class="num" data-subtotal></td>
      <td><button type="button" class="btn-icono" data-quitar-cargo aria-label="Quitar">Quitar</button></td></tr>`;
  const html = `<div id="cuerpoFactura">
    <div class="rejilla">
      <label class="doble"><span class="requerido">Paciente</span><select name="id_paciente" required ${idPaciente ? "disabled" : ""}>
        <option value="">Seleccione…</option>${pacientes.map((p) => `<option value="${p.id_paciente}" ${p.id_paciente === idPaciente ? "selected" : ""}>${esc(p.nombres)} ${esc(p.apellidos)}</option>`).join("")}</select></label>
      <label><span class="requerido">NIT</span><input name="nit" required value="CF" maxlength="15"></label>
      <label>Nombre en la factura<input name="nombre_facturacion" maxlength="120" value="${esc(p0 ? `${p0.nombres} ${p0.apellidos}` : "")}" placeholder="Nombre del paciente"></label>
    </div>
    <div class="cargos-cab"><h3>Cargos</h3>
      <label class="agregar-arancel">Agregar servicio<select id="selArancel"><option value="">Elija un servicio…</option>
        ${Object.entries(CATEGORIAS).map(([k, t]) => { const g = activos.filter((a) => a.categoria === k); return g.length ? `<optgroup label="${t}">${g.map((a) => `<option value="${esc(a.codigo)}">${esc(a.descripcion)} · ${Q(a.precio)}</option>`).join("")}</optgroup>` : ""; }).join("")}
      </select></label></div>
    <table class="tabla tabla-cargos"><thead><tr><th>Concepto</th><th>Cant.</th><th>Precio</th><th class="num">Subtotal</th><th></th></tr></thead>
      <tbody id="filasCargos">${lineas.map(fila).join("")}</tbody>
      <tfoot><tr><td colspan="3">Total</td><td class="num" id="totalFactura">Q0.00</td><td></td></tr></tfoot></table>
    <p class="ayuda" id="ayudaCargos">${lineas.length ? (origenTipo === "internamiento" ? "Cargos calculados por la base de datos con la estancia, los medicamentos aplicados y las cirugías. Puede ajustarlos antes de facturar." : "") : "Agregue los servicios desde la lista o escriba un cargo libre."}</p>
    <button type="button" class="btn sutil chico" data-cargo-libre>+ Cargo libre</button></div>`;
  abrirModal(titulo, html, "Emitir factura", async (fd) => {
    const d = datosForm(fd);
    const cargos = [...$("#filasCargos").querySelectorAll('[data-fila="cargo"]')].map((tr) =>
      Object.fromEntries([...tr.querySelectorAll("[data-k]")].map((i) => [i.dataset.k, i.value.trim()])));
    if (!cargos.length) throw new Error("Agregue al menos un cargo.");
    const body = { id_paciente: idPaciente || Number(d.id_paciente), nit: d.nit, nombre_facturacion: d.nombre_facturacion,
      origen_tipo: origenTipo, origen_id: origenId, lineas: cargos.map((c) => ({ ...c, cantidad: Number(c.cantidad), precio_unitario: Number(c.precio_unitario) })) };
    const f = await api("/api/billing/invoices", { method: "POST", body });
    avisar(`Factura ${f.numero_factura} por ${Q(f.monto_total)} emitida`);
    estado.volverAFactura = f.id_factura;
    refrescarCaja(f.id_factura);
  });
  const cuerpo = $("#cuerpoFactura");
  const total = () => {
    let t = 0;
    cuerpo.querySelectorAll('[data-fila="cargo"]').forEach((tr) => {
      const st = Number(tr.querySelector('[data-k="cantidad"]').value || 0) * Number(tr.querySelector('[data-k="precio_unitario"]').value || 0);
      t += st;
      tr.querySelector("[data-subtotal]").textContent = Q(st);
    });
    $("#totalFactura").textContent = Q(t);
  };
  cuerpo.addEventListener("input", total);
  cuerpo.addEventListener("change", (ev) => {
    if (ev.target.id === "selArancel" && ev.target.value) {
      const a = activos.find((x) => x.codigo === ev.target.value);
      $("#filasCargos").insertAdjacentHTML("beforeend", fila({ codigo_arancel: a.codigo, concepto: a.descripcion, cantidad: 1, precio_unitario: a.precio }));
      ev.target.value = "";
      total();
    }
    if (ev.target.name === "id_paciente") {
      const p = pacientes.find((x) => x.id_paciente === Number(ev.target.value));
      if (p) cuerpo.querySelector('[name="nombre_facturacion"]').value = `${p.nombres} ${p.apellidos}`;
    }
  });
  cuerpo.addEventListener("click", (ev) => {
    if (ev.target.closest("[data-quitar-cargo]")) { ev.target.closest("tr").remove(); total(); }
    if (ev.target.closest("[data-cargo-libre]")) { $("#filasCargos").insertAdjacentHTML("beforeend", fila()); $("#filasCargos tr:last-child input").focus(); total(); }
  });
  total();
}

async function generarCuentaInternamiento(idHosp, idPaciente) {
  try {
    const cargos = await api(`/api/billing/suggested?origen_tipo=internamiento&origen_id=${idHosp}`);
    formFactura({ idPaciente, lineas: cargos, origenTipo: "internamiento", origenId: idHosp, titulo: "Cuenta del internamiento" });
  } catch (e) { avisar(e.message, true); }
}

// ---- Cobrar (abono o pago total)
async function formCobro(id) {
  const f = estado.facturasCache[id] || await api(`/api/billing/invoices/${id}`);
  const saldo = Number((f.monto_total - f.monto_pagado).toFixed(2));
  const html = `<div id="cuerpoCobro"><div class="dosis-resumen"><b>Factura ${esc(f.numero_factura)} · ${esc(f.paciente)}</b>
      <span class="tenue">Total ${Q(f.monto_total)} · pagado ${Q(f.monto_pagado)}</span></div>
    <p class="saldo-grande">Saldo <b>${Q(saldo)}</b></p>
    <div class="rejilla">
      <label><span class="requerido">Monto</span><input name="monto" type="number" required min="0.01" max="${saldo}" step="0.01" value="${saldo}"></label>
      <label><span class="requerido">Método</span><select name="metodo_pago">${opciones(METODOS, "efectivo")}</select></label>
      <label class="doble" id="campoRef" hidden><span class="requerido">Referencia o autorización</span><input name="referencia" maxlength="40" placeholder="AUT-552190"></label>
    </div>
    <p class="ayuda" id="ayudaCobro">Paga la factura completa.</p></div>`;
  abrirModal("Cobrar", html, `Cobrar ${Q(saldo)}`, async (fd) => {
    const d = datosForm(fd);
    if (d.metodo_pago !== "efectivo" && !d.referencia) throw new Error("Indique la referencia o el número de autorización.");
    const r = await api(`/api/billing/invoices/${id}/pay`, { method: "POST", body: { ...d, monto: Number(d.monto) } });
    const p = r.pagos[r.pagos.length - 1];
    avisar(`Recibo ${p.numero_recibo} por ${Q(p.monto)}${r.estado === "pagada" ? " · factura pagada" : ` · saldo ${Q(r.monto_total - r.monto_pagado)}`}`);
    estado.volverAFactura = id;
    refrescarCaja(id);
  });
  const c = $("#cuerpoCobro");
  const act = () => {
    const m = Number(c.querySelector('[name="monto"]').value || 0);
    const met = c.querySelector('[name="metodo_pago"]').value;
    $("#campoRef").hidden = met === "efectivo";
    c.querySelector('[name="referencia"]').required = met !== "efectivo";
    $("#modalAceptar").textContent = `Cobrar ${Q(m)}`;
    $("#ayudaCobro").textContent = m >= saldo ? "Paga la factura completa." : m > 0 ? `Abono: quedará un saldo de ${Q(saldo - m)}.` : "";
  };
  c.addEventListener("input", act);
  c.addEventListener("change", act);
  act();
}

function formAnularFactura(id) {
  abrirModal("Anular factura", `<label><span class="requerido">Motivo</span><input name="motivo" required minlength="5" maxlength="200" placeholder="Error en los cargos"></label>
    <p class="ayuda">Solo se anulan facturas sin pagos. Si era la cuenta de una consulta o internamiento, se puede volver a emitir.</p>`,
  "Anular factura", async (fd) => {
    await api(`/api/billing/invoices/${id}/void`, { method: "POST", body: datosForm(fd) });
    avisar("Factura anulada");
    refrescarCaja(id);
  });
}

async function formArancel(codigo) {
  const lista = await aranceles();
  // En laboratorio y odontología la categoría es fija: exámenes y procedimientos del catálogo
  const fija = { laboratorio: "examen", odontologia: "procedimiento" }[estado.inst];
  const a = lista.find((x) => x.codigo === codigo) || { codigo: "", descripcion: "", categoria: fija || "consulta", precio: "", activo: true };
  const lab = Boolean(fija);
  const cats = Object.entries(CATEGORIAS).filter(([k]) => (estado.inst === "hospital" ? !["vacunacion", "examen"].includes(k) : estado.inst === "pediatrico" ? ["consulta", "vacunacion", "procedimiento", "medicamento", "otro"].includes(k) : k === fija));
  abrirModal(codigo ? `Editar ${codigo}` : "Nuevo arancel", `<div class="rejilla">
      <label><span class="requerido">Código</span><input name="codigo_arancel" required maxlength="15" value="${esc(a.codigo)}" ${codigo ? "readonly" : ""} placeholder="CURACION"></label>
      <label><span class="requerido">Precio (Q)</span><input name="precio" type="number" required min="0" max="100000" step="0.01" value="${a.precio}"></label>
      <label class="doble"><span class="requerido">Servicio</span><input name="descripcion" required minlength="3" maxlength="120" value="${esc(a.descripcion)}"></label>
      <label>Categoría<select name="categoria" ${lab ? "disabled" : ""}>${opciones(cats, a.categoria)}</select></label>
      <label class="check"><input type="checkbox" name="activo" value="1" ${a.activo ? "checked" : ""}> Disponible para facturar</label>
    </div><p class="ayuda">El cambio de precio aplica a las facturas nuevas; las emitidas conservan su precio.</p>`,
  "Guardar", async (fd) => {
    const d = datosForm(fd);
    await api("/api/billing/tariffs", { method: "POST", body: { codigo: d.codigo_arancel.toUpperCase(), descripcion: d.descripcion,
      categoria: fija || d.categoria, precio: Number(d.precio), activo: fd.get("activo") === "1" } });
    avisar("Arancel guardado");
    estado.aranceles = null;
    if (estado.pagina === "cobros") pintarListaCaja();
  });
}

// Comprobante imprimible (se abre en una ventana y se manda a imprimir)
async function imprimirFactura(id) {
  const f = estado.facturasCache[id] || await api(`/api/billing/invoices/${id}`);
  const inst = INST[estado.inst]?.nombre || "";
  const w = window.open("", "_blank", "width=720,height=900");
  if (!w) { avisar("Permita las ventanas emergentes para imprimir", true); return; }
  w.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${esc(f.numero_factura)}</title>
    <style>body{font:14px system-ui,sans-serif;color:#1d2a33;margin:32px}h1{font-size:20px;margin:0}table{width:100%;border-collapse:collapse;margin:16px 0}
    td,th{padding:6px 4px;border-bottom:1px solid #ddd;text-align:left}.n{text-align:right}tfoot td{font-weight:700;border:0}.t{color:#666;font-size:12px}
    .cab{display:flex;justify-content:space-between;border-bottom:2px solid #1d2a33;padding-bottom:10px;margin-bottom:12px}</style></head><body>
    <div class="cab"><div><h1>${esc(inst)}</h1><div class="t">Comprobante de servicios · documento interno, no es factura electrónica FEL</div></div>
      <div style="text-align:right"><b>${esc(f.numero_factura)}</b><br>${fecha(f.fecha_emision, true)}<br>${esc(ESTADO_FACTURA[f.estado]?.[0] || f.estado)}</div></div>
    <div><b>NIT:</b> ${esc(f.nit)} &nbsp; <b>Nombre:</b> ${esc(f.nombre_facturacion)} &nbsp; <b>Paciente:</b> ${esc(f.paciente)}</div>
    <table><thead><tr><th>Concepto</th><th class="n">Cant.</th><th class="n">Precio</th><th class="n">Subtotal</th></tr></thead>
    <tbody>${f.detalle.map((d) => `<tr><td>${esc(d.concepto)}</td><td class="n">${Number(d.cantidad)}</td><td class="n">${Q(d.precio_unitario)}</td><td class="n">${Q(d.subtotal)}</td></tr>`).join("")}</tbody>
    <tfoot><tr><td colspan="3" class="n">Total</td><td class="n">${Q(f.monto_total)}</td></tr><tr><td colspan="3" class="n">Pagado</td><td class="n">${Q(f.monto_pagado)}</td></tr>
    <tr><td colspan="3" class="n">Saldo</td><td class="n">${Q(f.estado === "anulada" ? 0 : f.monto_total - f.monto_pagado)}</td></tr></tfoot></table>
    ${f.pagos.length ? `<b>Pagos</b><table>${f.pagos.map((p) => `<tr><td>${esc(p.numero_recibo)}</td><td>${fecha(p.fecha_pago, true)}</td><td>${esc(texto(p.metodo_pago))}${p.referencia ? ` · ${esc(p.referencia)}` : ""}</td><td class="n">${Q(p.monto)}</td></tr>`).join("")}</table>` : ""}
    <script>window.onload=()=>window.print()<\/script></body></html>`);
  w.document.close();
}

// ---- Cuenta del paciente (pestaña de la ficha)
async function cargarCuentaPaciente() {
  const caja = $("#cuentaPaciente");
  if (!caja) return;
  const id = estado.historial.paciente.id_paciente;
  try {
    const facturas = await api(`/api/billing/invoices?id_paciente=${id}`);
    facturas.forEach((f) => { estado.facturasCache[f.id_factura] = { ...estado.facturasCache[f.id_factura], ...f }; });
    const saldo = facturas.filter((f) => f.estado !== "anulada").reduce((s, f) => s + f.saldo, 0);
    caja.innerHTML = `<div class="cuenta-resumen"><div><span class="tenue">Saldo pendiente</span><b class="${saldo > 0 ? "saldo-pend" : ""}">${Q(saldo)}</b></div>
        <button type="button" class="btn primario chico" data-accion="nueva-factura">+ Nueva factura</button></div>
      <div class="panel">${facturas.length ? tablaFacturas(facturas, false) : '<div class="vacio-tabla"><p>Este paciente no tiene facturas.</p></div>'}</div>`;
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}

let tBusCaja;
$("#contenido").addEventListener("input", (ev) => {
  if (ev.target.id !== "busCaja") return;
  estado.busCaja = ev.target.value;
  clearTimeout(tBusCaja);
  tBusCaja = setTimeout(pintarListaCaja, 150);
});

// ---------------------------------------------------------- Estado de motores
// Se consulta desde la pantalla de inicio de sesión (la ruta es pública) y desde el
// aviso de "datos simulados". No requiere sesión.
const filaMotor = (m) => {
  const i = INST[m.clave] || {};
  return `<tr${m.clave === estado.inst ? ' class="fila-propia"' : ""}>
    <td><span class="punto" style="background:${i.color}"></span><b>${esc(i.nombre || m.institucion)}</b><br><span class="tenue">${esc(m.motor)}</span></td>
    <td>${m.real ? `${esc(m.version || "")}<br><span class="tenue">${esc(m.base_datos || "")}</span>`
      : `<span>Datos de prueba en memoria</span>${m.detalle_conexion ? `<details class="motor-detalle"><summary>Por qué no se conectó</summary><p>${esc(m.detalle_conexion)}</p></details>` : ""}`}</td>
    <td><ul class="conteos">${Object.entries(m.conteos || {}).map(([k, v]) => `<li><b>${esc(v)}</b> ${esc(ETIQUETAS[k] || k)}</li>`).join("") || '<li class="tenue">—</li>'}</ul></td>
    <td class="tenue">${esc(m.consistencia || m.detalle || "")}</td>
    <td class="nowrap"><span class="estado ${m.estado === "online" ? "activo" : (m.real ? "baja" : "alerta")}">${m.estado === "online" ? "Conectado" : (m.real ? "Error" : "Simulado")}</span>
      ${m.latencia_ms != null ? `<br><small class="tenue">${m.latencia_ms} ms</small>` : ""}</td>
  </tr>`;
};

async function verMotores() {
  abrirModal("Estado de los motores", `<p class="tenue">Consultando los cuatro motores…</p>`, null, null);
  $("#modal").classList.add("modal-ancho");
  try {
    const r = await api("/api/engine/status");
    $("#modalCuerpo").innerHTML = `
      <p class="tenue">Cada institución guarda sus datos en su propio motor. La lógica de negocio es la misma para todos:
        el enrutador elige el adaptador según la institución del usuario que inicia sesión.</p>
      <div class="tabla-scroll"><table class="tabla-datos tabla-motores">
        <thead><tr><th>Institución</th><th>Versión / base</th><th>Datos</th><th>Consistencia</th><th>Estado</th></tr></thead>
        <tbody>${r.motores.map(filaMotor).join("")}</tbody></table></div>
      <p class="tenue">Si alguno dice <b>Simulado</b>, ese motor no respondió al arrancar y lo que se registre en esa institución no se guardará.</p>`;
  } catch (e) {
    $("#modalCuerpo").innerHTML = `<p class="error">No se pudo consultar: ${esc(e.message)}</p>`;
  }
}
$("#modal").addEventListener("close", () => $("#modal").classList.remove("modal-ancho"));
$("#btnVerMotores").addEventListener("click", verMotores);

// Chips de "Conectado / Simulado" junto a cada institución en la pantalla de inicio de sesión
async function pintarEstadoLogin() {
  try {
    const r = await api("/api/engine/status");
    for (const m of r.motores) {
      const el = document.querySelector(`[data-estado-motor="${m.clave}"]`);
      if (!el) continue;
      const ok = m.estado === "online";
      el.className = `estado-motor ${ok ? "ok" : "mal"}`;
      el.textContent = ok ? "conectado" : m.real ? "error" : "simulado";
    }
  } catch (_) { /* sin servidor: se queda sin chips */ }
}

// ===================================================== Hospital: quirófanos y enfermería
const TURNOS = [["manana", "Mañana", "07:00–15:00"], ["tarde", "Tarde", "15:00–23:00"], ["noche", "Noche", "23:00–07:00"]];
const ESTADO_CX = {
  programada: ["Programada", "alerta"], en_curso: ["En curso", "critico"],
  realizada: ["Realizada", "activo"], cancelada: ["Cancelada", "baja"],
};
const MAX_PACIENTES_TURNO = 6;
const hoyISO = (d = new Date()) => d.toLocaleDateString("en-CA");
function turnoActual() {
  const d = new Date();
  const h = d.getHours();
  if (h >= 7 && h < 15) return { fecha: hoyISO(d), turno: "manana" };
  if (h >= 15 && h < 23) return { fecha: hoyISO(d), turno: "tarde" };
  const f = new Date(d);
  if (h < 7) f.setDate(f.getDate() - 1);   // la noche empieza el día anterior
  return { fecha: hoyISO(f), turno: "noche" };
}
const nombreTurno = (t) => (TURNOS.find((x) => x[0] === t) || [t, t])[1];
const horaDe = (v) => (v ? String(v).replace("T", " ").slice(11, 16) : "—");
const badgeCx = (e) => `<span class="estado ${ESTADO_CX[e][1]}">${ESTADO_CX[e][0]}</span>`;
const duracionTxt = (m) => (m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ""}` : `${m} min`);

estado.quirofanos = [];
estado.qxVista = "hoy";
estado.qxFecha = hoyISO();
estado.enfFecha = turnoActual().fecha;
estado.enfTurno = turnoActual().turno;

async function todosLosPacientes() {
  try { return await api("/api/patients?q="); } catch (_) { return estado.pacientes; }
}

// ---------------------------------------------------------------- Quirófanos
function tablaCirugias(lista, conPaciente = true) {
  return `<table class="tabla-datos">
    <thead><tr><th>Fecha y hora</th><th>Quirófano</th>${conPaciente ? "<th>Paciente</th>" : ""}<th>Procedimiento</th>
      <th>Cirujano</th><th>Duración</th><th>Estado</th><th class="acc">Acciones</th></tr></thead>
    <tbody>${lista.map((c) => `<tr class="${c.estado === "en_curso" ? "fila-cirugia" : ""}">
      <td class="nowrap"><b>${fecha(c.fecha_hora_programada, true)}</b>
        ${c.fecha_hora_inicio ? `<br><small class="tenue">Inició ${horaDe(c.fecha_hora_inicio)}${c.fecha_hora_fin ? `, terminó ${horaDe(c.fecha_hora_fin)}` : ""}</small>` : ""}</td>
      <td><b>${esc(c.codigo_quirofano)}</b></td>
      ${conPaciente ? `<td><button type="button" class="enlace-paciente" data-id="${c.id_paciente}" data-pestana-ir="especial">${esc(c.paciente_nombre)}</button></td>` : ""}
      <td>${esc(c.procedimiento)}${c.tipo === "urgencia" ? ` <span class="estado critico">Urgencia</span>` : ""}
        ${c.motivo_cancelacion ? `<br><small class="tenue">Cancelada: ${esc(c.motivo_cancelacion)}</small>` : ""}
        ${c.estado === "realizada" && c.notas_operatorias ? `<br><small class="tenue">${esc(c.notas_operatorias)}</small>` : ""}</td>
      <td>${esc(c.cirujano_nombre)}</td>
      <td class="nowrap">${duracionTxt(c.duracion_estimada_min)}</td>
      <td>${badgeCx(c.estado)}</td>
      <td class="acc">${c.estado === "programada"
        ? `<button type="button" class="btn primario chico" data-iniciar-cx="${c.id_cirugia}">Iniciar</button><button type="button" class="btn sutil chico" data-cancelar-cx="${c.id_cirugia}">Cancelar</button>`
        : c.estado === "en_curso" ? `<button type="button" class="btn primario chico" data-finalizar-cx="${c.id_cirugia}">Finalizar</button>` : ""}</td>
    </tr>`).join("")}</tbody></table>`;
}

async function pintarQuirofanos() {
  cabecera({ titulo: "Quirófanos", acciones: btnAccion("programar-cx", "+ Programar cirugía") });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  const hoy = hoyISO();
  const filtro = estado.qxVista === "pendientes" ? "pendientes=1" : `fecha=${estado.qxVista === "hoy" ? hoy : estado.qxFecha}`;
  try {
    const [salas, lista, deHoy] = await Promise.all([
      api("/api/hospital/rooms"), api(`/api/hospital/surgeries?${filtro}`), api(`/api/hospital/surgeries?fecha=${hoy}`),
    ]);
    if (estado.pagina !== "quirofanos") return;
    estado.quirofanos = salas;
    const ahora = new Date().toLocaleString("sv-SE").slice(0, 16);
    const tablero = salas.map((q) => {
      const enCurso = deHoy.find((c) => c.codigo_quirofano === q.codigo && c.estado === "en_curso");
      const proxima = deHoy.filter((c) => c.codigo_quirofano === q.codigo && c.estado === "programada" && c.fecha_hora_programada >= ahora.slice(0, 10))
        .sort((a, b) => a.fecha_hora_programada.localeCompare(b.fecha_hora_programada))[0];
      return `<div class="sala ${enCurso ? "ocupada" : ""} ${q.estado !== "disponible" ? "mantenimiento" : ""}">
        <div class="sala-cab"><b>${esc(q.codigo)}</b>
          <span class="estado ${q.estado !== "disponible" ? "baja" : (enCurso ? "critico" : "activo")}">${q.estado !== "disponible" ? "Mantenimiento" : (enCurso ? "En uso" : "Libre")}</span></div>
        <small class="tenue">${esc(q.descripcion)}</small>
        ${enCurso ? `<p><b>${esc(enCurso.paciente_nombre)}</b><br>${esc(enCurso.procedimiento)}<br><small>Desde las ${horaDe(enCurso.fecha_hora_inicio)} · ${esc(enCurso.cirujano_nombre)}</small></p>`
          : proxima ? `<p><small class="tenue">Próxima hoy</small><br><b>${horaDe(proxima.fecha_hora_programada)}</b> ${esc(proxima.procedimiento)}</p>`
          : `<p class="tenue"><small>Sin más cirugías hoy</small></p>`}
      </div>`;
    }).join("");
    $("#vista").innerHTML = `
      <div class="salas">${tablero}</div>
      <div class="barra-filtros">
        ${pestanas([["hoy", `Hoy (${deHoy.length})`], ["pendientes", "Pendientes"], ["fecha", "Otra fecha"]], estado.qxVista, "data-qx-vista")}
        ${estado.qxVista === "fecha" ? `<label class="fecha-filtro">Fecha<input type="date" id="qxFecha" value="${estado.qxFecha}"></label>` : ""}
      </div>
      <div class="panel">${lista.length ? tablaCirugias(lista)
        : `<div class="vacio-tabla"><p>No hay cirugías ${estado.qxVista === "pendientes" ? "pendientes" : "en esa fecha"}.</p>${btnAccion("programar-cx", "+ Programar cirugía")}</div>`}</div>`;
  } catch (e) {
    $("#vista").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

async function formCirugia(idPaciente = null) {
  if (!estado.quirofanos.length) { try { estado.quirofanos = await api("/api/hospital/rooms"); } catch (_) { /* */ } }
  const pacientes = idPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const manana = new Date(Date.now() + 86400000);
  const fechaDef = `${hoyISO(manana)}T08:00`;
  const html = `<div class="rejilla">
    ${idPaciente ? `<p class="completo">Paciente: <b>${esc(estado.historial.paciente.nombres)} ${esc(estado.historial.paciente.apellidos)}</b></p>`
      : `<label class="doble"><span class="requerido">Paciente</span><select name="id_paciente" required>
          <option value="">Seleccione…</option>${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)}${p.estado === "hospitalizado" ? " (hospitalizado)" : ""}</option>`).join("")}
        </select></label>`}
    <label class="completo"><span class="requerido">Procedimiento</span><input name="procedimiento" required maxlength="200" placeholder="Colecistectomía laparoscópica"></label>
    ${campoProfesional("Cirujano")}
    <label><span class="requerido">Quirófano</span><select name="codigo_quirofano" required>
      ${estado.quirofanos.map((q) => `<option value="${esc(q.codigo)}" ${q.estado !== "disponible" ? "disabled" : ""}>${esc(q.codigo)} — ${esc(q.descripcion)}${q.estado !== "disponible" ? " (mantenimiento)" : ""}</option>`).join("")}
    </select></label>
    <label>Tipo<select name="tipo">${opciones([["electiva", "Electiva (programada)"], ["urgencia", "Urgencia"]])}</select></label>
    ${campo("fecha_hora_programada", "Fecha y hora", { tipo: "datetime-local", req: true, valor: fechaDef })}
    <label><span class="requerido">Duración estimada (min)</span><input name="duracion_estimada_min" type="number" min="15" max="720" step="15" value="60" required></label>
    <label class="completo">Indicaciones prequirúrgicas<textarea name="notas_operatorias" placeholder="Ayuno, profilaxis, reserva de sangre…"></textarea></label>
  </div>
  <p class="ayuda">La base de datos rechaza la cirugía si el quirófano o el cirujano ya están ocupados en ese horario.</p>`;
  abrirModal("Programar cirugía", html, "Programar cirugía", async (fd) => {
    const d = datosForm(fd);
    d.id_medico = d.id_profesional;
    delete d.id_profesional;
    if (idPaciente) d.id_paciente = idPaciente;
    const c = await api("/api/hospital/surgeries", { method: "POST", body: d });
    avisar(`Cirugía programada en ${c.codigo_quirofano} para el ${fecha(c.fecha_hora_programada, true)}`);
    refrescarHospital();
  });
}

async function accionCirugia(id, accion) {
  if (accion === "start") {
    try {
      await api(`/api/hospital/surgeries/${id}/start`, { method: "POST" });
      avisar("Cirugía iniciada");
      refrescarHospital();
    } catch (e) { avisar(e.message, true); }
    return;
  }
  const fin = accion === "finish";
  abrirModal(fin ? "Finalizar cirugía" : "Cancelar cirugía",
    fin ? `<label>Notas operatorias<textarea name="notas" placeholder="Hallazgos, complicaciones, indicaciones postoperatorias"></textarea></label>`
        : `<label><span class="requerido">Motivo de la cancelación</span><input name="motivo" required minlength="5" maxlength="200"></label>`,
    fin ? "Finalizar cirugía" : "Cancelar cirugía", async (fd) => {
      await api(`/api/hospital/surgeries/${id}/${accion}`, { method: "POST", body: datosForm(fd) });
      avisar(fin ? "Cirugía finalizada" : "Cirugía cancelada");
      refrescarHospital();
    });
}

function refrescarHospital() {
  if (estado.pagina === "paciente" && estado.idSeleccionado) abrirPaciente(estado.idSeleccionado, "especial");
  else ir(estado.pagina);
}


// ------------------------------------------------------- Habitaciones y camas
const TIPO_HAB = { individual: "Individual", compartida: "Compartida", aislamiento: "Aislamiento", intensivo: "Cuidados intensivos" };
const VIAS = ["Oral", "Intravenosa", "Intramuscular", "Subcutánea", "Sublingual", "Inhalada", "Tópica", "Rectal"];
const FRECUENCIAS = [[4, "Cada 4 horas"], [6, "Cada 6 horas"], [8, "Cada 8 horas"], [12, "Cada 12 horas"], [24, "Una vez al día"], [48, "Cada 48 horas"]];
const ts = (v) => String(v || "").replace("T", " ").slice(0, 16);
const ahoraTs = (masMin = 0) => new Date(Date.now() + masMin * 60000).toLocaleString("sv-SE").slice(0, 16);
estado.departamentos = [];

async function cargarDepartamentos() {
  try { estado.departamentos = await api("/api/hospital/departments"); } catch (_) { estado.departamentos = []; }
  return estado.departamentos;
}
const habitacionDe = (codigo) => {
  for (const d of estado.departamentos) {
    const h = d.habitaciones.find((x) => x.codigo === codigo);
    if (h) return { ...h, departamento: d.nombre, piso: d.piso };
  }
  return null;
};
const libres = (h) => (h.estado === "disponible" ? h.camas - h.ocupantes.length : 0);

// <select> de habitaciones agrupado por departamento; solo se pueden elegir las que tienen cama libre
function selectHabitacion(nombre, excepto = null, req = false) {
  const grupos = estado.departamentos.map((d) => `<optgroup label="${esc(d.nombre)} · piso ${d.piso}">
    ${d.habitaciones.filter((h) => h.codigo !== excepto).map((h) => {
      const l = libres(h);
      const txt = h.estado !== "disponible" ? "en mantenimiento" : l ? `${l} de ${h.camas} cama${h.camas > 1 ? "s" : ""} libre${l > 1 ? "s" : ""}` : "llena";
      return `<option value="${esc(h.codigo)}" ${l ? "" : "disabled"}>${esc(h.codigo)} — ${esc(TIPO_HAB[h.tipo] || h.tipo)}, ${txt}</option>`;
    }).join("")}</optgroup>`).join("");
  return `<select name="${nombre}" ${req ? "required" : ""}><option value="">Seleccione…</option>${grupos}</select>`;
}

async function pintarHabitaciones() {
  cabecera({ titulo: "Habitaciones", acciones: btnAccion("nuevo-depto", "+ Departamento", "sutil") + btnAccion("nueva-hab", "+ Agregar habitación") });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  try {
    const deps = await cargarDepartamentos();
    if (estado.pagina !== "habitaciones") return;
    const camas = deps.reduce((s, d) => s + d.camas, 0);
    const ocupadas = deps.reduce((s, d) => s + d.ocupadas, 0);
    $("#vista").innerHTML = `
      <p class="resumen-camas"><b>${ocupadas}</b> de <b>${camas}</b> camas ocupadas · <b>${camas - ocupadas}</b> libres</p>
      ${deps.map((d) => `<section class="depto">
        <header class="depto-cab">
          <div><h2>${esc(d.nombre)}</h2><small class="tenue">Piso ${d.piso}${d.extension ? ` · extensión ${esc(d.extension)}` : ""}</small></div>
          <div class="depto-acciones">
            <div class="depto-ocupacion"><span class="barra-carga" aria-hidden="true"><span style="width:${d.camas ? (d.ocupadas / d.camas) * 100 : 0}%"></span></span>
              <span>${d.ocupadas}/${d.camas} camas</span></div>
            <button type="button" class="btn sutil chico" data-nueva-hab="${d.id_departamento}">+ Habitación</button>
          </div>
        </header>
        <div class="habs">${d.habitaciones.map((h) => `<article class="hab ${h.estado !== "disponible" ? "mantenimiento" : libres(h) ? "" : "llena"}">
          <div class="hab-cab"><b>${esc(h.codigo)}</b>
            <span class="hab-meta"><small class="tenue">${esc(TIPO_HAB[h.tipo] || h.tipo)}${h.estado !== "disponible" ? " · mantenimiento" : ""}</small>
              <button type="button" class="btn-icono" data-editar-hab="${esc(h.codigo)}" aria-label="Editar ${esc(h.codigo)}" title="Editar camas y estado">Editar</button></span></div>
          <ul class="camas">${Array.from({ length: h.camas }, (_, i) => {
            const o = h.ocupantes[i];
            return o ? `<li class="cama ocupada"><span class="cama-n">Cama ${i + 1}</span>
                <button type="button" class="enlace-paciente" data-id="${o.id_paciente}" data-pestana-ir="especial">${esc(o.paciente)}</button>
                <small class="tenue">Desde ${fecha(o.fecha_ingreso)}</small>
                <button type="button" class="btn sutil chico" data-cambiar-hab="${o.id_hospitalizacion}" data-hab-actual="${esc(h.codigo)}">Cambiar habitación</button></li>`
              : h.estado !== "disponible"
                ? `<li class="cama"><span class="cama-n">Cama ${i + 1}</span><span class="tenue">Fuera de servicio</span></li>`
                : `<li class="cama libre"><span class="cama-n">Cama ${i + 1}</span><span class="tenue">Libre</span>
                    <button type="button" class="btn sutil chico" data-ingresar-hab="${esc(h.codigo)}">+ Ingresar paciente</button></li>`;
          }).join("")}</ul>
        </article>`).join("") || `<p class="tenue relleno">Sin habitaciones. <button type="button" class="btn sutil chico" data-nueva-hab="${d.id_departamento}">+ Agregar la primera</button></p>`}</div>
      </section>`).join("")}
      <p class="ayuda">Para ocupar una cama use “+ Ingresar paciente” en una cama libre, o marque “Ingresar al paciente en el hospital” al registrar su consulta.
        La base de datos no permite ocupar más camas de las que tiene una habitación.</p>`;
  } catch (e) {
    $("#vista").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}


// Ingreso directo desde una cama libre: registra la evaluación de ingreso (consulta)
// y la hospitalización en la misma transacción, igual que el formulario de consulta.
async function formIngresoCama(codigo) {
  const hab = habitacionDe(codigo);
  let pacientes = [];
  let ingresados = [];
  try {
    [pacientes, ingresados] = await Promise.all([todosLosPacientes(), api("/api/hospital/hospitalizations")]);
  } catch (e) { avisar(e.message, true); return; }
  const yaIngresados = new Set(ingresados.map((h) => h.id_paciente));
  const candidatos = pacientes.filter((p) => !ESTADOS_BAJA.includes(p.estado) && !yaIngresados.has(p.id_paciente))
    .sort((a, b) => `${a.apellidos} ${a.nombres}`.localeCompare(`${b.apellidos} ${b.nombres}`));
  if (!candidatos.length) {
    avisar("Todos los pacientes activos ya están ingresados. Registre al paciente nuevo en Pacientes.", true);
    return;
  }
  const html = `
    <div class="rejilla">
      <p class="completo">Habitación <b>${esc(codigo)}</b>${hab ? ` · ${esc(hab.departamento)} · ${esc(TIPO_HAB[hab.tipo] || hab.tipo)}` : ""}</p>
      <label class="completo"><span class="requerido">Paciente</span>
        <select name="id_paciente" required>
          <option value="">Seleccione…</option>
          ${candidatos.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)} · DPI ${esc(p.dpi || "—")}</option>`).join("")}
        </select>
      </label>
      ${campoProfesional("Médico que ingresa")}
      <label>Tipo de ingreso<select name="tipo_consulta">${opciones([["emergencia", "Por emergencia"], ["ordinaria", "Programado"]], "emergencia")}</select></label>
      <label class="completo"><span class="requerido">Motivo de ingreso</span>
        <input name="motivo" required maxlength="200" placeholder="Ej.: neumonía adquirida en la comunidad, observación"></label>
      ${campo("presion_arterial", "Presión arterial", { extra: 'placeholder="120/80"' })}
      ${campo("temperatura", "Temperatura (°C)", { tipo: "number", extra: 'step="0.1" min="30" max="45"' })}
      <p class="ayuda completo">Se registra como la consulta de ingreso del paciente (con su cobro en Caja) y la cama queda ocupada.</p>
    </div>`;
  abrirModal("Ingresar paciente", html, "Ingresar", async (fd) => {
    const d = datosForm(fd);
    d.id_paciente = Number(d.id_paciente);
    d.requiere_hospitalizacion = true;
    d.numero_habitacion = codigo;
    d.motivo_hospitalizacion = d.motivo;
    await api("/api/consultations", { method: "POST", body: d });
    avisar(`${nombreDe(d.id_paciente)} ingresado en ${codigo}`);
    await cargarPacientes("");
    pintarHabitaciones();
  });
}

// Código sugerido para una habitación nueva: mismo prefijo del departamento y el número siguiente
function codigoSugerido(idDep) {
  const d = estado.departamentos.find((x) => x.id_departamento === Number(idDep));
  const codigos = (d?.habitaciones || []).map((h) => h.codigo.match(/^([A-Z]{2,4})-(\d{2,3})$/)).filter(Boolean);
  if (!codigos.length) return "";
  const prefijo = codigos[0][1];
  const max = Math.max(...codigos.filter((m) => m[1] === prefijo).map((m) => Number(m[2])));
  return `${prefijo}-${String(max + 1).padStart(codigos[0][2].length, "0")}`;
}

async function formHabitacion(idDep = null) {
  if (!estado.departamentos.length) await cargarDepartamentos();
  if (!estado.departamentos.length) { avisar("Primero registre un departamento", true); return; }
  const dep = idDep ? Number(idDep) : estado.departamentos[0].id_departamento;
  const html = `<div class="rejilla">
      <label class="doble"><span class="requerido">Departamento</span><select name="id_departamento" required>
        ${opciones(estado.departamentos.map((d) => [String(d.id_departamento), `${d.nombre} · piso ${d.piso}`]), String(dep))}</select></label>
      <label><span class="requerido">Código</span><input name="codigo" required value="${esc(codigoSugerido(dep))}" placeholder="MI-104"></label>
      <label><span class="requerido">Camas</span><input name="camas" type="number" required value="2"></label>
      <label class="doble">Tipo<select name="tipo">${opciones(Object.entries(TIPO_HAB), "compartida")}</select></label>
    </div>
    <p class="ayuda">De 1 a 6 camas por habitación. El código lleva 2 a 4 letras, guion y 2 o 3 números.</p>`;
  abrirModal("Agregar habitación", html, "Agregar habitación", async (fd) => {
    const h = await api("/api/hospital/beds", { method: "POST", body: datosForm(fd) });
    avisar(`Habitación ${h.codigo} agregada con ${h.camas} cama${h.camas > 1 ? "s" : ""}`);
    refrescarHospital();
  });
  const selDep = $('#modalCuerpo [name="id_departamento"]');
  selDep.addEventListener("change", () => { $('#modalCuerpo [name="codigo"]').value = codigoSugerido(selDep.value); });
}

async function formEditarHabitacion(codigo) {
  await cargarDepartamentos();
  const h = habitacionDe(codigo);
  if (!h) return;
  const ocupadas = h.ocupantes.length;
  const html = `<div class="dosis-resumen"><b>${esc(h.codigo)} · ${esc(h.departamento)}</b>
      <span class="tenue">${ocupadas ? `${ocupadas} paciente${ocupadas > 1 ? "s" : ""} internado${ocupadas > 1 ? "s" : ""} ahora` : "Sin pacientes ahora"}</span></div>
    <div class="rejilla">
      <label><span class="requerido">Camas</span><input name="camas" type="number" required min="${Math.max(1, ocupadas)}" max="6" step="1" value="${h.camas}"></label>
      <label>Tipo<select name="tipo">${opciones(Object.entries(TIPO_HAB), h.tipo)}</select></label>
      <label class="doble">Estado<select name="estado">
        <option value="disponible" ${h.estado === "disponible" ? "selected" : ""}>Disponible</option>
        <option value="mantenimiento" ${h.estado === "mantenimiento" ? "selected" : ""} ${ocupadas ? "disabled" : ""}>En mantenimiento${ocupadas ? " (tiene pacientes)" : ""}</option>
      </select></label>
    </div>
    <p class="ayuda">${ocupadas ? `No puede quedar con menos de ${ocupadas} cama${ocupadas > 1 ? "s" : ""}: la base de datos lo impide.` : "Una habitación en mantenimiento no recibe ingresos."}</p>`;
  abrirModal(`Editar habitación ${h.codigo}`, html, "Guardar cambios", async (fd) => {
    const r = await api(`/api/hospital/beds/${encodeURIComponent(codigo)}`, { method: "PUT", body: datosForm(fd) });
    avisar(`${r.codigo}: ${r.camas} cama${r.camas > 1 ? "s" : ""}${r.estado === "mantenimiento" ? ", en mantenimiento" : ""}`);
    refrescarHospital();
  });
}

function formDepartamento() {
  abrirModal("Nuevo departamento", `<div class="rejilla">
      <label class="doble"><span class="requerido">Nombre</span><input name="nombre" required placeholder="Ginecología y Obstetricia"></label>
      <label><span class="requerido">Piso</span><input name="piso" type="number" required value="1"></label>
      <label>Extensión<input name="extension" placeholder="510"></label>
    </div><p class="ayuda">Después agregue sus habitaciones y camas.</p>`,
  "Crear departamento", async (fd) => {
    const d = await api("/api/hospital/departments", { method: "POST", body: datosForm(fd) });
    avisar(`Departamento ${d.nombre} creado`);
    await cargarDepartamentos();
    if (estado.pagina === "habitaciones") pintarHabitaciones();
    formHabitacion(d.id_departamento);
  });
}

async function formCambiarHabitacion(idHosp, actual) {
  await cargarDepartamentos();
  const h = habitacionDe(actual);
  abrirModal("Cambiar de habitación", `<div class="rejilla">
      <p class="completo">Habitación actual: <b>${esc(actual)}</b>${h ? ` · ${esc(h.departamento)}` : ""}</p>
      <label class="completo"><span class="requerido">Nueva habitación</span>${selectHabitacion("numero_habitacion", actual, true)}</label>
    </div><p class="ayuda">Los turnos de enfermería y la medicación siguen con el paciente.</p>`,
  "Cambiar habitación", async (fd) => {
    const r = await api(`/api/hospital/hospitalizations/${idHosp}/room`, { method: "POST", body: datosForm(fd) });
    avisar(`Paciente trasladado de ${r.anterior} a ${r.numero_habitacion}`);
    refrescarHospital();
  });
}

// --------------------------------------------------- Medicación (kárdex)
estado.medicamentos = [];
const ESTADO_DOSIS = { pendiente: ["Pendiente", "alerta"], aplicada: ["Aplicada", "activo"], omitida: ["No aplicada", "baja"] };
const ESTADO_ORDEN = { activa: ["Activa", "activo"], suspendida: ["Suspendida", "baja"], finalizada: ["Finalizada", "neutro"] };
const atrasada = (d) => d.estado === "pendiente" && ts(d.fecha_hora_programada) < ahoraTs(-60);
const tocaYa = (d) => d.estado === "pendiente" && ts(d.fecha_hora_programada) <= ahoraTs(60);

async function formOrdenMedicacion(idHosp) {
  if (!estado.medicamentos.length) { try { estado.medicamentos = await api("/api/hospital/medicines"); } catch (_) { /* */ } }
  const inicio = ahoraTs(60).slice(0, 13) + ":00";
  const html = `<div class="rejilla">
      <label class="doble"><span class="requerido">Medicamento</span><select name="id_medicamento" required>
        <option value="">Seleccione…</option>${estado.medicamentos.map((m) => `<option value="${m.id_medicamento}">${esc(m.nombre)} — ${esc(m.presentacion)}</option>`).join("")}
      </select></label>
      ${campo("dosis", "Dosis", { req: true, extra: 'maxlength="50" placeholder="500 mg"' })}
      <label><span class="requerido">Vía</span><select name="via_administracion">${opciones(VIAS.map((v) => [v, v]), "Intravenosa")}</select></label>
      <label><span class="requerido">Frecuencia</span><select name="frecuencia_horas">${opciones(FRECUENCIAS.map(([h, t]) => [String(h), t]), "8")}</select></label>
      <label><span class="requerido">Durante (días)</span><input name="duracion_dias" type="number" min="1" max="30" value="3" required></label>
      ${campo("fecha_inicio", "Primera dosis", { tipo: "datetime-local", req: true, valor: inicio.replace(" ", "T") })}
      ${campoProfesional("Indicado por")}
      <label class="completo">Indicaciones<input name="indicaciones" maxlength="200" placeholder="Pasar en 30 minutos, diluido en 100 ml de SSN"></label>
    </div>
    <p class="ayuda" id="resumenOrden"></p>`;
  abrirModal("Indicar medicamento", html, "Indicar medicamento", async (fd) => {
    const d = datosForm(fd);
    d.id_medico = d.id_profesional;
    delete d.id_profesional;
    const o = await api("/api/hospital/medication", { method: "POST", body: { ...d, id_hospitalizacion: idHosp } });
    avisar(`${o.medicamento}: ${o.total_dosis} dosis programadas`);
    refrescarHospital();
  });
  const f = $("#modalForm");
  const resumen = () => {
    const h = Number(f.frecuencia_horas.value), dias = Number(f.duracion_dias.value) || 0;
    const n = Math.ceil((dias * 24) / h);
    $("#resumenOrden").textContent = n > 0 ? `Se programarán ${n} dosis, cada una con su enfermero encargado según el turno.` : "";
  };
  f.frecuencia_horas.addEventListener("change", resumen);
  f.duracion_dias.addEventListener("input", resumen);
  resumen();
}

function formSuspenderOrden(id) {
  abrirModal("Suspender medicamento", `<label><span class="requerido">Motivo</span><input name="motivo" required minlength="5" maxlength="200" placeholder="Cambio de antibiótico"></label>
    <p class="ayuda">Las dosis pendientes se cancelan. Las ya aplicadas quedan en el registro.</p>`,
  "Suspender", async (fd) => {
    await api(`/api/hospital/medication/${id}/suspend`, { method: "POST", body: datosForm(fd) });
    avisar("Medicamento suspendido");
    refrescarHospital();
  });
}

const opcionesEnfermeros = (sel) => enfermerosActivos().map((n) => `<option value="${n.id_profesional}" ${n.id_profesional === sel ? "selected" : ""}>${esc(n.nombre_completo)}</option>`).join("");

function formRegistrarDosis(dosis, aplicar = true) {
  const encargado = dosis.id_encargado;
  const html = `<div class="dosis-resumen">
      <b>${esc(dosis.medicamento)} ${esc(dosis.dosis)}</b> · ${esc(dosis.via_administracion)}
      <span class="tenue">Programada ${fecha(dosis.fecha_hora_programada, true)} · ${esc(dosis.paciente)} (${esc(dosis.numero_habitacion)})</span>
      ${dosis.indicaciones ? `<span>${esc(dosis.indicaciones)}</span>` : ""}
    </div>
    <div class="rejilla">
      <label class="doble"><span class="${aplicar ? "requerido" : ""}">${aplicar ? "Aplicada por" : "Enfermero que reporta"}</span>
        <select name="id_enfermero" ${aplicar ? "required" : ""}><option value="">Seleccione…</option>${opcionesEnfermeros(encargado)}</select></label>
      ${aplicar ? `<label class="completo">Observaciones<input name="observaciones" maxlength="200" placeholder="Sin reacciones adversas"></label>`
        : `<label class="completo"><span class="requerido">¿Por qué no se aplicó?</span><input name="motivo" required minlength="5" maxlength="200" placeholder="Paciente en ayuno para cirugía"></label>`}
    </div>
    <p class="ayuda">${encargado ? `Encargado del turno: <b>${esc(dosis.encargado)}</b>.` : "Nadie tiene asignado a este paciente en ese turno."}
      ${aplicar ? " Se guarda la hora actual como hora de aplicación." : ""}</p>`;
  abrirModal(aplicar ? "Registrar aplicación" : "Dosis no aplicada", html, aplicar ? "Registrar aplicación" : "Registrar omisión", async (fd) => {
    await api(`/api/hospital/doses/${dosis.id_administracion}/${aplicar ? "apply" : "omit"}`, { method: "POST", body: datosForm(fd) });
    avisar(aplicar ? "Dosis aplicada" : "Omisión registrada");
    refrescarHospital();
  });
}

// Tabla de dosis: la usan la ficha del paciente y la página de Enfermería
function tablaDosis(lista, conPaciente = false) {
  return `<table class="tabla-datos tabla-dosis">
    <thead><tr><th>Hora</th>${conPaciente ? "<th>Paciente</th>" : ""}<th>Medicamento</th><th>Encargado</th><th>Estado</th><th class="acc"></th></tr></thead>
    <tbody>${lista.map((d) => {
      const [txt, cls] = ESTADO_DOSIS[d.estado] || [d.estado, ""];
      return `<tr class="${atrasada(d) ? "fila-atrasada" : ""}">
        <td class="nowrap"><b>${horaDe(d.fecha_hora_programada)}</b><br><small class="tenue">${fecha(d.fecha_hora_programada)} · ${nombreTurno(d.turno)}</small></td>
        ${conPaciente ? `<td><button type="button" class="enlace-paciente" data-id="${d.id_paciente}" data-pestana-ir="especial">${esc(d.paciente)}</button><br><small class="tenue">${esc(d.numero_habitacion)}</small></td>` : ""}
        <td><b>${esc(d.medicamento)}</b> ${esc(d.dosis)}<br><small class="tenue">${esc(d.via_administracion)}${d.indicaciones ? ` · ${esc(d.indicaciones)}` : ""}</small></td>
        <td>${d.encargado ? esc(d.encargado) : '<span class="sin-asignar">Sin asignar</span>'}</td>
        <td><span class="estado ${atrasada(d) ? "baja" : cls}">${atrasada(d) ? "Atrasada" : txt}</span>
          ${d.estado === "aplicada" ? `<br><small class="tenue">${esc(d.aplicada_por)} a las ${horaDe(d.fecha_hora_aplicada)}</small>` : ""}
          ${d.estado === "omitida" ? `<br><small class="tenue">${esc(d.observaciones)}</small>` : ""}</td>
        <td class="acc">${d.estado === "pendiente" && d.estado_orden === "activa"
          ? `${tocaYa(d) ? `<button type="button" class="btn primario chico" data-aplicar-dosis="${d.id_administracion}">Aplicar</button>` : ""}
             <button type="button" class="btn sutil chico" data-omitir-dosis="${d.id_administracion}">No aplicada</button>` : ""}</td>
      </tr>`;
    }).join("")}</tbody></table>`;
}

// ---------------------------------------------------------------- Enfermería
async function pintarEnfermeria() {
  cabecera({ titulo: "Enfermería" });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  try {
    const [hosp, turnos, dosis] = await Promise.all([
      api("/api/hospital/hospitalizations"), api(`/api/hospital/shifts?fecha=${estado.enfFecha}`),
      api(`/api/hospital/doses?fecha=${estado.enfFecha}&turno=${estado.enfTurno}`).catch(() => []),
    ]);
    if (estado.pagina !== "enfermeria") return;
    estado.cacheTurnos = turnos;
    guardarDosis(dosis);
    const pendientes = dosis.filter((d) => d.estado === "pendiente").length;
    const actual = turnoActual();
    const enTurno = turnos.filter((t) => t.turno === estado.enfTurno);
    const carga = enfermerosActivos().map((n) => ({ n, c: enTurno.filter((t) => t.id_enfermero === n.id_profesional).length }));
    $("#vista").innerHTML = `
      <div class="barra-filtros">
        ${pestanas(TURNOS.map(([k, t, h]) => [k, `${t} <small>${h}</small>${actual.fecha === estado.enfFecha && actual.turno === k ? ' <span class="ahora">ahora</span>' : ""}`]), estado.enfTurno, "data-turno-enf")}
        <label class="fecha-filtro">Fecha<input type="date" id="enfFecha" value="${estado.enfFecha}"></label>
      </div>
      <div class="enf-cols">
        <div class="panel">${hosp.length ? `<table class="tabla-datos">
          <thead><tr><th>Habitación</th><th>Paciente</th><th>Ingreso</th><th>Enfermeros en este turno</th><th class="acc"></th></tr></thead>
          <tbody>${hosp.map((h) => {
            const asignados = enTurno.filter((t) => t.id_hospitalizacion === h.id_hospitalizacion);
            return `<tr>
              <td><b>${esc(h.numero_habitacion)}</b>${h.departamento ? `<br><small class="tenue">${esc(h.departamento)}</small>` : ""}</td>
              <td><button type="button" class="enlace-paciente" data-id="${h.id_paciente}" data-pestana-ir="especial">${esc(h.paciente)}</button>
                ${h.en_cirugia ? ' <span class="estado critico">En cirugía</span>' : ""}<br><small class="tenue">${esc(h.motivo_ingreso)}</small></td>
              <td class="nowrap">${fecha(h.fecha_ingreso)}</td>
              <td>${asignados.length ? asignados.map((t) => `<span class="chip">${esc(t.enfermero_nombre)}
                  <button type="button" data-anular="${t.id_asignacion}" aria-label="Quitar a ${esc(t.enfermero_nombre)}">×</button></span>`).join("")
                : '<span class="sin-asignar">Sin enfermero asignado</span>'}</td>
              <td class="acc"><button type="button" class="btn primario chico" data-asignar="${h.id_hospitalizacion}">Asignar</button></td></tr>`;
          }).join("")}</tbody></table>`
          : `<div class="vacio-tabla"><p>No hay pacientes ingresados.</p>
             <p class="tenue">Se ingresan al registrar una consulta marcando "Ingresar al paciente".</p></div>`}</div>
        <section class="panel">
          <header class="panel-cab"><h2>Carga del turno</h2></header>
          <ul class="carga">${carga.map(({ n, c }) => `<li><span>${esc(n.nombre_completo)}</span>
            <span class="barra-carga" aria-hidden="true"><span style="width:${(c / MAX_PACIENTES_TURNO) * 100}%"></span></span>
            <b class="${c >= MAX_PACIENTES_TURNO ? "alerta-critica" : ""}">${c}/${MAX_PACIENTES_TURNO}</b></li>`).join("")
            || `<li class="tenue">No hay enfermeros activos. <button type="button" class="btn sutil chico" data-ir-enfermeros>Registrar</button></li>`}</ul>
        </section>
      </div>
      <section class="bloque-hosp bloque-dosis">
        <header class="panel-cab sin-borde"><h2>Medicamentos de este turno</h2>
          <span class="tenue">${dosis.length ? `${pendientes} pendiente${pendientes === 1 ? "" : "s"} de ${dosis.length}` : ""}</span></header>
        <div class="panel">${dosis.length ? tablaDosis(dosis, true)
          : `<p class="relleno tenue">No hay dosis programadas en el turno de ${nombreTurno(estado.enfTurno).toLowerCase()}. Los medicamentos se indican desde la ficha del paciente, en "Internamiento y cirugías".</p>`}</div>
      </section>`;
  } catch (e) {
    $("#vista").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

async function formAsignar(idHosp, fechaT = estado.enfFecha, turnoT = estado.enfTurno) {
  let turnos = [];
  try { turnos = await api(`/api/hospital/shifts?fecha=${fechaT}`); } catch (_) { /* */ }
  const activos = enfermerosActivos();
  const html = activos.length ? `<div class="rejilla">
      <label class="doble"><span class="requerido">Enfermero</span><select name="id_enfermero" required>
        <option value="">Seleccione…</option>
        ${activos.map((n) => {
          const c = turnos.filter((t) => t.id_enfermero === n.id_profesional && t.turno === turnoT).length;
          return `<option value="${n.id_profesional}" ${c >= MAX_PACIENTES_TURNO ? "disabled" : ""}>${esc(n.nombre_completo)} — ${c}/${MAX_PACIENTES_TURNO} pacientes${n.especialidad ? ` · ${esc(n.especialidad)}` : ""}</option>`;
        }).join("")}
      </select></label>
      ${campo("fecha", "Fecha", { tipo: "date", req: true, valor: fechaT })}
      <label><span class="requerido">Turno</span><select name="turno">${opciones(TURNOS.map(([k, t, h]) => [k, `${t} (${h})`]), turnoT)}</select></label>
      <label class="completo">Indicaciones para el turno<input name="observaciones" maxlength="200" placeholder="Signos vitales cada 4 horas"></label>
    </div><p class="ayuda">Máximo ${MAX_PACIENTES_TURNO} pacientes por enfermero en cada turno; la base de datos lo verifica.</p>`
    : `<div class="aviso-sin-personal">No hay enfermeros activos. <button type="button" class="btn sutil chico" data-ir-enfermeros>Registrar uno en Personal médico</button></div>`;
  abrirModal("Asignar enfermero", html, activos.length ? "Asignar" : "", async (fd) => {
    const d = datosForm(fd);
    await api("/api/hospital/shifts", { method: "POST", body: { ...d, id_hospitalizacion: idHosp } });
    avisar(`Enfermero asignado al turno de ${nombreTurno(d.turno).toLowerCase()}`);
    refrescarHospital();
  });
}

function confirmarAnular(id) {
  abrirModal("Quitar asignación", "<p>El enfermero dejará de estar a cargo de este paciente en ese turno. El registro queda anulado, no se borra.</p>",
    "Quitar asignación", async () => {
      await api(`/api/hospital/shifts/${id}/annul`, { method: "POST" });
      avisar("Asignación anulada");
      refrescarHospital();
    });
}

function formAlta(idHosp) {
  abrirModal("Egreso del paciente", `<div class="rejilla">
      <label class="doble"><span class="requerido">Tipo de egreso</span><select name="tipo">${opciones([["alta", "Alta médica"], ["referido", "Referido a otra institución"]])}</select></label>
    </div>
    <p>Se registra la fecha de egreso, se cancelan sus cirugías programadas de este internamiento y se anulan los turnos de enfermería de días siguientes.</p>`,
    "Registrar egreso", async (fd) => {
      const r = await api(`/api/hospital/hospitalizations/${idHosp}/discharge`, { method: "POST", body: datosForm(fd) });
      avisar(`Egreso registrado${r.cirugias_canceladas ? ` · ${r.cirugias_canceladas} cirugía(s) cancelada(s)` : ""}`);
      await cargarPacientes();
      refrescarHospital();
    });
}

// Pestaña del paciente: internamiento, enfermería y cirugías
function pintarHospitalPaciente() {
  const e = estado.especializado || {};
  const hp = estado.hospPaciente || { cirugias: [], turnos: [], ordenes: [], dosis: [] };
  const activo = estado.historial.estado === "activo";
  const internamientos = e.hospitalizaciones || [];
  const ingresado = internamientos.find((h) => h.estado === "ingresado");
  const desde = turnoActual().fecha;   // incluye el turno de noche que empezó ayer
  const turnos = hp.turnos.filter((t) => t.fecha >= desde).sort((a, b) => (a.fecha + TURNOS.findIndex((x) => x[0] === a.turno))
    .localeCompare(b.fecha + TURNOS.findIndex((x) => x[0] === b.turno)));
  return `
    <section class="bloque-hosp">
      <header class="panel-cab sin-borde"><h2>Internamiento</h2></header>
      <div class="panel">${internamientos.length ? `<table class="tabla-datos">
        <thead><tr><th>Habitación</th><th>Ingreso</th><th>Egreso</th><th>Motivo</th><th>Estado</th><th class="acc"></th></tr></thead>
        <tbody>${internamientos.map((h) => `<tr>
          <td><b>${esc(h.numero_habitacion)}</b>${habitacionDe(h.numero_habitacion) ? `<br><small class="tenue">${esc(habitacionDe(h.numero_habitacion).departamento)}</small>` : ""}</td><td class="nowrap">${fecha(h.fecha_ingreso, true)}</td>
          <td class="nowrap">${h.fecha_egreso ? fecha(h.fecha_egreso, true) : "—"}</td><td>${esc(h.motivo_ingreso)}</td>
          <td><span class="estado ${h.estado === "ingresado" ? "alerta" : "activo"}">${mayus(h.estado)}</span></td>
          <td class="acc">${h.estado === "ingresado" && activo ? `<button type="button" class="btn sutil chico" data-cambiar-hab="${h.id_hospitalizacion}" data-hab-actual="${esc(h.numero_habitacion)}">Cambiar habitación</button><button type="button" class="btn sutil chico" data-alta="${h.id_hospitalizacion}">Registrar egreso</button>` : ""}
            <button type="button" class="btn sutil chico" data-generar-cuenta="${h.id_hospitalizacion}" data-paciente="${h.id_paciente}">Generar cuenta</button></td>
        </tr>`).join("")}</tbody></table>`
        : `<p class="relleno tenue">No ha estado internado. Para ingresarlo, registre una consulta y marque "Ingresar al paciente".</p>`}</div>
    </section>

    ${ingresado ? seccionKardex(ingresado, hp, activo) : ""}

    ${ingresado ? `<section class="bloque-hosp">
      <header class="panel-cab sin-borde"><h2>Enfermería</h2>
        ${activo ? `<button type="button" class="btn primario chico" data-asignar="${ingresado.id_hospitalizacion}">Asignar enfermero</button>` : ""}</header>
      <div class="panel">${turnos.length ? `<table class="tabla-datos">
        <thead><tr><th>Fecha</th><th>Turno</th><th>Enfermero</th><th>Indicaciones</th><th class="acc"></th></tr></thead>
        <tbody>${turnos.map((t) => `<tr><td class="nowrap">${fecha(t.fecha)}</td><td class="nowrap">${nombreTurno(t.turno)}</td>
          <td>${esc(t.enfermero_nombre)}</td><td>${esc(t.observaciones || "—")}</td>
          <td class="acc"><button type="button" class="btn sutil chico" data-anular="${t.id_asignacion}">Quitar</button></td></tr>`).join("")}</tbody></table>`
        : `<p class="relleno tenue">Sin enfermeros asignados para los próximos turnos.</p>`}</div>
    </section>` : ""}

    <section class="bloque-hosp">
      <header class="panel-cab sin-borde"><h2>Cirugías</h2>
        ${activo ? `<button type="button" class="btn primario chico" data-accion="programar-cx-paciente">+ Programar cirugía</button>` : ""}</header>
      <div class="panel">${hp.cirugias.length ? tablaCirugias([...hp.cirugias].reverse(), false)
        : `<p class="relleno tenue">Sin cirugías registradas.</p>`}</div>
    </section>`;
}


// Kárdex del paciente ingresado: órdenes del médico y dosis con su enfermero encargado
estado.kardexTodo = false;
function seccionKardex(ingreso, hp, activo) {
  const ordenes = hp.ordenes || [];
  const todas = hp.dosis || [];
  // Por defecto: lo atrasado, lo de las últimas 8 horas y lo de las próximas 24
  const visibles = estado.kardexTodo ? todas
    : todas.filter((d) => atrasada(d) || (ts(d.fecha_hora_programada) >= ahoraTs(-8 * 60) && ts(d.fecha_hora_programada) <= ahoraTs(24 * 60)));
  const atrasadas = todas.filter(atrasada).length;
  return `<section class="bloque-hosp">
      <header class="panel-cab sin-borde"><h2>Medicación</h2>
        ${activo ? `<button type="button" class="btn primario chico" data-indicar-med="${ingreso.id_hospitalizacion}">+ Indicar medicamento</button>` : ""}</header>
      <div class="panel">${ordenes.length ? `<table class="tabla-datos">
        <thead><tr><th>Medicamento</th><th>Dosis y vía</th><th>Frecuencia</th><th>Periodo</th><th>Aplicadas</th><th>Estado</th><th class="acc"></th></tr></thead>
        <tbody>${ordenes.map((o) => {
          const [txt, cls] = ESTADO_ORDEN[o.estado] || [o.estado, ""];
          return `<tr>
            <td><b>${esc(o.medicamento)}</b><br><small class="tenue">Indicado por ${esc(o.medico)}</small></td>
            <td>${esc(o.dosis)}<br><small class="tenue">${esc(o.via_administracion)}</small></td>
            <td class="nowrap">${(FRECUENCIAS.find(([h]) => h === o.frecuencia_horas) || [0, `Cada ${o.frecuencia_horas} h`])[1]}</td>
            <td class="nowrap">${fecha(o.fecha_inicio)} – ${fecha(o.fecha_fin)}${o.proxima && o.estado === "activa" ? `<br><small class="tenue">Próxima ${fecha(o.proxima, true)}</small>` : ""}</td>
            <td class="nowrap"><span class="progreso" aria-hidden="true"><span style="width:${o.total_dosis ? (o.aplicadas / o.total_dosis) * 100 : 0}%"></span></span>
              ${o.aplicadas}/${o.total_dosis}${o.omitidas ? `<br><small class="tenue">${o.omitidas} no aplicada${o.omitidas > 1 ? "s" : ""}</small>` : ""}</td>
            <td><span class="estado ${cls}">${txt}</span>${o.motivo_suspension ? `<br><small class="tenue">${esc(o.motivo_suspension)}</small>` : ""}</td>
            <td class="acc">${o.estado === "activa" && activo ? `<button type="button" class="btn sutil chico" data-suspender-orden="${o.id_orden}">Suspender</button>` : ""}</td>
          </tr>`;
        }).join("")}</tbody></table>`
        : `<p class="relleno tenue">Sin medicamentos indicados en este internamiento.</p>`}</div>
      ${todas.length ? `<div class="sub-cab">
          <h3>Dosis ${estado.kardexTodo ? "de todo el internamiento" : "de las próximas 24 horas"}
            ${atrasadas ? `<span class="estado baja">${atrasadas} atrasada${atrasadas > 1 ? "s" : ""}</span>` : ""}</h3>
          <button type="button" class="btn sutil chico" data-kardex-todo>${estado.kardexTodo ? "Ver solo las próximas 24 horas" : "Ver todas las dosis"}</button>
        </div>
        <div class="panel">${visibles.length ? tablaDosis(visibles) : `<p class="relleno tenue">No hay dosis en estos días.</p>`}</div>` : ""}
    </section>`;
}

estado.cacheDosis = {};
function guardarDosis(lista) { lista.forEach((d) => { estado.cacheDosis[d.id_administracion] = d; }); }


// ---------------------------------------------------- Panel lateral: vista rápida
function abrirCajon({ ini, sub, titulo, cuerpo, pie }) {
  $("#cajonIni").textContent = ini;
  $("#cajonSub").textContent = sub;
  $("#cajonTitulo").textContent = titulo;
  $("#cajonCuerpo").innerHTML = cuerpo;
  $("#cajonPie").innerHTML = pie;
  if (!$("#cajon").open) $("#cajon").showModal();
}
const cerrarCajon = () => { if ($("#cajon").open) $("#cajon").close(); };
$("#cajon").addEventListener("click", async (ev) => {
  if (ev.target === $("#cajon") || ev.target.closest("[data-cerrar-cajon]")) { cerrarCajon(); return; }
  const cb = ev.target.closest("[data-cobrar]");
  if (cb) { estado.volverAFactura = Number(cb.dataset.cobrar); cerrarCajon(); formCobro(Number(cb.dataset.cobrar)); return; }
  const an = ev.target.closest("[data-anular-factura]");
  if (an) { cerrarCajon(); formAnularFactura(Number(an.dataset.anularFactura)); return; }
  const im = ev.target.closest("[data-imprimir-factura]");
  if (im) { imprimirFactura(Number(im.dataset.imprimirFactura)); return; }
  const po = ev.target.closest("[data-paso-orden]");
  if (po) { estado.volverAOrden = Number(po.dataset.orden); pasoOrden(po.dataset.pasoOrden, Number(po.dataset.orden)); return; }
  const b = ev.target.closest("[data-cajon]");
  if (!b) return;
  const id = Number(b.dataset.paciente);
  cerrarCajon();
  if (b.dataset.cajon === "historial") { abrirPaciente(id, b.dataset.pestana || "historial"); return; }
  await abrirPaciente(id, b.dataset.cajon === "consulta" ? "historial" : "citas");
  if (b.dataset.cajon === "consulta") formConsulta(); else formCita();
});

async function vistaRapida(id, pestana = null) {
  const p0 = estado.pacientes.find((x) => x.id_paciente === id);
  const nombre0 = p0 ? `${p0.nombres} ${p0.apellidos}` : "Paciente";
  abrirCajon({ ini: iniciales(nombre0), sub: "Cargando…", titulo: nombre0, cuerpo: '<p class="tenue">Cargando…</p>', pie: "" });
  try {
    const [h, esp] = await Promise.all([
      api(`/api/patients/${id}/history`),
      api(`/api/patients/${id}/specialized`).catch(() => null),
    ]);
    const p = h.paciente;
    const nombre = `${p.nombres} ${p.apellidos}`;
    const archivado = h.estado !== "activo";
    const ultima = [...(h.consultas || [])].sort((a, b) => String(b.fecha_hora_atencion || "").localeCompare(String(a.fecha_hora_atencion || "")))[0];
    const ahora = ahoraTs();
    const proxCita = (h.citas || []).filter((c) => c.estado_cita === "programada" && ts(c.fecha_hora_programada) >= ahora)
      .sort((a, b) => a.fecha_hora_programada.localeCompare(b.fecha_hora_programada))[0];

    let hosp = "";
    const ingreso = (esp?.hospitalizaciones || []).find((x) => x.estado === "ingresado");
    if (estado.inst === "hospital" && ingreso) {
      const t = turnoActual();
      if (!estado.departamentos.length) await cargarDepartamentos();
      const [dosis, turnos, cx] = await Promise.all([
        api(`/api/hospital/doses?id_hospitalizacion=${ingreso.id_hospitalizacion}`).catch(() => []),
        api(`/api/hospital/shifts?id_paciente=${id}`).catch(() => []),
        api(`/api/hospital/surgeries?id_paciente=${id}&pendientes=1`).catch(() => []),
      ]);
      guardarDosis(dosis);
      const hab = habitacionDe(ingreso.numero_habitacion);
      const enf = turnos.filter((x) => x.fecha === t.fecha && x.turno === t.turno);
      const prox = dosis.filter((d) => d.estado === "pendiente").sort((a, b) => ts(a.fecha_hora_programada).localeCompare(ts(b.fecha_hora_programada)))[0];
      const atras = dosis.filter(atrasada).length;
      const enCurso = cx.find((c) => c.estado === "en_curso");
      const progr = cx.find((c) => c.estado === "programada");
      hosp = `<section class="cajon-bloque">
        <div class="tarjeta-estado ${enCurso ? "alerta-cx" : ""}">
          ${enCurso ? `<span class="estado critico">En cirugía</span><b>${esc(enCurso.procedimiento)}</b><small>${esc(enCurso.codigo_quirofano)} · desde las ${horaDe(enCurso.fecha_hora_inicio)}</small>`
            : `<small class="tenue">Internado desde ${fecha(ingreso.fecha_ingreso, true)}</small>
               <b>Habitación ${esc(ingreso.numero_habitacion)}${hab ? ` · ${esc(hab.departamento)}` : ""}</b>
               <small>${esc(ingreso.motivo_ingreso || "")}</small>`}
        </div>
        <div style="margin-top:10px">
          <p class="linea-dato"><span>Enfermero en este turno</span><span>${enf.length ? enf.map((x) => esc(x.enfermero_nombre)).join(", ") : '<span class="sin-asignar">Sin asignar</span>'}</span></p>
          <p class="linea-dato"><span>Próximo medicamento</span><span>${prox ? `${esc(prox.medicamento)} ${esc(prox.dosis)}<br><small class="${atrasada(prox) ? "atrasada-txt" : "tenue"}">${fecha(prox.fecha_hora_programada, true)}</small>` : "Ninguno"}</span></p>
          ${atras ? `<p class="linea-dato"><span>Dosis atrasadas</span><span class="atrasada-txt">${atras}</span></p>` : ""}
          ${progr ? `<p class="linea-dato"><span>Cirugía programada</span><span>${esc(progr.procedimiento)}<br><small class="tenue">${fecha(progr.fecha_hora_programada, true)} · ${esc(progr.codigo_quirofano)}</small></span></p>` : ""}
        </div>
      </section>`;
    }

    const diag = ultima?.diagnosticos?.[0];
    abrirCajon({
      ini: iniciales(nombre),
      sub: `Historial n.º ${String(p.id_paciente).padStart(6, "0")}`,
      titulo: nombre,
      cuerpo: `
        <div><span class="estado ${archivado ? "baja" : p.estado === "hospitalizado" ? "alerta" : p.estado === "critico" ? "critico" : "activo"}">${mayus(archivado ? h.estado : p.estado)}</span></div>
        <dl class="datos-cortos">
          <div><dt>Edad</dt><dd>${edad(p.fecha_nacimiento)}</dd></div>
          <div><dt>Sexo</dt><dd>${p.sexo === "F" ? "Femenino" : p.sexo === "M" ? "Masculino" : esc(p.sexo)}</dd></div>
          <div><dt>${estado.inst === "pediatrico" ? "CUI" : "DPI"}</dt><dd>${esc(p.dpi || "—")}</dd></div>
          <div><dt>Sangre</dt><dd>${esc(p.tipo_sangre || "—")}</dd></div>
        </dl>
        ${hosp}
        <section class="cajon-bloque"><h3>Última atención</h3>
          ${ultima ? `<p><b>${fecha(ultima.fecha_hora_atencion, true)}</b> · ${esc(ultima.motivo)}</p>
            ${diag ? `<p class="tenue">${esc(diag.codigo_cie10)} ${esc(diag.descripcion)}</p>` : ""}` : '<p class="tenue">Todavía no tiene consultas.</p>'}
        </section>
        <section class="cajon-bloque"><h3>Próxima cita</h3>
          ${proxCita ? `<p><b>${fecha(proxCita.fecha_hora_programada, true)}</b> · ${esc(proxCita.motivo_consulta)}</p><p class="tenue">${esc(proxCita.profesional_nombre || "")}</p>` : '<p class="tenue">Sin citas programadas.</p>'}
        </section>
        <section class="cajon-bloque"><h3>Contacto</h3>
          <p class="linea-dato"><span>Teléfono</span><span>${esc(p.telefono || "—")}</span></p>
          <p class="linea-dato"><span>Emergencia</span><span>${esc(p.contacto_emergencia_nombre || "—")}${p.contacto_emergencia_telefono ? `<br><small class="tenue">${esc(p.contacto_emergencia_telefono)}</small>` : ""}</span></p>
        </section>`,
      pie: `<button type="button" class="btn primario" data-cajon="historial" data-paciente="${id}" data-pestana="${pestana || (ingreso ? "especial" : "historial")}">Abrir historial completo</button>
        ${archivado ? "" : `<button type="button" class="btn sutil" data-cajon="consulta" data-paciente="${id}">Registrar consulta</button>
        <button type="button" class="btn sutil" data-cajon="cita" data-paciente="${id}">Agendar cita</button>`}`,
    });
  } catch (e) {
    $("#cajonCuerpo").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

// ----------------------------------------------------------------- Expediente
async function abrirPaciente(id, pestana = null) {
  const mismo = estado.idSeleccionado === id && estado.pagina === "paciente";
  estado.idSeleccionado = id;
  if (!mismo) estado.pestana = pestana || "historial";
  if (pestana) estado.pestana = pestana;
  if (!mismo) {
    estado.pagina = "paciente";
    cabecera({ migas: `<button type="button" data-ir="pacientes">Pacientes</button>`, titulo: "Abriendo historial…" });
    $("#vista").innerHTML = "";
  }
  try {
    const [h, esp] = await Promise.all([
      api(`/api/patients/${id}/history`),
      esClinico() ? api(`/api/patients/${id}/specialized`).catch(() => null) : Promise.resolve(null),
    ]);
    estado.historial = h;
    estado.especializado = esp;
    estado.hospPaciente = null;
    estado.pediatricoPaciente = null;
    estado.dentalPaciente = null;
    if (estado.inst === "hospital") {
      const ingreso = (esp?.hospitalizaciones || []).find((x) => x.estado === "ingresado");
      const [cirugias, turnos, ordenes, dosis] = await Promise.all([
        api(`/api/hospital/surgeries?id_paciente=${id}`).catch(() => []),
        api(`/api/hospital/shifts?id_paciente=${id}`).catch(() => []),
        ingreso ? api(`/api/hospital/hospitalizations/${ingreso.id_hospitalizacion}/medication`).catch(() => []) : [],
        ingreso ? api(`/api/hospital/doses?id_hospitalizacion=${ingreso.id_hospitalizacion}`).catch(() => []) : [],
        cargarDepartamentos(),
      ]);
      guardarDosis(dosis);
      estado.hospPaciente = { cirugias, turnos, ordenes, dosis };
    } else if (estado.inst === "pediatrico") {
      estado.pediatricoPaciente = await api(`/api/pediatric/patients/${id}/details`).catch(() => null);
    } else if (estado.inst === "odontologia") {
      if (estado.odontoDe !== id) { piezaOdontoSeleccionada = null; estado.odontoDe = id; }
      [estado.dentalPaciente] = await Promise.all([api(`/api/dental/patients/${id}/details`).catch(() => null), catalogoHallazgos()]);
    }
    ir("paciente");
  } catch (e) {
    avisar(e.message, true);
  }
}

function pestanaEspecial() {
  const inst = estado.inst;
  const e = estado.especializado;
  if (inst === "hospital") return ["especial", "Internamiento y cirugías"];
  return null;
}

function pintarExpediente() {
  const h = estado.historial;
  const p = h.paciente;
  const deBaja = h.estado !== "activo";
  const inst = estado.inst;
  const idTxt = String(p.id_paciente).padStart(6, "0");
  const anchoBarra = 2 + (p.id_paciente % 3);
  const doc = inst === "pediatrico" ? "CUI" : "DPI";
  const ahora = new Date().toISOString().slice(0, 16).replace("T", " ");
  const proxima = (h.citas || []).filter((c) => c.estado_cita === "programada" && c.fecha_hora_programada >= ahora)
    .sort((a, b) => a.fecha_hora_programada.localeCompare(b.fecha_hora_programada))[0];
  const criticos = h.consultas.reduce((n, c) => n + (c.examenes_laboratorio || []).filter((e) => e.alertas_criticas).length, 0);
  const lab = inst === "laboratorio";

  cabecera({
    migas: `<button type="button" data-ir="pacientes">Pacientes</button><span aria-hidden="true">/</span><span>Historial n.º ${idTxt}</span>`,
    titulo: `${esc(p.nombres)} ${esc(p.apellidos)}`,
    acciones: deBaja ? btnAccion("imprimir", "Imprimir", "sutil") : [
      btnAccion("editar", "Editar datos", "sutil"),
      lab ? "" : btnAccion("cita", "Agendar cita", "secundario"),
      puedeRegistrar() ? btnAccion("consulta", lab ? "+ Nueva orden" : "+ Registrar consulta") : "",
      `<details class="mas-acciones"><summary class="btn sutil" aria-label="Más acciones">Más</summary>
        <div class="mas-menu">${btnAccion("imprimir", "Imprimir historial", "item")}
        ${puedeRegistrar() ? btnAccion("baja", "Dar de baja el historial…", "item peligro-txt") : ""}</div></details>`,
    ].join(""),
  });

  const especial = pestanaEspecial();
  const lista = [
    ["historial", `${lab ? "Órdenes y resultados" : "Historial clínico"} (${h.consultas.length})`],
    ["citas", `${lab ? "Tomas agendadas" : "Citas"} (${h.citas.length})`],
    ["datos", "Datos personales"],
  ];
  if (inst === "hospital" && especial) {
    lista.push(especial);
  } else if (inst === "pediatrico") {
    lista.push(["pediatrico-somatometria", `Somatometría (${estado.pediatricoPaciente?.somatometria?.length || 0})`]);
    lista.push(["pediatrico-vacunas", `Vacunas (${estado.pediatricoPaciente?.vacunaciones?.length || 0})`]);
    lista.push(["pediatrico-hitos", `Hitos Denver (${estado.pediatricoPaciente?.hitos_desarrollo?.length || 0})`]);
    lista.push(["pediatrico-alergias", `Alergias (${estado.pediatricoPaciente?.alergias?.length || 0})`]);
  } else if (inst === "odontologia") {
    lista.push(["dental-odontograma", "Odontograma interactivo"]);
    lista.push(["dental-planes", `Planes (${estado.dentalPaciente?.planes_tratamiento?.length || 0})`]);
  }
  if (conCaja()) lista.push(["cuenta", "Cuenta"]);
  if (!lista.some(([k]) => k === estado.pestana)) estado.pestana = "historial";

  let cuerpo = "";
  if (estado.pestana === "historial") {
    cuerpo = h.consultas.length ? `<ol class="linea-tiempo">${h.consultas.map(pintarConsulta).join("")}</ol>`
      : `<div class="panel vacio-tabla"><p>Todavía no hay registros clínicos para este paciente.</p>
         ${puedeRegistrar() && !deBaja ? btnAccion("consulta", lab ? "+ Registrar la primera orden" : "+ Registrar la primera consulta") : ""}</div>`;
  } else if (estado.pestana === "citas") {
    cuerpo = `<div class="panel">${h.citas.length ? tablaCitas(h.citas, null)
      : `<div class="vacio-tabla"><p>Este paciente no tiene citas.</p>${!deBaja ? btnAccion("cita", "+ Agendar cita") : ""}</div>`}</div>`;
  } else if (estado.pestana === "datos") {
    cuerpo = `<div class="panel relleno">${pintarDatos(p)}</div>`;
  } else if (estado.pestana === "pediatrico-somatometria") {
    cuerpo = pintarExpedienteSomatometria();
  } else if (estado.pestana === "pediatrico-vacunas") {
    cuerpo = pintarExpedienteVacunas();
  } else if (estado.pestana === "pediatrico-hitos") {
    cuerpo = pintarExpedienteHitos();
  } else if (estado.pestana === "pediatrico-alergias") {
    cuerpo = pintarExpedienteAlergias();
  } else if (estado.pestana === "dental-odontograma") {
    cuerpo = pintarExpedienteOdontograma();
  } else if (estado.pestana === "dental-planes") {
    cuerpo = pintarExpedientePlanes();
  } else if (estado.pestana === "cuenta") {
    cuerpo = '<div id="cuentaPaciente"><p class="tenue">Cargando…</p></div>';
    setTimeout(cargarCuentaPaciente, 0);
  } else {
    cuerpo = pintarEspecializado();
  }

  // Alertas clínicas de alto riesgo en la pulsera
  let alertasPulsera = "";
  if (inst === "odontologia") {
    const sist = estado.dentalPaciente?.antecedentes_sistemicos || {};
    if (sist.alergia_anestesia_local) alertasPulsera += '<span class="alerta-anafilaxia">⚠ Alergia a anestesia local</span>';
    if (sist.trastornos_hemorragicos) alertasPulsera += '<span class="alerta-anafilaxia">⚠ Trastornos hemorrágicos</span>';
    if (sist.embarazo) alertasPulsera += `<span class="estado alerta">Embarazo (${sist.meses_embarazo || 0} meses)</span>`;
    if (sist.alergia_latex) alertasPulsera += '<span class="estado alerta">Alergia látex</span>';
    if (sist.hipertension || sist.diabetes) alertasPulsera += '<span class="estado alerta">Riesgo sistémico</span>';
  } else if (inst === "pediatrico") {
    const alergias = estado.pediatricoPaciente?.alergias || [];
    if (alergias.some((a) => a.severidad === "grave" || a.riesgo_anafilaxia)) {
      alertasPulsera += '<span class="alerta-anafilaxia">⚠ Alerta anafilaxia</span>';
    }
  }

  $("#vista").innerHTML = `
    <article class="pulsera" aria-label="Identificación del paciente">
      <div class="pulsera-broche" aria-hidden="true"></div>
      <div class="pulsera-datos">
        <div class="pulsera-fila">
          <span>${doc} <b>${esc(p.dpi)}</b></span>
          <span><b>${edad(p.fecha_nacimiento)}</b> · nació el ${fecha(p.fecha_nacimiento)}</span>
          <span>${p.sexo === "F" ? "Femenino" : "Masculino"}</span>
          ${p.tipo_sangre ? `<span>Sangre <span class="sangre">${esc(p.tipo_sangre)}</span></span>` : ""}
          <span class="estado ${deBaja ? "baja" : (p.estado === "hospitalizado" ? "alerta" : "activo")}">
            ${deBaja ? `Historial ${texto(h.estado)}` : (p.estado === "hospitalizado" ? "Hospitalizado" : "Historial activo")}</span>
          ${estado.hospPaciente?.cirugias.some((c) => c.estado === "en_curso") ? '<span class="estado critico">En cirugía</span>' : ""}
          ${alertasPulsera}
        </div>
        <dl class="resumen">
          <div><dt>${lab ? "Órdenes" : "Consultas"}</dt><dd>${h.consultas.length}</dd></div>
          <div><dt>Última atención</dt><dd>${h.consultas[0] ? fecha(h.consultas[0].fecha_hora_atencion) : "Ninguna"}</dd></div>
          <div><dt>${lab ? "Próxima toma" : "Próxima cita"}</dt><dd>${proxima ? fecha(proxima.fecha_hora_programada, true) : "Sin agendar"}</dd></div>
          ${lab ? `<div><dt>Valores críticos</dt><dd class="${criticos ? "alerta-critica" : ""}">${criticos}</dd></div>`
                : `<div><dt>Historial abierto</dt><dd>${fecha(h.fecha_apertura)}</dd></div>`}
        </dl>
      </div>
      <div class="pulsera-codigo" aria-hidden="true">
        <div class="barras" style="--a:${anchoBarra}px;--b:${anchoBarra * 2 + 1}px"></div>
        <span>${idTxt}</span>
      </div>
    </article>
    ${deBaja ? `<p class="aviso-baja"><b>Historial dado de baja.</b> Motivo: ${esc(h.motivo_baja || "no indicado")}. Solo se puede consultar; no admite nuevos registros.</p>` : ""}
    ${pestanas(lista, estado.pestana)}
    <div class="pestana-cuerpo">${cuerpo}</div>`;
}

let tBuscarPagina;
$("#contenido").addEventListener("input", (ev) => {
  if (ev.target.id !== "buscarPagina") return;
  clearTimeout(tBuscarPagina);
  tBuscarPagina = setTimeout(async () => {
    const v = ev.target.value;
    $("#txtBuscar").value = v;
    await cargarPacientes(v.trim());
    pintarPacientes();
    const campo = $("#buscarPagina");
    campo.focus();
    campo.setSelectionRange(v.length, v.length);
  }, 250);
});

$("#contenido").addEventListener("change", (ev) => {
  if (ev.target.id === "qxFecha") { estado.qxFecha = ev.target.value; pintarQuirofanos(); }
  if (ev.target.id === "enfFecha") { estado.enfFecha = ev.target.value; pintarEnfermeria(); }
  if (ev.target.id === "chkTemporales") { estado.verTemporales = ev.target.checked; refrescarOdonto(); }
});

document.addEventListener("click", (ev) => {
  document.querySelectorAll("details.mas-acciones[open]").forEach((d) => {
    if (!d.contains(ev.target) || ev.target.closest(".mas-menu button")) d.open = false;
  });
});

// Un solo manejador para todos los botones del área de contenido
$("#contenido").addEventListener("click", async (ev) => {
  const t = ev.target;
  const irA = t.closest("[data-ir]");
  if (irA) { ir(irA.dataset.ir); return; }
  const filtro = t.closest("[data-filtro]");
  if (filtro) { estado.filtro = filtro.dataset.filtro; pintarPacientes(); return; }
  const filtroC = t.closest("[data-filtro-citas]");
  if (filtroC) { estado.filtroCitas = filtroC.dataset.filtroCitas; pintarListaCitas(); return; }
  const tipoP = t.closest("[data-tipo-personal]");
  if (tipoP) { estado.tipoPersonal = tipoP.dataset.tipoPersonal; estado.filtroPersonal = "activo"; pintarPersonal(); return; }
  const qxV = t.closest("[data-qx-vista]");
  if (qxV) { estado.qxVista = qxV.dataset.qxVista; pintarQuirofanos(); return; }
  const turnoE = t.closest("[data-turno-enf]");
  if (turnoE) { estado.enfTurno = turnoE.dataset.turnoEnf; pintarEnfermeria(); return; }
  const cxI = t.closest("[data-iniciar-cx]");
  if (cxI) { accionCirugia(Number(cxI.dataset.iniciarCx), "start"); return; }
  const cxF = t.closest("[data-finalizar-cx]");
  if (cxF) { accionCirugia(Number(cxF.dataset.finalizarCx), "finish"); return; }
  const cxC = t.closest("[data-cancelar-cx]");
  if (cxC) { accionCirugia(Number(cxC.dataset.cancelarCx), "cancel"); return; }
  const asig = t.closest("[data-asignar]");
  if (asig) {
    const enPaciente = estado.pagina === "paciente";
    const ta = turnoActual();
    formAsignar(Number(asig.dataset.asignar), enPaciente ? ta.fecha : estado.enfFecha, enPaciente ? ta.turno : estado.enfTurno);
    return;
  }
  const anu = t.closest("[data-anular]");
  if (anu) { confirmarAnular(Number(anu.dataset.anular)); return; }
  const alta = t.closest("[data-alta]");
  if (alta) { formAlta(Number(alta.dataset.alta)); return; }
  const fCaja = t.closest("[data-filtro-caja]");
  if (fCaja) { estado.filtroCaja = fCaja.dataset.filtroCaja; pintarListaCaja(); return; }
  const cobrar = t.closest("[data-cobrar]");
  if (cobrar) { formCobro(Number(cobrar.dataset.cobrar)); return; }
  const edAr = t.closest("[data-editar-arancel]");
  if (edAr) { formArancel(edAr.dataset.editarArancel); return; }
  const genCta = t.closest("[data-generar-cuenta]");
  if (genCta) { generarCuentaInternamiento(Number(genCta.dataset.generarCuenta), Number(genCta.dataset.paciente)); return; }
  const vFac = t.closest("[data-ver-factura]");
  if (vFac && (!t.closest("button") || t.closest("button").dataset.verFactura)) { verFactura(Number(vFac.dataset.verFactura)); return; }
  const paso = t.closest("[data-paso-orden]");
  if (paso) { pasoOrden(paso.dataset.pasoOrden, Number(paso.dataset.orden)); return; }
  const fOrd = t.closest("[data-filtro-ordenes]");
  if (fOrd) { estado.filtroOrdenes = fOrd.dataset.filtroOrdenes; pintarListaOrdenes(); return; }
  const vOrd = t.closest("[data-ver-orden]");
  const btnDentro = t.closest("button");
  // La fila abre la orden; un botón dentro de la fila (paciente, paso) hace lo suyo
  if (vOrd && (!btnDentro || btnDentro.dataset.verOrden)) { verOrden(Number(vOrd.dataset.verOrden)); return; }
  const nHab = t.closest("[data-nueva-hab]");
  if (nHab) { formHabitacion(nHab.dataset.nuevaHab); return; }
  const eHab = t.closest("[data-editar-hab]");
  if (eHab) { formEditarHabitacion(eHab.dataset.editarHab); return; }
  const ingHab = t.closest("[data-ingresar-hab]");
  if (ingHab) { formIngresoCama(ingHab.dataset.ingresarHab); return; }
  const camb = t.closest("[data-cambiar-hab]");
  if (camb) { formCambiarHabitacion(Number(camb.dataset.cambiarHab), camb.dataset.habActual); return; }
  const indMed = t.closest("[data-indicar-med]");
  if (indMed) { formOrdenMedicacion(Number(indMed.dataset.indicarMed)); return; }
  const susp = t.closest("[data-suspender-orden]");
  if (susp) { formSuspenderOrden(Number(susp.dataset.suspenderOrden)); return; }
  const apl = t.closest("[data-aplicar-dosis]");
  if (apl) { formRegistrarDosis(estado.cacheDosis[apl.dataset.aplicarDosis], true); return; }
  const omi = t.closest("[data-omitir-dosis]");
  if (omi) { formRegistrarDosis(estado.cacheDosis[omi.dataset.omitirDosis], false); return; }
  if (t.closest("[data-kardex-todo]")) { estado.kardexTodo = !estado.kardexTodo; pintarExpediente(); return; }
  if (t.closest("[data-ir-enfermeros]")) { estado.tipoPersonal = "enfermeros"; ir("personal"); return; }
  const filtroP = t.closest("[data-filtro-personal]");
  if (filtroP) { estado.filtroPersonal = filtroP.dataset.filtroPersonal; pintarPersonal(); return; }
  const editP = t.closest("[data-editar-prof]");
  if (editP) { formProfesional(estado.personal.find((x) => x.id_profesional === Number(editP.dataset.editarProf))); return; }
  const estP = t.closest("[data-estado-prof]");
  if (estP) { cambiarEstadoProfesional(Number(estP.dataset.estadoProf)); return; }
  const pest = t.closest("[data-pestana]");
  if (pest) { estado.pestana = pest.dataset.pestana; pintarExpediente(); return; }
  const atender = t.closest("[data-atender]");
  if (atender && atender.dataset.orden) { pasoOrden("muestra", Number(atender.dataset.orden)); return; }
  if (atender) {
    const idCita = Number(atender.dataset.atender);
    await abrirPaciente(Number(atender.dataset.paciente), "historial");
    formConsulta(idCita);
    return;
  }
  const rapida = t.closest(".enlace-paciente[data-id], .fila-reciente[data-id]");
  if (rapida && estado.pagina !== "paciente") { vistaRapida(Number(rapida.dataset.id), rapida.dataset.pestanaIr || null); return; }
  const abrir = t.closest("[data-id]");
  if (abrir) { abrirPaciente(Number(abrir.dataset.id), abrir.dataset.pestanaIr || null); return; }
  const avEt = t.closest("[data-avanzar-etapa]");
  if (avEt) {
    cambiarEstadoEtapaTratamiento(Number(avEt.dataset.planId), Number(avEt.dataset.avanzarEtapa), avEt.dataset.estado);
    return;
  }
  const hEst = t.closest("[data-hallazgo-estado]");
  if (hEst) { cambiarEstadoHallazgo(Number(hEst.dataset.fdi), hEst.dataset.cara, hEst.dataset.hallazgoEstado); return; }
  const hQuitar = t.closest("[data-hallazgo-quitar]");
  if (hQuitar) { quitarHallazgo(Number(hQuitar.dataset.fdi), hQuitar.dataset.cara); return; }
  const pincel = t.closest("[data-pincel]");
  if (pincel) {
    estado.pincelOdonto = pincel.dataset.pincel || null;
    refrescarOdonto();
    return;
  }
  const marcar = t.closest("[data-marcar]");
  if (marcar) { marcarHallazgo(Number(marcar.dataset.pieza), marcar.dataset.cara, marcar.dataset.marcar); return; }
  if (t.closest("[data-cerrar-pieza]")) {
    piezaOdontoSeleccionada = null;
    document.querySelectorAll(".boca .diente-caja.seleccionado").forEach((el) => el.classList.remove("seleccionado"));
    document.querySelectorAll(".cara-activa").forEach((el) => el.classList.remove("cara-activa"));
    const det = $("#detallePiezaOdontograma");
    det.className = "detalle-pieza-vacio";
    det.innerHTML = `<p class="tenue">Ningún diente seleccionado.</p>`;
    return;
  }
  const caraEl = t.closest("[data-cara-click]");
  if (caraEl) {
    const pieza = Number(caraEl.dataset.pieza);
    // con un hallazgo elegido en la paleta, el clic en un diente del odontograma lo marca
    if (estado.pincelOdonto && caraEl.closest(".boca")) marcarHallazgo(pieza, caraEl.dataset.caraClick, estado.pincelOdonto);
    else seleccionarPiezaOdontograma(pieza, caraEl.dataset.caraClick);
    return;
  }
  const dienteEl = t.closest("[data-diente-click]");
  if (dienteEl) {
    seleccionarPiezaOdontograma(Number(dienteEl.dataset.dienteClick));
    return;
  }
  const b = t.closest("[data-accion]");
  if (!b) return;
  const accion = b.dataset.accion;
  if (accion === "nuevo") formPaciente(null);
  if (accion === "nuevo-prof") formProfesional(null);
  if (accion === "cita-nueva") formCita(null);
  if (accion === "programar-cx") formCirugia(null);
  if (accion === "nueva-hab") formHabitacion(null);
  if (accion === "nuevo-depto") formDepartamento();
  if (accion === "programar-cx-paciente") formCirugia(estado.idSeleccionado);
  if (accion === "limpiar") { $("#txtBuscar").value = ""; await cargarPacientes(""); pintarPacientes(); }
  if (accion === "ver-motores") verMotores();
  if (accion === "consulta") { if (estado.inst === "laboratorio") formOrden(estado.historial?.paciente.id_paciente); else formConsulta(); }
  if (accion === "cita") formCita();
  if (accion === "nueva-factura") formFactura({ idPaciente: estado.pagina === "paciente" ? estado.historial?.paciente.id_paciente : null });
  if (accion === "nueva-orden") formOrden(estado.pagina === "paciente" ? estado.historial?.paciente.id_paciente : null);
  if (accion === "editar") formPaciente(estado.historial.paciente);
  if (accion === "baja") formBaja();
  if (accion === "imprimir") window.print();
  if (accion === "atender") formConsulta(Number(b.dataset.cita));
  if (accion === "editar-perinatal") formPerinatal(estado.idSeleccionado);
  if (accion === "editar-tutor") formTutor(estado.idSeleccionado);
  if (accion === "editar-sistemico") formAnamnesisSistemica(estado.idSeleccionado);
  if (accion === "nueva-somatometria") formSomatometria(null);
  if (accion === "nueva-somatometria-paciente") formSomatometria(estado.idSeleccionado);
  if (accion === "nueva-vacuna-lote") formNuevoLoteVacuna();
  if (accion === "aplicar-vacuna-general") formAplicarVacuna(null);
  if (accion === "aplicar-vacuna-paciente") formAplicarVacuna(estado.idSeleccionado);
  if (accion === "nuevo-hito") formHito(null);
  if (accion === "nuevo-hito-paciente") formHito(estado.idSeleccionado);
  if (accion === "nueva-alergia") formAlergia(null);
  if (accion === "nueva-alergia-paciente") formAlergia(estado.idSeleccionado);
  if (accion === "nuevo-hallazgo") formHallazgoDental(null, piezaOdontoSeleccionada, caraOdontoSeleccionada);
  if (accion === "hallazgo-en-pieza") formHallazgoDental(pacienteOdonto(), Number(b.dataset.piezaSel), b.dataset.caraSel);
  if (accion === "ver-expediente-odonto" && estado.pacienteOdontoSel) abrirPaciente(estado.pacienteOdontoSel, "dental-odontograma");
  if (accion === "nuevo-hallazgo-paciente") formHallazgoDental(estado.idSeleccionado, piezaOdontoSeleccionada, caraOdontoSeleccionada);
  if (accion === "nuevo-plan-tratamiento") formPlanTratamiento(null);
  if (accion === "nuevo-plan-paciente") formPlanTratamiento(estado.idSeleccionado);
  if (accion === "nuevo-procedimiento-arancel") formProcedimientoArancel();
});

function pintarDatos(p) {
  const filas = [
    ["Dirección", p.direccion],
    ["Teléfono", p.telefono],
    ["Correo", p.correo_electronico],
  ];
  if (p.nombre_tutor) {
    filas.push(["Tutor", `${p.nombre_tutor} (${p.parentesco_tutor || ""})`], ["DPI tutor", p.dpi_tutor],
      ["Gestación", p.semanas_gestacion ? `${p.semanas_gestacion} semanas` : ""],
      ["Al nacer", p.peso_nacer_kg ? `${p.peso_nacer_kg} kg, ${p.talla_nacer_cm} cm` : ""]);
  } else {
    filas.push(["Emergencia", [p.contacto_emergencia_nombre, p.contacto_emergencia_telefono].filter(Boolean).join(", ")]);
  }
  filas.push(["Registro", fecha(p.fecha_registro)]);
  let html = `<dl class="datos">${filas.filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${k === "Registro" ? v : esc(v)}</dd>`).join("")}</dl>`;

  if (estado.inst === "pediatrico") {
    const peri = estado.pediatricoPaciente?.antecedente_perinatal || {};
    const tutor = estado.pediatricoPaciente?.tutores?.[0] || {};
    html += `
      <div class="bloque-detalle" style="margin-top:24px; padding-top:16px; border-top:1px solid var(--linea)">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
          <h3 style="font-size:16px; margin:0">Antecedentes Perinatales y Datos del Nacimiento</h3>
          <button type="button" class="btn sutil chico" data-accion="editar-perinatal">Editar perinatales</button>
        </div>
        <dl class="datos">
          <dt>Semanas gestación</dt><dd>${peri.semanas_gestacion ? `${peri.semanas_gestacion} semanas` : "—"}</dd>
          <dt>Peso al nacer</dt><dd>${peri.peso_nacer_kg ? `${peri.peso_nacer_kg} kg` : "—"}</dd>
          <dt>Talla al nacer</dt><dd>${peri.talla_nacer_cm ? `${peri.talla_nacer_cm} cm` : "—"}</dd>
          <dt>Perímetro cefálico</dt><dd>${peri.perimetro_cefalico_nacer_cm ? `${peri.perimetro_cefalico_nacer_cm} cm` : "—"}</dd>
          <dt>Apgar 1 min / 5 min</dt><dd>${peri.apgar_1min != null ? `${peri.apgar_1min} / 10` : "—"} · ${peri.apgar_5min != null ? `${peri.apgar_5min} / 10` : "—"}</dd>
          <dt>Vía de parto</dt><dd>${esc(peri.tipo_parto || "—")}</dd>
          <dt>Complicaciones</dt><dd>${esc(peri.complicaciones_neonatales || "Sin complicaciones reportadas")}</dd>
        </dl>
      </div>
      <div class="bloque-detalle" style="margin-top:20px; padding-top:16px; border-top:1px solid var(--linea)">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
          <h3 style="font-size:16px; margin:0">Tutor Legal y Custodia</h3>
          <button type="button" class="btn sutil chico" data-accion="editar-tutor">Editar tutor</button>
        </div>
        <dl class="datos">
          <dt>Nombre del tutor</dt><dd><b>${esc(tutor.nombres ? `${tutor.nombres} ${tutor.apellidos || ""}`.trim() : (p.nombre_tutor || "—"))}</b></dd>
          <dt>Parentesco</dt><dd>${esc(tutor.parentesco || p.parentesco_tutor || "—")}</dd>
          <dt>DPI del tutor</dt><dd>${esc(tutor.dpi || p.dpi_tutor || "—")}</dd>
          <dt>Teléfono principal</dt><dd>${esc(tutor.telefono_principal || p.telefono_tutor || "—")}</dd>
          <dt>Dirección</dt><dd>${esc(tutor.direccion || p.direccion || "—")}</dd>
        </dl>
      </div>`;
  } else if (estado.inst === "odontologia") {
    const sist = estado.dentalPaciente?.antecedentes_sistemicos || {};
    html += `
      <div class="bloque-detalle" style="margin-top:24px; padding-top:16px; border-top:1px solid var(--linea)">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
          <h3 style="font-size:16px; margin:0">Anamnesis Médica y Riesgo Sistémico Dental</h3>
          <button type="button" class="btn sutil chico" data-accion="editar-sistemico">Editar antecedentes médicos</button>
        </div>
        <div class="cuadricula-sistemica" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:10px; margin-bottom:14px">
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.hipertension ? "#FFF4EB" : "var(--blanco)"}">
            <span class="tenue">Hipertensión:</span> <b style="color:${sist.hipertension ? "var(--ambar)" : "inherit"}">${sist.hipertension ? "SÍ (Vasoconstrictor prec.)" : "No"}</b>
          </div>
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.diabetes ? "#FFF4EB" : "var(--blanco)"}">
            <span class="tenue">Diabetes:</span> <b style="color:${sist.diabetes ? "var(--ambar)" : "inherit"}">${sist.diabetes ? "SÍ (Riesgo infección)" : "No"}</b>
          </div>
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.enfermedad_cardiaca ? "#FFF4EB" : "var(--blanco)"}">
            <span class="tenue">Cardiopatía:</span> <b style="color:${sist.enfermedad_cardiaca ? "var(--ambar)" : "inherit"}">${sist.enfermedad_cardiaca ? "SÍ (Profilaxis ATB)" : "No"}</b>
          </div>
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.trastornos_hemorragicos ? "#FDF2F2" : "var(--blanco)"}">
            <span class="tenue">Trastornos hemorrágicos:</span> <b style="color:${sist.trastornos_hemorragicos ? "var(--rojo)" : "inherit"}">${sist.trastornos_hemorragicos ? "SÍ (Alto riesgo sangrado)" : "No"}</b>
          </div>
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.alergia_anestesia_local ? "#FDF2F2" : "var(--blanco)"}">
            <span class="tenue">Alergia anestesia local:</span> <b style="color:${sist.alergia_anestesia_local ? "var(--rojo)" : "inherit"}">${sist.alergia_anestesia_local ? "SÍ (CONTRAINDICADA)" : "No"}</b>
          </div>
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.alergia_latex ? "#FFF4EB" : "var(--blanco)"}">
            <span class="tenue">Alergia al látex:</span> <b style="color:${sist.alergia_latex ? "var(--ambar)" : "inherit"}">${sist.alergia_latex ? "SÍ (Guantes nitrilo)" : "No"}</b>
          </div>
          <div style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${sist.embarazo ? "#FFF4EB" : "var(--blanco)"}">
            <span class="tenue">Embarazo:</span> <b style="color:${sist.embarazo ? "var(--ambar)" : "inherit"}">${sist.embarazo ? `SÍ (${sist.meses_embarazo || 0} meses)` : "No"}</b>
          </div>
        </div>
        <dl class="datos">
          <dt>Medicamentos actuales</dt><dd>${esc(sist.medicamentos_actuales || "Ninguno reportado")}</dd>
          <dt>Observaciones médicas</dt><dd>${esc(sist.observaciones_medicas || "Sin observaciones")}</dd>
          <dt>Última actualización</dt><dd>${fecha(sist.fecha_actualizacion || sist.fecha_evaluacion)}</dd>
        </dl>
      </div>`;
  }
  return html;
}

function pintarCitas(citas) {
  if (!citas?.length) return `<p class="tenue">Sin citas.</p>`;
  return `<ul class="citas">${citas.map((c) => `
    <li>
      <span class="fecha">${fecha(c.fecha_hora_programada, true)}
        <span class="estado ${c.estado_cita === "programada" ? "alerta" : (c.estado_cita === "atendida" ? "activo" : "baja")}">${texto(c.estado_cita)}</span></span>
      <span>${esc(c.motivo_consulta)}</span>
      <span class="tenue">${esc(c.profesional_nombre)}</span>
      ${c.estado_cita === "programada" && esClinico() && estado.historial.estado === "activo"
        ? `<span><button class="btn sutil chico" data-accion="atender" data-cita="${c.id_cita}">Atender esta cita</button></span>` : ""}
    </li>`).join("")}</ul>`;
}

function pintarConsulta(c) {
  const signos = [
    c.presion_arterial && `<span>PA <b>${esc(c.presion_arterial)}</b></span>`,
    c.temperatura != null && `<span>Temp. <b>${esc(c.temperatura)} °C</b></span>`,
    c.pulso != null && `<span>Pulso <b>${esc(c.pulso)} lpm</b></span>`,
    c.somatometria && `<span>Peso <b>${esc(c.somatometria.peso_kg)} kg</b></span>`,
    c.somatometria && `<span>Talla <b>${esc(c.somatometria.talla_cm)} cm</b></span>`,
    c.somatometria?.perimetro_cefalico_cm && `<span>P. cefálico <b>${esc(c.somatometria.perimetro_cefalico_cm)} cm</b></span>`,
    c.somatometria?.percentil_crecimiento != null && `<span>Percentil <b>${esc(c.somatometria.percentil_crecimiento)}</b></span>`,
  ].filter(Boolean);

  const recetas = c.recetas?.length ? c.recetas
    : [...(c.recetas_pediatricas || []), ...c.diagnosticos.flatMap((d) => d.tratamientos.flatMap((t) => t.recetas))];

  const partes = [`<p class="motivo">${esc(c.motivo)}</p>`];
  if (signos.length) partes.push(`<div class="signos">${signos.join("")}</div>`);

  if (c.diagnosticos.length) {
    partes.push(`<div><div class="subtitulo">Diagnóstico</div>${c.diagnosticos.map((d) => `
      <div class="diag"><span class="cie">${esc(d.codigo_cie10 || "—")}</span><span>${esc(d.descripcion)}${d.tipo && d.tipo !== "principal" ? ` <span class="tenue">(${esc(d.tipo)})</span>` : ""}</span>
      ${d.tratamientos.map((t) => `<span class="trat">Tratamiento: ${esc(t.descripcion)}${t.indicaciones ? ` — ${esc(t.indicaciones)}` : ""}</span>`).join("")}
      </div>`).join("")}</div>`);
  }

  if (recetas.length) {
    partes.push(`<div><div class="subtitulo">Receta</div><table class="tabla"><thead><tr><th>Medicamento</th><th>Dosis</th><th>Frecuencia</th><th class="num">Días</th></tr></thead><tbody>
      ${recetas.map((r) => `<tr><td>${esc(r.medicamento)}${r.presentacion && r.presentacion !== "No especificada" ? `<br><span class="tenue">${esc(r.presentacion)}</span>` : ""}</td>
        <td>${esc(r.dosis)}${r.dosis_mg_kg ? `<br><span class="tenue">${esc(r.dosis_mg_kg)} mg/kg</span>` : ""}</td>
        <td>${esc(r.frecuencia)}${r.via_administracion ? `<br><span class="tenue">${esc(r.via_administracion)}</span>` : ""}</td>
        <td class="num">${esc(r.duracion_dias)}</td></tr>`).join("")}</tbody></table></div>`);
  }

  if (c.vacunaciones?.length) {
    partes.push(`<div><div class="subtitulo">Vacunas aplicadas</div>${c.vacunaciones.map((v) =>
      `<div>${esc(v.nombre_vacuna)} — ${esc(v.dosis)} <span class="tenue">(lote ${esc(v.lote)}${v.proxima_fecha_refuerzo ? `, refuerzo ${fecha(v.proxima_fecha_refuerzo)}` : ""})</span></div>`).join("")}</div>`);
  }

  if (c.procedimientos_dentales?.length) {
    const total = c.procedimientos_dentales.reduce((s, p) => s + Number(p.costo || 0), 0);
    partes.push(`<div><div class="subtitulo">Procedimientos</div><table class="tabla"><thead><tr><th>Pieza</th><th>Procedimiento</th><th class="num">Costo</th></tr></thead><tbody>
      ${c.procedimientos_dentales.map((p) => `<tr><td><b>${esc(p.pieza_dental)}</b></td><td>${esc(p.nombre_procedimiento)}${p.observaciones ? `<br><span class="tenue">${esc(p.observaciones)}</span>` : ""}</td><td class="num">Q${Number(p.costo).toFixed(2)}</td></tr>`).join("")}
      <tr><td></td><td><b>Total</b></td><td class="num"><b>Q${total.toFixed(2)}</b></td></tr></tbody></table></div>`);
  }

  for (const ex of c.examenes_laboratorio || []) {
    partes.push(`<div><div class="subtitulo">${esc(ex.nombre_examen)} <span class="tenue">(${esc(ex.codigo_examen)}, ${texto(ex.estado)})</span>
      ${ex.alertas_criticas ? `<span class="alerta-critica"> · valor crítico</span>` : ""}</div>
      <table class="tabla"><thead><tr><th>Parámetro</th><th class="num">Resultado</th><th>Referencia</th><th></th></tr></thead><tbody>
      ${ex.parametros.map((p) => `<tr><td>${esc(p.nombre_parametro)}</td>
        <td class="num"><b>${esc(p.valor_resultado)}</b> ${esc(p.unidad_medida)}</td>
        <td class="tenue">${p.rango_referencia_min != null || p.rango_referencia_max != null ? `${esc(p.rango_referencia_min ?? "")} – ${esc(p.rango_referencia_max ?? "")}` : esc(p.valor_referencia_cualitativo || "")}</td>
        <td><span class="flag ${esc(p.interpretacion_alerta)}">${texto(p.interpretacion_alerta).toLowerCase()}</span></td></tr>`).join("")}
      </tbody></table>
      ${ex.conclusiones_diagnosticas ? `<p class="notas">${esc(ex.conclusiones_diagnosticas)}</p>` : ""}</div>`);
  }

  if (c.hospitalizacion) {
    const ho = c.hospitalizacion;
    partes.push(`<div><div class="subtitulo">Hospitalización</div>
      <div>Habitación <b>${esc(ho.numero_habitacion)}</b> · ingreso ${fecha(ho.fecha_ingreso, true)} · <span class="estado ${ho.estado === "ingresado" ? "alerta" : "activo"}">${texto(ho.estado)}</span></div>
      <div class="tenue">${esc(ho.motivo_ingreso)}</div></div>`);
  }

  if (c.notas_clinicas) partes.push(`<div><div class="subtitulo">Notas</div><p class="notas">${esc(c.notas_clinicas)}</p></div>`);

  if (c.estado_orden && c.estado_orden !== "entregada") {
    partes.unshift(`<div class="orden-en-curso">${chipEstadoOrden(c.estado_orden)}
      <button type="button" class="btn sutil chico" data-ver-orden="${c.id_consulta}">Ver orden ${numOrden(c.id_consulta)}</button></div>`);
  }
  return `<li class="evento">
    <div class="evento-cab"><time>${fecha(c.fecha_hora_atencion, true)}</time>
      <span class="tenue">${texto(c.tipo_consulta)}${c.profesional_nombre ? ` · ${esc(c.profesional_nombre)}` : ""}</span></div>
    <div class="tarjeta">${partes.join("")}</div></li>`;
}

function pintarEspecializado() {
  const e = estado.especializado;
  const inst = estado.inst;
  if (inst === "hospital") return pintarHospitalPaciente();
  if (inst === "odontologia") {
    const tratadas = new Set(estado.historial.datos_adicionales?.piezas_tratadas || Object.keys(e?.odontograma || {}));
    const diente = (n) => `<span class="diente ${tratadas.has(String(n)) ? "tratado" : ""} ${n === 21 || n === 31 ? "medio" : ""}">${n}</span>`;
    return `<section class="bloque"><div class="panel relleno odontograma">
      <div class="arcada">${PIEZAS_SUP.map(diente).join("")}</div>
      <div class="arcada">${PIEZAS_INF.map(diente).join("")}</div>
      <p class="ayuda">Las piezas resaltadas tienen procedimientos registrados.</p></div></section>`;
  }
  if (!e) return "";
  if (inst === "pediatrico" && e.control_crecimiento?.length) {
    return `<section class="bloque"><div class="panel relleno"><div class="subtitulo">Control de crecimiento</div>
      <table class="tabla"><thead><tr><th>Fecha</th><th class="num">Peso</th><th class="num">Talla</th><th class="num">Pc.</th></tr></thead><tbody>
      ${e.control_crecimiento.map((r) => `<tr><td>${fecha(r.fecha)}</td><td class="num">${esc(r.peso_kg)} kg</td><td class="num">${esc(r.talla_cm)} cm</td><td class="num">${esc(r.percentil ?? "—")}</td></tr>`).join("")}
      </tbody></table>
      ${e.esquema_vacunacion?.length ? `<div class="subtitulo" style="margin-top:14px">Esquema de vacunación</div>
      ${e.esquema_vacunacion.map((v) => `<div>${esc(v.nombre_vacuna)} <span class="tenue">· ${esc(v.dosis)} · ${fecha(v.fecha_aplicacion)}</span></div>`).join("")}` : ""}
      </div></section>`;
  }
  if (inst === "hospital" && e.hospitalizaciones?.length) {
    return `<section class="bloque"><div class="panel relleno"><ul class="citas">
      ${e.hospitalizaciones.map((h) => `<li><span class="fecha">${esc(h.numero_habitacion)} <span class="estado ${h.estado === "ingresado" ? "alerta" : "activo"}">${texto(h.estado)}</span></span>
        <span>${fecha(h.fecha_ingreso, true)}${h.fecha_egreso ? ` a ${fecha(h.fecha_egreso, true)}` : ""}</span>
        <span class="tenue">${esc(h.motivo_ingreso)}</span></li>`).join("")}</ul></div></section>`;
  }
  return "";
}

// ------------------------------------------------------------------- Modal

// ======================================================= Reglas de cada campo
// Una sola tabla para todos los formularios de las cuatro instituciones. Se aplica sola
// a cada campo por su nombre (name) o, en las filas de recetas/parámetros, por data-k.
// El servidor repite las mismas reglas (src/domain/validaciones.py) y las bases de datos
// las más importantes, así que esto es comodidad para el usuario, no la única defensa.
const RE = {
  letras: /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .\-]+$/u,
  telefono: /^[2-7]\d{3}-?\d{4}$/,
  correo: /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/,
  cie10: /^[A-Z]\d{2}(\.[0-9A-Z]{1,4})?$/,
  presion: /^(\d{2,3})\/(\d{2,3})$/,
  colegiado: /^[A-Z0-9-]{3,20}$/,
  lote: /^[A-Za-z0-9-]{3,30}$/,
  dosis: /^\d+([.,]\d+)?\s?[A-Za-zµÁÉÍÓÚáéíóúñ/%]+(\s[A-Za-zÁÉÍÓÚáéíóúñ/]+)*$/u,
};
const MSG_LETRAS = "use solo letras, espacios, punto, apóstrofo o guion";
const PIEZAS_FDI = new Set([1, 2, 3, 4].flatMap((c) => [1, 2, 3, 4, 5, 6, 7, 8].map((n) => c * 10 + n))
  .concat([5, 6, 7, 8].flatMap((c) => [1, 2, 3, 4, 5].map((n) => c * 10 + n))));

function revisarDPI(v) {
  if (!/^\d{13}$/.test(v)) return `debe tener exactamente 13 dígitos (lleva ${v.replace(/\D/g, "").length})`;
  const depto = Number(v.slice(9, 11)), muni = Number(v.slice(11, 13));
  if (depto < 1 || depto > 22) return "los dígitos 10 y 11 son el departamento (01 a 22)";
  if (muni < 1 || muni > 35) return "los dos últimos dígitos son el municipio (01 en adelante)";
  return null;
}
const nombreR = (max) => ({ attrs: { maxlength: max, minlength: 2, autocomplete: "off" }, re: RE.letras, msg: MSG_LETRAS, filtro: "letras" });
const telR = { attrs: { maxlength: 9, inputmode: "tel", placeholder: "5841-7501" }, re: RE.telefono, filtro: "telefono",
  msg: "8 dígitos de Guatemala que empiezan con 2 a 7 (ej. 5841-7501)" };
const dpiR = { attrs: { maxlength: 13, inputmode: "numeric", placeholder: "13 dígitos" }, filtro: "digitos", check: revisarDPI };
const txt = (max, min = 0) => ({ attrs: { maxlength: max, ...(min ? { minlength: min } : {}) } });
const num = (min, max, step = "any") => ({ attrs: { min, max, step, inputmode: "decimal" } });
const isoLocal = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const haceAnios = (n) => { const d = new Date(); d.setFullYear(d.getFullYear() - n); return hoyISO(d); };

const REGLAS = {
  nombres: nombreR(50), apellidos: nombreR(50), nombre_tutor: nombreR(100), contacto_emergencia_nombre: nombreR(100),
  nombre_completo: nombreR(100), parentesco_tutor: nombreR(30), especialidad: nombreR(80),
  dpi: dpiR, dpi_tutor: dpiR,
  telefono: telR, contacto_emergencia_telefono: telR, telefono_tutor: telR,
  correo_electronico: { attrs: { maxlength: 80, type: "email", placeholder: "nombre@dominio.com" }, re: RE.correo, msg: "escriba un correo válido (ej. nombre@dominio.com)" },
  direccion: txt(200, 5),
  fecha_nacimiento: { dinamico: () => ({ max: hoyISO(), min: haceAnios(estado.inst === "pediatrico" ? 18 : 120) }),
    msgRango: () => (estado.inst === "pediatrico" ? "debe ser de un menor de 18 años y no futura" : "no puede ser futura ni de hace más de 120 años") },
  semanas_gestacion: num(20, 45, 1), peso_nacer_kg: num(0.3, 7, 0.01), talla_nacer_cm: num(20, 65, 0.1),
  motivo: txt(200, 3), motivo_consulta: txt(200, 3), motivo_hospitalizacion: txt(200, 3), motivo_baja: txt(150, 5),
  presion_arterial: { attrs: { maxlength: 7, inputmode: "numeric" }, check: (v) => {
    const m = v.match(RE.presion);
    if (!m) return "use el formato 120/80";
    const [s, d] = [Number(m[1]), Number(m[2])];
    return s >= 60 && s <= 260 && d >= 30 && d <= 160 && s > d ? null : "fuera de rango (sistólica 60–260, diastólica 30–160, mayor la sistólica)";
  } },
  temperatura: num(30, 45, 0.1), pulso: num(20, 250, 1), peso_kg: num(0.3, 150, 0.01), talla_cm: num(20, 200, 0.1),
  perimetro_cefalico_cm: num(20, 70, 0.1), percentil_crecimiento: num(0, 100, 0.1),
  codigo_cie10: { attrs: { maxlength: 8 }, filtro: "mayus", re: RE.cie10, msg: "letra + 2 números y decimal opcional (ej. K80.0)" },
  descripcion_diagnostico: txt(300, 3), descripcion_tratamiento: txt(300, 3), indicaciones_tratamiento: txt(500), notas_clinicas: txt(2000),
  nombre_vacuna: txt(100, 2), dosis_vacuna: txt(30), lote_vacuna: { attrs: { maxlength: 30 }, re: RE.lote, msg: "use letras, números o guion (3 a 30)" },
  proxima_fecha_refuerzo: { dinamico: () => ({ min: hoyISO() }), msgRango: () => "no puede ser una fecha pasada" },
  tipo_muestra: txt(60), conclusiones_diagnosticas: txt(1000), observaciones_tecnicas: txt(300),
  numero_colegiado: { attrs: { maxlength: 20, minlength: 3, placeholder: "COL-12450" }, filtro: "mayus", re: RE.colegiado, msg: "use letras, números o guion (3 a 20)" },
  procedimiento: txt(200, 3), duracion_estimada_min: num(15, 720, 15), notas_operatorias: txt(1000), notas: txt(1000),
  fecha_hora_programada: { dinamico: () => ({ min: isoLocal(new Date(Date.now() - 5 * 60000)), max: isoLocal(new Date(Date.now() + 365 * 86400000)) }),
    msgRango: () => "debe ser desde ahora y dentro del próximo año" },
  fecha: { dinamico: () => ({ min: turnoActual().fecha }), msgRango: () => "no puede ser una fecha pasada" },
  fecha_inicio: { dinamico: () => ({ min: isoLocal(new Date(Date.now() - 60 * 60000)), max: isoLocal(new Date(Date.now() + 30 * 86400000)) }),
    msgRango: () => "debe ser desde hace una hora y dentro de los próximos 30 días" },
  dosis: { attrs: { maxlength: 50 }, re: RE.dosis, msg: "cantidad y unidad (ej. 500 mg, 1 g, 2 tabletas)" },
  duracion_dias: num(1, 30, 1), indicaciones: txt(200), observaciones: txt(200), motivo_omision: txt(200, 5),
  username: txt(50), password: txt(100),
  nit: { attrs: { maxlength: 15, placeholder: "CF" }, filtro: "mayus", check: (v) => revisarNIT(v) },
  nombre_facturacion: txt(120, 3), monto: num(0.01, 1000000, 0.01), referencia: txt(40, 3),
  descripcion: txt(120, 3), precio: num(0, 100000, 0.01),
  codigo_arancel: { attrs: { maxlength: 15 }, filtro: "mayus", re: /^[A-Z0-9-]{3,15}$/, msg: "mayúsculas, números y guion (3 a 15)" },
  codigo: { attrs: { maxlength: 8 }, filtro: "mayus", re: /^[A-Z]{2,4}-\d{2,3}$/, msg: "2 a 4 letras, guion y 2 o 3 números (ej. MI-104)" },
  camas: num(1, 6, 1), nombre: nombreR(80), piso: num(0, 20, 1),
  extension: { attrs: { maxlength: 5, inputmode: "numeric" }, filtro: "digitos", re: /^\d{2,5}$/, msg: "de 2 a 5 dígitos" },
  numero_lote: { attrs: { maxlength: 30 }, re: RE.lote, msg: "letras, números o guion (3 a 30 caracteres)" },
  temp_min_c: num(-20, 30, 0.1), temp_max_c: num(-20, 30, 0.1),
  dosis_disponibles: num(1, 100000, 1), dosis_recibidas: num(1, 100000, 1), fabricante: txt(100, 2),
  apgar_1min: num(0, 10, 1), apgar_5min: num(0, 10, 1), tipo_parto: txt(50), complicaciones_neonatales: txt(300),
  edad_meses: num(0, 216, 1), sintomas_observados: txt(200),
  monto_total: num(0, 100000, 0.01), monto_abono: num(0.01, 100000, 0.01),
  numero_recibo: txt(30, 2), numero_factura: txt(30, 2), numero_autorizacion: txt(50),
  diagnostico_plan: txt(300, 3), nombre_procedimiento: txt(100, 2), categoria_procedimiento: txt(50),
  costo_base: num(0, 50000, 0.01), duracion_minutos: num(5, 480, 5), hallazgo: txt(100, 2),
  nombre_etapa: txt(100, 2), costo_etapa: num(0, 50000, 0.01),
  medicamentos_actuales: txt(500), observaciones_medicas: txt(1000),
};
const REGLAS_FILA = {
  concepto: txt(150, 2), cantidad: num(0.01, 1000), precio_unitario: num(0, 100000, 0.01),
  medicamento: txt(100, 2), presentacion: txt(50), dosis: txt(50), frecuencia: txt(50), duracion_dias: num(1, 90, 1),
  dosis_mg_kg: num(0.01, 100, 0.01), concentracion_mg_ml: num(0.1, 1000, 0.1),
  pieza_dental: { attrs: { maxlength: 2, inputmode: "numeric" }, filtro: "digitos",
    check: (v) => (PIEZAS_FDI.has(Number(v)) ? null : "no existe en la notación FDI (11–48 permanentes, 51–85 temporales)") },
  costo: num(0, 50000, 0.01), observaciones: txt(200),
  nombre_parametro: txt(60, 2), valor_resultado: txt(40), unidad_medida: txt(20),
  rango_referencia_min: num(-1000000, 1000000), rango_referencia_max: num(-1000000, 1000000), valor_referencia_cualitativo: txt(60),
};
const reglaDe = (el) => (el.dataset.k ? REGLAS_FILA[el.dataset.k] : REGLAS[el.name]);

function aplicarReglas(raiz) {
  raiz.querySelectorAll("input, textarea").forEach((el) => {
    const r = reglaDe(el);
    if (!r) return;
    Object.entries({ ...(r.attrs || {}), ...(r.dinamico ? r.dinamico() : {}) }).forEach(([k, v]) => {
      if (k === "type") { if (el.type === "text") el.type = v; return; }
      if (k === "placeholder" && el.placeholder) return;
      if (!el.hasAttribute(k)) el.setAttribute(k, v);
    });
    if (el.tagName === "TEXTAREA" && el.maxLength > 0 && !el.nextElementSibling?.classList.contains("contador")) {
      el.insertAdjacentHTML("afterend", `<small class="contador" aria-hidden="true">0 / ${el.maxLength}</small>`);
    }
  });
}

// Mientras se escribe: solo deja pasar los caracteres que el campo admite
function filtrarEscritura(el) {
  const r = reglaDe(el);
  if (!r?.filtro) return;
  const antes = el.value;
  let v = antes;
  if (r.filtro === "digitos") v = v.replace(/\D/g, "");
  if (r.filtro === "letras") v = v.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .\-]/gu, "");
  if (r.filtro === "mayus") v = v.toUpperCase().replace(/\s/g, "");
  if (r.filtro === "telefono") {
    const d = v.replace(/\D/g, "").slice(0, 8);
    v = d.length > 4 ? `${d.slice(0, 4)}-${d.slice(4)}` : d;
  }
  if (v !== antes) el.value = v;
}

const etiquetaDe = (el) => {
  const lab = el.closest("label");
  const t = lab?.querySelector(".requerido")?.textContent || lab?.firstChild?.textContent || el.name || "Campo";
  return t.trim();
};

// Devuelve el problema del campo, o null si está bien
function problemaDe(el) {
  if (el.disabled || el.closest("[hidden]") || ["checkbox", "radio", "hidden", "button"].includes(el.type)) return null;
  const v = el.value.trim();
  if (!v) return el.required ? "es obligatorio" : null;
  if (el.minLength > 0 && v.length < el.minLength) return `debe tener al menos ${el.minLength} caracteres`;
  if (el.maxLength > 0 && v.length > el.maxLength) return `admite como máximo ${el.maxLength} caracteres`;
  const r = reglaDe(el);
  if (el.type === "number") {
    const n = Number(v);
    if (Number.isNaN(n)) return "debe ser un número";
    if (el.min !== "" && n < Number(el.min)) return `debe estar entre ${el.min} y ${el.max || "∞"}`;
    if (el.max !== "" && n > Number(el.max)) return `debe estar entre ${el.min || "−∞"} y ${el.max}`;
    if (el.step === "1" && !Number.isInteger(n)) return "debe ser un número entero";
  }
  if (["date", "datetime-local"].includes(el.type) && ((el.min && v < el.min) || (el.max && v > el.max))) {
    return r?.msgRango ? r.msgRango() : "está fuera del rango permitido";
  }
  if (r?.re && !r.re.test(v)) return r.msg;
  if (r?.check) return r.check(v, el);
  if (el.type === "email" && !RE.correo.test(v)) return "escriba un correo válido";
  return null;
}

function marcarCampo(el, msg) {
  const lab = el.closest("label") || el.parentElement;
  lab.querySelector(":scope > .msg-campo")?.remove();
  el.toggleAttribute("aria-invalid", Boolean(msg));
  if (msg) lab.insertAdjacentHTML("beforeend", `<small class="msg-campo">${esc(msg.charAt(0).toUpperCase() + msg.slice(1))}</small>`);
}

// Revisa todo el formulario; marca cada campo con problema y devuelve el primero
function revisarFormulario(form) {
  let primero = null;
  form.querySelectorAll("input, select, textarea").forEach((el) => {
    const msg = problemaDe(el);
    marcarCampo(el, msg);
    if (msg && !primero) primero = { el, msg: `${etiquetaDe(el)}: ${msg}` };
  });
  // Reglas entre campos
  form.querySelectorAll('[data-fila="parametro"]').forEach((f) => {
    const mn = f.querySelector('[data-k="rango_referencia_min"]'), mx = f.querySelector('[data-k="rango_referencia_max"]');
    if (mn?.value && mx?.value && Number(mn.value) > Number(mx.value)) {
      marcarCampo(mx, "debe ser mayor o igual que el mínimo");
      if (!primero) primero = { el: mx, msg: "Parámetro: el máximo de referencia debe ser mayor o igual que el mínimo" };
    }
  });
  const cen = form.querySelector('[name="contacto_emergencia_nombre"]'), cet = form.querySelector('[name="contacto_emergencia_telefono"]');
  if (cen?.value.trim() && cet && !cet.value.trim()) {
    marcarCampo(cet, "indique el teléfono del contacto");
    if (!primero) primero = { el: cet, msg: "Contacto de emergencia: falta el teléfono" };
  }
  return primero;
}

new MutationObserver((cambios) => cambios.forEach((c) => c.addedNodes.forEach((n) => { if (n.nodeType === 1) aplicarReglas(n.parentElement || n); })))
  .observe($("#modalCuerpo"), { childList: true, subtree: true });
$("#modalCuerpo").addEventListener("input", (ev) => {
  const el = ev.target;
  filtrarEscritura(el);
  if (el.hasAttribute("aria-invalid") && !problemaDe(el)) marcarCampo(el, null);
  const cont = el.nextElementSibling;
  if (cont?.classList.contains("contador")) cont.textContent = `${el.value.length} / ${el.maxLength}`;
});
$("#modalCuerpo").addEventListener("focusout", (ev) => {
  const el = ev.target;
  if (!el.matches("input, textarea") || !el.value.trim()) return;
  marcarCampo(el, problemaDe(el));
});

let alAceptar = null;

const cerrarModal = () => { if ($("#modal").open) $("#modal").close(); };
function abrirModal(titulo, html, textoBoton, accion) {
  $("#modalTitulo").textContent = titulo;
  $("#modalCuerpo").innerHTML = html;
  aplicarReglas($("#modalCuerpo"));
  $("#modalAceptar").textContent = textoBoton;
  $("#modalAceptar").hidden = !textoBoton;
  $(".modal-pie [data-cerrar]").textContent = textoBoton ? "Cancelar" : "Cerrar";
  $("#modalError").hidden = true;
  alAceptar = accion;
  $("#modal").showModal();
  const primero = $("#modalCuerpo input, #modalCuerpo select, #modalCuerpo textarea");
  if (primero) primero.focus();
}

document.querySelectorAll("[data-cerrar]").forEach((b) => b.addEventListener("click", () => $("#modal").close()));

$("#modalForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!alAceptar) return;
  const form = ev.target;
  const problema = revisarFormulario(form);
  if (problema) {
    mostrarErrorModal(`${problema.msg.charAt(0).toUpperCase()}${problema.msg.slice(1)}.`);
    problema.el.focus();
    return;
  }
  const boton = $("#modalAceptar");
  boton.disabled = true;
  try {
    await alAceptar(new FormData(form));
    $("#modal").close();
  } catch (e) {
    mostrarErrorModal(e.message);
  } finally {
    boton.disabled = false;
  }
});

function mostrarErrorModal(msg) {
  const el = $("#modalError");
  el.textContent = msg;
  el.hidden = false;
  el.scrollIntoView({ block: "nearest" });
}

const datosForm = (fd) => Object.fromEntries([...fd.entries()].map(([k, v]) => [k, typeof v === "string" ? v.trim() : v]));
const opciones = (pares, sel) => pares.map(([v, t]) => `<option value="${esc(v)}" ${v === sel ? "selected" : ""}>${esc(t)}</option>`).join("");
const campo = (nombre, etiqueta, { tipo = "text", req = false, valor = "", clase = "", extra = "" } = {}) =>
  `<label class="${clase}"><span class="${req ? "requerido" : ""}">${etiqueta}</span><input name="${nombre}" type="${tipo}" value="${esc(valor)}" ${req ? "required" : ""} ${extra}></label>`;

// ---------------------------------------------------------- Paciente (nuevo/editar)

function formPaciente(p) {
  const inst = estado.inst;
  const editar = Boolean(p);
  const v = p || {};
  const ped = inst === "pediatrico";
  const html = `
    <fieldset><legend>Datos personales</legend><div class="rejilla">
      ${campo("nombres", "Nombres", { req: true, valor: v.nombres })}
      ${campo("apellidos", "Apellidos", { req: true, valor: v.apellidos })}
      ${campo("fecha_nacimiento", "Fecha de nacimiento", { tipo: "date", req: true, valor: v.fecha_nacimiento })}
      <label><span class="requerido">Sexo</span><select name="sexo" required>${opciones([["F", "Femenino"], ["M", "Masculino"]], v.sexo)}</select></label>
      ${editar ? "" : campo("dpi", ped ? "CUI del niño" : "DPI", { req: true })}
      ${!ped && inst !== "odontologia" ? `<label>Tipo de sangre<select name="tipo_sangre">${opciones([["", "No indicado"], ...["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"].map((t) => [t, t])], v.tipo_sangre || "")}</select></label>` : ""}
      ${campo("direccion", "Dirección", { valor: v.direccion, clase: "doble" })}
      ${!ped ? campo("telefono", "Teléfono", { valor: v.telefono }) : ""}
      ${!ped ? campo("correo_electronico", "Correo", { tipo: "email", valor: v.correo_electronico }) : ""}
    </div></fieldset>
    ${ped ? `
    <fieldset><legend>Tutor responsable</legend><div class="rejilla">
      ${campo("nombre_tutor", "Nombre del tutor", { req: true, valor: v.nombre_tutor, clase: "doble" })}
      ${campo("parentesco_tutor", "Parentesco", { req: true, valor: v.parentesco_tutor })}
      ${campo("dpi_tutor", "DPI del tutor", { req: true, valor: v.dpi_tutor })}
      ${campo("telefono_tutor", "Teléfono del tutor", { req: true, valor: v.telefono_tutor })}
    </div></fieldset>
    <fieldset><legend>Datos al nacer</legend><div class="rejilla">
      ${campo("semanas_gestacion", "Semanas de gestación", { tipo: "number", valor: v.semanas_gestacion, extra: 'min="20" max="45"' })}
      ${campo("peso_nacer_kg", "Peso al nacer (kg)", { tipo: "number", valor: v.peso_nacer_kg, extra: 'step="0.01"' })}
      ${campo("talla_nacer_cm", "Talla al nacer (cm)", { tipo: "number", valor: v.talla_nacer_cm, extra: 'step="0.1"' })}
    </div></fieldset>` : `
    <fieldset><legend>Contacto de emergencia</legend><div class="rejilla">
      ${campo("contacto_emergencia_nombre", "Nombre", { valor: v.contacto_emergencia_nombre, clase: "doble" })}
      ${campo("contacto_emergencia_telefono", "Teléfono", { valor: v.contacto_emergencia_telefono })}
    </div></fieldset>`}`;

  abrirModal(editar ? "Editar datos del paciente" : "Registrar paciente nuevo", html,
    editar ? "Guardar cambios" : "Registrar paciente", async (fd) => {
      const datos = datosForm(fd);
      if (editar) {
        await api(`/api/patients/${p.id_paciente}`, { method: "PUT", body: datos });
        avisar("Datos guardados");
        await cargarPacientes();
        abrirPaciente(p.id_paciente, "datos");
      } else {
        const nuevo = await api("/api/patients", { method: "POST", body: datos });
        avisar(`Paciente registrado con historial n.º ${nuevo.id_paciente}`);
        $("#txtBuscar").value = "";
        await cargarPacientes("");
        estado.idSeleccionado = null;
        abrirPaciente(nuevo.id_paciente);
      }
    });
}

// ---------------------------------------------------------------------- Cita
async function formCita(idPaciente = estado.idSeleccionado) {
  const conPaciente = Boolean(idPaciente) && estado.pagina === "paciente";
  const pacientes = conPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const manana = new Date(Date.now() + 86400000);
  manana.setHours(9, 0, 0, 0);
  const local = new Date(manana.getTime() - manana.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const html = `<div class="rejilla">
    ${conPaciente ? "" : `<label class="completo"><span class="requerido">Paciente</span><select name="id_paciente" required>
      <option value="">Seleccione…</option>${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)} — ${esc(p.dpi)}</option>`).join("")}
    </select></label>`}
    ${campo("fecha_hora_programada", "Fecha y hora", { tipo: "datetime-local", req: true, valor: local })}
    ${campoProfesional(`${nombrePersonal()[0].toUpperCase()}${nombrePersonal().slice(1)} asignado`)}
    <label class="completo"><span class="requerido">Motivo</span><input name="motivo_consulta" required maxlength="200"></label>
  </div>`;
  abrirModal(conPaciente ? `Agendar cita para ${estado.historial.paciente.nombres}` : "Agendar cita", html, "Agendar cita", async (fd) => {
    const d = datosForm(fd);
    const pid = conPaciente ? idPaciente : Number(d.id_paciente);
    await api("/api/appointments", { method: "POST", body: { ...d, id_paciente: pid } });
    avisar("Cita agendada");
    if (conPaciente) abrirPaciente(pid, "citas");
    else ir(estado.pagina);
  });
}

// ---------------------------------------------------------------------- Baja
function formBaja() {
  const html = `
    <p>El historial no se borra: queda archivado y solo se podrá consultar. Las citas pendientes se cancelan en la misma operación.</p>
    <div class="rejilla">
      <label><span class="requerido">Causa</span><select name="categoria" required>
        ${opciones([["traslado", "Traslado a otra institución"], ["fallecimiento", "Fallecimiento"], ["administrativa", "Otra causa administrativa"]])}
      </select></label>
      <label class="completo"><span class="requerido">Detalle del motivo</span><input name="motivo_baja" required maxlength="150" placeholder="Ej. Trasladado al Hospital Regional de Occidente"></label>
    </div>`;
  abrirModal("Dar de baja el historial", html, "Dar de baja", async (fd) => {
    const d = datosForm(fd);
    const r = await api(`/api/patients/${estado.idSeleccionado}/deactivate`, { method: "POST", body: d });
    avisar(`Historial ${texto(r.estado)}${r.citas_canceladas ? ` · ${r.citas_canceladas} cita(s) cancelada(s)` : ""}`);
    await cargarPacientes();
    abrirPaciente(estado.idSeleccionado);
  });
}

// ------------------------------------------------------------------ Consulta
function filaReceta(ped) {
  return `<div class="fila-item" data-fila="receta">
    <label>Medicamento<input data-k="medicamento" required list="dlMedicamentos" autocomplete="off"></label>
    <label>Presentación<input data-k="presentacion" placeholder="${ped ? "Suspensión 250 mg/5 ml" : "Tabletas 500 mg"}"></label>
    ${ped ? `<label>Dosis (mg/kg)<input data-k="dosis_mg_kg" type="number" step="0.1"></label>
             <label>Concentración (mg/ml)<input data-k="concentracion_mg_ml" type="number" step="0.1"></label>`
          : `<label>Dosis<input data-k="dosis" placeholder="1 tableta"></label>
             <label>Vía<select data-k="via_administracion">${opciones([["Oral", "Oral"], ["Intravenosa", "Intravenosa"], ["Intramuscular", "Intramuscular"], ["Subcutánea", "Subcutánea"], ["Tópica", "Tópica"]])}</select></label>`}
    <label>Frecuencia<input data-k="frecuencia" placeholder="Cada 8 horas"></label>
    <label>Días<input data-k="duracion_dias" type="number" min="1" value="5"></label>
    <button type="button" class="btn sutil chico quitar" data-quitar>Quitar</button>
  </div>`;
}

function filaProcedimiento() {
  const procs = estado.catalogos.procedimientos || [];
  return `<div class="fila-item" data-fila="procedimiento">
    <label>Procedimiento${procs.length
      ? `<select data-k="id_procedimiento">${opciones(procs.map((p) => [String(p.id_procedimiento), `${p.nombre_procedimiento} (Q${p.costo})`]))}</select>`
      : `<input data-k="nombre_procedimiento" required>`}</label>
    <label>Pieza<input data-k="pieza_dental" placeholder="36" required></label>
    <label>Costo (Q)<input data-k="costo" type="number" step="0.01" placeholder="Del catálogo"></label>
    <label>Observaciones<input data-k="observaciones"></label>
    <button type="button" class="btn sutil chico quitar" data-quitar>Quitar</button>
  </div>`;
}

function filaParametro(p = {}) {
  return `<div class="fila-item param" data-fila="parametro">
    <label>Parámetro<input data-k="nombre_parametro" value="${esc(p.nombre_parametro)}" required></label>
    <label>Resultado<input data-k="valor_resultado"></label>
    <label>Unidad<input data-k="unidad_medida" value="${esc(p.unidad_medida)}"></label>
    <label>Mín.<input data-k="rango_referencia_min" type="number" step="any" value="${esc(p.rango_referencia_min)}"></label>
    <label>Máx.<input data-k="rango_referencia_max" type="number" step="any" value="${esc(p.rango_referencia_max)}"></label>
    <label>Referencia (texto)<input data-k="valor_referencia_cualitativo" value="${esc(p.valor_referencia_cualitativo)}"></label>
    <button type="button" class="btn sutil chico quitar" data-quitar>Quitar</button>
  </div>`;
}

function formConsulta(idCita = null) {
  const inst = estado.inst;
  const ped = inst === "pediatrico";
  const lab = inst === "laboratorio";
  const dent = inst === "odontologia";
  const examenes = estado.catalogos.tipos_examen?.length ? estado.catalogos.tipos_examen : EXAMENES_RESPALDO;
  const cita = idCita ? estado.historial.citas.find((c) => c.id_cita === idCita) : null;

  const html = `
    <fieldset class="paso"><legend>${lab ? "Orden de laboratorio" : "Consulta"}</legend><div class="rejilla">
      <label class="completo"><span class="requerido">Motivo</span><input name="motivo" required maxlength="200" value="${esc(cita?.motivo_consulta || "")}"></label>
      ${campoProfesional(lab ? "Laboratorista que procesa" : "Atendido por", cita?.id_profesional ?? null)}
      <label>${lab ? "Prioridad" : "Tipo"}<select name="tipo_consulta">${opciones(INST[inst].tipos)}</select></label>
      ${cita ? `<p class="ayuda completo">Se registrará como atención de la cita del ${fecha(cita.fecha_hora_programada, true)}.</p>` : ""}
    </div></fieldset>

    ${!lab && !dent ? `<fieldset class="paso"><legend>${ped ? "Signos vitales y somatometría" : "Signos vitales"} <span class="tenue">(opcional${ped ? " salvo peso y talla" : ""})</span></legend><div class="rejilla">
        ${!ped ? campo("presion_arterial", "Presión arterial", { extra: 'placeholder="120/80"' }) : ""}
        ${campo("temperatura", "Temperatura (°C)", { tipo: "number", extra: 'step="0.1" min="30" max="45"' })}
        ${campo("pulso", ped ? "Frecuencia cardiaca" : "Pulso (lpm)", { tipo: "number" })}
    ${ped ? `
      ${campo("peso_kg", "Peso (kg)", { tipo: "number", req: true, extra: 'step="0.01" min="0.5"' })}
      ${campo("talla_cm", "Talla (cm)", { tipo: "number", req: true, extra: 'step="0.1" min="20"' })}
      ${campo("perimetro_cefalico_cm", "Perímetro cefálico (cm)", { tipo: "number", extra: 'step="0.1"' })}
      ${campo("percentil_crecimiento", "Percentil OMS", { tipo: "number", extra: 'step="0.1" min="0" max="100"' })}` : ""}
    </div></fieldset>` : ""}

    ${lab ? `<fieldset class="paso"><legend>Examen y resultados</legend><div class="rejilla">
      <label class="doble"><span class="requerido">Tipo de examen</span><select name="codigo_examen" id="selExamen" required>
        ${opciones(examenes.map((e) => [e.codigo, `${e.codigo} · ${e.nombre_examen}`]))}</select></label>
      ${campo("tipo_muestra", "Muestra", { extra: 'placeholder="Sangre con EDTA"' })}
    </div>
    <p class="ayuda">Cada examen tiene parámetros distintos; se cargan los del tipo elegido y puede agregar más.</p>
    <div class="filas" id="filasParametros"></div>
    <button type="button" class="btn sutil chico btn-agregar" data-agregar="parametro">+ Agregar parámetro</button>
    <div class="rejilla">
      <label class="completo">Conclusiones<textarea name="conclusiones_diagnosticas"></textarea></label>
      <label class="completo">Observaciones técnicas<input name="observaciones_tecnicas"></label>
    </div></fieldset>` : ""}

    ${dent ? `<fieldset class="paso"><legend>Procedimientos por pieza</legend>
      <div class="odontograma">
        <div class="arcada">${PIEZAS_SUP.map((n) => `<button type="button" class="diente ${n === 21 ? "medio" : ""}" data-pieza="${n}">${n}</button>`).join("")}</div>
        <div class="arcada">${PIEZAS_INF.map((n) => `<button type="button" class="diente ${n === 31 ? "medio" : ""}" data-pieza="${n}">${n}</button>`).join("")}</div>
        <p class="ayuda">Toque una pieza para agregar un procedimiento en ella.</p>
      </div>
      <div class="filas" id="filasProcedimientos"></div>
      <button type="button" class="btn sutil chico btn-agregar" data-agregar="procedimiento">+ Agregar procedimiento general</button>
    </fieldset>` : ""}

    <fieldset class="paso"><legend>${lab ? "Diagnóstico presuntivo" : "Diagnóstico y tratamiento"}</legend><div class="rejilla">
      ${campo("codigo_cie10", "Código CIE-10", { extra: 'placeholder="Escriba o elija" maxlength="10" list="dlCie10" autocomplete="off"' })}
      <label class="doble">Descripción<input name="descripcion_diagnostico" maxlength="300"></label>
      ${!lab ? `${campo("descripcion_tratamiento", "Tratamiento", { clase: "doble" })}
      ${campo("indicaciones_tratamiento", "Indicaciones", { clase: "doble" })}` : ""}
    </div></fieldset>

    ${ped ? `<fieldset class="paso"><legend>Vacunación</legend>
      <label class="check"><input type="checkbox" data-revela="secVacuna"> Se aplicó una vacuna en esta consulta</label>
      <div class="rejilla" id="secVacuna" hidden>
      ${campo("nombre_vacuna", "Vacuna", { clase: "doble" })}
      ${campo("dosis_vacuna", "Dosis", { extra: 'placeholder="2.ª dosis"' })}
      ${campo("lote_vacuna", "Lote")}
      ${campo("proxima_fecha_refuerzo", "Próximo refuerzo", { tipo: "date" })}
    </div></fieldset>` : ""}

    ${!lab ? `<fieldset class="paso"><legend>Receta</legend>
      ${ped ? `<p class="ayuda">La dosis en ml se calcula con el peso: mg/kg × kg ÷ concentración.</p>` : ""}
      <div class="filas" id="filasRecetas"><p class="ayuda vacio-filas">Sin medicamentos. Para recetar, primero indique el diagnóstico.</p></div>
      <button type="button" class="btn sutil chico btn-agregar" data-agregar="receta">+ Agregar medicamento</button>
    </fieldset>` : ""}

    ${inst === "hospital" ? `<fieldset class="paso"><legend>Hospitalización</legend>
      <label class="check"><input type="checkbox" name="requiere_hospitalizacion" value="1" data-revela="secHosp"> Ingresar al paciente en el hospital</label>
      <div class="rejilla" id="secHosp" hidden>
      <label class="completo"><span class="requerido">Habitación</span>${selectHabitacion("numero_habitacion")}</label>
      ${campo("motivo_hospitalizacion", "Motivo de ingreso", { clase: "completo", extra: 'maxlength="200" placeholder="Si se deja vacío se usa el motivo de la consulta"' })}
    </div></fieldset>` : ""}

    <datalist id="dlCie10">${(CIE10[inst] || []).map(([c, d]) => `<option value="${c}">${esc(d)}</option>`).join("")}</datalist>
    <datalist id="dlMedicamentos">${(MEDICAMENTOS[inst] || []).map((m) => `<option value="${esc(m)}"></option>`).join("")}</datalist>
    <fieldset class="paso"><legend>${lab ? "Observaciones de la orden" : "Notas clínicas"} <span class="tenue">(opcional)</span></legend>
      <textarea name="notas_clinicas" aria-label="${lab ? "Observaciones de la orden" : "Notas clínicas"}"></textarea>
    </fieldset>`;

  abrirModal(lab ? "Registrar resultado de examen" : "Registrar consulta", html,
    lab ? "Guardar resultado" : "Guardar consulta", async (fd) => {
      const d = datosForm(fd);
      d.id_paciente = estado.idSeleccionado;
      if (idCita) d.id_cita = idCita;
      d.requiere_hospitalizacion = fd.get("requiere_hospitalizacion") === "1";
      if (d.requiere_hospitalizacion && !d.numero_habitacion) throw new Error("Elija la habitación donde se ingresa al paciente.");
      d.recetas = leerFilas("receta");
      d.procedimientos = leerFilas("procedimiento");
      d.parametros = leerFilas("parametro");
      if (d.recetas.length && !d.codigo_cie10 && !d.descripcion_diagnostico) {
        throw new Error("Para recetar se necesita un diagnóstico.");
      }
      await api("/api/consultations", { method: "POST", body: d });
      const conCobro = conCaja() && (estado.inst !== "odontologia" || d.procedimientos.length > 0);
      avisar(lab ? "Resultado guardado" : conCobro ? "Consulta guardada · su cobro quedó pendiente en Caja" : "Consulta guardada");
      abrirPaciente(estado.idSeleccionado, "historial");
    });

  const cie = $('#modalCuerpo [name="codigo_cie10"]');
  cie.addEventListener("change", () => {
    const desc = $('#modalCuerpo [name="descripcion_diagnostico"]');
    const hallado = (CIE10[inst] || []).find(([c]) => c.toLowerCase() === cie.value.trim().toLowerCase());
    if (hallado && !desc.value.trim()) desc.value = hallado[1];
  });

  if (lab) {
    const cargar = () => {
      const ex = examenes.find((e) => e.codigo === $("#selExamen").value);
      $("#filasParametros").innerHTML = (ex?.parametros_plantilla || [{}]).map(filaParametro).join("");
    };
    $("#selExamen").addEventListener("change", cargar);
    cargar();
  }
}

function leerFilas(tipo) {
  return [...document.querySelectorAll(`#modalCuerpo [data-fila="${tipo}"]`)].map((f) =>
    Object.fromEntries([...f.querySelectorAll("[data-k]")].map((i) => [i.dataset.k, i.value.trim()])));
}

$("#modalCuerpo").addEventListener("change", (ev) => {
  const r = ev.target.closest("[data-revela]");
  if (!r) return;
  const sec = document.getElementById(r.dataset.revela);
  sec.hidden = !r.checked;
  if (r.checked) sec.querySelector("input, select")?.focus();
});

$("#modalCuerpo").addEventListener("click", (ev) => {
  if (ev.target.closest("[data-ir-personal]")) { $("#modal").close(); estado.tipoPersonal = "medicos"; ir("personal"); return; }
  if (ev.target.closest("[data-ir-enfermeros]")) { $("#modal").close(); estado.tipoPersonal = "enfermeros"; ir("personal"); return; }
  const agregar = ev.target.closest("[data-agregar]");
  if (agregar) {
    const tipo = agregar.dataset.agregar;
    const cont = { receta: "#filasRecetas", procedimiento: "#filasProcedimientos", parametro: "#filasParametros" }[tipo];
    const html = tipo === "receta" ? filaReceta(estado.inst === "pediatrico") : tipo === "procedimiento" ? filaProcedimiento() : filaParametro();
    $(cont).querySelector(".vacio-filas")?.remove();
    $(cont).insertAdjacentHTML("beforeend", html);
    $(cont).lastElementChild.querySelector("input, select").focus();
    return;
  }
  const quitar = ev.target.closest("[data-quitar]");
  if (quitar) { quitar.closest(".fila-item").remove(); return; }
  const pieza = ev.target.closest("[data-pieza]");
  if (pieza) {
    $("#filasProcedimientos").insertAdjacentHTML("beforeend", filaProcedimiento());
    const fila = $("#filasProcedimientos").lastElementChild;
    fila.querySelector('[data-k="pieza_dental"]').value = pieza.dataset.pieza;
    pieza.classList.add("elegido");
    fila.querySelector("select, input").focus();
  }
});

// ==============================================================================
// MÓDULOS ESPECIALIZADOS: CENTRO PEDIÁTRICO Y CLÍNICA ODONTOLÓGICA
// ==============================================================================

// ---------------------------------------------------------------- Odontograma SVG
const PIEZAS_PERM_SUP = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
const PIEZAS_PERM_INF = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
const PIEZAS_TEMP_SUP = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
const PIEZAS_TEMP_INF = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];
const CARAS_TXT = { O: "Oclusal / Incisal", V: "Vestibular", L: "Lingual / Palatina", M: "Mesial", D: "Distal", G: "Toda la pieza" };
const ESTADOS_HALLAZGO = { activo: "Por tratar", tratado: "Tratado", en_observacion: "En observación" };

let piezaOdontoSeleccionada = null;
let caraOdontoSeleccionada = null;

// Catálogo de hallazgos (simbología). Se pide una vez por sesión.
async function catalogoHallazgos() {
  if (!estado.catHallazgos?.length) {
    const lista = await api("/api/dental/findings-catalog").catch(() => []);
    estado.catHallazgos = lista.map((h) => ({
      codigo: h.codigo || "", nombre: h.nombre || h.nombre_hallazgo || "", color: h.color_hex || h.color_sugerido || "#B42318",
      toda: Boolean(h.toda_la_pieza), tipo: h.tipo || "",
    })).filter((h) => h.nombre);
  }
  return estado.catHallazgos;
}

// Código del hallazgo: el guardado o, en registros antiguos, deducido del nombre
function codigoHallazgo(h) {
  if (h.codigo_hallazgo) return h.codigo_hallazgo;
  const t = String(h.hallazgo || "").toLowerCase();
  if (t.includes("ausente") || t.includes("extraída") || t.includes("perdida")) return "ausente";
  if (t.includes("endodon") || t.includes("conducto")) return "endodoncia";
  if (t.includes("corona")) return "corona";
  return "";
}

// Paleta: elegir un hallazgo y luego hacer clic en las caras del diente para marcarlo
const leyendaOdonto = () => {
  const p = estado.pincelOdonto;
  return `
  <div class="paleta-odonto" role="toolbar" aria-label="Qué marcar en el odontograma">
    <button type="button" class="pincel ${!p ? "activo" : ""}" data-pincel="">
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 2l9 5-4 1 2 5-2 1-2-5-3 3z" fill="currentColor"/></svg>Ver detalle</button>
    ${(estado.catHallazgos || []).map((h) => `<button type="button" class="pincel ${p === h.nombre ? "activo" : ""}" data-pincel="${esc(h.nombre)}">
      <i style="background:${esc(h.color)}"></i>${esc(h.nombre)}</button>`).join("")}
  </div>`;
};

// Cuadrante FDI: 1, 4, 5 y 8 son el lado derecho del paciente (se ven a la izquierda)
const ladoDerecho = (p) => [1, 4, 5, 8].includes(Math.floor(p / 10));
const esSuperior = (p) => [1, 2, 5, 6].includes(Math.floor(p / 10));
const esAnterior = (p) => p % 10 <= 3;

// Qué cara va en cada posición del dibujo, como en un odontograma clínico:
// arriba vestibular en los superiores y lingual en los inferiores; mesial hacia la línea media.
function carasDe(pieza) {
  return {
    arriba: esSuperior(pieza) ? "V" : "L",
    abajo: esSuperior(pieza) ? "L" : "V",
    izq: ladoDerecho(pieza) ? "D" : "M",
    der: ladoDerecho(pieza) ? "M" : "D",
    centro: "O",
  };
}
const nombreCara = (pieza, k) => (k === "O" ? (esAnterior(pieza) ? "Incisal" : "Oclusal") : k === "L" ? (esSuperior(pieza) ? "Palatina" : "Lingual") : CARAS_TXT[k]);

function renderDienteSVG(pieza, hallazgosPieza = [], seleccionada = false, { grande = false } = {}) {
  const color = {};
  let cruz = null;
  let endodoncia = false;
  let corona = null;
  for (const h of hallazgosPieza) {
    const c = String(h.cara || "O").toUpperCase() === "P" ? "L" : String(h.cara || "O").toUpperCase();
    const cod = codigoHallazgo(h);
    const col = h.color_hex || "#B42318";
    if (cod === "ausente" || cod === "extraccion_indicada") { cruz = col; continue; }
    if (cod === "endodoncia") { endodoncia = true; continue; }
    if (cod === "corona") { corona = col; continue; }
    // una patología ya tratada se dibuja tenue: sigue en el registro, pero ya no es pendiente
    const tenue = h.estado === "tratado" && (h.codigo_hallazgo ? ["caries", "fractura"].includes(cod) : /caries|fractura/i.test(h.hallazgo || ""));
    const val = { col, tenue };
    if (c === "G") ["O", "V", "L", "M", "D"].forEach((k) => { color[k] = color[k] || val; });
    else color[c] = val;
  }
  const ausente = hallazgosPieza.some((h) => codigoHallazgo(h) === "ausente");
  const relleno = (k) => (ausente ? "fill:#E7ECEB" : color[k] ? `fill:${color[k].col}${color[k].tenue ? "; fill-opacity:.35" : ""}` : "fill:#FFFFFF");
  const pos = carasDe(pieza);
  const forma = { arriba: "4,4 36,4 28,12 12,12", abajo: "12,28 28,28 36,36 4,36", izq: "4,4 12,12 12,28 4,36", der: "28,12 36,4 36,36 28,28", centro: "12,12 28,12 28,28 12,28" };
  const letra = { arriba: [20, 9.5], abajo: [20, 33.5], izq: [8, 21.5], der: [32, 21.5], centro: [20, 21.5] };
  const caras = Object.entries(pos).map(([lugar, k]) => `
    <polygon points="${forma[lugar]}" style="${relleno(k)}" data-cara-click="${k}" data-pieza="${pieza}"
      class="cara-diente ${caraOdontoSeleccionada === k && seleccionada ? "cara-activa" : ""}"><title>Pieza ${pieza} · ${nombreCara(pieza, k)}</title></polygon>
    ${grande ? `<text x="${letra[lugar][0]}" y="${letra[lugar][1]}" class="letra-cara">${k === "L" && esSuperior(pieza) ? "P" : k === "O" && esAnterior(pieza) ? "I" : k}</text>` : ""}`).join("");
  const resumen = hallazgosPieza.length
    ? hallazgosPieza.map((h) => `${h.cara === "G" ? "Toda la pieza" : nombreCara(pieza, h.cara)}: ${h.hallazgo} (${ESTADOS_HALLAZGO[h.estado] || h.estado})`).join("\n")
    : `Pieza ${pieza}: sana`;
  const tam = grande ? 140 : pieza >= 51 ? 36 : 44;

  return `
    <div class="diente-caja ${seleccionada ? "seleccionado" : ""} ${hallazgosPieza.length ? "con-hallazgo" : ""} ${grande ? "diente-grande" : ""}" data-diente="${pieza}" title="${esc(resumen)}">
      ${!grande && esSuperior(pieza) ? `<span class="diente-num" data-diente-click="${pieza}">${pieza}</span>` : ""}
      <svg class="diente-svg" viewBox="0 0 40 40" width="${tam}" height="${tam}" style="width:${tam}px; height:${tam}px" aria-label="Pieza dental FDI ${pieza}">
        ${caras}
        ${corona ? `<rect x="2" y="2" width="36" height="36" rx="3" class="corona" style="fill:none; stroke:${corona}; stroke-width:3" pointer-events="none"/>` : ""}
        ${endodoncia ? '<line x1="20" y1="5" x2="20" y2="35" stroke="#7A4FB0" stroke-width="3.5" pointer-events="none"/>' : ""}
        ${cruz ? `<g pointer-events="none"><line x1="5" y1="5" x2="35" y2="35" stroke="${cruz}" stroke-width="3"/><line x1="35" y1="5" x2="5" y2="35" stroke="${cruz}" stroke-width="3"/></g>` : ""}
      </svg>
      ${!grande && !esSuperior(pieza) ? `<span class="diente-num" data-diente-click="${pieza}">${pieza}</span>` : ""}
    </div>`;
}

// El odontograma completo (página general y pestaña del expediente usan el mismo).
// Se ve como si el paciente estuviera de frente: su lado derecho queda a la izquierda.
function bloqueOdontograma(odonto) {
  const piezas = odonto.piezas || {};
  const d = (p) => renderDienteSVG(p, piezas[String(p)] || [], p === piezaOdontoSeleccionada);
  const fila = (lista, clase = "") => `
    <div class="fila-dientes ${clase}">
      <div class="mitad der">${lista.slice(0, lista.length / 2).map(d).join("")}</div>
      <div class="mitad izq">${lista.slice(lista.length / 2).map(d).join("")}</div>
    </div>`;
  const r = odonto.resumen || {};
  const conTemporales = estado.verTemporales ?? Object.keys(piezas).some((p) => Number(p) >= 51);
  return `
    <div class="odontograma-box ${estado.pincelOdonto ? "modo-pincel" : ""}">
      <div class="odonto-cab">
        <div class="odonto-resumen">
          <span class="${r.por_tratar ? "peligro-txt" : ""}"><b>${r.por_tratar ?? 0}</b> por tratar</span>
          <span><b>${r.tratados ?? 0}</b> tratados</span>
          <span><b>${r.piezas_con_hallazgos ?? Object.keys(piezas).length}</b> piezas con registros</span>
        </div>
        <label class="interruptor"><input type="checkbox" id="chkTemporales" ${conTemporales ? "checked" : ""}> Dientes de leche</label>
      </div>

      <div class="paso-odonto"><b>1.</b> Elija qué marcar <span class="tenue">(o deje “Ver detalle” para solo consultar)</span></div>
      ${leyendaOdonto()}
      <div class="paso-odonto"><b>2.</b> ${estado.pincelOdonto
        ? `Haga clic en las caras de los dientes para marcar <b>${esc(estado.pincelOdonto)}</b>. Se guarda al instante.`
        : "Haga clic en un diente para ver sus caras y sus registros."}</div>

      <div class="boca">
        <div class="lados"><span>Derecha del paciente</span><span>Izquierda del paciente</span></div>
        <div class="arcada-nombre">Superior</div>
        ${fila(PIEZAS_PERM_SUP)}
        ${conTemporales ? fila(PIEZAS_TEMP_SUP, "temporales") + fila(PIEZAS_TEMP_INF, "temporales") : '<div class="separador-arcadas"></div>'}
        ${fila(PIEZAS_PERM_INF)}
        <div class="arcada-nombre">Inferior</div>
      </div>
    </div>
    <div id="detallePiezaOdontograma" class="detalle-pieza-vacio">
      <p class="tenue">Ningún diente seleccionado.</p>
    </div>
    <h3 class="titulo-sec">Todos los hallazgos</h3>
    ${tablaHallazgos(odonto.hallazgos || [], true)}`;
}

function seleccionarPiezaOdontograma(pieza, cara = null) {
  const piezas = odontoActual().piezas || {};
  const hallazgos = piezas[String(pieza)] || [];
  caraOdontoSeleccionada = cara || (piezaOdontoSeleccionada === pieza ? caraOdontoSeleccionada : null) || "O";
  piezaOdontoSeleccionada = pieza;
  const k = caraOdontoSeleccionada;
  document.querySelectorAll(".boca .diente-caja").forEach((el) => {
    const p = Number(el.dataset.diente);
    el.classList.toggle("seleccionado", p === pieza);
    el.querySelectorAll(".cara-diente").forEach((c) => c.classList.toggle("cara-activa", p === pieza && c.dataset.caraClick === k));
  });
  const cont = $("#detallePiezaOdontograma");
  if (!cont) return;
  const tipo = pieza >= 51 ? "temporal" : "permanente";
  const lado = `${esSuperior(pieza) ? "superior" : "inferior"} ${ladoDerecho(pieza) ? "derecha" : "izquierda"}`;
  const enCara = hallazgos.filter((h) => h.cara === k || h.cara === "G");
  cont.className = "tarjeta-detalle-pieza";
  cont.innerHTML = `
    <div class="detalle-diente">
      ${renderDienteSVG(pieza, hallazgos, true, { grande: true })}
      <div class="caras-botones">
        ${["V", "L", "M", "D", "O"].map((c) => `<button type="button" class="cara-btn ${c === k ? "activo" : ""}" data-cara-click="${c}" data-pieza="${pieza}">${nombreCara(pieza, c)}</button>`).join("")}
      </div>
    </div>
    <div class="detalle-info">
      <header>
        <div><h4>Pieza ${pieza}</h4><p class="tenue">${tipo} · ${lado}</p></div>
        <button type="button" class="cerrar-detalle" data-cerrar-pieza aria-label="Cerrar">×</button>
      </header>
      <p class="cara-elegida">Cara elegida: <b>${nombreCara(pieza, k)}</b>${enCara.length ? ` · ${enCara.map((h) => `<i class="punto-color" style="background:${esc(h.color_hex)}"></i>${esc(h.hallazgo)}`).join(", ")}` : " · sana"}</p>
      <div class="marcar-rapido">
        <span class="tenue">Marcar en esta cara:</span>
        ${(estado.catHallazgos || []).map((h) => `<button type="button" class="pincel" data-marcar="${esc(h.nombre)}" data-pieza="${pieza}" data-cara="${h.toda ? "G" : k}" title="${h.toda ? "Se aplica a toda la pieza" : `Cara ${nombreCara(pieza, k)}`}"><i style="background:${esc(h.color)}"></i>${esc(h.nombre)}</button>`).join("")}
        <button type="button" class="btn sutil chico" data-accion="hallazgo-en-pieza" data-pieza-sel="${pieza}" data-cara-sel="${k}">Con notas y severidad…</button>
      </div>
      ${hallazgos.length ? tablaHallazgos(hallazgos, false) : `<p class="tenue">Esta pieza no tiene registros: está sana.</p>`}
    </div>`;
  cont.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// Guarda un hallazgo con un clic (desde la paleta o desde el detalle de la pieza)
async function marcarHallazgo(pieza, cara, nombre) {
  const h = (estado.catHallazgos || []).find((x) => x.nombre === nombre);
  if (!h) return;
  const caraFinal = h.toda ? "G" : cara;
  try {
    await api(`/api/dental/patients/${pacienteOdonto()}/odontogram/findings`, { method: "POST", body: {
      codigo_fdi: pieza, cara: caraFinal, hallazgo: h.nombre, color_hex: h.color,
      estado: ["restauracion", "ausencia"].includes(h.tipo) ? "tratado" : "activo",
    } });
    avisar(`Pieza ${pieza} · ${caraFinal === "G" ? "toda la pieza" : nombreCara(pieza, caraFinal)}: ${h.nombre}`);
    piezaOdontoSeleccionada = pieza;
    caraOdontoSeleccionada = caraFinal === "G" ? cara : caraFinal;
    refrescarOdonto();
  } catch (e) { avisar(e.message, true); }
}

function tablaHallazgos(lista, conPieza) {
  if (!lista.length) return `<div class="vacio-tabla"><p>Sin hallazgos registrados: todas las piezas se consideran sanas.</p></div>`;
  return `
    <table class="tabla-datos tabla-hallazgos">
      <thead><tr>${conPieza ? "<th>Pieza</th>" : ""}<th>Cara</th><th>Hallazgo</th><th>Estado</th><th>Severidad</th><th>Notas</th><th>Registrado</th><th></th></tr></thead>
      <tbody>
        ${lista.map((h) => `
          <tr>
            ${conPieza ? `<td><button type="button" class="enlace-pieza" data-diente-click="${h.codigo_fdi}">${h.codigo_fdi}</button></td>` : ""}
            <td>${esc(CARAS_TXT[h.cara] || h.cara)}</td>
            <td><i class="punto-color" style="background:${esc(h.color_hex || "#B42318")}"></i>${esc(h.hallazgo)}</td>
            <td><span class="estado ${h.estado === "tratado" ? "activo" : h.estado === "activo" ? "alerta" : "sutil"}">${esc(ESTADOS_HALLAZGO[h.estado] || h.estado || "Por tratar")}</span></td>
            <td>${esc(h.severidad || "—")}</td>
            <td>${esc(h.notas || "—")}</td>
            <td class="tenue">${fecha(h.fecha_registro, true)}${h.registrado_por ? `<br>${esc(h.registrado_por)}` : ""}</td>
            <td class="acciones-hallazgo">
              ${h.estado !== "tratado" ? `<button type="button" class="btn sutil chico" data-hallazgo-estado="tratado" data-fdi="${h.codigo_fdi}" data-cara="${h.cara}">Marcar tratado</button>` : ""}
              <button type="button" class="btn sutil chico peligro-txt" data-hallazgo-quitar data-fdi="${h.codigo_fdi}" data-cara="${h.cara}">Quitar</button>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

const odontoActual = () => (estado.pagina === "paciente" ? estado.dentalPaciente?.odontograma : estado.odontogramaGeneral) || {};
const pacienteOdonto = () => (estado.pagina === "paciente" ? estado.idSeleccionado : estado.pacienteOdontoSel);

// Vuelve a pintar el odontograma después de un cambio y conserva la pieza elegida
async function refrescarOdonto() {
  const [pieza, cara] = [piezaOdontoSeleccionada, caraOdontoSeleccionada];
  if (estado.pagina === "paciente") await abrirPaciente(estado.idSeleccionado, "dental-odontograma");
  else await pintarDentalOdontograma();
  if (pieza && $("#detallePiezaOdontograma")) seleccionarPiezaOdontograma(pieza, cara);
}

async function cambiarEstadoHallazgo(fdi, cara, nuevo) {
  try {
    await api(`/api/dental/patients/${pacienteOdonto()}/odontogram/findings/${fdi}/${cara}`, { method: "PATCH", body: { estado: nuevo } });
    avisar(`Pieza ${fdi}: hallazgo marcado como ${ESTADOS_HALLAZGO[nuevo].toLowerCase()}`);
    refrescarOdonto();
  } catch (e) { avisar(e.message, true); }
}

function quitarHallazgo(fdi, cara) {
  const h = (odontoActual().piezas?.[String(fdi)] || []).find((x) => x.cara === cara);
  abrirModal("Quitar hallazgo", `<p>Se quitará <b>${esc(h?.hallazgo || "el hallazgo")}</b> de la pieza ${fdi} (${esc(CARAS_TXT[cara] || cara)}).
    Use esta opción solo si se registró por error; si ya se atendió, márquelo como tratado.</p>`, "Quitar", async () => {
    await api(`/api/dental/patients/${pacienteOdonto()}/odontogram/findings/${fdi}/${cara}`, { method: "DELETE" });
    avisar(`Hallazgo quitado de la pieza ${fdi}`);
    refrescarOdonto();
  });
}

// ------------------------------------------------------------- Pestañas del Paciente
function pintarExpedienteOdontograma() {
  return `
    <div class="panel relleno">
      <header class="panel-cab">
        <div><h2>Odontograma</h2><p class="tenue">Notación FDI. Cada cara del diente se puede seleccionar.</p></div>
        ${btnAccion("nuevo-hallazgo-paciente", "+ Registrar hallazgo")}
      </header>
      ${bloqueOdontograma(estado.dentalPaciente?.odontograma || {})}
    </div>`;
}

function pintarExpedientePlanes() {
  const planes = estado.dentalPaciente?.planes_tratamiento || [];
  return `
    <div class="panel relleno">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
        <div>
          <h2 style="margin:0 0 4px 0">Planes de Tratamiento Odontológico</h2>
          <p class="tenue" style="margin:0">Evolución de fases terapéuticas (profilaxis, operatoria, endodoncia, prótesis).</p>
        </div>
        <div>${btnAccion("nuevo-plan-paciente", "+ Proponer plan de tratamiento")}</div>
      </div>

      ${planes.length ? `
        <div class="lista-planes" style="display:flex; flex-direction:column; gap:16px">
          ${planes.map((pl) => `
            <div class="tarjeta-plan" style="padding:16px; border:1px solid var(--linea); border-radius:8px; background:var(--blanco)">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px">
                <div>
                  <h3 style="margin:0 0 4px 0; font-size:16px">${esc(pl.diagnostico_general || "Plan Odontológico Integral")}</h3>
                  <span class="tenue">Propuesto el ${fecha(pl.fecha_propuesta)} · Odontólogo: ${esc(pl.odontologo_nombre || "Clínico")}</span>
                </div>
                <div style="text-align:right">
                  <span class="estado ${pl.estado === "aprobado_paciente" ? "activo" : (pl.estado === "en_curso" ? "alerta" : "sutil")}">${esc(pl.estado || "propuesto")}</span>
                  <div style="margin-top:4px; font-size:16px; font-weight:700">Q${Number(pl.costo_total_estimado || 0).toFixed(2)}</div>
                  ${pl.id_factura ? `<button type="button" class="btn sutil chico" data-ver-factura="${pl.id_factura}">Factura ${esc(pl.numero_factura || "")}</button>` : ""}
                </div>
              </div>

              <h4 style="margin:12px 0 8px 0; font-size:14px">Etapas y Fases de Tratamiento:</h4>
              <div class="grid-etapas" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:10px">
                ${(pl.etapas || []).map((et) => `
                  <div class="etapa-card" style="padding:12px; border-radius:6px; border:1px solid var(--linea); background:${et.estado === "completada" ? "#E8F5E9" : (et.estado === "en_curso" ? "#FFF8E1" : "var(--papel)")}">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
                      <b>Fase ${et.numero_etapa}: ${esc(et.nombre_etapa)}</b>
                      <span class="estado ${et.estado === "completada" ? "activo" : (et.estado === "en_curso" ? "alerta" : "sutil")}">${esc(et.estado)}</span>
                    </div>
                    <p style="font-size:13px; margin:0 0 8px 0; color:var(--tinta-2)">${esc(et.procedimientos_planificados || "Sin detalle")}</p>
                    <div style="display:flex; justify-content:space-between; align-items:center">
                      <small class="tenue">Costo: Q${Number(et.costo_estimado || 0).toFixed(2)}</small>
                      ${et.estado !== "completada" ? `
                        <div style="display:flex; gap:6px">
                          ${et.estado === "pendiente" ? `<button type="button" class="btn sutil chico" data-avanzar-etapa="${et.id_etapa}" data-plan-id="${pl.id_plan}" data-estado="en_curso">Iniciar</button>` : ""}
                          <button type="button" class="btn primario chico" data-avanzar-etapa="${et.id_etapa}" data-plan-id="${pl.id_plan}" data-estado="completada">Completar</button>
                        </div>
                      ` : '<span style="color:var(--verde); font-weight:600; font-size:12px">✓ Finalizada</span>'}
                    </div>
                  </div>
                `).join("")}
              </div>
            </div>
          `).join("")}
        </div>
      ` : `<div class="vacio-tabla"><p>No hay planes de tratamiento formulados para este paciente.</p>${btnAccion("nuevo-plan-paciente", "+ Proponer primer plan")}</div>`}
    </div>`;
}


function pintarExpedienteSomatometria() {
  const somas = estado.pediatricoPaciente?.somatometria || [];
  return `
    <div class="panel relleno">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
        <div>
          <h2 style="margin:0 0 4px 0">Control de Somatometría y Crecimiento</h2>
          <p class="tenue" style="margin:0">Evaluaciones antropométricas de peso, talla, perímetro cefálico y percentiles OMS.</p>
        </div>
        <div>${btnAccion("nueva-somatometria-paciente", "+ Registrar somatometría")}</div>
      </div>

      ${somas.length ? `
        <table class="tabla-datos">
          <thead><tr><th>Fecha Control</th><th>Edad</th><th class="num">Peso (kg)</th><th class="num">Talla (cm)</th><th class="num">P. Cefálico</th><th class="num">IMC</th><th>Percentil OMS</th><th>Observaciones</th></tr></thead>
          <tbody>
            ${somas.map((s) => `
              <tr>
                <td><b>${fecha(s.fecha_atencion || s.fecha || hoyISO())}</b></td>
                <td>${s.edad_meses_atencion != null ? `${s.edad_meses_atencion} meses` : "—"}</td>
                <td class="num"><b>${Number(s.peso_kg).toFixed(2)}</b> kg</td>
                <td class="num">${Number(s.talla_cm).toFixed(1)} cm</td>
                <td class="num">${s.perimetro_cefalico_cm ? `${Number(s.perimetro_cefalico_cm).toFixed(1)} cm` : "—"}</td>
                <td class="num">${s.imc_calculado ? Number(s.imc_calculado).toFixed(2) : "—"}</td>
                <td><span class="estado activo">P${s.percentil_peso_edad ?? s.percentil_crecimiento ?? 50}</span></td>
                <td class="tenue">${esc(s.observaciones || "Control ponderal adecuado")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<div class="vacio-tabla"><p>No hay registros de somatometría para este paciente.</p>${btnAccion("nueva-somatometria-paciente", "+ Registrar primera evaluación")}</div>`}
    </div>`;
}

function pintarExpedienteVacunas() {
  const vacs = estado.pediatricoPaciente?.vacunaciones || [];
  return `
    <div class="panel relleno">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
        <div>
          <h2 style="margin:0 0 4px 0">Carnet Oficial de Vacunación</h2>
          <p class="tenue" style="margin:0">Registro de biológicos aplicados, dosis, lotes y refuerzos programados.</p>
        </div>
        <div>${btnAccion("aplicar-vacuna-paciente", "+ Aplicar vacuna")}</div>
      </div>

      ${vacs.length ? `
        <table class="tabla-datos">
          <thead><tr><th>Biológico</th><th>Dosis</th><th>N.º Lote</th><th>Fecha Aplicación</th><th>Vía / Sitio</th><th>Profesional</th><th>Próximo Refuerzo</th></tr></thead>
          <tbody>
            ${vacs.map((v) => `
              <tr>
                <td><b>${esc(v.nombre_vacuna)}</b></td>
                <td>${esc(v.dosis || `Dosis #${v.numero_dosis || 1}`)}</td>
                <td><span class="estado sutil">${esc(v.lote || v.numero_lote || "LOTE-01")}</span></td>
                <td>${fecha(v.fecha_aplicacion)}</td>
                <td class="tenue">${esc(v.via_administracion || "Intramuscular")}</td>
                <td>${esc(v.profesional_aplico || v.profesional_nombre || "Enfermería")}</td>
                <td>${v.proxima_fecha_refuerzo ? `<span class="estado alerta">${fecha(v.proxima_fecha_refuerzo)}</span>` : "—"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<div class="vacio-tabla"><p>No hay vacunas registradas en el carnet del paciente.</p>${btnAccion("aplicar-vacuna-paciente", "+ Registrar primera vacuna")}</div>`}
    </div>`;
}

function pintarExpedienteHitos() {
  const hitos = estado.pediatricoPaciente?.hitos_desarrollo || [];
  const AREAS = {
    motricidad_gruesa: "Motricidad Gruesa",
    motricidad_fina: "Motricidad Fina / Adaptativa",
    lenguaje: "Lenguaje y Comunicación",
    personal_social: "Personal - Social"
  };

  return `
    <div class="panel relleno">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
        <div>
          <h2 style="margin:0 0 4px 0">Hitos del Desarrollo Psicomotor (Denver II)</h2>
          <p class="tenue" style="margin:0">Evaluación de maduración neurológica y psicomotriz por áreas funcionales.</p>
        </div>
        <div>${btnAccion("nuevo-hito-paciente", "+ Evaluar hito")}</div>
      </div>

      <div class="grid-hitos" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:14px; margin-bottom:20px">
        ${Object.entries(AREAS).map(([k, nombre]) => {
          const list = hitos.filter((h) => h.area_desarrollo === k);
          return `
            <div class="area-card" style="padding:14px; border:1px solid var(--linea); border-radius:8px; background:var(--blanco)">
              <h3 style="font-size:15px; margin:0 0 10px 0; color:var(--inst)">${nombre}</h3>
              ${list.length ? `
                <ul style="list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:8px">
                  ${list.map((h) => `
                    <li style="padding:8px; border-radius:6px; background:var(--papel); font-size:13px">
                      <div style="display:flex; justify-content:space-between; align-items:center">
                        <b>${esc(h.hito_evaluado)}</b>
                        <span class="estado ${h.cumple_hito ? "activo" : "baja"}">${h.cumple_hito ? "Logrado ✓" : "En proceso"}</span>
                      </div>
                      ${h.observaciones ? `<p class="tenue" style="margin:4px 0 0 0">${esc(h.observaciones)}</p>` : ""}
                    </li>
                  `).join("")}
                </ul>
              ` : `<p class="tenue" style="margin:0; font-size:13px">Sin evaluaciones en esta área.</p>`}
            </div>
          `;
        }).join("")}
      </div>
    </div>`;
}

function pintarExpedienteAlergias() {
  const alergias = estado.pediatricoPaciente?.alergias || [];
  const tieneGrave = alergias.some((a) => a.severidad === "grave" || a.riesgo_anafilaxia);

  return `
    <div class="panel relleno">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
        <div>
          <h2 style="margin:0 0 4px 0">Alergias Pediátricas</h2>
          <p class="tenue" style="margin:0">Diagnóstico de alérgenos con evaluación de riesgo anafiláctico.</p>
        </div>
        <div>${btnAccion("nueva-alergia-paciente", "+ Registrar alergia")}</div>
      </div>

      ${tieneGrave ? `
        <div class="alerta-anafilaxia-box" style="padding:12px 16px; border-radius:6px; background:#FDF2F2; border:1px solid var(--rojo); color:var(--rojo); margin-bottom:18px; display:flex; align-items:center; gap:10px">
          <span style="font-size:20px; font-weight:bold">⚠</span>
          <div>
            <b>ALERTA CLÍNICA: Paciente con alergia severa o riesgo de shock anafiláctico.</b>
            <p style="margin:2px 0 0 0; font-size:13px">Verifique medicamentos y alimentos antes de cualquier procedimiento clínico.</p>
          </div>
        </div>
      ` : ""}

      ${alergias.length ? `
        <table class="tabla-datos">
          <thead><tr><th>Alérgeno</th><th>Categoría</th><th>Severidad</th><th>Síntomas Observados</th><th>Fecha Diagnóstico</th></tr></thead>
          <tbody>
            ${alergias.map((a) => `
              <tr>
                <td><b>${esc(a.nombre_alergeno)}</b></td>
                <td><span class="estado sutil">${texto(a.tipo_alergeno)}</span></td>
                <td>
                  <span class="estado ${a.severidad === "grave" || a.riesgo_anafilaxia ? "critico" : (a.severidad === "moderada" ? "alerta" : "sutil")}">
                    ${a.severidad === "grave" || a.riesgo_anafilaxia ? "Grave (Anafilaxia)" : esc(a.severidad)}
                  </span>
                </td>
                <td>${esc(a.sintomas_observados || "—")}</td>
                <td class="tenue">${fecha(a.fecha_deteccion)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<div class="vacio-tabla"><p>No se han registrado alergias para este paciente (sin alergias conocidas).</p>${btnAccion("nueva-alergia-paciente", "+ Registrar alergia")}</div>`}
    </div>`;
}

// ------------------------------------------------------------- Páginas Pediátricas
async function pintarPediatricoVacunas() {
  cabecera({
    titulo: "Control de Vacunas y Cadena de Frío",
    acciones: btnAccion("nueva-vacuna-lote", "+ Nuevo lote de vacuna") + " " + btnAccion("aplicar-vacuna-general", "+ Registrar aplicación de vacuna")
  });
  $("#vista").innerHTML = `<p class="tenue relleno">Cargando control de biológicos…</p>`;

  try {
    const [cat, lotes, vacs] = await Promise.all([
      api("/api/pediatric/vaccines").catch(() => []),
      api("/api/pediatric/vaccine-batches").catch(() => []),
      api("/api/pediatric/vaccinations").catch(() => []),
    ]);
    if (estado.pagina !== "pediatrico-vacunas") return;

    const dosisDisp = lotes.reduce((s, l) => s + Number(l.dosis_disponibles || 0), 0);

    $("#vista").innerHTML = `
      <div class="cifras" style="margin-bottom:20px">
        <div class="cifra-caja">
          <span class="cifra-ico">${svg("vacuna")}</span>
          <span class="cifra-texto"><span class="cifra">${cat.length}</span><span class="cifra-etq">Biológicos en catálogo</span></span>
        </div>
        <div class="cifra-caja">
          <span class="cifra-ico">${svg("vacuna")}</span>
          <span class="cifra-texto"><span class="cifra">${lotes.length}</span><span class="cifra-etq">Lotes en frío (2°C – 8°C)</span></span>
        </div>
        <div class="cifra-caja">
          <span class="cifra-ico">${svg("frasco")}</span>
          <span class="cifra-texto"><span class="cifra">${dosisDisp}</span><span class="cifra-etq">Dosis disponibles</span></span>
        </div>
        <div class="cifra-caja">
          <span class="cifra-ico">${svg("vacuna")}</span>
          <span class="cifra-texto"><span class="cifra">${vacs.length}</span><span class="cifra-etq">Vacunas aplicadas</span></span>
        </div>
      </div>

      <div class="panel" style="margin-bottom:24px">
        <header class="panel-cab">
          <h2>Inventario de Lotes y Cadena de Frío</h2>
          <button type="button" class="btn sutil chico" data-accion="nueva-vacuna-lote">+ Nuevo lote</button>
        </header>
        ${lotes.length ? `
          <table class="tabla-datos">
            <thead><tr><th>N.º Lote</th><th>Vacuna</th><th>Cadena de Frío</th><th class="num">Dosis Disponibles</th><th>Vencimiento</th><th>Fabricante</th></tr></thead>
            <tbody>
              ${lotes.map((l) => `
                <tr>
                  <td><b>${esc(l.numero_lote)}</b></td>
                  <td>${esc(l.nombre_vacuna || `Vacuna #${l.id_vacuna}`)}</td>
                  <td><span class="temp-badge">${Number(l.temp_min_celsius).toFixed(1)}°C a ${Number(l.temp_max_celsius).toFixed(1)}°C</span></td>
                  <td class="num"><b>${esc(l.dosis_disponibles)}</b></td>
                  <td>${fecha(l.fecha_vencimiento)}</td>
                  <td class="tenue">${esc(l.fabricante || "—")}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No hay lotes de vacunas registrados en inventario.</p></div>`}
      </div>

      <div class="panel">
        <header class="panel-cab">
          <h2>Registro Histórico de Aplicación de Vacunas</h2>
          <button type="button" class="btn primario chico" data-accion="aplicar-vacuna-general">+ Aplicar vacuna</button>
        </header>
        ${vacs.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Fecha</th><th>Paciente</th><th>Vacuna</th><th>Dosis</th><th>Lote</th><th>Vía</th><th>Profesional</th><th>Refuerzo</th></tr></thead>
            <tbody>
              ${vacs.map((v) => `
                <tr>
                  <td>${fecha(v.fecha_aplicacion)}</td>
                  <td><button type="button" class="enlace-paciente" data-id="${v.id_paciente}" data-pestana-ir="pediatrico-vacunas"><b>${esc(v.paciente_nombre || nombreDe(v.id_paciente))}</b></button></td>
                  <td>${esc(v.nombre_vacuna)}</td>
                  <td>${esc(v.dosis || `Dosis #${v.numero_dosis || 1}`)}</td>
                  <td><span class="estado sutil">${esc(v.numero_lote || v.lote || "—")}</span></td>
                  <td class="tenue">${esc(v.via_administracion || "Intramuscular")}</td>
                  <td>${esc(v.profesional_aplico || v.profesional_nombre || "Enfermería")}</td>
                  <td>${v.proxima_fecha_refuerzo ? fecha(v.proxima_fecha_refuerzo) : "—"}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No se han registrado aplicaciones de biológicos.</p></div>`}
      </div>`;
  } catch (e) {
    avisar(e.message, true);
  }
}

async function pintarPediatricoCrecimiento() {
  cabecera({
    titulo: "Curvas de Crecimiento y Somatometría (OMS)",
    acciones: btnAccion("nueva-somatometria", "+ Registrar somatometría")
  });
  $("#vista").innerHTML = `<p class="tenue relleno">Cargando datos antropométricos y curvas de la OMS…</p>`;

  try {
    const [percentiles, somas] = await Promise.all([
      api("/api/pediatric/growth-percentiles").catch(() => []),
      api("/api/pediatric/somatometry").catch(() => []),
    ]);
    if (estado.pagina !== "pediatrico-crecimiento") return;

    $("#vista").innerHTML = `
      <div class="panel" style="margin-bottom:24px">
        <header class="panel-cab">
          <h2>Evaluaciones Somatométricas Registradas</h2>
          <button type="button" class="btn primario chico" data-accion="nueva-somatometria">+ Registrar somatometría</button>
        </header>
        ${somas.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Fecha</th><th>Paciente</th><th>Edad</th><th class="num">Peso (kg)</th><th class="num">Talla (cm)</th><th class="num">P. Cefálico</th><th class="num">IMC</th><th>Percentil OMS</th></tr></thead>
            <tbody>
              ${somas.map((s) => `
                <tr>
                  <td>${fecha(s.fecha_atencion || s.fecha || hoyISO())}</td>
                  <td><button type="button" class="enlace-paciente" data-id="${s.id_paciente}" data-pestana-ir="pediatrico-somatometria"><b>${esc(s.paciente_nombre || nombreDe(s.id_paciente))}</b></button></td>
                  <td>${s.edad_meses_atencion != null ? `${s.edad_meses_atencion} meses` : "—"}</td>
                  <td class="num"><b>${Number(s.peso_kg).toFixed(2)}</b> kg</td>
                  <td class="num">${Number(s.talla_cm).toFixed(1)} cm</td>
                  <td class="num">${s.perimetro_cefalico_cm ? `${Number(s.perimetro_cefalico_cm).toFixed(1)} cm` : "—"}</td>
                  <td class="num"><b>${s.imc_calculado ? Number(s.imc_calculado).toFixed(2) : "—"}</b></td>
                  <td><span class="estado activo">P${s.percentil_peso_edad ?? s.percentil_crecimiento ?? 50}</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No hay mediciones somatométricas registradas.</p></div>`}
      </div>

      <div class="panel">
        <header class="panel-cab">
          <h2>Tablas de Referencia Normativa OMS (0 a 5 años)</h2>
          <span class="tenue">Patrones de Crecimiento Infantil Organización Mundial de la Salud</span>
        </header>
        ${percentiles.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Parámetro</th><th>Sexo</th><th class="num">Edad (meses)</th><th class="num">P3 (-2 DE)</th><th class="num">P15</th><th class="num">Mediana P50</th><th class="num">P85</th><th class="num">P97 (+2 DE)</th></tr></thead>
            <tbody>
              ${percentiles.slice(0, 15).map((p) => `
                <tr>
                  <td><b>${texto(p.parametro)}</b></td>
                  <td>${p.sexo === "M" ? "Niños" : "Niñas"}</td>
                  <td class="num">${p.edad_meses} m</td>
                  <td class="num" style="color:var(--rojo)">${Number(p.p3).toFixed(2)}</td>
                  <td class="num">${Number(p.p15).toFixed(2)}</td>
                  <td class="num"><b>${Number(p.p50).toFixed(2)}</b></td>
                  <td class="num">${Number(p.p85).toFixed(2)}</td>
                  <td class="num" style="color:var(--ambar)">${Number(p.p97).toFixed(2)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<p class="tenue relleno">Cargando catálogo OMS…</p>`}
      </div>`;
  } catch (e) {
    avisar(e.message, true);
  }
}

async function pintarPediatricoDesarrollo() {
  cabecera({
    titulo: "Desarrollo Psicomotor (Denver II) y Alergias",
    acciones: btnAccion("nuevo-hito", "+ Evaluar hito Denver") + " " + btnAccion("nueva-alergia", "+ Registrar alergia")
  });
  $("#vista").innerHTML = `<p class="tenue relleno">Cargando hitos psicomotores y catálogo de alergias…</p>`;

  try {
    const [hitos, alergias] = await Promise.all([
      api("/api/pediatric/milestones").catch(() => []),
      api("/api/pediatric/allergies").catch(() => []),
    ]);
    if (estado.pagina !== "pediatrico-desarrollo") return;

    $("#vista").innerHTML = `
      <div class="panel" style="margin-bottom:24px">
        <header class="panel-cab">
          <h2>Evaluaciones de Desarrollo Psicomotor Denver II</h2>
          <button type="button" class="btn sutil chico" data-accion="nuevo-hito">+ Evaluar hito</button>
        </header>
        ${hitos.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Paciente</th><th>Área del Desarrollo</th><th>Hito Evaluado</th><th>Resultado</th><th>Observaciones</th></tr></thead>
            <tbody>
              ${hitos.map((h) => `
                <tr>
                  <td><button type="button" class="enlace-paciente" data-id="${h.id_paciente}" data-pestana-ir="pediatrico-hitos"><b>${esc(h.paciente_nombre || nombreDe(h.id_paciente))}</b></button></td>
                  <td><b>${texto(h.area_desarrollo)}</b></td>
                  <td>${esc(h.hito_evaluado)}</td>
                  <td><span class="estado ${h.cumple_hito ? "activo" : "baja"}">${h.cumple_hito ? "Logrado ✓" : "En proceso"}</span></td>
                  <td class="tenue">${esc(h.observaciones || "—")}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No se han registrado evaluaciones de hitos psicomotores.</p></div>`}
      </div>

      <div class="panel">
        <header class="panel-cab">
          <h2>Registro de Alergias Pediátricas Activas</h2>
          <button type="button" class="btn primario chico" data-accion="nueva-alergia">+ Registrar alergia</button>
        </header>
        ${alergias.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Paciente</th><th>Alérgeno</th><th>Categoría</th><th>Severidad</th><th>Síntomas</th><th>Fecha Detección</th></tr></thead>
            <tbody>
              ${alergias.map((a) => `
                <tr>
                  <td><button type="button" class="enlace-paciente" data-id="${a.id_paciente}" data-pestana-ir="pediatrico-alergias"><b>${esc(a.paciente_nombre || nombreDe(a.id_paciente))}</b></button></td>
                  <td><b>${esc(a.nombre_alergeno)}</b></td>
                  <td><span class="estado sutil">${texto(a.tipo_alergeno)}</span></td>
                  <td>
                    <span class="estado ${a.severidad === "grave" || a.riesgo_anafilaxia ? "critico" : (a.severidad === "moderada" ? "alerta" : "sutil")}">
                      ${a.severidad === "grave" || a.riesgo_anafilaxia ? "Grave (Anafilaxia)" : esc(a.severidad)}
                    </span>
                  </td>
                  <td>${esc(a.sintomas_observados || "—")}</td>
                  <td class="tenue">${fecha(a.fecha_deteccion)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No hay registros de alergias pediátricas.</p></div>`}
      </div>`;
  } catch (e) {
    avisar(e.message, true);
  }
}

// ----------------------------------------------------------- Páginas Odontológicas
async function pintarDentalOdontograma() {
  cabecera({ titulo: "Odontograma", acciones: btnAccion("nuevo-hallazgo", "+ Registrar hallazgo") });
  if (!$("#selPacienteOdonto")) $("#vista").innerHTML = `<p class="tenue relleno">Cargando odontograma…</p>`;
  try {
    const [pacientes] = await Promise.all([todosLosPacientes(), catalogoHallazgos()]);
    if (estado.pagina !== "dental-odontograma") return;
    const activos = pacientes.filter((p) => !ESTADOS_BAJA.includes(p.estado));
    if (!activos.some((p) => p.id_paciente === estado.pacienteOdontoSel)) {
      estado.pacienteOdontoSel = activos[0]?.id_paciente || null;
      piezaOdontoSeleccionada = null;
    }
    if (!estado.pacienteOdontoSel) {
      $("#vista").innerHTML = `<div class="vacio-tabla"><p>Aún no hay pacientes activos. Registre uno en Pacientes para abrir su odontograma.</p></div>`;
      return;
    }
    const odonto = await api(`/api/dental/patients/${estado.pacienteOdontoSel}/odontogram`);
    if (estado.pagina !== "dental-odontograma") return;
    estado.odontogramaGeneral = odonto;

    $("#vista").innerHTML = `
      <div class="barra-filtros barra-odonto">
        <label>Paciente
          <select id="selPacienteOdonto">
            ${activos.map((p) => `<option value="${p.id_paciente}" ${p.id_paciente === estado.pacienteOdontoSel ? "selected" : ""}>${esc(p.apellidos)}, ${esc(p.nombres)} · DPI ${esc(p.dpi)}</option>`).join("")}
          </select>
        </label>
        <button type="button" class="btn sutil" data-accion="ver-expediente-odonto">Abrir expediente</button>
      </div>
      <div class="panel relleno">${bloqueOdontograma(odonto)}</div>`;

    $("#selPacienteOdonto").addEventListener("change", (ev) => {
      estado.pacienteOdontoSel = Number(ev.target.value);
      piezaOdontoSeleccionada = null;
      estado.verTemporales = undefined;
      pintarDentalOdontograma();
    });
  } catch (e) {
    $("#vista").innerHTML = `<div class="vacio-tabla"><p>No se pudo cargar el odontograma: ${esc(e.message)}</p></div>`;
  }
}

async function pintarDentalPlanes() {
  cabecera({
    titulo: "Planes de Tratamiento Odontológico",
    acciones: btnAccion("nuevo-plan-tratamiento", "+ Proponer plan de tratamiento")
  });
  $("#vista").innerHTML = `<p class="tenue relleno">Cargando planes de tratamiento…</p>`;

  try {
    const planes = await api("/api/dental/treatment-plans").catch(() => []);
    if (estado.pagina !== "dental-planes") return;

    $("#vista").innerHTML = `
      <div class="panel">
        <header class="panel-cab">
          <h2>Planes Activos y Fases Terapéuticas</h2>
          <button type="button" class="btn primario chico" data-accion="nuevo-plan-tratamiento">+ Proponer plan</button>
        </header>
        ${planes.length ? `
          <div class="lista-planes" style="padding:16px; display:flex; flex-direction:column; gap:16px">
            ${planes.map((pl) => `
              <div class="tarjeta-plan" style="padding:16px; border:1px solid var(--linea); border-radius:8px; background:var(--blanco)">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px">
                  <div>
                    <h3 style="margin:0 0 4px 0; font-size:16px">${esc(pl.diagnostico_general || "Plan Dental")}</h3>
                    <span class="tenue">Paciente: <button type="button" class="enlace-paciente" data-id="${pl.id_paciente}" data-pestana-ir="dental-planes"><b>${esc(pl.paciente_nombre || nombreDe(pl.id_paciente))}</b></button> · ${fecha(pl.fecha_propuesta)}</span>
                  </div>
                  <div style="text-align:right">
                    <span class="estado ${pl.estado === "aprobado_paciente" ? "activo" : (pl.estado === "en_curso" ? "alerta" : "sutil")}">${esc(pl.estado || "propuesto")}</span>
                    <div style="margin-top:4px; font-size:16px; font-weight:700">Q${Number(pl.costo_total_estimado || 0).toFixed(2)}</div>
                  ${pl.id_factura ? `<button type="button" class="btn sutil chico" data-ver-factura="${pl.id_factura}">Factura ${esc(pl.numero_factura || "")}</button>` : ""}
                  </div>
                </div>

                <div class="grid-etapas" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:10px; margin-top:10px">
                  ${(pl.etapas || []).map((et) => `
                    <div class="etapa-card" style="padding:10px; border-radius:6px; border:1px solid var(--linea); background:${et.estado === "completada" ? "#E8F5E9" : (et.estado === "en_curso" ? "#FFF8E1" : "var(--papel)")}">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px">
                        <b>Fase ${et.numero_etapa}: ${esc(et.nombre_etapa)}</b>
                        <span class="estado ${et.estado === "completada" ? "activo" : (et.estado === "en_curso" ? "alerta" : "sutil")}">${esc(et.estado)}</span>
                      </div>
                      <p style="font-size:13px; margin:0 0 6px 0; color:var(--tinta-2)">${esc(et.procedimientos_planificados || "Sin detalle")}</p>
                      <div style="display:flex; justify-content:space-between; align-items:center">
                        <small class="tenue">Q${Number(et.costo_estimado || 0).toFixed(2)}</small>
                        ${et.estado !== "completada" ? `
                          <div style="display:flex; gap:6px">
                            ${et.estado === "pendiente" ? `<button type="button" class="btn sutil chico" data-avanzar-etapa="${et.id_etapa}" data-plan-id="${pl.id_plan}" data-estado="en_curso">Iniciar</button>` : ""}
                            <button type="button" class="btn primario chico" data-avanzar-etapa="${et.id_etapa}" data-plan-id="${pl.id_plan}" data-estado="completada">Completar</button>
                          </div>
                        ` : '<span style="color:var(--verde); font-weight:600; font-size:12px">✓ Completada</span>'}
                      </div>
                    </div>
                  `).join("")}
                </div>
              </div>
            `).join("")}
          </div>
        ` : `<div class="vacio-tabla"><p>No se han registrado planes de tratamiento odontológico.</p></div>`}
      </div>`;
  } catch (e) {
    avisar(e.message, true);
  }
}

async function pintarDentalAranceles() {
  cabecera({
    titulo: "Aranceles e Insumos Odontológicos",
    acciones: btnAccion("nuevo-procedimiento-arancel", "+ Nuevo procedimiento")
  });
  $("#vista").innerHTML = `<p class="tenue relleno">Cargando catálogo de aranceles e insumos…</p>`;

  try {
    const [procs, insumos] = await Promise.all([
      api("/api/dental/procedures").catch(() => []),
      api("/api/dental/supplies").catch(() => []),
    ]);
    if (estado.pagina !== "dental-aranceles") return;

    $("#vista").innerHTML = `
      <div class="panel" style="margin-bottom:24px">
        <header class="panel-cab">
          <h2>Aranceles y Catálogo de Procedimientos Dentales</h2>
          <button type="button" class="btn primario chico" data-accion="nuevo-procedimiento-arancel">+ Nuevo procedimiento</button>
        </header>
        ${procs.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Código</th><th>Procedimiento</th><th>Especialidad</th><th class="num">Costo Base</th><th class="num">Duración (min)</th></tr></thead>
            <tbody>
              ${procs.map((pr) => `
                <tr>
                  <td><b>${esc(pr.codigo || `DENT-${pr.id_procedimiento}`)}</b></td>
                  <td>${esc(pr.nombre_procedimiento)}</td>
                  <td><span class="estado sutil">${texto(pr.categoria || "Operatoria")}</span></td>
                  <td class="num"><b>Q${Number(pr.costo || pr.costo_base || 0).toFixed(2)}</b></td>
                  <td class="num">${esc(pr.duracion_minutos || pr.duracion_estimada_min || pr.duracion_promedio_min || 30)} min</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No hay procedimientos registrados en el arancel.</p></div>`}
      </div>

      <div class="panel">
        <header class="panel-cab">
          <h2>Inventario de Insumos y Biomateriales Dentales</h2>
          <span class="tenue">Resinas, amalgamas, anestésicos, conos y selladores</span>
        </header>
        ${insumos.length ? `
          <table class="tabla-datos">
            <thead><tr><th>Insumo / Biomaterial</th><th>Categoría</th><th class="num">Stock Actual</th><th class="num">Stock Mínimo</th><th>Unidad</th><th>Estado</th></tr></thead>
            <tbody>
              ${insumos.map((i) => {
                const bajo = Number(i.stock_actual) <= Number(i.stock_minimo);
                return `
                  <tr>
                    <td><b>${esc(i.nombre_insumo || i.nombre)}</b></td>
                    <td>${texto(i.categoria || "Materiales")}</td>
                    <td class="num"><b>${esc(i.stock_actual)}</b></td>
                    <td class="num">${esc(i.stock_minimo)}</td>
                    <td class="tenue">${esc(i.unidad_medida || "unidad")}</td>
                    <td><span class="estado ${bajo ? "critico" : "activo"}">${bajo ? "Stock bajo" : "Adecuado"}</span></td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        ` : `<div class="vacio-tabla"><p>No hay insumos registrados en inventario.</p></div>`}
      </div>`;
  } catch (e) {
    avisar(e.message, true);
  }
}

// ------------------------------------------------------------- Formularios Modales
async function formNuevoLoteVacuna() {
  const cat = await api("/api/pediatric/vaccines").catch(() => []);
  const manana = new Date(Date.now() + 365 * 86400000).toISOString().slice(0, 10);
  const html = `
    <div class="rejilla">
      <label class="completo"><span class="requerido">Vacuna / Biológico</span>
        <select name="id_vacuna" required>
          <option value="">Seleccione biológico…</option>
          ${cat.map((v) => `<option value="${v.id_vacuna}">${esc(v.nombre_vacuna)} (${esc(v.via_administracion)})</option>`).join("")}
        </select>
      </label>
      ${campo("numero_lote", "Número de lote", { req: true, extra: 'placeholder="Ej. LOT-2026-BCG"' })}
      ${campo("fecha_vencimiento", "Fecha de vencimiento", { tipo: "date", req: true, valor: manana })}
      ${campo("dosis_disponibles", "Dosis disponibles", { tipo: "number", req: true, valor: "50" })}
      ${campo("temp_min_celsius", "Temp. Mínima (°C)", { tipo: "number", req: true, valor: "2.0", extra: 'step="0.1"' })}
      ${campo("temp_max_celsius", "Temp. Máxima (°C)", { tipo: "number", req: true, valor: "8.0", extra: 'step="0.1"' })}
      ${campo("fabricante", "Laboratorio fabricante", { valor: "Sanofi Pasteur" })}
    </div>`;

  abrirModal("Registrar Lote de Vacuna en Cadena de Frío", html, "Guardar Lote", async (fd) => {
    const d = datosForm(fd);
    d.id_vacuna = Number(d.id_vacuna);
    d.dosis_disponibles = Number(d.dosis_disponibles);
    d.dosis_recibidas = d.dosis_disponibles;
    d.temp_min_celsius = Number(d.temp_min_celsius);
    d.temp_max_celsius = Number(d.temp_max_celsius);
    await api("/api/pediatric/vaccine-batches", { method: "POST", body: d });
    avisar(`Lote ${d.numero_lote} registrado correctamente en cadena de frío`);
    if (estado.pagina === "pediatrico-vacunas") pintarPediatricoVacunas();
  });
}

async function formAplicarVacuna(idPaciente = null) {
  const pacientes = idPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const lotes = await api("/api/pediatric/vaccine-batches").catch(() => []);
  const html = `
    <div class="rejilla">
      ${idPaciente ? `<p class="completo">Paciente: <b>${nombreDe(idPaciente)}</b></p>` : `
        <label class="completo"><span class="requerido">Paciente infantil</span>
          <select name="id_paciente" required>
            <option value="">Seleccione paciente…</option>
            ${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)} — ${esc(p.dpi)}</option>`).join("")}
          </select>
        </label>`}
      <label class="completo"><span class="requerido">Lote de Vacuna (Cadena de Frío)</span>
        <select name="id_lote" required>
          <option value="">Seleccione lote…</option>
          ${lotes.map((l) => `<option value="${l.id_lote}">${esc(l.nombre_vacuna)} · Lote ${esc(l.numero_lote)} (Disp: ${l.dosis_disponibles})</option>`).join("")}
        </select>
      </label>
      <label><span class="requerido">Número de dosis</span>
        <select name="numero_dosis" required>
          <option value="1">1.ª Dosis</option>
          <option value="2">2.ª Dosis</option>
          <option value="3">3.ª Dosis</option>
          <option value="4">Refuerzo 1</option>
          <option value="5">Refuerzo 2</option>
        </select>
      </label>
      <label><span class="requerido">Vía de administración</span>
        <select name="via_administracion" required>
          <option value="Intramuscular">Intramuscular</option>
          <option value="Subcutánea">Subcutánea</option>
          <option value="Oral">Oral</option>
          <option value="Intradérmica">Intradérmica</option>
        </select>
      </label>
      ${campo("profesional_aplico", "Profesional aplicador", { req: true, valor: estado.usuario?.nombre_completo || "Enfermería" })}
      ${campo("proxima_fecha_refuerzo", "Próximo refuerzo (opcional)", { tipo: "date" })}
    </div>`;

  abrirModal("Registrar Aplicación de Vacuna", html, "Registrar Aplicación", async (fd) => {
    const d = datosForm(fd);
    const pid = idPaciente || Number(d.id_paciente);
    d.id_lote = Number(d.id_lote);
    d.numero_dosis = Number(d.numero_dosis);
    d.dosis = `${d.numero_dosis}.ª dosis`;
    await api(`/api/pediatric/patients/${pid}/vaccinations`, { method: "POST", body: d });
    avisar("Vacuna aplicada y registrada en el carnet infantil");
    if (estado.pagina === "paciente") abrirPaciente(pid, "pediatrico-vacunas");
    else if (estado.pagina === "pediatrico-vacunas") pintarPediatricoVacunas();
  });
}

async function formSomatometria(idPaciente = null) {
  const pacientes = idPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const html = `
    <div class="rejilla">
      ${idPaciente ? `<p class="completo">Paciente: <b>${nombreDe(idPaciente)}</b></p>` : `
        <label class="completo"><span class="requerido">Paciente infantil</span>
          <select name="id_paciente" required>
            <option value="">Seleccione paciente…</option>
            ${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)} — ${esc(p.dpi)}</option>`).join("")}
          </select>
        </label>`}
      ${campo("peso_kg", "Peso (kg)", { tipo: "number", req: true, extra: 'step="0.01" min="0.3" max="150" placeholder="12.5"' })}
      ${campo("talla_cm", "Talla (cm)", { tipo: "number", req: true, extra: 'step="0.1" min="20" max="200" placeholder="85.0"' })}
      ${campo("perimetro_cefalico_cm", "Perímetro cefálico (cm)", { tipo: "number", extra: 'step="0.1" min="20" max="70" placeholder="47.0"' })}
      ${campo("edad_meses_atencion", "Edad en meses", { tipo: "number", extra: 'min="0" max="216" placeholder="24"' })}
      ${campo("observaciones", "Observaciones clínicas", { clase: "completo", extra: 'placeholder="Curva de crecimiento adecuada"' })}
    </div>`;

  abrirModal("Registrar Control de Somatometría", html, "Guardar Medición", async (fd) => {
    const d = datosForm(fd);
    const pid = idPaciente || Number(d.id_paciente);
    d.peso_kg = Number(d.peso_kg);
    d.talla_cm = Number(d.talla_cm);
    if (d.perimetro_cefalico_cm) d.perimetro_cefalico_cm = Number(d.perimetro_cefalico_cm);
    if (d.edad_meses_atencion) d.edad_meses_atencion = Number(d.edad_meses_atencion);
    await api(`/api/pediatric/patients/${pid}/somatometry`, { method: "POST", body: d });
    avisar("Somatometría registrada y percentiles calculados");
    if (estado.pagina === "paciente") abrirPaciente(pid, "pediatrico-somatometria");
    else if (estado.pagina === "pediatrico-crecimiento") pintarPediatricoCrecimiento();
  });
}

async function formHito(idPaciente = null) {
  const pacientes = idPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const html = `
    <div class="rejilla">
      ${idPaciente ? `<p class="completo">Paciente: <b>${nombreDe(idPaciente)}</b></p>` : `
        <label class="completo"><span class="requerido">Paciente</span>
          <select name="id_paciente" required>
            <option value="">Seleccione paciente…</option>
            ${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)}</option>`).join("")}
          </select>
        </label>`}
      <label class="completo"><span class="requerido">Área del Desarrollo</span>
        <select name="area_desarrollo" required>
          <option value="motricidad_gruesa">Motricidad Gruesa</option>
          <option value="motricidad_fina">Motricidad Fina / Adaptativa</option>
          <option value="lenguaje">Lenguaje y Comunicación</option>
          <option value="personal_social">Personal - Social</option>
        </select>
      </label>
      ${campo("hito_evaluado", "Hito psicomotor evaluado", { req: true, clase: "completo", extra: 'placeholder="Ej. Sostiene la cabeza firmemente al sentarse"' })}
      <label><span class="requerido">Resultado</span>
        <select name="cumple_hito" required>
          <option value="1">Logrado (Normal para la edad) ✓</option>
          <option value="0">En desarrollo / En proceso</option>
        </select>
      </label>
      ${campo("observaciones", "Observaciones", { clase: "completo" })}
    </div>`;

  abrirModal("Evaluar Hito Psicomotor (Denver II)", html, "Guardar Evaluación", async (fd) => {
    const d = datosForm(fd);
    const pid = idPaciente || Number(d.id_paciente);
    d.cumple_hito = d.cumple_hito === "1";
    await api(`/api/pediatric/patients/${pid}/milestones`, { method: "POST", body: d });
    avisar("Hito psicomotor registrado");
    if (estado.pagina === "paciente") abrirPaciente(pid, "pediatrico-hitos");
    else if (estado.pagina === "pediatrico-desarrollo") pintarPediatricoDesarrollo();
  });
}

async function formAlergia(idPaciente = null) {
  const pacientes = idPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const cat = await api("/api/pediatric/allergens").catch(() => []);
  const html = `
    <div class="rejilla">
      ${idPaciente ? `<p class="completo">Paciente: <b>${nombreDe(idPaciente)}</b></p>` : `
        <label class="completo"><span class="requerido">Paciente</span>
          <select name="id_paciente" required>
            <option value="">Seleccione paciente…</option>
            ${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)}</option>`).join("")}
          </select>
        </label>`}
      <label class="completo"><span class="requerido">Alérgeno</span>
        <select name="id_alergeno" required>
          <option value="">Seleccione alérgeno…</option>
          ${cat.map((a) => `<option value="${a.id_alergeno}">${esc(a.nombre_alergeno)} (${texto(a.tipo_alergeno)})${a.riesgo_anafilaxia ? " ⚠ Anafiláctico" : ""}</option>`).join("")}
        </select>
      </label>
      <label><span class="requerido">Severidad</span>
        <select name="severidad" required>
          <option value="leve">Leve (eritema / prurito leve)</option>
          <option value="moderada">Moderada (urticaria extensa / angioedema)</option>
          <option value="grave">Grave / Anafilaxia (broncoespasmo / hipotensión)</option>
        </select>
      </label>
      ${campo("fecha_deteccion", "Fecha de detección", { tipo: "date", req: true, valor: hoyISO() })}
      ${campo("sintomas_observados", "Síntomas observados", { clase: "completo", extra: 'placeholder="Urticaria facial y dificultad respiratoria"' })}
    </div>`;

  abrirModal("Registrar Diagnóstico de Alergia Infantil", html, "Registrar Alergia", async (fd) => {
    const d = datosForm(fd);
    const pid = idPaciente || Number(d.id_paciente);
    d.id_alergeno = Number(d.id_alergeno);
    await api(`/api/pediatric/patients/${pid}/allergies`, { method: "POST", body: d });
    avisar("Alergia pediátrica registrada en el expediente");
    if (estado.pagina === "paciente") abrirPaciente(pid, "pediatrico-alergias");
    else if (estado.pagina === "pediatrico-desarrollo") pintarPediatricoDesarrollo();
  });
}

function formPerinatal(pid) {
  const peri = estado.pediatricoPaciente?.antecedente_perinatal || {};
  const html = `
    <div class="rejilla">
      ${campo("semanas_gestacion", "Semanas de gestación", { tipo: "number", valor: peri.semanas_gestacion || 39, extra: 'min="20" max="45"' })}
      ${campo("peso_nacer_kg", "Peso al nacer (kg)", { tipo: "number", valor: peri.peso_nacer_kg || 3.2, extra: 'step="0.01" min="0.3" max="7"' })}
      ${campo("talla_nacer_cm", "Talla al nacer (cm)", { tipo: "number", valor: peri.talla_nacer_cm || 50.0, extra: 'step="0.1" min="20" max="65"' })}
      ${campo("perimetro_cefalico_nacer_cm", "P. Cefálico al nacer (cm)", { tipo: "number", valor: peri.perimetro_cefalico_nacer_cm || 34.5, extra: 'step="0.1" min="20" max="50"' })}
      <label><span class="requerido">Vía de parto</span>
        <select name="tipo_parto" required>
          ${opciones([["Eutócico vaginal", "Eutócico vaginal"], ["Cesárea electiva", "Cesárea electiva"], ["Cesárea de urgencia", "Cesárea de urgencia"], ["Parto instrumentado", "Parto instrumentado"]], peri.tipo_parto || "Eutócico vaginal")}
        </select>
      </label>
      ${campo("apgar_1min", "Apgar al 1 min (0–10)", { tipo: "number", valor: peri.apgar_1min != null ? peri.apgar_1min : 9, extra: 'min="0" max="10"' })}
      ${campo("apgar_5min", "Apgar a los 5 min (0–10)", { tipo: "number", valor: peri.apgar_5min != null ? peri.apgar_5min : 10, extra: 'min="0" max="10"' })}
      ${campo("complicaciones_neonatales", "Complicaciones neonatales", { clase: "completo", valor: peri.complicaciones_neonatales || "Sin complicaciones" })}
    </div>`;

  abrirModal("Actualizar Antecedentes Perinatales", html, "Guardar Antecedentes", async (fd) => {
    const d = datosForm(fd);
    d.semanas_gestacion = Number(d.semanas_gestacion);
    d.peso_nacer_kg = Number(d.peso_nacer_kg);
    d.talla_nacer_cm = Number(d.talla_nacer_cm);
    d.apgar_1min = Number(d.apgar_1min);
    d.apgar_5min = Number(d.apgar_5min);
    await api(`/api/pediatric/patients/${pid}/perinatal`, { method: "PUT", body: d });
    avisar("Antecedentes perinatales actualizados");
    abrirPaciente(pid, "datos");
  });
}

function formTutor(pid) {
  const tutor = estado.pediatricoPaciente?.tutores?.[0] || {};
  const html = `
    <div class="rejilla">
      ${campo("nombres", "Nombres del tutor", { req: true, valor: tutor.nombres || "" })}
      ${campo("apellidos", "Apellidos del tutor", { valor: tutor.apellidos || "" })}
      ${campo("parentesco", "Parentesco", { req: true, valor: tutor.parentesco || "Madre", extra: 'placeholder="Madre, Padre, Abuela..."' })}
      ${campo("dpi", "DPI del tutor", { req: true, valor: tutor.dpi || "" })}
      ${campo("telefono_principal", "Teléfono de contacto", { req: true, valor: tutor.telefono_principal || "" })}
      ${campo("direccion", "Dirección de residencia", { clase: "completo", valor: tutor.direccion || "" })}
    </div>`;

  abrirModal("Actualizar Tutor Legal y Custodia", html, "Guardar Tutor", async (fd) => {
    const d = datosForm(fd);
    await api(`/api/pediatric/patients/${pid}/guardian`, { method: "PUT", body: d });
    avisar("Tutor legal actualizado correctamente");
    abrirPaciente(pid, "datos");
  });
}

function formAnamnesisSistemica(pid) {
  const s = estado.dentalPaciente?.antecedentes_sistemicos || {};
  const html = `
    <div class="rejilla">
      <p class="completo tenue" style="margin:0 0 10px 0">Marque las condiciones médicas preexistentes para activar las precauciones clínicas en los procedimientos odontológicos:</p>
      <label><input type="checkbox" name="hipertension" value="1" ${s.hipertension ? "checked" : ""}> Hipertensión arterial</label>
      <label><input type="checkbox" name="diabetes" value="1" ${s.diabetes ? "checked" : ""}> Diabetes mellitus</label>
      <label><input type="checkbox" name="enfermedad_cardiaca" value="1" ${s.enfermedad_cardiaca ? "checked" : ""}> Cardiopatía / Soplo</label>
      <label><input type="checkbox" name="trastornos_hemorragicos" value="1" ${s.trastornos_hemorragicos ? "checked" : ""}> Trastornos de coagulación</label>
      <label><input type="checkbox" name="alergia_anestesia_local" value="1" ${s.alergia_anestesia_local ? "checked" : ""}> Alergia a anestesia local</label>
      <label><input type="checkbox" name="alergia_latex" value="1" ${s.alergia_latex ? "checked" : ""}> Alergia al látex</label>
      <label><input type="checkbox" name="embarazo" value="1" ${s.embarazo ? "checked" : ""}> Paciente embarazada</label>
      ${campo("meses_embarazo", "Meses de gestación", { tipo: "number", valor: s.meses_embarazo || 0, extra: 'min="0" max="9"' })}
      <label class="completo">Medicamentos actuales que consume
        <textarea name="medicamentos_actuales" placeholder="Antihipertensivos, hipoglucemiantes, anticoagulantes...">${esc(s.medicamentos_actuales || "")}</textarea>
      </label>
      <label class="completo">Observaciones médicas y antecedentes hospitalarios
        <textarea name="observaciones_medicas" placeholder="Observaciones para el acto odontológico">${esc(s.observaciones_medicas || "")}</textarea>
      </label>
    </div>`;

  abrirModal("Anamnesis Médica y Riesgo Sistémico Odontológico", html, "Guardar Antecedentes", async (fd) => {
    const d = {
      hipertension: fd.get("hipertension") === "1",
      diabetes: fd.get("diabetes") === "1",
      enfermedad_cardiaca: fd.get("enfermedad_cardiaca") === "1",
      trastornos_hemorragicos: fd.get("trastornos_hemorragicos") === "1",
      alergia_anestesia_local: fd.get("alergia_anestesia_local") === "1",
      alergia_latex: fd.get("alergia_latex") === "1",
      embarazo: fd.get("embarazo") === "1",
      meses_embarazo: Number(fd.get("meses_embarazo") || 0),
      medicamentos_actuales: String(fd.get("medicamentos_actuales") || "").trim(),
      observaciones_medicas: String(fd.get("observaciones_medicas") || "").trim(),
    };
    await api(`/api/dental/patients/${pid}/systemic`, { method: "PUT", body: d });
    avisar("Anamnesis médica actualizada con éxito");
    abrirPaciente(pid, "datos");
  });
}

async function formHallazgoDental(idPaciente = null, piezaPre = null, caraPre = null) {
  const pid = idPaciente || estado.pacienteOdontoSel || estado.idSeleccionado;
  if (!pid) { avisar("Elija primero un paciente", true); return; }
  const cat = await catalogoHallazgos();
  if (!cat.length) { avisar("No se pudo cargar el catálogo de hallazgos", true); return; }
  const grupo = (titulo, lista) => `<optgroup label="${titulo}">${lista.map((p) => `<option value="${p}" ${p === piezaPre ? "selected" : ""}>${p}</option>`).join("")}</optgroup>`;
  const html = `
    <div class="rejilla" id="cuerpoHallazgo">
      <p class="completo">Paciente: <b>${esc(nombreDe(pid))}</b></p>
      <label><span class="requerido">Pieza (FDI)</span>
        <select name="codigo_fdi" required>
          ${piezaPre ? "" : `<option value="">Seleccione…</option>`}
          ${grupo("Permanentes superiores", [...PIEZAS_PERM_SUP].sort((a, b) => a - b))}
          ${grupo("Permanentes inferiores", [...PIEZAS_PERM_INF].sort((a, b) => a - b))}
          ${grupo("Temporales superiores", [...PIEZAS_TEMP_SUP].sort((a, b) => a - b))}
          ${grupo("Temporales inferiores", [...PIEZAS_TEMP_INF].sort((a, b) => a - b))}
        </select>
      </label>
      <label><span class="requerido">Cara</span>
        <select name="cara" required>${opciones(Object.entries(CARAS_TXT), caraPre || "O")}</select>
      </label>
      <label class="completo"><span class="requerido">Hallazgo</span>
        <select name="hallazgo" required id="selHallazgoOdonto">
          <option value="">Seleccione…</option>
          ${["patologia", "restauracion", "ausencia"].map((tipo) => {
            const lista = cat.filter((h) => (["restauracion", "ausencia"].includes(h.tipo) ? h.tipo : "patologia") === tipo);
            return lista.length ? `<optgroup label="${{ patologia: "Patologías", restauracion: "Tratamientos y restauraciones", ausencia: "Ausencias" }[tipo]}">
              ${lista.map((h) => `<option value="${esc(h.nombre)}" data-color="${esc(h.color)}" data-toda="${h.toda ? 1 : ""}" data-tipo="${esc(h.tipo)}">${esc(h.nombre)}</option>`).join("")}</optgroup>` : "";
          }).join("")}
        </select>
      </label>
      <label><span class="requerido">Estado</span>
        <select name="estado" required>${opciones(Object.entries(ESTADOS_HALLAZGO), "activo")}</select>
      </label>
      <label>Severidad
        <select name="severidad">${opciones([["", "—"], ["leve", "Leve"], ["moderada", "Moderada"], ["severa", "Severa"]], "")}</select>
      </label>
      <label>Color en el odontograma
        <input type="color" name="color_hex" value="${esc(cat[0].color)}" id="colorHallazgoOdonto">
      </label>
      <p class="completo tenue" id="ayudaHallazgo">Si esa cara ya tenía un hallazgo, se reemplaza y el anterior queda en su historial.</p>
      <label class="completo">Notas clínicas
        <textarea name="notas" maxlength="255" placeholder="Ej.: cavitación con compromiso dentinario"></textarea>
      </label>
    </div>`;

  abrirModal("Registrar hallazgo", html, "Guardar hallazgo", async (fd) => {
    const d = datosForm(fd);
    d.codigo_fdi = Number(d.codigo_fdi);
    await api(`/api/dental/patients/${pid}/odontogram/findings`, { method: "POST", body: d });
    avisar(`Hallazgo registrado en la pieza ${d.codigo_fdi}`);
    piezaOdontoSeleccionada = d.codigo_fdi;
    caraOdontoSeleccionada = d.cara;
    refrescarOdonto();
  });

  const cuerpo = $("#cuerpoHallazgo");
  cuerpo.querySelector("#selHallazgoOdonto").addEventListener("change", (ev) => {
    const op = ev.target.selectedOptions[0];
    if (!op?.value) return;
    cuerpo.querySelector("#colorHallazgoOdonto").value = op.dataset.color || "#B42318";
    // Ausencias, coronas y endodoncias afectan a toda la pieza
    if (op.dataset.toda) cuerpo.querySelector("[name=cara]").value = "G";
    if (op.dataset.tipo === "restauracion" || op.dataset.tipo === "ausencia") cuerpo.querySelector("[name=estado]").value = "tratado";
    if (op.dataset.tipo === "patologia") cuerpo.querySelector("[name=estado]").value = "activo";
  });
}

async function formPlanTratamiento(idPaciente = null) {
  const pacientes = idPaciente ? [] : (await todosLosPacientes()).filter((p) => !ESTADOS_BAJA.includes(p.estado));
  const html = `
    <div class="rejilla">
      ${idPaciente ? `<p class="completo">Paciente: <b>${nombreDe(idPaciente)}</b></p>` : `
        <label class="completo"><span class="requerido">Paciente</span>
          <select name="id_paciente" required>
            <option value="">Seleccione paciente…</option>
            ${pacientes.map((p) => `<option value="${p.id_paciente}">${esc(p.apellidos)}, ${esc(p.nombres)}</option>`).join("")}
          </select>
        </label>`}
      ${campo("diagnostico_general", "Diagnóstico general", { req: true, clase: "completo", extra: 'placeholder="Caries múltiple y gingivitis marginal crónica"' })}
      ${campo("costo_total_estimado", "Costo total estimado (Q)", { tipo: "number", req: true, extra: 'step="0.01" placeholder="1850.00"' })}
      <fieldset class="completo paso"><legend>Primera Etapa del Plan</legend>
        <div class="rejilla">
          ${campo("nombre_etapa", "Nombre de la fase", { req: true, valor: "Fase 1: Higiene y Detartraje" })}
          ${campo("costo_estimado", "Costo de esta fase (Q)", { tipo: "number", req: true, valor: "350.00", extra: 'step="0.01"' })}
          ${campo("procedimientos_planificados", "Procedimientos planificados", { clase: "completo", valor: "Profilaxis dental completa, raspaje supra y subgingival" })}
        </div>
      </fieldset>
    </div>`;

  abrirModal("Formular Plan de Tratamiento Odontológico", html, "Crear Plan", async (fd) => {
    const d = datosForm(fd);
    const pid = idPaciente || Number(d.id_paciente);
    const payload = {
      id_paciente: pid,
      diagnostico_general: d.diagnostico_general,
      costo_total_estimado: Number(d.costo_total_estimado),
      etapas: [{
        numero_etapa: 1,
        nombre_etapa: d.nombre_etapa,
        procedimientos_planificados: d.procedimientos_planificados,
        costo_estimado: Number(d.costo_estimado),
        estado: "pendiente"
      }]
    };
    const plan = await api("/api/dental/treatment-plans", { method: "POST", body: payload });
    avisar(plan.numero_factura ? `Plan propuesto · la factura ${plan.numero_factura} quedó en Caja para abonos` : "Plan de tratamiento propuesto");
    if (estado.pagina === "paciente") abrirPaciente(pid, "dental-planes");
    else if (estado.pagina === "dental-planes") pintarDentalPlanes();
  });
}

async function cambiarEstadoEtapaTratamiento(planId, etapaId, nuevoEstado) {
  try {
    await api(`/api/dental/treatment-plans/${planId}/stages/${etapaId}`, { method: "PUT", body: { estado: nuevoEstado } });
    avisar(`Fase marcada como "${nuevoEstado}"`);
    if (estado.pagina === "paciente") abrirPaciente(estado.idSeleccionado, "dental-planes");
    else if (estado.pagina === "dental-planes") pintarDentalPlanes();
  } catch (e) {
    avisar(e.message, true);
  }
}

function formProcedimientoArancel() {
  const html = `
    <div class="rejilla">
      ${campo("codigo", "Código de arancel", { req: true, extra: 'placeholder="OP-10"' })}
      ${campo("nombre_procedimiento", "Nombre del procedimiento", { req: true, clase: "doble", extra: 'placeholder="Restauración con resina compuesta fotocurable"' })}
      <label><span class="requerido">Especialidad</span>
        <select name="categoria" required>
          <option value="Operatoria">Operatoria Dental</option>
          <option value="Endodoncia">Endodoncia</option>
          <option value="Periodoncia">Periodoncia</option>
          <option value="Cirugía">Cirugía Bucal</option>
          <option value="Odontopediatría">Odontopediatría</option>
          <option value="Ortodoncia">Ortodoncia</option>
          <option value="Rehabilitación">Rehabilitación Oral</option>
        </select>
      </label>
      ${campo("costo", "Costo base (Q)", { tipo: "number", req: true, extra: 'step="0.01" placeholder="250.00"' })}
      ${campo("duracion_minutos", "Duración estimada (min)", { tipo: "number", valor: "45", extra: 'step="5"' })}
    </div>`;

  abrirModal("Nuevo Procedimiento al Arancel Odontológico", html, "Guardar Procedimiento", async (fd) => {
    const d = datosForm(fd);
    d.costo = Number(d.costo);
    d.duracion_minutos = Number(d.duracion_minutos);
    await api("/api/dental/procedures", { method: "POST", body: d });
    avisar("Procedimiento añadido al arancel");
    if (estado.pagina === "dental-aranceles") pintarDentalAranceles();
  });
}

// -------------------------------------------------------------------- Inicio
(async function inicio() {
  const s = leerSesion();
  if (s?.token) {
    estado.token = s.token;
    try {
      const u = await api("/api/auth/me");
      entrar({ ...u, token: s.token });
      return;
    } catch (_) {
      guardarSesion(null);
      estado.token = null;
    }
  }
  iniciarLogin();
})();
