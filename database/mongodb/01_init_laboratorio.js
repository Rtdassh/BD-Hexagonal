/**
 * ============================================================================
 * PROYECTO FINAL BASES DE DATOS II - UNIVERSIDAD RAFAEL LANDÍVAR
 * INSTITUCIÓN: LABORATORIO CLÍNICO
 * MOTOR DE BASE DE DATOS: MongoDB (NoSQL Documental)
 * ARQUITECTURA DOCUMENTAL: 
 *   - Colección Pacientes: Referenciada (independiente para evitar 'unbounded arrays')
 *   - Colección Resultados: Embebe los Parámetros y Valores Analíticos Dinámicos
 *   - Colección Muestras: Trazabilidad por código de barras y estado biológico
 * ============================================================================
 */

// Seleccionar base de datos
const dbName = 'laboratorio_clinico';
const dbInstance = db.getSiblingDB(dbName);

// ----------------------------------------------------------------------------
// 1. LIMPIEZA DE COLECCIONES PREVIAS
// ----------------------------------------------------------------------------
dbInstance.pacientes.drop();
dbInstance.medicos_solicitantes.drop();
dbInstance.laboratoristas.drop();
dbInstance.tipos_examen.drop();
dbInstance.ordenes.drop();
dbInstance.muestras.drop();
dbInstance.resultados.drop();
dbInstance.historiales_clinicos.drop();

// ----------------------------------------------------------------------------
// 2. CREACIÓN DE COLECCIONES CON VALIDACIÓN DE ESQUEMA (JSON SCHEMA)
// ----------------------------------------------------------------------------

// A. Pacientes
dbInstance.createCollection('pacientes', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['id_paciente', 'nombres', 'apellidos', 'fecha_nacimiento', 'sexo', 'dpi', 'estado'],
      properties: {
        id_paciente: { bsonType: 'int', description: 'Identificador único secuencial' },
        nombres: { bsonType: 'string' },
        apellidos: { bsonType: 'string' },
        fecha_nacimiento: { bsonType: 'string' },
        sexo: { enum: ['M', 'F'] },
        dpi: { bsonType: 'string', description: 'Documento personal de identificación único' },
        direccion: { bsonType: 'string' },
        telefono: { bsonType: 'string' },
        correo_electronico: { bsonType: 'string' },
        tipo_sangre: { bsonType: 'string' },
        contacto_emergencia: {
          bsonType: 'object',
          properties: {
            nombre: { bsonType: 'string' },
            telefono: { bsonType: 'string' }
          }
        },
        fecha_registro: { bsonType: 'string' },
        estado: { enum: ['activo', 'inactivo', 'dado_de_baja'] }
      }
    }
  }
});
dbInstance.pacientes.createIndex({ dpi: 1 }, { unique: true });
dbInstance.pacientes.createIndex({ id_paciente: 1 }, { unique: true });

// B. Tipos de Examen (Catálogo polimórfico de áreas del laboratorio)
dbInstance.createCollection('tipos_examen', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['codigo', 'nombre_examen', 'area_laboratorio', 'costo'],
      properties: {
        codigo: { bsonType: 'string' },
        nombre_examen: { bsonType: 'string' },
        area_laboratorio: { enum: ['Hematología', 'Química Clínica', 'Uroanálisis', 'Microbiología', 'Inmunología'] },
        descripcion: { bsonType: 'string' },
        indicaciones_preparacion: { bsonType: 'string' },
        tiempo_estimado_horas: { bsonType: 'int' },
        costo: { bsonType: ['double', 'int'], description: 'mongosh guarda 120.00 como entero' }
      }
    }
  }
});
dbInstance.tipos_examen.createIndex({ codigo: 1 }, { unique: true });

// C. Muestras Biológicas (Trazabilidad estricta de tubos y frascos)
dbInstance.createCollection('muestras', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['id_muestra', 'id_orden', 'tipo_muestra', 'codigo_etiqueta_barras', 'estado'],
      properties: {
        id_muestra: { bsonType: 'int' },
        id_orden: { bsonType: 'int' },
        tipo_muestra: { bsonType: 'string' },
        codigo_etiqueta_barras: { bsonType: 'string' },
        fecha_hora_toma: { bsonType: 'string' },
        condicion_muestra: { bsonType: 'string' },
        estado: { enum: ['recolectada', 'recibida', 'apta_analisis', 'rechazada', 'procesada'] }
      }
    }
  }
});
dbInstance.muestras.createIndex({ codigo_etiqueta_barras: 1 }, { unique: true });

// D. Resultados con parámetros dinámicos embebidos
dbInstance.createCollection('resultados', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['id_resultado', 'id_orden', 'id_paciente', 'codigo_examen', 'estado', 'parametros'],
      properties: {
        id_resultado: { bsonType: 'int' },
        id_orden: { bsonType: 'int' },
        id_paciente: { bsonType: 'int' },
        codigo_examen: { bsonType: 'string' },
        nombre_examen: { bsonType: 'string' },
        id_laboratorista_analista: { bsonType: 'int' },
        id_laboratorista_validador: { bsonType: 'int' },
        fecha_hora_analisis: { bsonType: 'string' },
        fecha_hora_validacion: { bsonType: 'string' },
        estado: { enum: ['en_analisis', 'preliminar', 'validado', 'entregado'] },
        alertas_criticas: { bsonType: 'bool' },
        observaciones_tecnicas: { bsonType: 'string' },
        conclusiones_diagnosticas: { bsonType: 'string' },
        parametros: {
          bsonType: 'array',
          items: {
            bsonType: 'object',
            required: ['nombre_parametro', 'valor_resultado', 'unidad_medida', 'interpretacion_alerta'],
            properties: {
              nombre_parametro: { bsonType: 'string' },
              valor_resultado: { bsonType: ['double', 'string', 'int'] },
              unidad_medida: { bsonType: 'string' },
              rango_referencia_min: { bsonType: ['double', 'null', 'int'] },
              rango_referencia_max: { bsonType: ['double', 'null', 'int'] },
              valor_referencia_cualitativo: { bsonType: ['string', 'null'] },
              interpretacion_alerta: { enum: ['NORMAL', 'ALTO', 'BAJO', 'CRITICO_ALTO', 'CRITICO_BAJO', 'POSITIVO', 'NEGATIVO'] }
            }
          }
        }
      }
    }
  }
});
dbInstance.resultados.createIndex({ id_paciente: 1, fecha_hora_analisis: -1 });
dbInstance.resultados.createIndex({ id_orden: 1 });

// E. Historiales Clínicos de Laboratorio
dbInstance.createCollection('historiales_clinicos');
dbInstance.historiales_clinicos.createIndex({ id_paciente: 1 }, { unique: true });

// ----------------------------------------------------------------------------
// 3. INSERCIÓN DE DATOS SEMILLA / SEED DATA
// ----------------------------------------------------------------------------

// A. Médicos solicitantes
dbInstance.medicos_solicitantes.insertMany([
  {
    id_medico: 1,
    nombre_completo: "Dr. Roberto Villagrán Santos",
    numero_colegiado: "COL-98711",
    especialidad: "Medicina Interna",
    institucion_procedencia: "Clínica Privada Los Altos",
    telefono: "5553-0101",
    correo_electronico: "rvillagran@losaltos.com"
  }
]);

// B. Bioquímicos y laboratoristas
dbInstance.laboratoristas.insertMany([
  {
    id_laboratorista: 1,
    nombre_completo: "Licda. Brenda Marisol Morales",
    numero_colegiado_licencia: "QB-4521",
    cargo_especialidad: "Química Bióloga - Jefa de Control de Calidad",
    telefono: "5553-0201",
    correo_electronico: "bmorales@laboratoriolandivar.gt",
    estado: "activo"
  }
]);

// C. Tipos de Examen
dbInstance.tipos_examen.insertMany([
  {
    codigo: "HEM-01",
    nombre_examen: "Hematología Completa Automatizada",
    area_laboratorio: "Hematología",
    descripcion: "Recuento completo de leucocitos, hematíes, plaquetas e índices eritrocitarios",
    indicaciones_preparacion: "Ayuno mínimo de 4 horas",
    tiempo_estimado_horas: 3,
    costo: 120.00
  },
  {
    codigo: "QUI-01",
    nombre_examen: "Perfil Glucémico y Renal (Glucosa + Creatinina)",
    area_laboratorio: "Química Clínica",
    descripcion: "Determinación cuantitativa de glucosa basal y creatinina sérica",
    indicaciones_preparacion: "Ayuno estricto de 8 a 12 horas",
    tiempo_estimado_horas: 2,
    costo: 95.00
  },
  {
    codigo: "URO-01",
    nombre_examen: "Uroanálisis General y Sedimento Urinario",
    area_laboratorio: "Uroanálisis",
    descripcion: "Análisis físico, químico y microscópico del sedimento en orina fresca",
    indicaciones_preparacion: "Primera orina de la mañana, chorro medio previo aseo",
    tiempo_estimado_horas: 1,
    costo: 60.00
  }
]);

// D. Paciente 1 (Paciente con resultado analítico normal)
dbInstance.pacientes.insertOne({
  id_paciente: 1,
  nombres: "Estuardo René",
  apellidos: "Guzmán Barrios",
  fecha_nacimiento: "1988-11-23",
  sexo: "M",
  dpi: "2389104520101",
  direccion: "Zona 9, Quetzaltenango",
  telefono: "4811-2299",
  correo_electronico: "eguzman@gmail.com",
  tipo_sangre: "A+",
  contacto_emergencia: {
    nombre: "Claudia de Guzmán",
    telefono: "4811-2200"
  },
  fecha_registro: "2026-02-10",
  estado: "activo"
});

dbInstance.historiales_clinicos.insertOne({
  id_historial: 1,
  id_paciente: 1,
  fecha_apertura: "2026-02-10",
  fecha_ultima_actualizacion: "2026-03-01T11:45:00Z",
  estado: "activo",
  motivo_baja: null,
  total_examenes_realizados: 1
});

// Orden 1
dbInstance.ordenes.insertOne({
  id_orden: 1,
  id_paciente: 1,
  id_medico_solicitante: 1,
  fecha_hora_ingreso: "2026-03-01T07:15:00Z",
  prioridad: "normal",
  diagnostico_presuntivo: "Chequeo médico laboral de rutina",
  estado_orden: "completada",
  observaciones: "Paciente en ayuno adecuado"
});

// Muestra 1
dbInstance.muestras.insertOne({
  id_muestra: 1,
  id_orden: 1,
  tipo_muestra: "Sangre total con EDTA (Tubo lila)",
  codigo_etiqueta_barras: "LAB-2026-000101",
  fecha_hora_toma: "2026-03-01T07:30:00Z",
  condicion_muestra: "Volumen adecuado, sin hemólisis ni microcoágulos",
  estado: "procesada"
});

// Resultado 1: Hematología Completa (Estructura dinámica de parámetros)
dbInstance.resultados.insertOne({
  id_resultado: 1,
  id_orden: 1,
  id_paciente: 1,
  codigo_examen: "HEM-01",
  nombre_examen: "Hematología Completa Automatizada",
  id_laboratorista_analista: 1,
  id_laboratorista_validador: 1,
  fecha_hora_analisis: "2026-03-01T09:30:00Z",
  fecha_hora_validacion: "2026-03-01T10:15:00Z",
  estado: "validado",
  alertas_criticas: false,
  observaciones_tecnicas: "Curvas citométricas normales",
  conclusiones_diagnosticas: "Serie roja, leucocitaria y plaquetaria sin alteraciones patológicas.",
  parametros: [
    {
      nombre_parametro: "Leucocitos Totales",
      valor_resultado: 7.2,
      unidad_medida: "10^3/uL",
      rango_referencia_min: 4.5,
      rango_referencia_max: 11.0,
      valor_referencia_cualitativo: null,
      interpretacion_alerta: "NORMAL"
    },
    {
      nombre_parametro: "Hemoglobina",
      valor_resultado: 15.1,
      unidad_medida: "g/dL",
      rango_referencia_min: 13.5,
      rango_referencia_max: 17.5,
      valor_referencia_cualitativo: null,
      interpretacion_alerta: "NORMAL"
    },
    {
      nombre_parametro: "Hematocrito",
      valor_resultado: 45.3,
      unidad_medida: "%",
      rango_referencia_min: 41.0,
      rango_referencia_max: 50.0,
      valor_referencia_cualitativo: null,
      interpretacion_alerta: "NORMAL"
    },
    {
      nombre_parametro: "Plaquetas",
      valor_resultado: 245.0,
      unidad_medida: "10^3/uL",
      rango_referencia_min: 150.0,
      rango_referencia_max: 450.0,
      valor_referencia_cualitativo: null,
      interpretacion_alerta: "NORMAL"
    }
  ]
});

// Paciente 2 (Paciente con Valor Crítico de Glucosa)
dbInstance.pacientes.insertOne({
  id_paciente: 2,
  nombres: "Marta Alicia",
  apellidos: "Hernández de León",
  fecha_nacimiento: "1965-04-18",
  sexo: "F",
  dpi: "1890334410101",
  direccion: "Zona 1, Quetzaltenango",
  telefono: "5901-4433",
  correo_electronico: "mhernandez@hotmail.com",
  tipo_sangre: "O+",
  contacto_emergencia: {
    nombre: "Jorge Hernández (Hijo)",
    telefono: "5901-4434"
  },
  fecha_registro: "2026-03-01",
  estado: "activo"
});

dbInstance.historiales_clinicos.insertOne({
  id_historial: 2,
  id_paciente: 2,
  fecha_apertura: "2026-03-01",
  fecha_ultima_actualizacion: "2026-03-01T12:00:00Z",
  estado: "activo",
  motivo_baja: null,
  total_examenes_realizados: 1
});

dbInstance.ordenes.insertOne({
  id_orden: 2,
  id_paciente: 2,
  id_medico_solicitante: 1,
  fecha_hora_ingreso: "2026-03-01T08:00:00Z",
  prioridad: "emergencia",
  diagnostico_presuntivo: "Sospecha de cetoacidosis / descompensación diabética",
  estado_orden: "completada",
  observaciones: "Priorizar reporte telefónico"
});

dbInstance.resultados.insertOne({
  id_resultado: 2,
  id_orden: 2,
  id_paciente: 2,
  codigo_examen: "QUI-01",
  nombre_examen: "Perfil Glucémico y Renal (Glucosa + Creatinina)",
  id_laboratorista_analista: 1,
  id_laboratorista_validador: 1,
  fecha_hora_analisis: "2026-03-01T09:00:00Z",
  fecha_hora_validacion: "2026-03-01T09:15:00Z",
  estado: "validado",
  alertas_criticas: true,
  observaciones_tecnicas: "Alerta crítica notificada vía telefónica a médico solicitante a las 09:20 hrs.",
  conclusiones_diagnosticas: "Hiperglucemia severa descompensada fuera de rango fisiológico. Compromiso metabólico agudo.",
  parametros: [
    {
      nombre_parametro: "Glucosa Sérica Basal",
      valor_resultado: 348.0,
      unidad_medida: "mg/dL",
      rango_referencia_min: 70.0,
      rango_referencia_max: 100.0,
      valor_referencia_cualitativo: null,
      interpretacion_alerta: "CRITICO_ALTO"
    },
    {
      nombre_parametro: "Creatinina Sérica",
      valor_resultado: 1.85,
      unidad_medida: "mg/dL",
      rango_referencia_min: 0.5,
      rango_referencia_max: 1.1,
      valor_referencia_cualitativo: null,
      interpretacion_alerta: "ALTO"
    }
  ]
});

// ----------------------------------------------------------------------------
// 4. ÍNDICES ADICIONALES, CONTADORES Y USUARIO DE APLICACIÓN
// ----------------------------------------------------------------------------
dbInstance.ordenes.createIndex({ id_orden: 1 }, { unique: true });
dbInstance.ordenes.createIndex({ id_paciente: 1, fecha_hora_ingreso: -1 });
dbInstance.resultados.createIndex({ id_resultado: 1 }, { unique: true });
dbInstance.pacientes.createIndex({ apellidos: 1, nombres: 1 });

// Diagnóstico presuntivo con código CIE-10 en las órdenes semilla
dbInstance.ordenes.updateOne({ id_orden: 1 }, { $set: { codigo_cie10: "Z02.1" } });
dbInstance.ordenes.updateOne({ id_orden: 2 }, { $set: { codigo_cie10: "E11.1" } });

// Plantillas de parámetros por tipo de examen: cada examen tiene una estructura distinta
// (numérica con rangos, cualitativa, o mixta). Esto es lo que justifica usar un modelo documental.
dbInstance.tipos_examen.insertOne({
  codigo: "MIC-01",
  nombre_examen: "Urocultivo con antibiograma",
  area_laboratorio: "Microbiología",
  descripcion: "Cultivo de orina, identificación del microorganismo y sensibilidad antibiótica",
  indicaciones_preparacion: "Primera orina de la mañana en frasco estéril",
  tiempo_estimado_horas: 48,
  costo: 180.00
});
dbInstance.tipos_examen.updateOne({ codigo: "HEM-01" }, { $set: { parametros_plantilla: [
  { nombre_parametro: "Leucocitos Totales", unidad_medida: "10^3/uL", rango_referencia_min: 4.5, rango_referencia_max: 11.0 },
  { nombre_parametro: "Hemoglobina", unidad_medida: "g/dL", rango_referencia_min: 13.5, rango_referencia_max: 17.5 },
  { nombre_parametro: "Hematocrito", unidad_medida: "%", rango_referencia_min: 41.0, rango_referencia_max: 50.0 },
  { nombre_parametro: "Plaquetas", unidad_medida: "10^3/uL", rango_referencia_min: 150.0, rango_referencia_max: 450.0 }
] } });
dbInstance.tipos_examen.updateOne({ codigo: "QUI-01" }, { $set: { parametros_plantilla: [
  { nombre_parametro: "Glucosa Sérica Basal", unidad_medida: "mg/dL", rango_referencia_min: 70.0, rango_referencia_max: 100.0 },
  { nombre_parametro: "Creatinina Sérica", unidad_medida: "mg/dL", rango_referencia_min: 0.5, rango_referencia_max: 1.1 }
] } });
dbInstance.tipos_examen.updateOne({ codigo: "URO-01" }, { $set: { parametros_plantilla: [
  { nombre_parametro: "Color", unidad_medida: "", valor_referencia_cualitativo: "Amarillo" },
  { nombre_parametro: "Aspecto", unidad_medida: "", valor_referencia_cualitativo: "Transparente" },
  { nombre_parametro: "pH", unidad_medida: "", rango_referencia_min: 5.0, rango_referencia_max: 8.0 },
  { nombre_parametro: "Proteínas", unidad_medida: "", valor_referencia_cualitativo: "Negativo" },
  { nombre_parametro: "Leucocitos (sedimento)", unidad_medida: "por campo", rango_referencia_min: 0, rango_referencia_max: 5 }
] } });
dbInstance.tipos_examen.updateOne({ codigo: "MIC-01" }, { $set: { parametros_plantilla: [
  { nombre_parametro: "Crecimiento bacteriano", unidad_medida: "", valor_referencia_cualitativo: "Negativo" },
  { nombre_parametro: "Recuento de colonias", unidad_medida: "UFC/mL", rango_referencia_min: 0, rango_referencia_max: 10000 },
  { nombre_parametro: "Microorganismo aislado", unidad_medida: "", valor_referencia_cualitativo: "Ninguno" },
  { nombre_parametro: "Sensibilidad antibiótica", unidad_medida: "", valor_referencia_cualitativo: "No aplica" }
] } });

// Citas de toma de muestra (agenda del laboratorio)
dbInstance.citas.drop();
dbInstance.citas.createIndex({ id_cita: 1 }, { unique: true });
dbInstance.citas.createIndex({ id_paciente: 1, fecha_hora_programada: -1 });

// Contadores para ids enteros secuenciales (se incrementan con $inc dentro de la transacción)
dbInstance.contadores.drop();
dbInstance.contadores.insertMany([
  { _id: "pacientes", seq: 2 },
  { _id: "historiales_clinicos", seq: 2 },
  { _id: "ordenes", seq: 2 },
  { _id: "muestras", seq: 1 },
  { _id: "resultados", seq: 2 },
  { _id: "citas", seq: 0 }
]);

// Usuario de la aplicación con mínimo privilegio (solo lectura/escritura en esta base)
if (!dbInstance.getUser("app_laboratorio")) {
  dbInstance.createUser({
    user: "app_laboratorio",
    pwd: "LaboratorioApp2026!",
    roles: [{ role: "readWrite", db: dbName }]
  });
}

print("==> Base de datos 'laboratorio_clinico' inicializada exitosamente con 10 colecciones y datos semilla polimórficos.");

