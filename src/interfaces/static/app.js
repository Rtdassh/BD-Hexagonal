/* Red de historiales clínicos — cliente web.
 * La interfaz es la misma para los 4 motores: solo consume la API REST.
 * Lo que cambia entre instituciones son los CAMPOS del dominio (somatometría, exámenes,
 * piezas dentales...), nunca el motor de base de datos. */

"use strict";

// ------------------------------------------------------------------ Constantes
const INST = {
  hospital:    { nombre: "Hospital General",         motor: "PostgreSQL",               color: "#2F5E9E",
                 tipos: [["ordinaria", "Ordinaria"], ["emergencia", "Emergencia"], ["seguimiento", "Seguimiento"]] },
  pediatrico:  { nombre: "Centro Médico Pediátrico", motor: "MySQL",                    color: "#7A4FB0",
                 tipos: [["control_sano", "Control de niño sano"], ["urgencia", "Urgencia"], ["seguimiento", "Seguimiento"], ["vacunacion", "Vacunación"]] },
  laboratorio: { nombre: "Laboratorio Clínico",      motor: "MongoDB",                  color: "#0B7A80",
                 tipos: [["normal", "Prioridad normal"], ["urgente", "Urgente"], ["emergencia", "Emergencia"]] },
  odontologia: { nombre: "Clínica Odontológica",     motor: "Firebase Cloud Firestore", color: "#A8436A",
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
  const sep = ruta.includes("?") ? "&" : "?";
  const url = estado.usuario?.rol === "administrador" && ruta.startsWith("/api/") && !ruta.startsWith("/api/auth")
    ? `${ruta}${sep}institucion=${estado.inst}` : ruta;
  const res = await fetch(url, {
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
  el.textContent = texto;
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
const texto = (s) => esc(String(s ?? "").replaceAll("_", " "));

// --------------------------------------------------------------------- Login
async function iniciarLogin() {
  $("#vistaApp").hidden = true;
  $("#vistaLogin").hidden = false;

  $("#listaInstituciones").innerHTML = Object.values(INST).map((i) => `
    <li><span class="franja" style="background:${i.color}"></span><span>${i.nombre}</span>
    <span class="motor-nombre">${i.motor}</span></li>`).join("");

  try {
    const cuentas = await api("/api/auth/demo-users");
    $("#cuentasDemo").innerHTML = cuentas.map((c) => `
      <button type="button" class="cuenta" data-u="${esc(c.username)}" style="--c:${INST[c.institucion].color}">
        <span class="u">${esc(c.username)}</span>
        <span class="r">${esc(c.nombre_completo)} · ${esc(ROLES[c.rol] || c.rol)}</span>
        <span class="m">${esc(INST[c.institucion].nombre)}</span>
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
  motores: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
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
  $("#adminInst").hidden = u.rol !== "administrador";
  $("#selInstitucion").value = estado.inst;
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
$("#selInstitucion").addEventListener("change", (ev) => { estado.inst = ev.target.value; aplicarInstitucion(); });

async function aplicarInstitucion() {
  const i = INST[estado.inst];
  document.documentElement.style.setProperty("--inst", i.color);
  $("#nombreInst").textContent = i.nombre;
  $("#motorInst").textContent = i.motor;
  document.title = `${i.nombre} — Historiales clínicos`;
  $("#txtBuscar").value = "";
  try { estado.catalogos = await api("/api/catalogs"); } catch (_) { estado.catalogos = {}; }
  await cargarPacientes("");
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
  ({ inicio: pintarInicio, pacientes: pintarPacientes, citas: pintarCitasPagina, motores: pintarMotores, paciente: pintarExpediente })[pagina]();
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
    ${pestanas([["activos", `Activos (${todos.length - nBaja})`], ["baja", `De baja (${nBaja})`], ["todos", `Todos (${todos.length})`]], estado.filtro, "data-filtro")}
    ${q ? `<p class="filtro-activo">Resultados para <b>"${esc(q)}"</b> <button type="button" class="btn sutil chico" data-accion="limpiar">Quitar búsqueda</button></p>` : ""}
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
        : `<div class="vacio-tabla"><p>${q ? `Ningún paciente coincide con "${esc(q)}".` : "No hay pacientes en esta lista."}</p>
           ${btnAccion("nuevo", "+ Registrar paciente")}</div>`}
    </div>`;
}

// --------------------------------------------------------------------- Inicio
const ETIQUETAS = { ordenes: "órdenes", hospitalizados: "hospitalizados ahora", vacunas: "vacunas aplicadas" };

async function pintarInicio() {
  const u = estado.usuario;
  const nombre = u.nombre_completo.split(" ").slice(0, 2).join(" ");
  cabecera({ titulo: `${saludo()}, ${esc(nombre)}`, acciones: btnAccion("nuevo", "+ Registrar paciente") });
  $("#vista").innerHTML = `
    <div class="cifras" id="inicioCifras"><div class="cifra-caja"><span class="tenue">Cargando…</span></div></div>
    <div class="inicio-cols">
      <section class="panel">
        <header class="panel-cab"><h2>Próximas citas</h2><button type="button" class="btn sutil chico" data-ir="citas">Ver todas</button></header>
        <div id="inicioCitas"><p class="tenue relleno">Cargando…</p></div>
      </section>
      <section class="panel">
        <header class="panel-cab"><h2>Pacientes recientes</h2><button type="button" class="btn sutil chico" data-ir="pacientes">Ver todos</button></header>
        <ul class="recientes">${[...estado.pacientes].sort((a, b) => String(b.fecha_registro).localeCompare(String(a.fecha_registro))).slice(0, 5).map((p) => `
          <li><button type="button" class="enlace-paciente" data-id="${p.id_paciente}"><span class="ini" aria-hidden="true">${esc(iniciales(`${p.nombres} ${p.apellidos}`))}</span>
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
  $("#inicioCifras").innerHTML = Object.entries(m?.conteos || {}).map(([k, v]) =>
    `<div class="cifra-caja"><span class="cifra">${esc(v)}</span><span>${esc(ETIQUETAS[k] || k)}</span></div>`).join("")
    + `<div class="cifra-caja motor-caja"><span class="tenue">Base de datos</span><b>${esc(INST[estado.inst].motor)}</b>
       <span class="estado ${m?.real ? "activo" : "alerta"}">${m?.real ? "Conectado" : "Simulado"}</span></div>`;

  const ahora = new Date().toISOString().slice(0, 16).replace("T", " ");
  const proximas = citas.filter((c) => c.fecha_hora_programada >= ahora)
    .sort((a, b) => a.fecha_hora_programada.localeCompare(b.fecha_hora_programada)).slice(0, 5);
  $("#inicioCitas").innerHTML = proximas.length ? tablaCitas(proximas, false)
    : `<p class="tenue relleno">No hay citas programadas. Agéndelas desde el historial de cada paciente.</p>`;
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
async function pintarCitasPagina() {
  cabecera({ titulo: "Citas" });
  $("#vista").innerHTML = `<p class="tenue">Cargando…</p>`;
  const citas = await api("/api/appointments").catch((e) => { avisar(e.message, true); return []; });
  if (estado.pagina !== "citas") return;
  const ahora = new Date().toISOString().slice(0, 16).replace("T", " ");
  const proximas = citas.filter((c) => c.fecha_hora_programada >= ahora).sort((a, b) => a.fecha_hora_programada.localeCompare(b.fecha_hora_programada));
  const vencidas = citas.filter((c) => c.fecha_hora_programada < ahora);
  const lista = estado.filtroCitas === "proximas" ? proximas : vencidas;
  $("#vista").innerHTML = `
    ${pestanas([["proximas", `Próximas (${proximas.length})`], ["vencidas", `Pendientes de fechas pasadas (${vencidas.length})`]], estado.filtroCitas, "data-filtro-citas")}
    <div class="panel">${lista.length ? tablaCitas(lista)
      : `<div class="vacio-tabla"><p>${estado.filtroCitas === "proximas" ? "No hay citas próximas." : "No hay citas pendientes atrasadas."}</p>
         <p class="tenue">Para agendar, abra el historial de un paciente y use "Agendar cita".</p></div>`}</div>`;
}

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
            <td>${m.real ? `${esc(m.version || "")}<br><span class="tenue">${esc(m.base_datos || "")}</span>` : `<span class="tenue">Simulado en memoria${m.detalle_conexion ? `: ${esc(m.detalle_conexion)}` : ""}</span>`}</td>
            <td>${Object.entries(m.conteos || {}).map(([k, v]) => `${esc(v)} ${esc(ETIQUETAS[k] || k)}`).join("<br>")}</td>
            <td class="tenue">${esc(m.consistencia || m.detalle || "")}</td>
            <td class="nowrap"><span class="estado ${m.estado === "online" ? "activo" : (m.real ? "baja" : "alerta")}">${m.estado === "online" ? "Conectado" : (m.real ? "Error" : "Simulado")}</span>
              ${m.latencia_ms != null ? `<br><small class="tenue">${m.latencia_ms} ms</small>` : ""}</td>
          </tr>`;
        }).join("")}</tbody></table></div>`;
  } catch (e) {
    $("#vista").innerHTML = `<p class="error">${esc(e.message)}</p>`;
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
  if (inst === "hospital" && e?.hospitalizaciones?.length) return ["especial", "Hospitalizaciones"];
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
      puedeRegistrar() ? btnAccion("consulta", lab ? "+ Nuevo resultado" : "+ Nueva consulta") : "",
      btnAccion("cita", "+ Agendar cita"),
      btnAccion("editar", "Editar datos", "sutil"),
      puedeRegistrar() ? btnAccion("baja", "Dar de baja", "peligro") : "",
      btnAccion("imprimir", "Imprimir", "sutil"),
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

// Un solo manejador para todos los botones del área de contenido
$("#contenido").addEventListener("click", async (ev) => {
  const t = ev.target;
  const irA = t.closest("[data-ir]");
  if (irA) { ir(irA.dataset.ir); return; }
  const filtro = t.closest("[data-filtro]");
  if (filtro) { estado.filtro = filtro.dataset.filtro; pintarPacientes(); return; }
  const filtroC = t.closest("[data-filtro-citas]");
  if (filtroC) { estado.filtroCitas = filtroC.dataset.filtroCitas; pintarCitasPagina(); return; }
  const pest = t.closest("[data-pestana]");
  if (pest) { estado.pestana = pest.dataset.pestana; pintarExpediente(); return; }
  const atender = t.closest("[data-atender]");
  if (atender) {
    const idCita = Number(atender.dataset.atender);
    await abrirPaciente(Number(atender.dataset.paciente), "historial");
    formConsulta(idCita);
    return;
  }
  const abrir = t.closest("[data-id]");
  if (abrir) { abrirPaciente(Number(abrir.dataset.id)); return; }
  const b = t.closest("[data-accion]");
  if (!b) return;
  const accion = b.dataset.accion;
  if (accion === "nuevo") formPaciente(null);
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
let alAceptar = null;

function abrirModal(titulo, html, textoBoton, accion) {
  $("#modalTitulo").textContent = titulo;
  $("#modalCuerpo").innerHTML = html;
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
  const faltante = [...form.querySelectorAll("[required]")].find((i) => !i.value.trim());
  if (faltante) {
    mostrarErrorModal(`Complete el campo "${faltante.closest("label")?.firstChild?.textContent.trim() || faltante.name}".`);
    faltante.focus();
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
      ${editar ? "" : campo("dpi", ped ? "CUI del niño" : "DPI", { req: true, extra: 'inputmode="numeric" maxlength="20"' })}
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
function formCita() {
  const odont = estado.inst === "odontologia" ? (estado.catalogos.odontologos || []) : [];
  const manana = new Date(Date.now() + 86400000);
  manana.setHours(9, 0, 0, 0);
  const local = new Date(manana.getTime() - manana.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const html = `<div class="rejilla">
    ${campo("fecha_hora_programada", "Fecha y hora", { tipo: "datetime-local", req: true, valor: local })}
    ${odont.length ? `<label>Odontólogo<select name="id_odontologo">${opciones(odont.map((o) => [String(o.id_odontologo), o.nombre_completo]))}</select></label>` : ""}
    <label class="completo"><span class="requerido">Motivo</span><input name="motivo_consulta" required maxlength="200"></label>
  </div>`;
  abrirModal(`Agendar cita para ${estado.historial.paciente.nombres}`, html, "Agendar cita", async (fd) => {
    const d = datosForm(fd);
    await api("/api/appointments", { method: "POST", body: { ...d, id_paciente: estado.idSeleccionado } });
    avisar("Cita agendada");
    abrirPaciente(estado.idSeleccionado, "citas");
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
    <fieldset><legend>${lab ? "Orden de laboratorio" : "Consulta"}</legend><div class="rejilla">
      <label class="completo"><span class="requerido">Motivo</span><input name="motivo" required maxlength="200" value="${esc(cita?.motivo_consulta || "")}"></label>
      <label>${lab ? "Prioridad" : "Tipo"}<select name="tipo_consulta">${opciones(INST[inst].tipos)}</select></label>
      ${!lab && !dent ? `
        ${!ped ? campo("presion_arterial", "Presión arterial", { extra: 'placeholder="120/80"' }) : ""}
        ${campo("temperatura", "Temperatura (°C)", { tipo: "number", extra: 'step="0.1" min="30" max="45"' })}
        ${campo("pulso", ped ? "Frecuencia cardiaca" : "Pulso (lpm)", { tipo: "number" })}` : ""}
      ${cita ? `<p class="ayuda completo">Se registrará como atención de la cita del ${fecha(cita.fecha_hora_programada, true)}.</p>` : ""}
    </div></fieldset>

    ${ped ? `<fieldset><legend>Somatometría</legend><div class="rejilla">
      ${campo("peso_kg", "Peso (kg)", { tipo: "number", req: true, extra: 'step="0.01" min="0.5"' })}
      ${campo("talla_cm", "Talla (cm)", { tipo: "number", req: true, extra: 'step="0.1" min="20"' })}
      ${campo("perimetro_cefalico_cm", "Perímetro cefálico (cm)", { tipo: "number", extra: 'step="0.1"' })}
      ${campo("percentil_crecimiento", "Percentil OMS", { tipo: "number", extra: 'step="0.1" min="0" max="100"' })}
    </div></fieldset>` : ""}

    ${lab ? `<fieldset><legend>Examen y resultados</legend><div class="rejilla">
      <label class="doble"><span class="requerido">Tipo de examen</span><select name="codigo_examen" id="selExamen" required>
        ${opciones(examenes.map((e) => [e.codigo, `${e.codigo} · ${e.nombre_examen}`]))}</select></label>
      ${campo("tipo_muestra", "Muestra", { extra: 'placeholder="Sangre con EDTA"' })}
    </div>
    <p class="ayuda">Cada examen tiene parámetros distintos; se cargan los del tipo elegido y puede agregar más.</p>
    <div class="filas" id="filasParametros"></div>
    <button type="button" class="btn sutil chico" data-agregar="parametro">Agregar parámetro</button>
    <div class="rejilla">
      <label class="completo">Conclusiones<textarea name="conclusiones_diagnosticas"></textarea></label>
      <label class="completo">Observaciones técnicas<input name="observaciones_tecnicas"></label>
    </div></fieldset>` : ""}

    ${dent ? `<fieldset><legend>Procedimientos por pieza</legend>
      <div class="odontograma">
        <div class="arcada">${PIEZAS_SUP.map((n) => `<button type="button" class="diente ${n === 21 ? "medio" : ""}" data-pieza="${n}">${n}</button>`).join("")}</div>
        <div class="arcada">${PIEZAS_INF.map((n) => `<button type="button" class="diente ${n === 31 ? "medio" : ""}" data-pieza="${n}">${n}</button>`).join("")}</div>
        <p class="ayuda">Toque una pieza para agregar un procedimiento en ella.</p>
      </div>
      <div class="filas" id="filasProcedimientos"></div>
      <button type="button" class="btn sutil chico" data-agregar="procedimiento">Agregar procedimiento general</button>
    </fieldset>` : ""}

    <fieldset><legend>${lab ? "Diagnóstico presuntivo" : "Diagnóstico"}</legend><div class="rejilla">
      ${campo("codigo_cie10", "Código CIE-10", { extra: 'placeholder="Escriba o elija" maxlength="10" list="dlCie10" autocomplete="off"' })}
      <label class="doble">Descripción<input name="descripcion_diagnostico" maxlength="300"></label>
      ${!lab ? `${campo("descripcion_tratamiento", "Tratamiento", { clase: "doble" })}
      ${campo("indicaciones_tratamiento", "Indicaciones", { clase: "doble" })}` : ""}
    </div></fieldset>

    ${ped ? `<fieldset><legend>Vacuna aplicada <span class="tenue">(opcional)</span></legend><div class="rejilla">
      ${campo("nombre_vacuna", "Vacuna", { clase: "doble" })}
      ${campo("dosis_vacuna", "Dosis", { extra: 'placeholder="2.ª dosis"' })}
      ${campo("lote_vacuna", "Lote")}
      ${campo("proxima_fecha_refuerzo", "Próximo refuerzo", { tipo: "date" })}
    </div></fieldset>` : ""}

    ${!lab ? `<fieldset><legend>Receta</legend>
      ${ped ? `<p class="ayuda">La dosis en ml se calcula con el peso: mg/kg × kg ÷ concentración.</p>` : ""}
      <div class="filas" id="filasRecetas"></div>
      <button type="button" class="btn sutil chico" data-agregar="receta">Agregar medicamento</button>
    </fieldset>` : ""}

    ${inst === "hospital" ? `<fieldset><legend>Hospitalización</legend><div class="rejilla">
      <label class="check completo"><input type="checkbox" name="requiere_hospitalizacion" value="1"> Ingresar al paciente</label>
      ${campo("numero_habitacion", "Habitación", { extra: 'placeholder="HAB-210"' })}
      ${campo("motivo_hospitalizacion", "Motivo de ingreso", { clase: "doble" })}
    </div></fieldset>` : ""}

    <datalist id="dlCie10">${(CIE10[inst] || []).map(([c, d]) => `<option value="${c}">${esc(d)}</option>`).join("")}</datalist>
    <datalist id="dlMedicamentos">${(MEDICAMENTOS[inst] || []).map((m) => `<option value="${esc(m)}"></option>`).join("")}</datalist>
    ${!lab ? `<label>Notas clínicas<textarea name="notas_clinicas"></textarea></label>`
           : `<label>Observaciones de la orden<textarea name="notas_clinicas"></textarea></label>`}`;

  abrirModal(lab ? "Registrar resultado de examen" : "Registrar consulta", html,
    lab ? "Guardar resultado" : "Guardar consulta", async (fd) => {
      const d = datosForm(fd);
      d.id_paciente = estado.idSeleccionado;
      if (idCita) d.id_cita = idCita;
      d.requiere_hospitalizacion = fd.get("requiere_hospitalizacion") === "1";
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

$("#modalCuerpo").addEventListener("click", (ev) => {
  const agregar = ev.target.closest("[data-agregar]");
  if (agregar) {
    const tipo = agregar.dataset.agregar;
    const cont = { receta: "#filasRecetas", procedimiento: "#filasProcedimientos", parametro: "#filasParametros" }[tipo];
    const html = tipo === "receta" ? filaReceta(estado.inst === "pediatrico") : tipo === "procedimiento" ? filaProcedimiento() : filaParametro();
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
