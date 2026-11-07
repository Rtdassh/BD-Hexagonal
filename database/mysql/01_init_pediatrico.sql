-- ============================================================================
-- PROYECTO FINAL BASES DE DATOS II - UNIVERSIDAD RAFAEL LANDÍVAR
-- INSTITUCIÓN: CENTRO MÉDICO PEDIÁTRICO
-- MOTOR DE BASE DE DATOS: MySQL
-- ARQUITECTURA: Relacional con Motor InnoDB (Transaccional, Integridad Referencial)
-- ESPECIALIDAD: Consultas rápidas, somatometría (peso/talla/perímetro), percentiles OMS, vacunas
-- ============================================================================

SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS centro_pediatrico CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE centro_pediatrico;

-- Limpieza ordenada para reinstalación segura
DROP TABLE IF EXISTS receta;
DROP TABLE IF EXISTS vacunacion;
DROP TABLE IF EXISTS consulta;
DROP TABLE IF EXISTS cita;
DROP TABLE IF EXISTS historial_pediatrico;
DROP TABLE IF EXISTS pediatra;
DROP TABLE IF EXISTS paciente_pediatrico;

-- ----------------------------------------------------------------------------
-- 1. TABLA: paciente_pediatrico
-- Expediente del menor incluyendo datos del tutor responsable y antecedentes perinatales.
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
    fecha_registro DATE NOT NULL DEFAULT (CURRENT_DATE),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_paciente_sexo CHECK (sexo IN ('M', 'F')),
    CONSTRAINT chk_paciente_estado CHECK (estado IN ('activo', 'inactivo', 'dado_de_baja'))
) ENGINE=InnoDB;

CREATE INDEX idx_pediatrico_cui ON paciente_pediatrico(cui_nacimiento);
CREATE INDEX idx_pediatrico_tutor_dpi ON paciente_pediatrico(dpi_tutor);

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
    CONSTRAINT chk_pediatra_estado CHECK (estado IN ('activo', 'inactivo'))
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. TABLA: cita
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
    CONSTRAINT chk_cita_estado CHECK (estado_cita IN ('programada', 'atendida', 'cancelada', 'no_asistio')),
    CONSTRAINT fk_ped_cita_paciente FOREIGN KEY (id_paciente) 
        REFERENCES paciente_pediatrico(id_paciente)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ped_cita_pediatra FOREIGN KEY (id_pediatra) 
        REFERENCES pediatra(id_pediatra)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. TABLA: consulta
-- Registro ágil de la atención pediátrica: signos vitales, somatometría (peso/talla/perímetro cefálico), percentil OMS y diagnóstico CIE-10.
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
-- 5. TABLA: vacunacion
-- Registro de inmunizaciones administradas (carnet de vacunación y refuerzos).
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
-- 6. TABLA: receta
-- Prescripción farmacológica con cálculo dosimétrico según el peso del menor (mg/kg -> ml).
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
-- 7. TABLA: historial_pediatrico
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

-- ============================================================================
-- DATOS SEMILLA / SEED DATA PARA CENTRO MÉDICO PEDIÁTRICO
-- ============================================================================

INSERT INTO pediatra (nombre_completo, numero_colegiado, especialidad, telefono, correo_electronico, estado) VALUES
('Dra. Mariana Lucía Batres', 'PED-08912', 'Pediatría general', '5552-0101', 'mbatres@centropediatrico.com', 'activo'),
('Dr. Fernando José Castillo', 'PED-07654', 'Neonatología', '5552-0102', 'fcastillo@centropediatrico.com', 'activo');

-- Paciente infantil 1
INSERT INTO paciente_pediatrico (
    nombres, apellidos, fecha_nacimiento, sexo, cui_nacimiento, direccion,
    nombre_tutor, parentesco_tutor, dpi_tutor, telefono_tutor,
    semanas_gestacion, peso_nacer_kg, talla_nacer_cm, estado
) VALUES (
    'Mateo Alejandro', 'Ríos Castillo', '2024-02-15', 'M', '3024881920101', 'Zona 3, Quetzaltenango',
    'Andrea Castillo de Ríos', 'Madre', '1987543210101', '4211-0022',
    39, 3.25, 49.50, 'activo'
);

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

INSERT INTO vacunacion (id_paciente, id_consulta, nombre_vacuna, dosis, lote, fecha_aplicacion, proxima_fecha_refuerzo)
VALUES (1, 1, 'Triple Viral (SPR - Sarampión, Paperas, Rubéola)', '2da Dosis (Refuerzo)', 'SPR-2026-99A', '2026-02-15', '2028-02-15');

INSERT INTO receta (id_consulta, medicamento, presentacion, dosis_mg_kg, dosis_calculada_ml, frecuencia, duracion_dias, indicaciones)
VALUES (1, 'Multivitamínico Pediátrico con Zinc', 'Jarabe 120ml', 5.00, 2.50, 'Cada 24 horas por la mañana', 30, 'Administrar con el desayuno durante 1 mes para suplementación preventiva');

