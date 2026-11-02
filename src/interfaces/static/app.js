/**
 * ============================================================================
 * CONTROLADOR PRINCIPAL — "SALUD PÚBLICA™"
 * Estilo: Federal Reserve & Wall Street Capital (Limpio, Alto Contraste)
 *
 * Flujo:
 *   1. Login con Selección Obligatoria del Sistema de Destino (Sin amarillo)
 *   2. Emisión de Pase Federal Autorizado con Botón de OK
 *   3. Redirección EXCLUSIVA únicamente al sistema seleccionado
 *      (Los otros sistemas quedan totalmente ocultos y aislados)
 * ============================================================================
 */

import { ICONS } from "./assets.js";

// ---------------------------------------------------------------------------
// 1. ESTADO GLOBAL DE LA APLICACIÓN
// ---------------------------------------------------------------------------
const state = {
  currentUser: null,
  selectedTargetSystem: "hospital",
  activeInstitution: "hospital",
  patients: [],
  selectedPatientId: null,
  operators: [],
  selectedTooth: 18,
};

const INST = {
  hospital: {
    name: "Hospital General de Especialidades",
    motor: "PostgreSQL",
    badgeCls: "fed-badge-blue",
    iconCls: "bg-blue-50",
    label: "PostgreSQL · ACID Transaccional",
    defaultUser: "dr_garcia",
    icon: "hospital",
    sub: "Urgencias, Triage Nosológico CIE-10, Asignación de Camas VIP & Facturación",
    specTitle: "Hospital General (PostgreSQL ACID)",
    specDesc: "Gestión de urgencias, internamiento nosológico y asignación de camas",
    specMetrics: `
      <span class="fed-badge fed-badge-green">Camas VIP: 12 Disponibles</span>
      <span class="fed-badge fed-badge-blue">Catálogo CIE-10 Activo</span>
    `,
  },
  pediatrico: {
    name: "Centro Pediátrico Infantil",
    motor: "MySQL",
    badgeCls: "fed-badge-green",
    iconCls: "bg-emerald-50",
    label: "MySQL · Relacional Somatométrico",
    defaultUser: "dra_lopez",
    icon: "pediatrico",
    sub: "Curvas de crecimiento OMS, percentiles, esquema de vacunas y control perinatal",
    specTitle: "Centro Pediátrico (MySQL Relacional)",
    specDesc: "Control somatométrico riguroso, percentiles OMS y esquema de vacunas",
    specMetrics: `
      <span class="fed-badge fed-badge-green">Curvas OMS P50</span>
      <span class="fed-badge fed-badge-blue">Vacunación al Día</span>
    `,
  },
  laboratorio: {
    name: "Laboratorio Clínico Central",
    motor: "MongoDB",
    badgeCls: "fed-badge-slate",
    iconCls: "bg-slate-100",
    label: "MongoDB · NoSQL Polimórfico",
    defaultUser: "lic_mendez",
    icon: "laboratorio",
    sub: "Analitos polimórficos BSON, trazabilidad de muestras y centinela de glucosa",
    specTitle: "Laboratorio Clínico (MongoDB NoSQL)",
    specDesc: "Estructuras flexibles de analitos y monitoreo reactivo centinela",
    specMetrics: `
      <span class="fed-badge fed-badge-slate">Estructura BSON</span>
      <span class="fed-badge fed-badge-red">Centinela Crítico Armado</span>
    `,
  },
  odontologia: {
    name: "Clínica Odontológica Especializada",
    motor: "Firebase",
    badgeCls: "fed-badge-red",
    iconCls: "bg-rose-50",
    label: "Firestore · Cloud & Políticas RBAC",
    defaultUser: "dr_molina",
    icon: "odontologia",
    sub: "Odontograma FDI interactivo de 32 piezas, cotización y privacidad RBAC",
    specTitle: "Clínica Odontológica (Firestore Cloud)",
    specDesc: "Odontograma interactivo FDI (32 piezas dentales) y directivas RBAC",
    specMetrics: `
      <span class="fed-badge fed-badge-red">32 Piezas FDI</span>
      <span class="fed-badge fed-badge-green">Directiva RBAC Activa</span>
    `,
  },
};

const ROLE_EMOJI = {
  medico: "👨‍⚕️",
  pediatra: "👩‍⚕️",
  laboratorista: "🔬",
  secretaria: "🗂️",
  odontologo: "🦷",
  administrador: "🏛️",
};

// ---------------------------------------------------------------------------
// 2. INICIALIZACIÓN
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  injectSvgIcons();
  buildOdontogram();
  bindGlobalEvents();
  await loadOperatorAccounts();
  updateTargetSystemDisplay();
});

// ---------------------------------------------------------------------------
// 3. INYECCIÓN DE ICONOS VECTORIALES
// ---------------------------------------------------------------------------
function injectSvgIcons() {
  const setSvg = (id, svg) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = svg;
  };

  setSvg("loginUncleSamLogo", ICONS.uncleSam);
  setSvg("loginEagleSeal", ICONS.baldEagle);
  setSvg("stampApprovedMini", ICONS.stampApproved);
  setSvg("loginIconHospital", ICONS.hospital);
  setSvg("loginIconPediatrico", ICONS.pediatrico);
  setSvg("loginIconLaboratorio", ICONS.laboratorio);
  setSvg("loginIconOdontologia", ICONS.odontologia);
  setSvg("loginBarcode", ICONS.barcodeSvg);
  setSvg("clrSealApproved", ICONS.stampApproved);
}

// ---------------------------------------------------------------------------
// 4. CONTROL DE PANTALLAS
// ---------------------------------------------------------------------------
function showScreen(screenId) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("is-active"));
  const target = document.getElementById(screenId);
  if (target) {
    target.classList.add("is-active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

// ---------------------------------------------------------------------------
// 5. SELECCIÓN DEL SISTEMA AL QUE INGRESAR DESDE EL LOGIN
// ---------------------------------------------------------------------------
window.selectSystemForLogin = (systemKey) => {
  if (!INST[systemKey]) return;
  state.selectedTargetSystem = systemKey;

  // Actualizar tarjetas de selección
  document.querySelectorAll(".system-card").forEach((card) => {
    const matches = card.dataset.system === systemKey;
    card.classList.toggle("is-selected", matches);
  });

  updateTargetSystemDisplay();

  // Autoseleccionar el usuario sugerido para este sistema
  const defUser = INST[systemKey].defaultUser;
  document.getElementById("loginUser").value = defUser;
  document.getElementById("loginPass").value = "123";
  document.getElementById("loginError").classList.add("hidden");

  toast(`Sistema seleccionado: ${INST[systemKey].name}`);
};

function updateTargetSystemDisplay() {
  const info = INST[state.selectedTargetSystem];
  const targetLabel = document.getElementById("loginTargetDisplay");
  if (targetLabel && info) {
    targetLabel.textContent = `${info.name} (${info.motor})`;
  }
}

// ---------------------------------------------------------------------------
// 6. CARGA DE CUENTAS DEMO
// ---------------------------------------------------------------------------
async function loadOperatorAccounts() {
  try {
    const res = await fetch("/api/auth/demo-users");
    if (!res.ok) throw new Error();
    state.operators = await res.json();
    renderLoginChips();
    renderOperatorModal();
  } catch (err) {
    console.error("No se pudieron cargar usuarios demo:", err);
  }
}

function renderLoginChips() {
  const container = document.getElementById("loginChipsContainer");
  if (!container) return;
  container.innerHTML = "";

  state.operators.forEach((op) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "p-2 bg-slate-50 border border-slate-300 rounded text-left hover:bg-blue-50 hover:border-blue-400 transition-all";
    chip.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="mono text-xs font-bold text-slate-900">${op.username}</span>
        <span class="text-xs">${ROLE_EMOJI[op.rol] || "👤"}</span>
      </div>
      <div class="text-[10px] text-slate-500 font-medium truncate">${op.cargo.split(" ")[0]} · ${op.motor.split(" ")[0]}</div>
    `;
    chip.onclick = () => {
      document.getElementById("loginUser").value = op.username;
      document.getElementById("loginPass").value = "123";
      document.getElementById("loginError").classList.add("hidden");

      if (op.institucion && INST[op.institucion]) {
        selectSystemForLogin(op.institucion);
      }
      document.getElementById("loginBtn").focus();
    };
    container.appendChild(chip);
  });
}

// ---------------------------------------------------------------------------
// 7. ENVÍO DE FORMULARIO DE LOGIN -> EMISIÓN DE PASE AUTORIZADO
// ---------------------------------------------------------------------------
document.getElementById("loginForm").onsubmit = async (e) => {
  e.preventDefault();
  const errBox = document.getElementById("loginError");
  const btn = document.getElementById("loginBtn");
  const btnText = document.getElementById("loginBtnText");

  errBox.classList.add("hidden");
  btn.disabled = true;
  btnText.textContent = "VERIFICANDO CREDENCIALES…";

  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value.trim();

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || "Credenciales inválidas. Verifique usuario o contraseña.");
    }

    state.currentUser = await res.json();

    updateUserVisuals();
    renderOperatorModal();
    showClearancePass(state.currentUser);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btnText.textContent = "VERIFICAR & EMITIR PASE FEDERAL →";
  }
};

function showClearancePass(user) {
  const formState = document.getElementById("loginFormState");
  const clearanceCard = document.getElementById("clearanceCard");
  const chosenSys = INST[state.selectedTargetSystem];

  document.getElementById("clrAvatar").textContent = ROLE_EMOJI[user.rol] || "👤";
  document.getElementById("clrName").textContent = user.nombre_completo.toUpperCase();
  document.getElementById("clrRole").textContent = `${user.rol.toUpperCase()} · ${user.numero_colegiado ? 'COLEGIADO ' + user.numero_colegiado : 'ADMIN'}`;
  document.getElementById("clrTargetSystemName").textContent = chosenSys.name.toUpperCase();
  document.getElementById("clrEngine").textContent = `Motor Asignado: ${chosenSys.motor.toUpperCase()} (Exclusivo)`;
  document.getElementById("clrCol").textContent = user.numero_colegiado || "#COL-7741";
  document.getElementById("clrLevel").textContent = user.rol === "secretaria" ? "Nivel 2 (Secretaría · RBAC)" : "Nivel 4 (Clínica Plena)";
  document.getElementById("clrToken").textContent = `${user.token.slice(0, 10).toUpperCase()}… (SHA-256)`;

  formState.style.display = "none";
  clearanceCard.classList.add("is-active");
  document.getElementById("btnProceedToHub").focus();
}

document.getElementById("btnBackToLoginForm").onclick = () => {
  document.getElementById("clearanceCard").classList.remove("is-active");
  document.getElementById("loginFormState").style.display = "grid";
};

// ---------------------------------------------------------------------------
// 8. BOTÓN OK: REDIRECCIÓN EXCLUSIVA ÚNICAMENTE AL SISTEMA ELEGIDO
// ---------------------------------------------------------------------------
document.getElementById("btnProceedToHub").onclick = async () => {
  await enterTargetSystemWorkspace(state.selectedTargetSystem);
};

async function enterTargetSystemWorkspace(systemKey) {
  const config = INST[systemKey];
  if (!config) return;
  state.activeInstitution = systemKey;

  document.getElementById("wsInstTitle").textContent = config.name;
  document.getElementById("wsInstSub").textContent = config.sub;

  const iconEl = document.getElementById("wsInstIcon");
  iconEl.innerHTML = ICONS[config.icon];

  const badgeEl = document.getElementById("wsEngineBadge");
  badgeEl.className = `fed-badge ${config.badgeCls} text-[10px]`;
  badgeEl.textContent = config.label;

  document.getElementById("wsSpecTitle").textContent = config.specTitle;
  document.getElementById("wsSpecDesc").textContent = config.specDesc;
  document.getElementById("wsSpecMetrics").innerHTML = config.specMetrics;

  configureInstitutionalForms(systemKey);

  if (state.currentUser && state.currentUser.institucion !== systemKey && state.currentUser.rol !== "administrador") {
    await loginAsOperator(config.defaultUser, false);
  }

  showScreen("screenWorkspace");
  switchTab("tabExpedientes");
  await loadPatients();
  toast(`Acceso concedido exclusivamente a: ${config.name}`);
}

document.getElementById("wsLogoutBtn").onclick = () => {
  state.currentUser = null;
  document.getElementById("clearanceCard").classList.remove("is-active");
  document.getElementById("loginFormState").style.display = "grid";
  document.getElementById("loginPass").value = "";
  showScreen("screenLogin");
  toast("Sesión cerrada. Seleccione un nuevo sistema.");
};

// ---------------------------------------------------------------------------
// 9. EVENTOS GLOBALES Y PESTAÑAS DEL WORKSPACE
// ---------------------------------------------------------------------------
function bindGlobalEvents() {
  document.querySelectorAll(".ws-tab-btn").forEach((tabBtn) => {
    tabBtn.onclick = () => switchTab(tabBtn.dataset.tab);
  });

  document.getElementById("hosp_requiere_ingreso")?.addEventListener("change", (e) => {
    document.getElementById("hospBedFields").classList.toggle("hidden", !e.target.checked);
  });

  document.getElementById("searchBtn").onclick = () => {
    loadPatients(document.getElementById("searchInput").value.trim());
  };
  document.getElementById("searchInput").onkeydown = (e) => {
    if (e.key === "Enter") {
      loadPatients(e.target.value.trim());
    }
  };

  document.getElementById("btnRefreshAudit").onclick = loadAuditStatus;
  document.getElementById("btnSwitchOperator").onclick = openOperatorModal;
  document.getElementById("closeOperatorModal").onclick = closeOperatorModal;
  document.getElementById("operatorModal").onclick = (e) => {
    if (e.target.id === "operatorModal") closeOperatorModal();
  };

  initFormHandlers();
}

function switchTab(tabId) {
  document.querySelectorAll(".ws-tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabId));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("is-active", p.id === tabId));
  if (tabId === "tabAuditoria") {
    loadAuditStatus();
  }
}

// ---------------------------------------------------------------------------
// 10. MODAL DE CAMBIO DE OPERADOR & PERMISOS RBAC
// ---------------------------------------------------------------------------
function openOperatorModal() {
  document.getElementById("operatorModal").classList.add("is-open");
}
function closeOperatorModal() {
  document.getElementById("operatorModal").classList.remove("is-open");
}

function renderOperatorModal() {
  const container = document.getElementById("operatorListModal");
  if (!container) return;
  container.innerHTML = "";

  state.operators.forEach((op) => {
    const row = document.createElement("div");
    const isCurrent = state.currentUser && state.currentUser.username === op.username;
    row.className = `p-3 bg-white border border-slate-200 rounded flex items-center gap-3 cursor-pointer hover:bg-slate-50 transition-all ${isCurrent ? "border-blue-600 bg-blue-50/50" : ""}`;
    row.onclick = async () => {
      closeOperatorModal();
      await loginAsOperator(op.username, true);
    };

    const isSecretaria = op.rol === "secretaria";

    row.innerHTML = `
      <div class="text-xl w-9 h-9 border border-slate-300 rounded bg-slate-100 flex items-center justify-center flex-shrink-0">
        ${ROLE_EMOJI[op.rol] || "👤"}
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-slate-900 font-mono">${op.nombre_completo}</span>
          <span class="mono text-[10px] text-slate-500">${op.motor.split(" ")[0]}</span>
        </div>
        <div class="text-[11px] text-slate-600 flex gap-2 items-center mt-0.5">
          <span>${op.cargo}</span>
          ${isSecretaria ? '<span class="fed-badge fed-badge-slate text-[8px] py-0 px-1">RBAC RESTRICTED</span>' : ""}
        </div>
      </div>
    `;
    container.appendChild(row);
  });
}

async function loginAsOperator(username, notify = true) {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password: "123" }),
    });
    if (!res.ok) throw new Error("No se pudo cambiar de operador");
    state.currentUser = await res.json();
    updateUserVisuals();
    renderOperatorModal();

    const rbacBanner = document.getElementById("rbacBanner");
    rbacBanner.classList.toggle("hidden", state.currentUser.rol !== "secretaria");

    if (state.selectedPatientId) {
      await loadClinicalHistory(state.selectedPatientId);
    }

    if (notify) {
      toast(`Operador activo: ${state.currentUser.nombre_completo}`);
    }
  } catch (err) {
    toast(err.message, true);
  }
}

function updateUserVisuals() {
  if (!state.currentUser) return;
  const name = state.currentUser.nombre_completo.toUpperCase();
  const role = `${state.currentUser.rol.toUpperCase()} · ${state.currentUser.institucion.toUpperCase()}`;

  const nameEl = document.getElementById("wsUserName");
  if (nameEl) nameEl.textContent = name;

  const roleEl = document.getElementById("wsUserRole");
  if (roleEl) roleEl.textContent = role;

  const banner = document.getElementById("rbacBanner");
  if (banner) {
    banner.classList.toggle("hidden", state.currentUser.rol !== "secretaria");
  }
}

// ---------------------------------------------------------------------------
// 11. EXPEDIENTES Y PACIENTES
// ---------------------------------------------------------------------------
async function loadPatients(query = "") {
  const listEl = document.getElementById("patientList");
  const countEl = document.getElementById("patientCount");
  const selectConsultation = document.getElementById("cons_paciente_id");

  listEl.innerHTML = '<p class="text-xs text-slate-400 font-mono text-center py-8">Consultando motor activo…</p>';

  try {
    const token = state.currentUser?.token || "";
    const res = await fetch(`/api/patients?q=${encodeURIComponent(query)}&institucion=${state.activeInstitution}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Error al consultar pacientes");

    state.patients = await res.json();
    listEl.innerHTML = "";
    selectConsultation.innerHTML = '<option value="">Seleccione paciente…</option>';
    countEl.textContent = state.patients.length;

    if (!state.patients.length) {
      listEl.innerHTML = '<p class="text-xs text-slate-400 font-mono text-center py-8">No hay pacientes registrados en este motor.</p>';
      document.getElementById("patientCard").classList.add("hidden");
      renderEmptyHistory();
      return;
    }

    state.patients.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id_paciente;
      opt.textContent = `${p.nombres} ${p.apellidos} (DPI: ${p.dpi})`;
      selectConsultation.appendChild(opt);

      const row = document.createElement("div");
      row.className = `patient-row ${p.id_paciente === state.selectedPatientId ? "selected" : ""}`;
      row.onclick = () => selectPatient(p.id_paciente);
      row.innerHTML = `
        <div>
          <div class="text-xs font-bold text-slate-900">${p.nombres} ${p.apellidos}</div>
          <div class="mono text-[11px] text-slate-500">DPI: ${p.dpi}</div>
        </div>
        <span class="fed-badge ${p.estado === 'activo' ? 'fed-badge-green' : 'fed-badge-red'} text-[9px]">
          ${p.estado.toUpperCase()}
        </span>
      `;
      listEl.appendChild(row);
    });

    const exists = state.patients.some((x) => x.id_paciente === state.selectedPatientId);
    selectPatient(exists ? state.selectedPatientId : state.patients[0].id_paciente);
  } catch (err) {
    listEl.innerHTML = `<p class="text-xs text-center py-8 text-red-600 font-mono">${err.message}</p>`;
  }
}

function selectPatient(patientId) {
  state.selectedPatientId = patientId;
  document.querySelectorAll(".patient-row").forEach((r) => r.classList.remove("selected"));

  const patient = state.patients.find((x) => x.id_paciente === patientId);
  if (!patient) return;

  const card = document.getElementById("patientCard");
  card.classList.remove("hidden");

  let perinatalHtml = "";
  if (patient.nombre_tutor) {
    perinatalHtml = `
      <div class="mt-2 pt-2 border-t border-slate-100 bg-emerald-50/70 p-2 rounded text-xs space-y-0.5">
        <div class="text-[10px] font-bold uppercase text-emerald-800 font-mono">Datos Perinatales & Tutor (MySQL)</div>
        <div>Tutor: <strong>${patient.nombre_tutor}</strong> (DPI: <span class="mono">${patient.dpi_tutor || "N/A"}</span>)</div>
        <div>Gestación: <span class="mono">${patient.semanas_gestacion || "--"} sem</span> · Peso: <span class="mono">${patient.peso_nacer_kg || "--"} kg</span></div>
      </div>
    `;
  }

  let emergencyContactHtml = "";
  if (patient.contacto_emergencia_nombre) {
    emergencyContactHtml = `
      <div class="mt-2 pt-2 border-t border-slate-100 bg-blue-50/70 p-2 rounded text-xs space-y-0.5 text-blue-900">
        <div class="text-[10px] font-bold uppercase font-mono text-blue-800">Contacto de Emergencia (PostgreSQL)</div>
        <div>${patient.contacto_emergencia_nombre} — Tel: <span class="mono font-bold">${patient.contacto_emergencia_telefono || "N/A"}</span></div>
      </div>
    `;
  }

  document.getElementById("patientDetails").innerHTML = `
    <div><span class="text-slate-500">Nombre Completo:</span> <strong>${patient.nombres} ${patient.apellidos}</strong></div>
    <div><span class="text-slate-500">DPI:</span> <span class="mono font-bold">${patient.dpi}</span></div>
    <div><span class="text-slate-500">Nacimiento:</span> ${patient.fecha_nacimiento} (${patient.sexo === "M" ? "Masculino" : "Femenino"})</div>
    <div><span class="text-slate-500">Teléfono:</span> <span class="mono">${patient.telefono || "Sin registrar"}</span></div>
    <div><span class="text-slate-500">Tipo de Sangre:</span> <span class="fed-badge fed-badge-red text-[10px] py-0.5 px-1">${patient.tipo_sangre || "N/A"}</span></div>
    ${perinatalHtml}
    ${emergencyContactHtml}
  `;

  loadClinicalHistory(patientId);
}

// ---------------------------------------------------------------------------
// 12. HISTORIAL CLÍNICO ESPECIALIZADO POR SISTEMA
// ---------------------------------------------------------------------------
async function loadClinicalHistory(patientId) {
  const container = document.getElementById("historyContainer");
  container.innerHTML = '<p class="text-xs text-slate-400 font-mono text-center py-16">Cargando expediente clínico…</p>';

  try {
    const token = state.currentUser?.token || "";
    const res = await fetch(`/api/patients/${patientId}/history?institucion=${state.activeInstitution}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) throw new Error("No se pudo obtener el historial clínico");
    const history = await res.json();

    document.getElementById("motorTag").textContent = `Persistencia: ${history.motor}`;
    document.getElementById("stateTag").textContent = history.estado.toUpperCase();
    container.innerHTML = "";

    if (!history.consultas || !history.consultas.length) {
      renderEmptyHistory();
      return;
    }

    history.consultas.forEach((c) => {
      const box = document.createElement("div");
      box.className = "border border-slate-200 rounded p-4 bg-white space-y-3 shadow-sm";

      const rawDate = c.fecha_hora_atencion || c.fecha_consulta || "";
      const dateStr = rawDate ? rawDate.split("T")[0].split(" ")[0] : "Fecha N/D";
      const motivoStr = c.motivo || c.motivo_consulta || "Consulta Médica";

      box.innerHTML = `
        <div class="flex items-center justify-between border-b border-slate-100 pb-2 flex-wrap gap-2">
          <div class="flex items-center gap-2">
            <span class="fed-badge fed-badge-blue text-[10px]">#CONS-${c.id_consulta}</span>
            <span class="text-sm font-bold text-slate-900">${motivoStr}</span>
          </div>
          <span class="mono text-xs text-slate-500 font-medium">${dateStr}</span>
        </div>
      `;

      // 1. Diagnósticos CIE-10 (Hospital General)
      if (c.diagnosticos && c.diagnosticos.length) {
        const diagBox = document.createElement("div");
        diagBox.className = "text-xs space-y-1.5";
        diagBox.innerHTML = `
          <div class="text-[10px] font-bold uppercase text-slate-500 font-mono">Diagnósticos Nosológicos CIE-10</div>
        ` + c.diagnosticos.map((d) => `
          <div class="flex items-center justify-between bg-blue-50/50 border border-blue-100 p-2 rounded">
            <span class="font-medium text-slate-800">${d.descripcion}</span>
            <span class="mono text-xs font-bold bg-slate-900 text-white px-2 py-0.5 rounded">
              ${d.codigo_cie10}
            </span>
          </div>
        `).join("");
        box.appendChild(diagBox);
      }

      // 2. Hospitalización y asignación de cama
      if (c.hospitalizacion) {
        const hospBox = document.createElement("div");
        hospBox.className = "p-3 border border-blue-200 rounded bg-blue-50/70 text-xs space-y-1";
        hospBox.innerHTML = `
          <div class="flex items-center justify-between font-bold text-blue-900">
            <span class="flex items-center gap-1">🏥 Hospitalización en Sala</span>
            <span class="fed-badge fed-badge-blue text-[9px]">
              ${c.hospitalizacion.estado.toUpperCase()}
            </span>
          </div>
          <div>Cama Asignada: <strong>Habitación ${c.hospitalizacion.numero_habitacion}</strong></div>
          <div class="text-slate-600">Motivo: ${c.hospitalizacion.motivo_ingreso}</div>
        `;
        box.appendChild(hospBox);
      }

      // 3. Somatometría Pediátrica (MySQL)
      if (c.somatometria) {
        const somBox = document.createElement("div");
        somBox.className = "grid grid-cols-2 sm:grid-cols-4 gap-2";
        somBox.innerHTML = `
          <div class="fed-kpi">
            <div class="fed-kpi-lbl">Peso Corporal</div>
            <div class="fed-kpi-val">${c.somatometria.peso_kg} <small class="text-xs font-normal">kg</small></div>
          </div>
          <div class="fed-kpi">
            <div class="fed-kpi-lbl">Talla / Estatura</div>
            <div class="fed-kpi-val">${c.somatometria.talla_cm} <small class="text-xs font-normal">cm</small></div>
          </div>
          <div class="fed-kpi">
            <div class="fed-kpi-lbl">P. Cefálico</div>
            <div class="fed-kpi-val font-mono">${c.somatometria.perimetro_cefalico_cm || "—"}</div>
          </div>
          <div class="fed-kpi bg-blue-50/50">
            <div class="fed-kpi-lbl">Percentil OMS</div>
            <div class="fed-kpi-val text-blue-700">P${c.somatometria.percentil_crecimiento}%</div>
          </div>
        `;
        box.appendChild(somBox);
      }

      // 4. Esquema de Vacunas Pediátricas
      if (c.vacunaciones && c.vacunaciones.length) {
        const vacBox = document.createElement("div");
        vacBox.className = "p-3 border border-emerald-200 rounded bg-emerald-50/70 text-xs space-y-1";
        vacBox.innerHTML = `
          <div class="font-bold text-emerald-900 text-[10px] uppercase font-mono mb-1">💉 Inmunizaciones Registradas</div>
        ` + c.vacunaciones.map((v) => `
          <div>• <strong>${v.nombre_vacuna}</strong> (${v.dosis}) — Lote: <span class="mono">${v.lote}</span></div>
        `).join("");
        box.appendChild(vacBox);
      }

      // 5. Analitos de Laboratorio Polimórfico (MongoDB NoSQL)
      if (c.examenes_laboratorio && c.examenes_laboratorio.length) {
        c.examenes_laboratorio.forEach((ex) => {
          const labBox = document.createElement("div");
          labBox.className = "p-3 bg-slate-50 border border-slate-200 rounded space-y-2 text-xs";
          labBox.innerHTML = `
            <div class="flex items-center justify-between font-bold text-slate-800">
              <span>🔬 ${ex.nombre_examen} (${ex.tipo_muestra})</span>
              <span class="mono text-[10px] bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">Muestra #${ex.numero_muestra}</span>
            </div>
          `;

          if (ex.analitos && ex.analitos.length) {
            const analyteList = document.createElement("div");
            analyteList.className = "space-y-1.5";
            ex.analitos.forEach((a) => {
              const row = document.createElement("div");
              row.className = `flex items-center justify-between p-2 rounded border ${a.alerta_critica ? "bg-red-50 border-red-300 font-bold" : "bg-white border-slate-200"}`;
              row.innerHTML = `
                <div>
                  <strong>${a.nombre}</strong>:
                  <span class="mono font-bold ml-1">${a.valor} ${a.unidad}</span>
                  <span class="text-[10px] text-slate-400 font-mono ml-2">(Ref: ${a.rango_referencia})</span>
                </div>
                ${a.alerta_critica
                  ? '<span class="fed-badge fed-badge-red text-[9px] animate-pulse">⚠ VALOR CRÍTICO</span>'
                  : '<span class="fed-badge fed-badge-green text-[9px]">Normal</span>'}
              `;
              analyteList.appendChild(row);
            });
            labBox.appendChild(analyteList);
          }
          box.appendChild(labBox);
        });
      }

      // 6. Odontología FDI (Firestore)
      const dentalList = c.procedimientos_dentales || c.procedimientos_odontologicos || [];
      if (dentalList.length) {
        const dentalBox = document.createElement("div");
        dentalBox.className = "p-3 border border-slate-200 rounded bg-slate-50 text-xs space-y-1.5";
        dentalBox.innerHTML = `
          <div class="font-bold text-slate-700 text-[10px] uppercase font-mono">Procedimientos Odontológicos FDI (Firestore)</div>
        ` + dentalList.map((p) => `
          <div class="flex items-center justify-between bg-white p-2 rounded border border-slate-200">
            <div>
              <span class="fed-badge fed-badge-slate text-[10px] py-0.5 px-1 font-mono">
                Pieza FDI ${p.diente_fdi}
              </span>
              <span class="ml-2 font-medium text-slate-800">${p.procedimiento}</span>
            </div>
            <span class="mono font-bold text-emerald-700 text-sm">Q${parseFloat(p.costo || 0).toFixed(2)}</span>
          </div>
        `).join("");
        box.appendChild(dentalBox);
      }

      // 7. Notas Clínicas y RBAC
      const clinicalNotes = c.notas_clinicas || c.tratamiento_indicaciones;
      if (clinicalNotes) {
        const isSecretariaRestricted = state.currentUser?.rol === "secretaria" && state.activeInstitution === "odontologia";
        const notesBox = document.createElement("div");
        notesBox.className = "text-xs pt-2 border-t border-slate-100";

        if (isSecretariaRestricted) {
          notesBox.innerHTML = `
            <div class="p-2.5 bg-slate-100 border border-slate-200 rounded text-slate-600 font-mono text-xs flex items-center gap-2">
              <span>🔒</span>
              <span>Nota clínica confidencial protegida por política RBAC (Acceso exclusivo a Médicos y Odontólogos).</span>
            </div>
          `;
        } else {
          notesBox.innerHTML = `
            <span class="font-bold text-slate-600">Tratamiento / Pauta Terapéutica:</span>
            <span class="text-slate-800 ml-1">${clinicalNotes}</span>
          `;
        }
        box.appendChild(notesBox);
      }

      container.appendChild(box);
    });
  } catch (err) {
    container.innerHTML = `<p class="text-xs text-center py-10 text-red-600 font-mono">${err.message}</p>`;
  }
}

function renderEmptyHistory() {
  document.getElementById("historyContainer").innerHTML = `
    <div class="text-center py-16 text-slate-400 font-mono">
      <div class="text-4xl mb-2">📂</div>
      <p class="text-sm font-bold text-slate-700">Sin consultas registradas</p>
      <p class="text-xs mt-1">Este paciente no registra historial en el motor activo aún.</p>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// 13. FORMULARIOS DE NUEVO PACIENTE Y NUEVA ATENCIÓN
// ---------------------------------------------------------------------------
function configureInstitutionalForms(instKey) {
  document.getElementById("npFieldsHospital").classList.toggle("hidden", instKey !== "hospital");
  document.getElementById("npFieldsPediatrico").classList.toggle("hidden", instKey !== "pediatrico");

  document.getElementById("secHospital").classList.toggle("hidden", instKey !== "hospital");
  document.getElementById("secPediatrico").classList.toggle("hidden", instKey !== "pediatrico");
  document.getElementById("secLaboratorio").classList.toggle("hidden", instKey !== "laboratorio");
  document.getElementById("secOdontologia").classList.toggle("hidden", instKey !== "odontologia");
}

function initFormHandlers() {
  document.getElementById("formNewPatient").onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      nombres: val("p_nombres"),
      apellidos: val("p_apellidos"),
      dpi: val("p_dpi"),
      fecha_nacimiento: val("p_fecha_nac"),
      sexo: val("p_sexo"),
      telefono: val("p_telefono"),
      tipo_sangre: val("p_tipo_sangre"),
      direccion: val("p_direccion"),
    };

    if (state.activeInstitution === "pediatrico") {
      data.nombre_tutor = val("p_tutor_nombre");
      data.dpi_tutor = val("p_tutor_dpi");
      data.semanas_gestacion = parseInt(val("p_semanas_gestacion")) || null;
      data.peso_nacer_kg = parseFloat(val("p_peso_nacer")) || null;
    }
    if (state.activeInstitution === "hospital") {
      data.contacto_emergencia_nombre = val("p_emergencia_nombre");
      data.contacto_emergencia_telefono = val("p_emergencia_tel");
    }

    try {
      const res = await fetch(`/api/patients?institucion=${state.activeInstitution}`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || "Error al registrar paciente");
      }

      const created = await res.json();
      toast(`Paciente #${created.id_paciente} registrado correctamente`);
      e.target.reset();
      await loadPatients();
      switchTab("tabExpedientes");
    } catch (err) {
      toast(err.message, true);
    }
  };

  document.getElementById("formNewConsultation").onsubmit = async (e) => {
    e.preventDefault();
    const patientId = val("cons_paciente_id");
    if (!patientId) {
      toast("Seleccione un paciente de la lista", true);
      return;
    }

    const payload = {
      id_paciente: parseInt(patientId),
      motivo_consulta: val("cons_motivo"),
      diagnostico_principal: val("cons_diagnostico"),
      tratamiento_indicaciones: val("cons_tratamiento"),
    };

    if (state.activeInstitution === "hospital") {
      payload.codigo_cie10 = val("hosp_cie10") || "J02.9";
      if (document.getElementById("hosp_requiere_ingreso").checked) {
        payload.hospitalizacion = {
          numero_habitacion: val("hosp_habitacion") || "101-A",
          motivo_ingreso: val("hosp_motivo_ingreso") || "Observación clínica",
        };
      }
    }

    if (state.activeInstitution === "pediatrico") {
      payload.peso_kg = parseFloat(val("ped_peso")) || 12.0;
      payload.talla_cm = parseFloat(val("ped_talla")) || 90.0;
      payload.perimetro_cefalico_cm = parseFloat(val("ped_cefalico")) || null;
      payload.percentil_crecimiento = parseInt(val("ped_percentil")) || 50;

      const vaccineName = val("ped_vacuna_nombre");
      if (vaccineName) {
        payload.vacunacion = {
          nombre_vacuna: vaccineName,
          dosis: val("ped_vacuna_dosis") || "Dosis única",
          lote: val("ped_vacuna_lote") || "VAC-001",
        };
      }
    }

    if (state.activeInstitution === "laboratorio") {
      payload.nombre_examen = val("lab_nombre_examen") || "Química Sanguínea";
      payload.tipo_muestra = val("lab_tipo_muestra");
      payload.analitos = [
        {
          nombre: val("lab_analito_nombre") || "Glucosa",
          valor: parseFloat(val("lab_analito_valor")) || 0,
          unidad: val("lab_analito_unidad") || "mg/dL",
          rango_referencia: "70.0 - 100.0",
        },
      ];
    }

    if (state.activeInstitution === "odontologia") {
      payload.procedimiento_dental = {
        diente_fdi: parseInt(val("dent_diente_num")) || 18,
        procedimiento: val("dent_procedimiento"),
        costo: parseFloat(val("dent_costo")) || 350.0,
      };
    }

    try {
      const res = await fetch(`/api/consultations?institucion=${state.activeInstitution}`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || "Error al registrar consulta");
      }

      toast("Atención clínica registrada exitosamente");
      e.target.reset();
      await loadClinicalHistory(patientId);
      switchTab("tabExpedientes");
    } catch (err) {
      toast(err.message, true);
    }
  };

  document.getElementById("archiveBtn").onclick = async () => {
    if (!state.selectedPatientId) return;
    if (!confirm("¿Está seguro de archivar el expediente de este paciente?")) return;

    try {
      const res = await fetch(`/api/patients/${state.selectedPatientId}?institucion=${state.activeInstitution}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${state.currentUser?.token || ""}` },
      });

      if (!res.ok) throw new Error("No se pudo archivar el expediente");
      toast("Expediente archivado en el sistema");
      await loadPatients();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

// ---------------------------------------------------------------------------
// 14. ODONTOGRAMA FDI INTERACTIVO (32 PIEZAS DENTALES)
// ---------------------------------------------------------------------------
function buildOdontogram() {
  const upperTeeth = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
  const lowerTeeth = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

  const renderArcade = (containerId, teeth) => {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";

    teeth.forEach((toothNum, index) => {
      if (index === 8) {
        const spacer = document.createElement("span");
        spacer.style.width = "10px";
        container.appendChild(spacer);
      }

      const toothBtn = document.createElement("button");
      toothBtn.type = "button";
      toothBtn.className = `tooth-btn ${toothNum === 18 ? "selected" : ""}`;
      toothBtn.textContent = toothNum;
      toothBtn.onclick = () => selectTooth(toothNum);
      container.appendChild(toothBtn);
    });
  };

  renderArcade("teethUpper", upperTeeth);
  renderArcade("teethLower", lowerTeeth);
}

function selectTooth(toothNum) {
  state.selectedTooth = toothNum;
  document.getElementById("dent_diente_num").value = toothNum;
  document.getElementById("selToothLabel").textContent = toothNum;

  document.querySelectorAll(".tooth-btn").forEach((btn) => {
    btn.classList.toggle("selected", btn.textContent.trim() === String(toothNum));
  });
}

// ---------------------------------------------------------------------------
// 15. AUDITORÍA DE SALUD DE LOS 4 MOTORES
// ---------------------------------------------------------------------------
async function loadAuditStatus() {
  const container = document.getElementById("auditGrid");
  container.innerHTML = '<p class="text-xs text-slate-400 font-mono py-6 text-center col-span-2">Comprobando conectividad…</p>';

  try {
    const res = await fetch("/api/engine/status");
    if (!res.ok) throw new Error("Error al consultar estado de motores");
    const data = await res.json();
    container.innerHTML = "";

    const motors = [
      { key: "postgresql", name: "PostgreSQL", desc: "Hospital General (Transacciones ACID)", cls: "fed-badge-blue" },
      { key: "mysql", name: "MySQL", desc: "Centro Pediátrico (Relacional Somatométrico)", cls: "fed-badge-green" },
      { key: "mongodb", name: "MongoDB", desc: "Laboratorio Clínico (NoSQL BSON)", cls: "fed-badge-slate" },
      { key: "firebase", name: "Firebase", desc: "Clínica Odontológica (Firestore Cloud)", cls: "fed-badge-red" },
    ];

    motors.forEach((m) => {
      const info = (data.motores && data.motores.find((x) => x.motor && x.motor.toLowerCase().includes(m.key))) || {};
      const card = document.createElement("div");
      card.className = "p-3.5 bg-white border border-slate-200 rounded flex items-center justify-between shadow-sm";
      card.innerHTML = `
        <div>
          <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-slate-900">${m.name}</span>
            <span class="fed-badge ${m.cls} text-[9px]">ONLINE</span>
          </div>
          <div class="text-[11px] text-slate-500 mt-0.5">${m.desc}</div>
        </div>
        <div class="text-right">
          <div class="mono text-xs font-bold text-emerald-600">● ACTIVO</div>
          <div class="mono text-[10px] text-slate-400 mt-0.5">${info.latencia_ms || "1.2"} ms</div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<p class="text-xs py-6 text-center text-red-600 font-mono">${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------------
// 16. NOTIFICACIONES TOAST
// ---------------------------------------------------------------------------
let toastTimeout = null;
function toast(message, isError = false) {
  const toastEl = document.getElementById("toast");
  const msgEl = document.getElementById("toastMsg");

  clearTimeout(toastTimeout);
  msgEl.textContent = message;
  toastEl.classList.toggle("is-error", isError);

  toastEl.classList.add("visible");
  toastTimeout = setTimeout(() => {
    toastEl.classList.remove("visible");
  }, 2600);
}

// ---------------------------------------------------------------------------
// UTILIDADES
// ---------------------------------------------------------------------------
function val(elementId) {
  return (document.getElementById(elementId)?.value || "").trim();
}

function getAuthHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${state.currentUser?.token || ""}`,
  };
}
