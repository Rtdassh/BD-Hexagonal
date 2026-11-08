-- ============================================================================
-- PROYECTO FINAL BASES DE DATOS II - UNIVERSIDAD RAFAEL LANDÍVAR
-- INSTITUCIÓN: CLÍNICA ODONTOLÓGICA
-- MODELO: Relacional Normalizado en Tercera Forma Normal (3FN)
-- MOTOR: MySQL 8.x con InnoDB
-- TOTAL TABLAS: 28 TABLAS
-- ============================================================================

SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS clinica_odontologica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE clinica_odontologica;

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Paciente Dental
CREATE TABLE IF NOT EXISTS paciente (
    id_paciente INT AUTO_INCREMENT PRIMARY KEY,
    dpi_identificacion VARCHAR(15) NOT NULL UNIQUE,
    nombres VARCHAR(60) NOT NULL,
    apellidos VARCHAR(60) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    sexo ENUM('M', 'F') NOT NULL,
    telefono VARCHAR(15) NOT NULL,
    correo VARCHAR(80),
    direccion VARCHAR(200) NOT NULL,
    fecha_registro DATE NOT NULL DEFAULT (CURRENT_DATE),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_pac_odo_estado CHECK (estado IN ('activo', 'inactivo', 'archivado'))
) ENGINE=InnoDB;

-- 2. Contacto de Emergencia
CREATE TABLE IF NOT EXISTS contacto_emergencia_paciente (
    id_contacto INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    parentesco VARCHAR(30) NOT NULL,
    telefono_emergencia VARCHAR(15) NOT NULL,
    CONSTRAINT fk_cep_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 3. Anamnesis y Antecedentes Médicos Sistémicos (1:1)
CREATE TABLE IF NOT EXISTS antecedente_medico_dental (
    id_antecedente INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL UNIQUE,
    padece_diabetes BOOLEAN NOT NULL DEFAULT FALSE,
    padece_hipertension BOOLEAN NOT NULL DEFAULT FALSE,
    padece_coagulopatia BOOLEAN NOT NULL DEFAULT FALSE,
    es_alergico_anestesia BOOLEAN NOT NULL DEFAULT FALSE,
    es_alergico_latex BOOLEAN NOT NULL DEFAULT FALSE,
    esta_embarazada BOOLEAN NOT NULL DEFAULT FALSE,
    medicamentos_actuales TEXT,
    observaciones_medicas TEXT,
    CONSTRAINT fk_amd_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 4. Catálogo de Especialidades Dentales
CREATE TABLE IF NOT EXISTS especialidad_dental (
    id_especialidad INT AUTO_INCREMENT PRIMARY KEY,
    nombre_especialidad VARCHAR(80) NOT NULL UNIQUE,
    descripcion TEXT,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB;

-- 5. Cirujanos Dentistas / Odontólogos
CREATE TABLE IF NOT EXISTS odontologo (
    id_odontologo INT AUTO_INCREMENT PRIMARY KEY,
    numero_colegiado VARCHAR(20) NOT NULL UNIQUE,
    nombres VARCHAR(60) NOT NULL,
    apellidos VARCHAR(60) NOT NULL,
    telefono VARCHAR(15),
    correo_electronico VARCHAR(80),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB;

-- 6. Acreditación Odontólogo - Especialidad (N:M)
CREATE TABLE IF NOT EXISTS odontologo_especialidad (
    id_odontologo_especialidad INT AUTO_INCREMENT PRIMARY KEY,
    id_odontologo INT NOT NULL,
    id_especialidad INT NOT NULL,
    fecha_certificacion DATE NOT NULL,
    CONSTRAINT uk_odonto_esp UNIQUE (id_odontologo, id_especialidad),
    CONSTRAINT fk_oe_odonto FOREIGN KEY (id_odontologo) REFERENCES odontologo(id_odontologo) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_oe_esp FOREIGN KEY (id_especialidad) REFERENCES especialidad_dental(id_especialidad) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 7. Personal de Secretaría y Recepción
CREATE TABLE IF NOT EXISTS secretaria_recepcion (
    id_secretaria INT AUTO_INCREMENT PRIMARY KEY,
    nombres VARCHAR(60) NOT NULL,
    apellidos VARCHAR(60) NOT NULL,
    usuario_sistema VARCHAR(30) NOT NULL UNIQUE,
    telefono VARCHAR(15),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB;

-- 8. Horarios y Sillones Asignados
CREATE TABLE IF NOT EXISTS horario_odontologo (
    id_horario INT AUTO_INCREMENT PRIMARY KEY,
    id_odontologo INT NOT NULL,
    dia_semana ENUM('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado') NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    sillon_dental_asignado VARCHAR(10) NOT NULL,
    CONSTRAINT fk_ho_odonto FOREIGN KEY (id_odontologo) REFERENCES odontologo(id_odontologo) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 9. Historial Clínico Odontológico
CREATE TABLE IF NOT EXISTS historial_clinico_dental (
    id_historial INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL UNIQUE,
    fecha_apertura DATE NOT NULL DEFAULT (CURRENT_DATE),
    fecha_ultima_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'activo',
    motivo_baja VARCHAR(150),
    CONSTRAINT fk_hcd_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 10. Citas Dentales
CREATE TABLE IF NOT EXISTS cita_dental (
    id_cita INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_odontologo INT NOT NULL,
    id_secretaria INT NOT NULL,
    fecha_hora_programada DATETIME NOT NULL,
    motivo_consulta VARCHAR(200) NOT NULL,
    duracion_estimada_min INT NOT NULL DEFAULT 30,
    estado_cita ENUM('programada', 'confirmada', 'en_espera', 'atendida', 'cancelada', 'no_asistio') NOT NULL DEFAULT 'programada',
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cd_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cd_odonto FOREIGN KEY (id_odontologo) REFERENCES odontologo(id_odontologo) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cd_secretaria FOREIGN KEY (id_secretaria) REFERENCES secretaria_recepcion(id_secretaria) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 11. Cuadrantes Anatómicos FDI (1-8)
CREATE TABLE IF NOT EXISTS cuadrante_dental (
    id_cuadrante INT AUTO_INCREMENT PRIMARY KEY,
    numero_cuadrante INT NOT NULL UNIQUE,
    tipo_denticion ENUM('Permanente', 'Temporal') NOT NULL,
    arco_dental ENUM('Superior', 'Inferior') NOT NULL,
    hemiarcada ENUM('Derecha', 'Izquierda') NOT NULL
) ENGINE=InnoDB;

-- 12. Piezas Dentales FDI (11-48, 51-85)
CREATE TABLE IF NOT EXISTS pieza_dental (
    codigo_fdi INT PRIMARY KEY,
    id_cuadrante INT NOT NULL,
    nombre_anatomico VARCHAR(80) NOT NULL,
    tipo_diente ENUM('Incisivo central', 'Incisivo lateral', 'Canino', 'Primer premolar', 'Segundo premolar', 'Primer molar', 'Segundo molar', 'Tercer molar') NOT NULL,
    CONSTRAINT fk_pd_cuadrante FOREIGN KEY (id_cuadrante) REFERENCES cuadrante_dental(id_cuadrante) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 13. Caras Dentales
CREATE TABLE IF NOT EXISTS cara_dental (
    id_cara INT AUTO_INCREMENT PRIMARY KEY,
    codigo_cara VARCHAR(2) NOT NULL UNIQUE,
    nombre_cara VARCHAR(50) NOT NULL,
    descripcion VARCHAR(150)
) ENGINE=InnoDB;

-- 14. Catálogo de Hallazgos y Diagnósticos Dentales
CREATE TABLE IF NOT EXISTS catalogo_hallazgo_dental (
    id_hallazgo INT AUTO_INCREMENT PRIMARY KEY,
    codigo_hallazgo VARCHAR(30) NOT NULL UNIQUE,
    nombre_hallazgo VARCHAR(100) NOT NULL,
    color_simbologia_hex VARCHAR(7) NOT NULL DEFAULT '#FF0000'
) ENGINE=InnoDB;

-- 15. Odontograma (Sesión de Mapeo Dental)
CREATE TABLE IF NOT EXISTS odontograma (
    id_odontograma INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_odontologo INT NOT NULL,
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_odontograma ENUM('inicial', 'evolucion', 'posoperatorio') NOT NULL DEFAULT 'inicial',
    observaciones_generales TEXT,
    CONSTRAINT fk_odg_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_odg_odonto FOREIGN KEY (id_odontologo) REFERENCES odontologo(id_odontologo) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 16. Detalle del Odontograma por Cara y Diente
CREATE TABLE IF NOT EXISTS detalle_odontograma (
    id_detalle_odontograma INT AUTO_INCREMENT PRIMARY KEY,
    id_odontograma INT NOT NULL,
    codigo_fdi INT NOT NULL,
    id_cara INT NOT NULL,
    id_hallazgo INT NOT NULL,
    notas_especificas VARCHAR(255),
    CONSTRAINT uk_odonto_diente_cara UNIQUE (id_odontograma, codigo_fdi, id_cara),
    CONSTRAINT fk_do_odontograma FOREIGN KEY (id_odontograma) REFERENCES odontograma(id_odontograma) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_do_fdi FOREIGN KEY (codigo_fdi) REFERENCES pieza_dental(codigo_fdi) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_do_cara FOREIGN KEY (id_cara) REFERENCES cara_dental(id_cara) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_do_hallazgo FOREIGN KEY (id_hallazgo) REFERENCES catalogo_hallazgo_dental(id_hallazgo) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 17. Categorías de Procedimientos Dentales
CREATE TABLE IF NOT EXISTS categoria_procedimiento (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    nombre_categoria VARCHAR(60) NOT NULL UNIQUE,
    descripcion TEXT
) ENGINE=InnoDB;

-- 18. Catálogo Arancelario de Procedimientos
CREATE TABLE IF NOT EXISTS catalogo_procedimiento (
    id_procedimiento INT AUTO_INCREMENT PRIMARY KEY,
    id_categoria INT NOT NULL,
    nombre_procedimiento VARCHAR(100) NOT NULL,
    codigo_arancelario VARCHAR(20) NOT NULL UNIQUE,
    duracion_estimada_min INT NOT NULL DEFAULT 30,
    costo_base DECIMAL(10,2) NOT NULL,
    requiere_pieza_dental BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_proc_costo CHECK (costo_base >= 0),
    CONSTRAINT fk_cp_cat FOREIGN KEY (id_categoria) REFERENCES categoria_procedimiento(id_categoria) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 19. Planes Globales de Tratamiento Dental
CREATE TABLE IF NOT EXISTS plan_tratamiento (
    id_plan INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_odontologo INT NOT NULL,
    fecha_propuesta DATE NOT NULL DEFAULT (CURRENT_DATE),
    costo_total_estimado DECIMAL(10,2) NOT NULL,
    estado_aprobacion ENUM('pendiente', 'aprobado', 'en_ejecucion', 'finalizado', 'rechazado') NOT NULL DEFAULT 'pendiente',
    fecha_aprobacion DATE,
    CONSTRAINT chk_plan_costo CHECK (costo_total_estimado >= 0),
    CONSTRAINT fk_pt_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pt_odonto FOREIGN KEY (id_odontologo) REFERENCES odontologo(id_odontologo) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 20. Etapas del Plan de Tratamiento
CREATE TABLE IF NOT EXISTS etapa_tratamiento (
    id_etapa INT AUTO_INCREMENT PRIMARY KEY,
    id_plan INT NOT NULL,
    numero_etapa INT NOT NULL,
    descripcion_fase VARCHAR(200) NOT NULL,
    costo_fase DECIMAL(10,2) NOT NULL,
    estado_fase ENUM('pendiente', 'en_curso', 'completada') NOT NULL DEFAULT 'pendiente',
    CONSTRAINT fk_et_plan FOREIGN KEY (id_plan) REFERENCES plan_tratamiento(id_plan) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 21. Consulta / Sesión de Atención Dental
CREATE TABLE IF NOT EXISTS consulta_atencion_dental (
    id_consulta INT AUTO_INCREMENT PRIMARY KEY,
    id_cita INT NOT NULL,
    id_etapa INT,
    fecha_hora_atencion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notas_evolucion TEXT NOT NULL,
    anestesia_utilizada_ml DECIMAL(5,2) DEFAULT 0.00,
    odontologo_atendio VARCHAR(100) NOT NULL,
    CONSTRAINT fk_cad_cita FOREIGN KEY (id_cita) REFERENCES cita_dental(id_cita) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cad_etapa FOREIGN KEY (id_etapa) REFERENCES etapa_tratamiento(id_etapa) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 22. Procedimientos Aplicados en la Sesión
CREATE TABLE IF NOT EXISTS procedimiento_aplicado (
    id_procedimiento_aplicado INT AUTO_INCREMENT PRIMARY KEY,
    id_consulta INT NOT NULL,
    id_procedimiento INT NOT NULL,
    codigo_fdi INT,
    id_cara INT,
    precio_cobrado DECIMAL(10,2) NOT NULL,
    observaciones TEXT,
    CONSTRAINT fk_pa_consulta FOREIGN KEY (id_consulta) REFERENCES consulta_atencion_dental(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pa_proc FOREIGN KEY (id_procedimiento) REFERENCES catalogo_procedimiento(id_procedimiento) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pa_fdi FOREIGN KEY (codigo_fdi) REFERENCES pieza_dental(codigo_fdi) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_pa_cara FOREIGN KEY (id_cara) REFERENCES cara_dental(id_cara) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 23. Catálogo de Insumos y Materiales Dentales
CREATE TABLE IF NOT EXISTS catalogo_insumo_dental (
    id_insumo INT AUTO_INCREMENT PRIMARY KEY,
    nombre_insumo VARCHAR(100) NOT NULL,
    unidad_medida VARCHAR(30) NOT NULL,
    stock_actual INT NOT NULL DEFAULT 0,
    stock_minimo INT NOT NULL DEFAULT 5,
    precio_unitario_costo DECIMAL(8,2) NOT NULL DEFAULT 0.00
) ENGINE=InnoDB;

-- 24. Insumos Consumidos por Procedimiento
CREATE TABLE IF NOT EXISTS consumo_insumo_procedimiento (
    id_consumo INT AUTO_INCREMENT PRIMARY KEY,
    id_procedimiento_aplicado INT NOT NULL,
    id_insumo INT NOT NULL,
    cantidad_utilizada DECIMAL(6,2) NOT NULL,
    CONSTRAINT fk_cip_proc FOREIGN KEY (id_procedimiento_aplicado) REFERENCES procedimiento_aplicado(id_procedimiento_aplicado) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_cip_insumo FOREIGN KEY (id_insumo) REFERENCES catalogo_insumo_dental(id_insumo) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 25. Estudios Radiográficos e Imagenología Intraoral
CREATE TABLE IF NOT EXISTS estudio_radiografico (
    id_radiografia INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_consulta INT,
    tipo_estudio ENUM('Periapical', 'Panorámica', 'Oclusal', 'Tomografía Cone Beam', 'Fotografía intraoral') NOT NULL,
    ruta_archivo_digital VARCHAR(255) NOT NULL,
    fecha_toma DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    interpretacion_clinica TEXT,
    CONSTRAINT fk_er_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_er_consulta FOREIGN KEY (id_consulta) REFERENCES consulta_atencion_dental(id_consulta) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 26. Facturas de Cobro
CREATE TABLE IF NOT EXISTS factura_cobro (
    id_factura INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_plan INT,
    fecha_emision DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    monto_total DECIMAL(10,2) NOT NULL,
    monto_pagado DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    saldo_pendiente DECIMAL(10,2) NOT NULL,
    estado_factura ENUM('pendiente', 'parcial', 'cancelada', 'anulada') NOT NULL DEFAULT 'pendiente',
    CONSTRAINT chk_fact_montos CHECK (monto_total >= 0 AND monto_pagado >= 0),
    CONSTRAINT fk_fc_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_fc_plan FOREIGN KEY (id_plan) REFERENCES plan_tratamiento(id_plan) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 27. Detalle de Pagos y Abonos en Recepción
CREATE TABLE IF NOT EXISTS detalle_pago_abono (
    id_pago INT AUTO_INCREMENT PRIMARY KEY,
    id_factura INT NOT NULL,
    id_secretaria INT NOT NULL,
    fecha_pago DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    monto_abonado DECIMAL(10,2) NOT NULL,
    metodo_pago ENUM('Efectivo', 'Tarjeta de Crédito/Débito', 'Transferencia bancaria') NOT NULL,
    numero_recibo VARCHAR(30) NOT NULL UNIQUE,
    CONSTRAINT chk_abono_monto CHECK (monto_abonado > 0),
    CONSTRAINT fk_dpa_factura FOREIGN KEY (id_factura) REFERENCES factura_cobro(id_factura) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_dpa_sec FOREIGN KEY (id_secretaria) REFERENCES secretaria_recepcion(id_secretaria) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- 28. Auditoría de Modificaciones Clínicas y Financieras
CREATE TABLE IF NOT EXISTS auditoria_modificacion_dental (
    id_auditoria INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL,
    accion VARCHAR(50) NOT NULL,
    tabla_afectada VARCHAR(50) NOT NULL,
    registro_id INT NOT NULL,
    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    detalles TEXT NOT NULL
) ENGINE=InnoDB;

CREATE INDEX idx_odo_pac_dpi ON paciente(dpi_identificacion);
CREATE INDEX idx_odo_cita_fecha ON cita_dental(fecha_hora_programada);
CREATE INDEX idx_factura_saldo ON factura_cobro(saldo_pendiente);

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- DATOS SEMILLA (CATÁLOGOS ANATÓMICOS Y PRUEBAS)
-- ============================================================================

INSERT INTO especialidad_dental (nombre_especialidad, descripcion) VALUES
('Odontología General', 'Atención integral, operatoria y profilaxis básica'),
('Ortodoncia', 'Corrección de anomalías de posición dental y maxilofacial'),
('Endodoncia', 'Tratamiento de patologías pulpares y conductos radiculares'),
('Periodoncia', 'Enfermedades de las encías y hueso de soporte dental');

INSERT INTO cuadrante_dental (numero_cuadrante, tipo_denticion, arco_dental, hemiarcada) VALUES
(1, 'Permanente', 'Superior', 'Derecha'),
(2, 'Permanente', 'Superior', 'Izquierda'),
(3, 'Permanente', 'Inferior', 'Izquierda'),
(4, 'Permanente', 'Inferior', 'Derecha'),
(5, 'Temporal', 'Superior', 'Derecha'),
(6, 'Temporal', 'Superior', 'Izquierda'),
(7, 'Temporal', 'Inferior', 'Izquierda'),
(8, 'Temporal', 'Inferior', 'Derecha');

INSERT INTO cara_dental (codigo_cara, nombre_cara, descripcion) VALUES
('O', 'Oclusal / Incisal', 'Superficie masticatoria o borde cortante'),
('M', 'Mesial', 'Cara proximal dirigida hacia la línea media dental'),
('D', 'Distal', 'Cara proximal más alejada de la línea media dental'),
('V', 'Vestibular', 'Cara externa en contacto con labios y mejillas'),
('L', 'Lingual / Palatina', 'Cara interna en contacto con la lengua o paladar');

INSERT INTO catalogo_hallazgo_dental (codigo_hallazgo, nombre_hallazgo, color_simbologia_hex) VALUES
('CARIES_ACTIVA', 'Caries dental activa', '#E53935'),
('RESINA_BUENA', 'Obturación de resina en buen estado', '#1E88E5'),
('AMALGAMA', 'Obturación con amalgama metálica', '#757575'),
('ENDODONCIA', 'Tratamiento de conducto radicular', '#FB8C00'),
('DIENTE_AUSENTE', 'Pieza dental ausente o extraída', '#000000'),
('CORONA', 'Corona protésica fija', '#8E24AA');

-- Piezas dentales representativas
INSERT INTO pieza_dental (codigo_fdi, id_cuadrante, nombre_anatomico, tipo_diente) VALUES
(11, 1, 'Incisivo Central Superior Derecho', 'Incisivo central'),
(12, 1, 'Incisivo Lateral Superior Derecho', 'Incisivo lateral'),
(13, 1, 'Canino Superior Derecho', 'Canino'),
(16, 1, 'Primer Molar Superior Derecho', 'Primer molar'),
(21, 2, 'Incisivo Central Superior Izquierdo', 'Incisivo central'),
(36, 3, 'Primer Molar Inferior Izquierdo', 'Primer molar'),
(46, 4, 'Primer Molar Inferior Derecho', 'Primer molar');

INSERT INTO categoria_procedimiento (nombre_categoria, descripcion) VALUES
('Preventiva', 'Higiene bucal, flúor y sellantes dentales'),
('Operatoria Dental', 'Restauraciones estéticas directas con resina'),
('Endodoncia', 'Terapia pulpar e instrumentación rotatoria'),
('Cirugía Bucal', 'Extracciones dentales y exodoncias de terceros molares');

INSERT INTO catalogo_procedimiento (id_categoria, nombre_procedimiento, codigo_arancelario, duracion_estimada_min, costo_base, requiere_pieza_dental) VALUES
(1, 'Profilaxis Dental con Ultrasonido', 'PROC-PREV-01', 30, 250.00, FALSE),
(2, 'Restauración con Resina Compuesta Fotocurable', 'PROC-OPER-01', 45, 350.00, TRUE),
(3, 'Tratamiento de Conducto Molar (Biopulpectomía)', 'PROC-ENDO-01', 90, 1200.00, TRUE),
(4, 'Exodoncia Simple de Tercer Molar', 'PROC-CIRU-01', 60, 600.00, TRUE);

INSERT INTO catalogo_insumo_dental (nombre_insumo, unidad_medida, stock_actual, stock_minimo, precio_unitario_costo) VALUES
('Anestubo de Lidocaína 2% con Epinefrina', 'Carpule', 200, 30, 8.50),
('Tubo de Resina Compuesta Estética 3M A2', 'Jeringa 4g', 25, 5, 220.00),
('Dique de Goma para Aislamiento Absoluto', 'Caja 36 uds', 15, 3, 110.00);

INSERT INTO odontologo (numero_colegiado, nombres, apellidos, telefono, correo_electronico) VALUES
('COL-OD-501', 'Dra. Andrea Michelle', 'Vásquez Gómez', '5552-1100', 'avasquez@dental.url.gt');

INSERT INTO odontologo_especialidad (id_odontologo, id_especialidad, fecha_certificacion) VALUES
(1, 2, '2019-11-10');

INSERT INTO secretaria_recepcion (nombres, apellidos, usuario_sistema, telefono) VALUES
('Lucía Fernanda', 'López Barrios', 'lflopez', '5552-0000');

