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

  $("#listaInstituciones").innerHTML = Object.values(INST).map((i) => `
    <li><span class="punto" style="background:${i.color}"></span><span>${i.nombre}</span>
    <span class="motor-nombre">${i.motor}</span></li>`).join("");

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
  salir: '<path d="M15 4h4v16h-4"/><path d="M10 8l-4 4 4 4"/><path d="M6 12h10"/>',
};
const svg = (n) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONO[n]}</svg>`;
document.querySelectorAll("[data-icono]").forEach((el) => { el.innerHTML = svg(el.dataset.icono); });

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
  try { estado.catalogos = await api("/api/catalogs"); } catch (_) { estado.catalogos = {}; }
  await Promise.all([cargarPacientes(""), cargarPersonal()]);
  ir("inicio");
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
  ({ inicio: pintarInicio, pacientes: pintarPacientes, citas: pintarCitasPagina, personal: pintarPersonal,
     quirofanos: pintarQuirofanos, enfermeria: pintarEnfermeria, habitaciones: pintarHabitaciones, motores: pintarMotores, paciente: pintarExpediente })[pagina]();
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
        <header class="panel-cab"><h2>Próximas citas</h2><button type="button" class="btn sutil chico" data-ir="citas">Ver todas</button></header>
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
        <button type="button" class="btn primario chico" data-atender="${c.id_cita}" data-paciente="${c.id_paciente}">Atender</button>
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
        ? `<button type="button" class="btn primario chico" data-atender="${c.id_cita}" data-paciente="${c.id_paciente}">Atender</button>`
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

// ---------------------------------------------------------- Estado de motores
async function pintarMotores() {
  cabecera({ titulo: "Estado de los motores", acciones: btnAccion("refrescar-motores", "Actualizar", "sutil") });
  $("#vista").innerHTML = `<p class="tenue">Consultando…</p>`;
  try {
    const r = await api("/api/engine/status");
    if (estado.pagina !== "motores") return;
    $("#vista").innerHTML = `
      <p class="intro">Cada institución guarda sus datos en su propio motor. La lógica de negocio es la misma para todos:
      el enrutador elige el adaptador según la institución del usuario que inicia sesión.</p>
      <div class="panel"><table class="tabla-datos">
        <thead><tr><th>Institución</th><th>Motor</th><th>Versión / base</th><th>Datos</th><th>Consistencia</th><th>Estado</th></tr></thead>
        <tbody>${r.motores.map((m) => {
          const i = INST[m.clave] || {};
          return `<tr${m.clave === estado.inst ? ' class="fila-propia"' : ""}>
            <td><span class="punto" style="background:${i.color}"></span><b>${esc(i.nombre || m.institucion)}</b></td>
            <td>${esc(m.motor)}</td>
            <td>${m.real ? `${esc(m.version || "")}<br><span class="tenue">${esc(m.base_datos || "")}</span>`
              : `<span>Datos de prueba en memoria</span>${m.detalle_conexion ? `<details class="motor-detalle"><summary>Por qué no se conectó</summary><p>${esc(m.detalle_conexion)}</p></details>` : ""}`}</td>
            <td><ul class="conteos">${Object.entries(m.conteos || {}).map(([k, v]) => `<li><b>${esc(v)}</b> ${esc(ETIQUETAS[k] || k)}</li>`).join("") || '<li class="tenue">—</li>'}</ul></td>
            <td class="tenue">${esc(m.consistencia || m.detalle || "")}</td>
            <td class="nowrap"><span class="estado ${m.estado === "online" ? "activo" : (m.real ? "baja" : "alerta")}">${m.estado === "online" ? "Conectado" : (m.real ? "Error" : "Simulado")}</span>
              ${m.latencia_ms != null ? `<br><small class="tenue">${m.latencia_ms} ms</small>` : ""}</td>
          </tr>`;
        }).join("")}</tbody></table></div>`;
  } catch (e) {
    $("#vista").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
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
              : `<li class="cama"><span class="cama-n">Cama ${i + 1}</span><span class="tenue">${h.estado !== "disponible" ? "Fuera de servicio" : "Libre"}</span></li>`;
          }).join("")}</ul>
        </article>`).join("") || `<p class="tenue relleno">Sin habitaciones. <button type="button" class="btn sutil chico" data-nueva-hab="${d.id_departamento}">+ Agregar la primera</button></p>`}</div>
      </section>`).join("")}
      <p class="ayuda">Los pacientes se ingresan al registrar una consulta. La base de datos no permite ocupar más camas de las que tiene una habitación.</p>`;
  } catch (e) {
    $("#vista").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
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
          <td class="acc">${h.estado === "ingresado" && activo ? `<button type="button" class="btn sutil chico" data-cambiar-hab="${h.id_hospitalizacion}" data-hab-actual="${esc(h.numero_habitacion)}">Cambiar habitación</button><button type="button" class="btn sutil chico" data-alta="${h.id_hospitalizacion}">Registrar egreso</button>` : ""}</td>
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
    }
    ir("paciente");
  } catch (e) {
    avisar(e.message, true);
  }
}

function pestanaEspecial() {
  const inst = estado.inst;
  const e = estado.especializado;
  if (inst === "odontologia") return ["especial", "Odontograma"];
  if (inst === "pediatrico" && e?.control_crecimiento?.length) return ["especial", "Crecimiento y vacunas"];
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
      btnAccion("cita", "Agendar cita", "secundario"),
      puedeRegistrar() ? btnAccion("consulta", lab ? "+ Registrar resultado" : "+ Registrar consulta") : "",
      `<details class="mas-acciones"><summary class="btn sutil" aria-label="Más acciones">Más</summary>
        <div class="mas-menu">${btnAccion("imprimir", "Imprimir historial", "item")}
        ${puedeRegistrar() ? btnAccion("baja", "Dar de baja el historial…", "item peligro-txt") : ""}</div></details>`,
    ].join(""),
  });

  const especial = pestanaEspecial();
  const lista = [
    ["historial", `${lab ? "Órdenes y resultados" : "Historial clínico"} (${h.consultas.length})`],
    ["citas", `Citas (${h.citas.length})`],
    ["datos", "Datos personales"],
    ...(especial ? [especial] : []),
  ];
  if (!lista.some(([k]) => k === estado.pestana)) estado.pestana = "historial";

  let cuerpo = "";
  if (estado.pestana === "historial") {
    cuerpo = h.consultas.length ? `<ol class="linea-tiempo">${h.consultas.map(pintarConsulta).join("")}</ol>`
      : `<div class="panel vacio-tabla"><p>Todavía no hay registros clínicos para este paciente.</p>
         ${puedeRegistrar() && !deBaja ? btnAccion("consulta", lab ? "+ Registrar el primer resultado" : "+ Registrar la primera consulta") : ""}</div>`;
  } else if (estado.pestana === "citas") {
    cuerpo = `<div class="panel">${h.citas.length ? tablaCitas(h.citas, null)
      : `<div class="vacio-tabla"><p>Este paciente no tiene citas.</p>${!deBaja ? btnAccion("cita", "+ Agendar cita") : ""}</div>`}</div>`;
  } else if (estado.pestana === "datos") {
    cuerpo = `<div class="panel relleno">${pintarDatos(p)}</div>`;
  } else {
    cuerpo = pintarEspecializado();
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
        </div>
        <dl class="resumen">
          <div><dt>Consultas</dt><dd>${h.consultas.length}</dd></div>
          <div><dt>Última atención</dt><dd>${h.consultas[0] ? fecha(h.consultas[0].fecha_hora_atencion) : "Ninguna"}</dd></div>
          <div><dt>Próxima cita</dt><dd>${proxima ? fecha(proxima.fecha_hora_programada, true) : "Sin agendar"}</dd></div>
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
  const nHab = t.closest("[data-nueva-hab]");
  if (nHab) { formHabitacion(nHab.dataset.nuevaHab); return; }
  const eHab = t.closest("[data-editar-hab]");
  if (eHab) { formEditarHabitacion(eHab.dataset.editarHab); return; }
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
  if (accion === "refrescar-motores") pintarMotores();
  if (accion === "consulta") formConsulta();
  if (accion === "cita") formCita();
  if (accion === "editar") formPaciente(estado.historial.paciente);
  if (accion === "baja") formBaja();
  if (accion === "imprimir") window.print();
  if (accion === "atender") formConsulta(Number(b.dataset.cita));
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
  return `<dl class="datos">${filas.filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${k === "Registro" ? v : esc(v)}</dd>`).join("")}</dl>`;
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
  codigo: { attrs: { maxlength: 8 }, filtro: "mayus", re: /^[A-Z]{2,4}-\d{2,3}$/, msg: "2 a 4 letras, guion y 2 o 3 números (ej. MI-104)" },
  camas: num(1, 6, 1), nombre: nombreR(80), piso: num(0, 20, 1),
  extension: { attrs: { maxlength: 5, inputmode: "numeric" }, filtro: "digitos", re: /^\d{2,5}$/, msg: "de 2 a 5 dígitos" },
};
const REGLAS_FILA = {
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
      avisar(lab ? "Resultado guardado" : "Consulta guardada");
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
