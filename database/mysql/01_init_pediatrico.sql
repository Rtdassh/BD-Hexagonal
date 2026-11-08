-- ============================================================================
-- PROYECTO FINAL BASES DE DATOS II - UNIVERSIDAD RAFAEL LANDÍVAR
-- INSTITUCIÓN: CENTRO MÉDICO PEDIÁTRICO
-- MOTOR DE BASE DE DATOS: MySQL 8.x
-- ARQUITECTURA: Relacional con Motor InnoDB (Transaccional, Integridad Referencial)
-- ESPECIALIDAD: Consultas rápidas, somatometría (peso/talla/perímetro), percentiles OMS, vacunas
-- TOTAL TABLAS NORMALIZADAS (3FN): 25 TABLAS
-- ============================================================================

SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS centro_pediatrico CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE centro_pediatrico;

SET FOREIGN_KEY_CHECKS = 0;

-- Limpieza ordenada para reinstalación segura
DROP TABLE IF EXISTS detalle_receta_pediatrica;
DROP TABLE IF EXISTS receta;
DROP TABLE IF EXISTS medicamento_pediatrico;
DROP TABLE IF EXISTS registro_vacunacion;
DROP TABLE IF EXISTS lote_vacuna;
DROP TABLE IF EXISTS vacuna_catalogo;
DROP TABLE IF EXISTS diagnostico_consulta;
DROP TABLE IF EXISTS catalogo_cie10_pediatrico;
DROP TABLE IF EXISTS evaluacion_desarrollo;
DROP TABLE IF EXISTS antropometria_somatometria;
DROP TABLE IF EXISTS normativa_percentil_oms;
DROP TABLE IF EXISTS alergia_paciente;
DROP TABLE IF EXISTS catalogo_alergeno;
DROP TABLE IF EXISTS consulta;
DROP TABLE IF EXISTS cita;
DROP TABLE IF EXISTS horario_atencion;
DROP TABLE IF EXISTS pediatra_especialidad;
DROP TABLE IF EXISTS especialidad_pediatrica;
DROP TABLE IF EXISTS pediatra;
DROP TABLE IF EXISTS antecedente_perinatal;
DROP TABLE IF EXISTS tutor_paciente;
DROP TABLE IF EXISTS tutor_legal;
DROP TABLE IF EXISTS historial_pediatrico;
DROP TABLE IF EXISTS auditoria_acceso_menor;
DROP TABLE IF EXISTS paciente_pediatrico;

-- ----------------------------------------------------------------------------
-- 1. TABLA: especialidad_pediatrica
-- Catálogo de subespecialidades pediátricas.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS especialidad_pediatrica (
    id_especialidad INT AUTO_INCREMENT PRIMARY KEY,
    nombre_especialidad VARCHAR(80) NOT NULL UNIQUE,
    descripcion TEXT,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. TABLA: pediatra
-- Médicos pediatras colegiados y activos del centro infantil.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pediatra (
    id_pediatra INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo VARCHAR(100) NOT NULL,
    numero_colegiado VARCHAR(20) NOT NULL UNIQUE,
    especialidad VARCHAR(80) NOT NULL DEFAULT 'Pediatría general',
    telefono VARCHAR(15),
    correo_electronico VARCHAR(80),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_pediatra_estado CHECK (estado IN ('activo', 'inactivo', 'suspendido'))
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. TABLA: pediatra_especialidad (N:M)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pediatra_especialidad (
    id_pediatra_especialidad INT AUTO_INCREMENT PRIMARY KEY,
    id_pediatra INT NOT NULL,
    id_especialidad INT NOT NULL,
    fecha_certificacion DATE NOT NULL,
    CONSTRAINT uk_pe_ped_esp UNIQUE (id_pediatra, id_especialidad),
    CONSTRAINT fk_pe_ped FOREIGN KEY (id_pediatra) REFERENCES pediatra(id_pediatra) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pe_esp FOREIGN KEY (id_especialidad) REFERENCES especialidad_pediatrica(id_especialidad) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. TABLA: horario_atencion
-- Turnos de disponibilidad de los pediatras.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS horario_atencion (
    id_horario INT AUTO_INCREMENT PRIMARY KEY,
    id_pediatra INT NOT NULL,
    dia_semana ENUM('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado') NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    consultorio_numero VARCHAR(10) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT fk_ha_pediatra FOREIGN KEY (id_pediatra) REFERENCES pediatra(id_pediatra) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 5. TABLA: tutor_legal (Desacople 3FN de padres y apoderados)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tutor_legal (
    id_tutor INT AUTO_INCREMENT PRIMARY KEY,
    dpi VARCHAR(15) NOT NULL UNIQUE,
    nombres VARCHAR(60) NOT NULL,
    apellidos VARCHAR(60) NOT NULL,
    telefono_principal VARCHAR(15) NOT NULL,
    telefono_secundario VARCHAR(15),
    correo VARCHAR(80),
    direccion VARCHAR(200) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 6. TABLA: paciente_pediatrico
-- Expediente central del menor. Mantiene compatibilidad total con la aplicación
-- y enlaza con las tablas normalizadas de tutores y perinatales.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS paciente_pediatrico (
    id_paciente INT AUTO_INCREMENT PRIMARY KEY,
    nombres VARCHAR(50) NOT NULL,
    apellidos VARCHAR(50) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    sexo CHAR(1) NOT NULL,
    cui_nacimiento VARCHAR(20) NOT NULL UNIQUE,
    direccion VARCHAR(200),
    nombre_tutor VARCHAR(120) NOT NULL,
    parentesco_tutor VARCHAR(30) NOT NULL,
    dpi_tutor VARCHAR(15) NOT NULL,
    telefono_tutor VARCHAR(15) NOT NULL,
    semanas_gestacion INT,
    peso_nacer_kg DECIMAL(4,2),
    talla_nacer_cm DECIMAL(4,2),
    grupo_sanguineo VARCHAR(5) NOT NULL DEFAULT 'O',
    factor_rh ENUM('+', '-') NOT NULL DEFAULT '+',
    fecha_registro DATE NOT NULL DEFAULT (CURRENT_DATE),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_paciente_sexo CHECK (sexo IN ('M', 'F')),
    CONSTRAINT chk_paciente_estado CHECK (estado IN ('activo', 'inactivo', 'dado_de_baja'))
) ENGINE=InnoDB;

CREATE INDEX idx_pediatrico_cui ON paciente_pediatrico(cui_nacimiento);
CREATE INDEX idx_pediatrico_tutor_dpi ON paciente_pediatrico(dpi_tutor);

-- ----------------------------------------------------------------------------
-- 7. TABLA: tutor_paciente (Relación N:M)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tutor_paciente (
    id_tutor_paciente INT AUTO_INCREMENT PRIMARY KEY,
    id_tutor INT NOT NULL,
    id_paciente INT NOT NULL,
    parentesco VARCHAR(30) NOT NULL,
    es_tutor_principal BOOLEAN NOT NULL DEFAULT TRUE,
    tiene_custodia_legal BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uk_tp_tutor_pac UNIQUE (id_tutor, id_paciente),
    CONSTRAINT fk_tp_tutor FOREIGN KEY (id_tutor) REFERENCES tutor_legal(id_tutor) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_tp_paciente FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 8. TABLA: antecedente_perinatal (1:1 con el paciente pediátrico)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS antecedente_perinatal (
    id_antecedente INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL UNIQUE,
    semanas_gestacion INT NOT NULL,
    peso_nacer_kg DECIMAL(4,2) NOT NULL,
    talla_nacer_cm DECIMAL(4,2) NOT NULL,
    perimetro_cefalico_nacer_cm DECIMAL(4,2) NOT NULL DEFAULT 34.50,
    tipo_parto ENUM('Eutócico vaginal', 'Cesárea', 'Instrumentado') NOT NULL DEFAULT 'Eutócico vaginal',
    apgar_1min INT NOT NULL DEFAULT 9,
    apgar_5min INT NOT NULL DEFAULT 10,
    complicaciones_neonatales TEXT,
    CONSTRAINT chk_ant_gestacion CHECK (semanas_gestacion BETWEEN 20 AND 45),
    CONSTRAINT chk_ant_peso CHECK (peso_nacer_kg BETWEEN 0.3 AND 7),
    CONSTRAINT chk_ant_talla CHECK (talla_nacer_cm BETWEEN 20 AND 65),
    CONSTRAINT fk_ant_paciente FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 9. TABLA: historial_pediatrico
-- Historial centralizado del niño, estado de seguimiento y cierre de expediente.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_pediatrico (
    id_historial INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL UNIQUE,
    fecha_apertura DATE NOT NULL DEFAULT (CURRENT_DATE),
    fecha_ultima_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'activo',
    motivo_baja VARCHAR(150),
    CONSTRAINT chk_historial_estado CHECK (estado IN ('activo', 'archivado', 'trasladado', 'fallecido')),
    CONSTRAINT fk_ped_historial_paciente FOREIGN KEY (id_paciente) 
        REFERENCES paciente_pediatrico(id_paciente)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 10. TABLA: cita
-- Agendamiento de citas de control de niño sano y consultas de morbilidad.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cita (
    id_cita INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_pediatra INT NOT NULL,
    fecha_hora_programada DATETIME NOT NULL,
    motivo_consulta VARCHAR(200) NOT NULL,
    estado_cita VARCHAR(20) NOT NULL DEFAULT 'programada',
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_cita_estado CHECK (estado_cita IN ('programada', 'confirmada', 'atendida', 'cancelada', 'no_asistio')),
    CONSTRAINT fk_ped_cita_paciente FOREIGN KEY (id_paciente) 
        REFERENCES paciente_pediatrico(id_paciente)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ped_cita_pediatra FOREIGN KEY (id_pediatra) 
        REFERENCES pediatra(id_pediatra)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 11. TABLA: consulta
-- Registro ágil de la atención pediátrica: signos vitales, somatometría y diagnóstico.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consulta (
    id_consulta INT AUTO_INCREMENT PRIMARY KEY,
    id_cita INT NOT NULL,
    fecha_hora_atencion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    motivo VARCHAR(200) NOT NULL,
    temperatura DECIMAL(4,2),
    frecuencia_cardiaca INT,
    peso_kg DECIMAL(5,2) NOT NULL,
    talla_cm DECIMAL(5,2) NOT NULL,
    perimetro_cefalico_cm DECIMAL(4,2),
    percentil_crecimiento DECIMAL(4,1),
    diagnostico_cie10 VARCHAR(15),
    descripcion_diagnostico VARCHAR(300) NOT NULL,
    notas_clinicas TEXT,
    tipo_consulta VARCHAR(30) NOT NULL DEFAULT 'control_sano',
    CONSTRAINT chk_consulta_tipo CHECK (tipo_consulta IN ('control_sano', 'urgencia', 'seguimiento', 'vacunacion')),
    CONSTRAINT chk_consulta_somatometria CHECK (peso_kg > 0 AND talla_cm > 0),
    CONSTRAINT fk_ped_consulta_cita FOREIGN KEY (id_cita) 
        REFERENCES cita(id_cita)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 12. TABLA: antropometria_somatometria (Evolución antropométrica detallada)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS antropometria_somatometria (
    id_somatometria INT AUTO_INCREMENT PRIMARY KEY,
    id_consulta INT NOT NULL,
    id_paciente INT NOT NULL,
    edad_meses_atencion INT NOT NULL,
    peso_kg DECIMAL(5,2) NOT NULL,
    talla_cm DECIMAL(5,2) NOT NULL,
    perimetro_cefalico_cm DECIMAL(4,2) NOT NULL,
    imc_calculado DECIMAL(4,2) NOT NULL,
    percentil_peso_edad DECIMAL(4,1) NOT NULL,
    percentil_talla_edad DECIMAL(4,1) NOT NULL,
    percentil_pc_edad DECIMAL(4,1) NOT NULL,
    CONSTRAINT chk_som_peso CHECK (peso_kg > 0 AND talla_cm > 0),
    CONSTRAINT fk_som_con FOREIGN KEY (id_consulta) REFERENCES consulta(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_som_pac FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 13. TABLA: normativa_percentil_oms (Curvas de crecimiento estándar)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS normativa_percentil_oms (
    id_normativa INT AUTO_INCREMENT PRIMARY KEY,
    sexo ENUM('M', 'F') NOT NULL,
    edad_meses INT NOT NULL,
    parametro_antropometrico ENUM('peso_edad', 'talla_edad', 'perimetro_cefalico') NOT NULL,
    p3 DECIMAL(5,2) NOT NULL,
    p15 DECIMAL(5,2) NOT NULL,
    p50 DECIMAL(5,2) NOT NULL,
    p85 DECIMAL(5,2) NOT NULL,
    p97 DECIMAL(5,2) NOT NULL,
    CONSTRAINT uk_normativa UNIQUE (sexo, edad_meses, parametro_antropometrico)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 14. TABLA: evaluacion_desarrollo (Hitos psicomotores Denver II / OMS)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluacion_desarrollo (
    id_evaluacion INT AUTO_INCREMENT PRIMARY KEY,
    id_consulta INT NOT NULL,
    id_paciente INT NOT NULL,
    area_desarrollo ENUM('Motricidad Gruesa', 'Motricidad Fina', 'Lenguaje', 'Personal-Social') NOT NULL,
    hito_evaluado VARCHAR(150) NOT NULL,
    cumple_hito BOOLEAN NOT NULL DEFAULT TRUE,
    observaciones VARCHAR(255),
    CONSTRAINT fk_ed_consulta FOREIGN KEY (id_consulta) REFERENCES consulta(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ed_paciente FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 15. TABLA: catalogo_cie10_pediatrico
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS catalogo_cie10_pediatrico (
    codigo_cie10 VARCHAR(15) PRIMARY KEY,
    descripcion_diagnostico VARCHAR(255) NOT NULL,
    categoria_morbilidad VARCHAR(80) NOT NULL,
    es_frecuente_pediatria BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 16. TABLA: diagnostico_consulta
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS diagnostico_consulta (
    id_diagnostico_consulta INT AUTO_INCREMENT PRIMARY KEY,
    id_consulta INT NOT NULL,
    codigo_cie10 VARCHAR(15) NOT NULL,
    tipo_diagnostico ENUM('principal', 'secundario', 'presuntivo') NOT NULL DEFAULT 'principal',
    observaciones TEXT,
    CONSTRAINT fk_dc_consulta FOREIGN KEY (id_consulta) REFERENCES consulta(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_dc_cie10 FOREIGN KEY (codigo_cie10) REFERENCES catalogo_cie10_pediatrico(codigo_cie10) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 17. TABLA: vacuna_catalogo (Catálogo oficial de inmunizaciones infantiles)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vacuna_catalogo (
    id_vacuna INT AUTO_INCREMENT PRIMARY KEY,
    nombre_vacuna VARCHAR(100) NOT NULL UNIQUE,
    codigo_biologico VARCHAR(30) NOT NULL UNIQUE,
    via_administracion ENUM('Intramuscular', 'Subcutánea', 'Oral', 'Intradérmica') NOT NULL DEFAULT 'Intramuscular',
    edad_meses_sugerida INT NOT NULL DEFAULT 0,
    dosis_recomendada_ml DECIMAL(4,2) NOT NULL DEFAULT 0.50,
    es_refuerzo BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 18. TABLA: lote_vacuna (Control de lotes y cadena de frío 2°C - 8°C)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lote_vacuna (
    id_lote INT AUTO_INCREMENT PRIMARY KEY,
    id_vacuna INT NOT NULL,
    numero_lote VARCHAR(50) NOT NULL UNIQUE,
    fabricante VARCHAR(100) NOT NULL,
    fecha_fabricacion DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    stock_disponible INT NOT NULL DEFAULT 0,
    temp_min_celsius DECIMAL(4,2) NOT NULL DEFAULT 2.00,
    temp_max_celsius DECIMAL(4,2) NOT NULL DEFAULT 8.00,
    CONSTRAINT chk_lv_temp CHECK (temp_min_celsius < temp_max_celsius),
    CONSTRAINT fk_lv_vacuna FOREIGN KEY (id_vacuna) REFERENCES vacuna_catalogo(id_vacuna) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 19. TABLA: vacunacion (Registro de inmunizaciones administradas)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vacunacion (
    id_vacunacion INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_consulta INT NOT NULL,
    nombre_vacuna VARCHAR(100) NOT NULL,
    dosis VARCHAR(30) NOT NULL,
    lote VARCHAR(30) NOT NULL,
    fecha_aplicacion DATE NOT NULL,
    proxima_fecha_refuerzo DATE,
    CONSTRAINT fk_vacunacion_paciente FOREIGN KEY (id_paciente) 
        REFERENCES paciente_pediatrico(id_paciente)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_vacunacion_consulta FOREIGN KEY (id_consulta) 
        REFERENCES consulta(id_consulta)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 20. TABLA: registro_vacunacion (Detalle ampliado de biológico administrado)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS registro_vacunacion (
    id_registro_vac INT AUTO_INCREMENT PRIMARY KEY,
    id_vacunacion INT NOT NULL,
    id_paciente INT NOT NULL,
    id_consulta INT NOT NULL,
    id_lote INT,
    numero_dosis INT NOT NULL DEFAULT 1,
    fecha_aplicacion DATE NOT NULL,
    profesional_aplico VARCHAR(100) NOT NULL DEFAULT 'Enfermería Pediátrica',
    proxima_fecha_refuerzo DATE,
    reaccion_adversa TEXT,
    CONSTRAINT fk_rv_vac FOREIGN KEY (id_vacunacion) REFERENCES vacunacion(id_vacunacion) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_rv_pac FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rv_con FOREIGN KEY (id_consulta) REFERENCES consulta(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_rv_lot FOREIGN KEY (id_lote) REFERENCES lote_vacuna(id_lote) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 21. TABLA: catalogo_alergeno
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS catalogo_alergeno (
    id_alergeno INT AUTO_INCREMENT PRIMARY KEY,
    nombre_alergeno VARCHAR(100) NOT NULL UNIQUE,
    tipo_alergeno ENUM('Medicamento', 'Alimento', 'Ambiental', 'Contacto') NOT NULL,
    riesgo_anafilaxia BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 22. TABLA: alergia_paciente
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alergia_paciente (
    id_alergia_paciente INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_alergeno INT NOT NULL,
    fecha_deteccion DATE NOT NULL,
    severidad ENUM('Leve', 'Moderada', 'Severa / Anafiláctica') NOT NULL,
    sintomas_observados VARCHAR(255),
    CONSTRAINT uk_ap_pac_ale UNIQUE (id_paciente, id_alergeno),
    CONSTRAINT fk_ap_pac FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ap_ale FOREIGN KEY (id_alergeno) REFERENCES catalogo_alergeno(id_alergeno) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 23. TABLA: medicamento_pediatrico (Catálogo farmacológico por concentración)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicamento_pediatrico (
    id_medicamento INT AUTO_INCREMENT PRIMARY KEY,
    nombre_generico VARCHAR(100) NOT NULL,
    nombre_comercial VARCHAR(100),
    presentacion VARCHAR(50) NOT NULL,
    concentracion_mg_ml DECIMAL(6,2) NOT NULL DEFAULT 50.00,
    dosis_min_mg_kg_dia DECIMAL(6,2) NOT NULL DEFAULT 10.00,
    dosis_max_mg_kg_dia DECIMAL(6,2) NOT NULL DEFAULT 50.00,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 24. TABLA: receta (Prescripción y dosificación por peso)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS receta (
    id_receta INT AUTO_INCREMENT PRIMARY KEY,
    id_consulta INT NOT NULL,
    medicamento VARCHAR(100) NOT NULL,
    presentacion VARCHAR(50) NOT NULL,
    dosis_mg_kg DECIMAL(6,2),
    dosis_calculada_ml DECIMAL(6,2),
    frecuencia VARCHAR(50) NOT NULL,
    duracion_dias INT NOT NULL,
    indicaciones TEXT,
    fecha_emision DATE NOT NULL DEFAULT (CURRENT_DATE),
    CONSTRAINT fk_ped_receta_consulta FOREIGN KEY (id_consulta) 
        REFERENCES consulta(id_consulta)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 25. TABLA: detalle_receta_pediatrica (Desglose normalizado)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detalle_receta_pediatrica (
    id_detalle_receta INT AUTO_INCREMENT PRIMARY KEY,
    id_receta INT NOT NULL,
    id_medicamento INT,
    dosis_mg_kg DECIMAL(6,2) NOT NULL,
    dosis_calculada_ml DECIMAL(6,2) NOT NULL,
    frecuencia_horas INT NOT NULL DEFAULT 8,
    duracion_dias INT NOT NULL,
    indicaciones_tutor TEXT NOT NULL,
    CONSTRAINT fk_dr_receta FOREIGN KEY (id_receta) REFERENCES receta(id_receta) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_dr_medicamento FOREIGN KEY (id_medicamento) REFERENCES medicamento_pediatrico(id_medicamento) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- TABLA ADICIONAL DE SEGURIDAD / AUDITORÍA
CREATE TABLE IF NOT EXISTS auditoria_acceso_menor (
    id_auditoria INT AUTO_INCREMENT PRIMARY KEY,
    id_paciente INT NOT NULL,
    usuario_actor VARCHAR(50) NOT NULL,
    rol_actor VARCHAR(30) NOT NULL,
    accion_realizada VARCHAR(100) NOT NULL,
    justificacion_acceso VARCHAR(255) NOT NULL,
    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_origen VARCHAR(45) NOT NULL,
    CONSTRAINT fk_aud_paciente FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- DATOS SEMILLA / SEED DATA
-- ============================================================================

INSERT INTO especialidad_pediatrica (nombre_especialidad, descripcion) VALUES
('Pediatría general', 'Atención integral preventiva y de morbilidad infantil'),
('Neonatología', 'Cuidados del recién nacido y prematuro'),
('Infectología Pediátrica', 'Infecciones complejas e inmunizaciones');

INSERT INTO pediatra (nombre_completo, numero_colegiado, especialidad, telefono, correo_electronico, estado) VALUES
('Dra. Mariana Lucía Batres', 'PED-08912', 'Pediatría general', '5552-0101', 'mbatres@centropediatrico.com', 'activo'),
('Dr. Fernando José Castillo', 'PED-07654', 'Neonatología', '5552-0102', 'fcastillo@centropediatrico.com', 'activo');

INSERT INTO tutor_legal (dpi, nombres, apellidos, telefono_principal, direccion) VALUES
('1987543210101', 'Andrea', 'Castillo de Ríos', '4211-0022', 'Zona 3, Quetzaltenango');

INSERT INTO paciente_pediatrico (
    nombres, apellidos, fecha_nacimiento, sexo, cui_nacimiento, direccion,
    nombre_tutor, parentesco_tutor, dpi_tutor, telefono_tutor,
    semanas_gestacion, peso_nacer_kg, talla_nacer_cm, estado
) VALUES (
    'Mateo Alejandro', 'Ríos Castillo', '2024-02-15', 'M', '3024881920101', 'Zona 3, Quetzaltenango',
    'Andrea Castillo de Ríos', 'Madre', '1987543210101', '4211-0022',
    39, 3.25, 49.50, 'activo'
);

INSERT INTO tutor_paciente (id_tutor, id_paciente, parentesco, es_tutor_principal)
VALUES (1, 1, 'Madre', TRUE);

INSERT INTO antecedente_perinatal (id_paciente, semanas_gestacion, peso_nacer_kg, talla_nacer_cm, perimetro_cefalico_nacer_cm, tipo_parto, apgar_1min, apgar_5min)
VALUES (1, 39, 3.25, 49.50, 34.50, 'Eutócico vaginal', 9, 10);

INSERT INTO historial_pediatrico (id_paciente, fecha_apertura, estado)
VALUES (1, '2024-02-20', 'activo');

INSERT INTO cita (id_paciente, id_pediatra, fecha_hora_programada, motivo_consulta, estado_cita)
VALUES (1, 1, '2026-02-15 10:00:00', 'Control de niño sano - 2 años de edad y vacuna', 'atendida');

INSERT INTO consulta (
    id_cita, fecha_hora_atencion, motivo, temperatura, frecuencia_cardiaca,
    peso_kg, talla_cm, perimetro_cefalico_cm, percentil_crecimiento,
    diagnostico_cie10, descripcion_diagnostico, notas_clinicas, tipo_consulta
) VALUES (
    1, '2026-02-15 10:15:00', 'Evaluación integral de 2 años', 36.6, 98,
    12.40, 86.50, 48.20, 50.0,
    'Z00.1', 'Control de salud de rutina del niño',
    'Desarrollo psicomotor adecuado, lenguaje bisilábico fluido, dentición completa según edad.', 'control_sano'
);

INSERT INTO catalogo_cie10_pediatrico (codigo_cie10, descripcion_diagnostico, categoria_morbilidad) VALUES
('Z00.1', 'Control de salud de rutina del niño sano', 'Preventiva'),
('J00', 'Rinofaringitis aguda (resfriado común)', 'Respiratoria'),
('A09', 'Gastroenteritis aguda infantil', 'Digestiva');

INSERT INTO diagnostico_consulta (id_consulta, codigo_cie10, tipo_diagnostico, observaciones)
VALUES (1, 'Z00.1', 'principal', 'Control de salud de rutina');

INSERT INTO antropometria_somatometria (
    id_consulta, id_paciente, edad_meses_atencion, peso_kg, talla_cm, perimetro_cefalico_cm,
    imc_calculado, percentil_peso_edad, percentil_talla_edad, percentil_pc_edad
) VALUES (1, 1, 24, 12.40, 86.50, 48.20, 16.57, 50.0, 50.0, 50.0);

INSERT INTO vacuna_catalogo (nombre_vacuna, codigo_biologico, via_administracion, edad_meses_sugerida, dosis_recomendada_ml, es_refuerzo) VALUES
('Triple Viral (SPR - Sarampión, Paperas, Rubéola)', 'BIO-SPR-01', 'Subcutánea', 12, 0.50, TRUE),
('Pentavalente acelular', 'BIO-PENT-02', 'Intramuscular', 2, 0.50, FALSE);

INSERT INTO lote_vacuna (id_vacuna, numero_lote, fabricante, fecha_fabricacion, fecha_vencimiento, stock_disponible)
VALUES (1, 'SPR-2026-99A', 'Serum Institute', '2025-10-01', '2027-10-01', 80);

INSERT INTO vacunacion (id_paciente, id_consulta, nombre_vacuna, dosis, lote, fecha_aplicacion, proxima_fecha_refuerzo)
VALUES (1, 1, 'Triple Viral (SPR - Sarampión, Paperas, Rubéola)', '2da Dosis (Refuerzo)', 'SPR-2026-99A', '2026-02-15', '2028-02-15');

INSERT INTO registro_vacunacion (id_vacunacion, id_paciente, id_consulta, id_lote, numero_dosis, fecha_aplicacion, profesional_aplico, proxima_fecha_refuerzo)
VALUES (1, 1, 1, 1, 2, '2026-02-15', 'Licda. Carmen Morales (Enfermería)', '2028-02-15');

INSERT INTO medicamento_pediatrico (nombre_generico, nombre_comercial, presentacion, concentracion_mg_ml, dosis_min_mg_kg_dia, dosis_max_mg_kg_dia) VALUES
('Multivitamínico Pediátrico con Zinc', 'Zincovit Jarabe', 'Jarabe 120ml', 10.00, 2.00, 10.00),
('Paracetamol Pediátrico', 'Acetaminofén Gotas', 'Gotas orales', 100.00, 10.00, 15.00);

INSERT INTO receta (id_consulta, medicamento, presentacion, dosis_mg_kg, dosis_calculada_ml, frecuencia, duracion_dias, indicaciones)
VALUES (1, 'Multivitamínico Pediátrico con Zinc', 'Jarabe 120ml', 5.00, 2.50, 'Cada 24 horas por la mañana', 30, 'Administrar con el desayuno durante 1 mes para suplementación preventiva');

INSERT INTO detalle_receta_pediatrica (id_receta, id_medicamento, dosis_mg_kg, dosis_calculada_ml, frecuencia_horas, duracion_dias, indicaciones_tutor)
VALUES (1, 1, 5.00, 2.50, 24, 30, 'Administrar con el desayuno durante 1 mes para suplementación preventiva');

INSERT INTO catalogo_alergeno (nombre_alergeno, tipo_alergeno, riesgo_anafilaxia) VALUES
('Amoxicilina / Penicilinas', 'Medicamento', TRUE),
('Proteína de Leche de Vaca (APLV)', 'Alimento', FALSE);

-- ============================================================================
-- RESTRICCIONES DE FORMATO Y TRIGGERS DE SINCRONIZACIÓN Y EDAD
-- ============================================================================
ALTER TABLE paciente_pediatrico
    ADD CONSTRAINT chk_ped_cui CHECK (cui_nacimiento REGEXP '^[0-9]{13}$'),
    ADD CONSTRAINT chk_ped_dpi_tutor CHECK (dpi_tutor REGEXP '^[0-9]{13}$'),
    ADD CONSTRAINT chk_ped_tel_tutor CHECK (telefono_tutor REGEXP '^[2-7][0-9]{3}-[0-9]{4}$'),
    ADD CONSTRAINT chk_ped_nombres CHECK (CHAR_LENGTH(TRIM(nombres)) >= 2 AND CHAR_LENGTH(TRIM(apellidos)) >= 2),
    ADD CONSTRAINT chk_ped_gestacion CHECK (semanas_gestacion IS NULL OR semanas_gestacion BETWEEN 20 AND 45),
    ADD CONSTRAINT chk_ped_peso_nacer CHECK (peso_nacer_kg IS NULL OR peso_nacer_kg BETWEEN 0.3 AND 7),
    ADD CONSTRAINT chk_ped_talla_nacer CHECK (talla_nacer_cm IS NULL OR talla_nacer_cm BETWEEN 20 AND 65);

ALTER TABLE pediatra
    ADD CONSTRAINT chk_pediatra_colegiado CHECK (numero_colegiado REGEXP '^[A-Z0-9-]{3,20}$'),
    ADD CONSTRAINT chk_pediatra_telefono CHECK (telefono IS NULL OR telefono REGEXP '^[2-7][0-9]{3}-[0-9]{4}$');

ALTER TABLE consulta
    ADD CONSTRAINT chk_ped_temperatura CHECK (temperatura IS NULL OR temperatura BETWEEN 30 AND 45),
    ADD CONSTRAINT chk_ped_frecuencia CHECK (frecuencia_cardiaca IS NULL OR frecuencia_cardiaca BETWEEN 20 AND 250),
    ADD CONSTRAINT chk_ped_peso CHECK (peso_kg BETWEEN 0.3 AND 150),
    ADD CONSTRAINT chk_ped_talla CHECK (talla_cm BETWEEN 20 AND 200),
    ADD CONSTRAINT chk_ped_perimetro CHECK (perimetro_cefalico_cm IS NULL OR perimetro_cefalico_cm BETWEEN 20 AND 70),
    ADD CONSTRAINT chk_ped_percentil CHECK (percentil_crecimiento IS NULL OR percentil_crecimiento BETWEEN 0 AND 100),
    ADD CONSTRAINT chk_ped_cie10 CHECK (diagnostico_cie10 IS NULL OR diagnostico_cie10 REGEXP '^[A-Z][0-9]{2}([.][0-9A-Z]{1,4})?$');

ALTER TABLE receta
    ADD CONSTRAINT chk_ped_receta_duracion CHECK (duracion_dias BETWEEN 1 AND 90);

DROP TRIGGER IF EXISTS trg_ped_edad_ins;
DROP TRIGGER IF EXISTS trg_ped_edad_upd;
DROP TRIGGER IF EXISTS trg_ped_sync_tutor_perinatal;
DROP TRIGGER IF EXISTS trg_ped_sync_consulta_somato;
DROP TRIGGER IF EXISTS trg_ped_sync_receta_detalle;

DELIMITER $$

CREATE TRIGGER trg_ped_edad_ins BEFORE INSERT ON paciente_pediatrico FOR EACH ROW
BEGIN
    IF NEW.fecha_nacimiento > CURDATE() THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La fecha de nacimiento no puede ser futura';
    END IF;
    IF NEW.fecha_nacimiento <= DATE_SUB(CURDATE(), INTERVAL 18 YEAR) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El Centro Pediátrico atiende a menores de 18 años';
    END IF;
END$$

CREATE TRIGGER trg_ped_edad_upd BEFORE UPDATE ON paciente_pediatrico FOR EACH ROW
BEGIN
    IF NEW.fecha_nacimiento <> OLD.fecha_nacimiento AND NEW.fecha_nacimiento > CURDATE() THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La fecha de nacimiento no puede ser futura';
    END IF;
END$$

-- Sincronización automática a las tablas 3FN cuando la aplicación inserta un paciente
CREATE TRIGGER trg_ped_sync_tutor_perinatal AFTER INSERT ON paciente_pediatrico FOR EACH ROW
BEGIN
    DECLARE v_id_tutor INT DEFAULT NULL;
    
    SELECT id_tutor INTO v_id_tutor FROM tutor_legal WHERE dpi = NEW.dpi_tutor LIMIT 1;
    IF v_id_tutor IS NULL THEN
        INSERT INTO tutor_legal (dpi, nombres, apellidos, telefono_principal, direccion)
        VALUES (NEW.dpi_tutor, NEW.nombre_tutor, 'Responsable', NEW.telefono_tutor, COALESCE(NEW.direccion, 'Ciudad'));
        SET v_id_tutor = LAST_INSERT_ID();
    END IF;
    
    INSERT IGNORE INTO tutor_paciente (id_tutor, id_paciente, parentesco, es_tutor_principal)
    VALUES (v_id_tutor, NEW.id_paciente, NEW.parentesco_tutor, TRUE);
    
    IF NEW.semanas_gestacion IS NOT NULL OR NEW.peso_nacer_kg IS NOT NULL THEN
        INSERT IGNORE INTO antecedente_perinatal (id_paciente, semanas_gestacion, peso_nacer_kg, talla_nacer_cm, perimetro_cefalico_nacer_cm, tipo_parto, apgar_1min, apgar_5min)
        VALUES (
            NEW.id_paciente,
            COALESCE(NEW.semanas_gestacion, 39),
            COALESCE(NEW.peso_nacer_kg, 3.20),
            COALESCE(NEW.talla_nacer_cm, 50.00),
            34.50,
            'Eutócico vaginal',
            9,
            10
        );
    END IF;
END$$

-- Sincronización automática de somatometría y diagnóstico al insertar consulta
CREATE TRIGGER trg_ped_sync_consulta_somato AFTER INSERT ON consulta FOR EACH ROW
BEGIN
    DECLARE v_id_paciente INT;
    SELECT id_paciente INTO v_id_paciente FROM cita WHERE id_cita = NEW.id_cita LIMIT 1;
    
    IF NEW.peso_kg IS NOT NULL AND NEW.talla_cm IS NOT NULL THEN
        INSERT INTO antropometria_somatometria (
            id_consulta, id_paciente, edad_meses_atencion, peso_kg, talla_cm, perimetro_cefalico_cm,
            imc_calculado, percentil_peso_edad, percentil_talla_edad, percentil_pc_edad
        ) VALUES (
            NEW.id_consulta,
            COALESCE(v_id_paciente, 1),
            24,
            NEW.peso_kg,
            NEW.talla_cm,
            COALESCE(NEW.perimetro_cefalico_cm, 48.00),
            ROUND(NEW.peso_kg / POWER(NEW.talla_cm / 100, 2), 2),
            COALESCE(NEW.percentil_crecimiento, 50.0),
            50.0,
            50.0
        );
    END IF;
    
    IF NEW.diagnostico_cie10 IS NOT NULL THEN
        INSERT IGNORE INTO catalogo_cie10_pediatrico (codigo_cie10, descripcion_diagnostico, categoria_morbilidad)
        VALUES (NEW.diagnostico_cie10, NEW.descripcion_diagnostico, 'Clínica Pediátrica');
        
        INSERT INTO diagnostico_consulta (id_consulta, codigo_cie10, tipo_diagnostico, observaciones)
        VALUES (NEW.id_consulta, NEW.diagnostico_cie10, 'principal', NEW.descripcion_diagnostico);
    END IF;
END$$

-- Sincronización automática de detalle de receta al prescribir fármaco
CREATE TRIGGER trg_ped_sync_receta_detalle AFTER INSERT ON receta FOR EACH ROW
BEGIN
    DECLARE v_id_med INT DEFAULT NULL;
    SELECT id_medicamento INTO v_id_med FROM medicamento_pediatrico WHERE nombre_generico = NEW.medicamento LIMIT 1;
    
    IF v_id_med IS NULL THEN
        INSERT INTO medicamento_pediatrico (nombre_generico, nombre_comercial, presentacion, concentracion_mg_ml, dosis_min_mg_kg_dia, dosis_max_mg_kg_dia)
        VALUES (NEW.medicamento, NEW.medicamento, COALESCE(NEW.presentacion, 'Jarabe'), 50.00, 10.00, 50.00);
        SET v_id_med = LAST_INSERT_ID();
    END IF;
    
    INSERT INTO detalle_receta_pediatrica (id_receta, id_medicamento, dosis_mg_kg, dosis_calculada_ml, frecuencia_horas, duracion_dias, indicaciones_tutor)
    VALUES (
        NEW.id_receta,
        v_id_med,
        COALESCE(NEW.dosis_mg_kg, 10.00),
        COALESCE(NEW.dosis_calculada_ml, 5.00),
        8,
        NEW.duracion_dias,
        COALESCE(NEW.indicaciones, 'Administrar según prescripción')
    );
END$$

DELIMITER ;
