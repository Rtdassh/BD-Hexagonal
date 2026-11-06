-- ============================================================================
-- PROYECTO FINAL BASES DE DATOS II - UNIVERSIDAD RAFAEL LANDÍVAR
-- INSTITUCIÓN: HOSPITAL GENERAL
-- MOTOR DE BASE DE DATOS: PostgreSQL
-- ARQUITECTURA: Relacional Normalizada (3FN) con Integridad Transaccional Fuerte (ACID)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS hospital;
SET search_path TO hospital, public;

-- ----------------------------------------------------------------------------
-- 1. TABLA: hospital.Paciente
-- Almacena los datos personales y de contacto de los pacientes del hospital.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS hospital.Hospitalizacion CASCADE;
DROP TABLE IF EXISTS hospital.Receta CASCADE;
DROP TABLE IF EXISTS hospital.Medicamento CASCADE;
DROP TABLE IF EXISTS hospital.Tratamiento CASCADE;
DROP TABLE IF EXISTS hospital.Diagnostico CASCADE;
DROP TABLE IF EXISTS hospital.Consulta CASCADE;
DROP TABLE IF EXISTS hospital.Cita CASCADE;
DROP TABLE IF EXISTS hospital.Historial_Clinico CASCADE;
DROP TABLE IF EXISTS hospital.Medico_Especialidad CASCADE;
DROP TABLE IF EXISTS hospital.Medico CASCADE;
DROP TABLE IF EXISTS hospital.Especialidad CASCADE;
DROP TABLE IF EXISTS hospital.Paciente CASCADE;

CREATE TABLE hospital.Paciente (
    id_paciente SERIAL PRIMARY KEY,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    sexo CHAR(1) NOT NULL,
    dpi VARCHAR(20) NOT NULL UNIQUE,
    direccion VARCHAR(200),
    telefono VARCHAR(15),
    correo_electronico VARCHAR(100),
    tipo_sangre VARCHAR(5),
    contacto_emergencia_nombre VARCHAR(150),
    contacto_emergencia_telefono VARCHAR(15),
    fecha_registro DATE NOT NULL DEFAULT CURRENT_DATE,
    estado_salud VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_paciente_sexo CHECK (sexo IN ('M', 'F')),
    CONSTRAINT chk_paciente_estado CHECK (estado_salud IN ('activo', 'dado_de_baja', 'critico', 'estable', 'hospitalizado'))
);

CREATE INDEX idx_hospital_paciente_dpi ON hospital.Paciente(dpi);
CREATE INDEX idx_hospital_paciente_apellidos ON hospital.Paciente(apellidos);

-- ----------------------------------------------------------------------------
-- 2. TABLA: hospital.Especialidad
-- Catálogo de especialidades médicas disponibles en el Hospital General.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Especialidad (
    id_especialidad SERIAL PRIMARY KEY,
    nombre_especialidad VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

-- ----------------------------------------------------------------------------
-- 3. TABLA: hospital.Medico
-- Personal médico colegiado del hospital.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Medico (
    id_medico SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    numero_colegiado VARCHAR(20) NOT NULL UNIQUE,
    telefono VARCHAR(15),
    correo_electronico VARCHAR(100),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_medico_estado CHECK (estado IN ('activo', 'inactivo'))
);

-- ----------------------------------------------------------------------------
-- 4. TABLA: hospital.Medico_Especialidad
-- Relación muchos a muchos entre Médicos y sus Especialidades.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Medico_Especialidad (
    id_medico INT NOT NULL,
    id_especialidad INT NOT NULL,
    PRIMARY KEY (id_medico, id_especialidad),
    CONSTRAINT fk_me_medico FOREIGN KEY (id_medico) 
        REFERENCES hospital.Medico(id_medico) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_me_especialidad FOREIGN KEY (id_especialidad) 
        REFERENCES hospital.Especialidad(id_especialidad) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 5. TABLA: hospital.Historial_Clinico
-- Expediente central del paciente con trazabilidad de estado y motivo de baja.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Historial_Clinico (
    id_historial SERIAL PRIMARY KEY,
    id_paciente INT NOT NULL UNIQUE,
    fecha_apertura DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_ultima_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    motivo_baja VARCHAR(150),
    CONSTRAINT chk_historial_estado CHECK (estado IN ('activo', 'archivado', 'trasladado', 'fallecido')),
    CONSTRAINT fk_historial_paciente FOREIGN KEY (id_paciente) 
        REFERENCES hospital.Paciente(id_paciente) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 6. TABLA: hospital.Cita
-- Agendamiento de citas médicas hospitalarias.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Cita (
    id_cita SERIAL PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_medico INT NOT NULL,
    fecha_hora_programada TIMESTAMP NOT NULL,
    motivo_consulta VARCHAR(200) NOT NULL,
    estado_cita VARCHAR(20) NOT NULL DEFAULT 'programada',
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_cita_estado CHECK (estado_cita IN ('programada', 'atendida', 'cancelada', 'no_asistio')),
    CONSTRAINT fk_cita_paciente FOREIGN KEY (id_paciente) 
        REFERENCES hospital.Paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cita_medico FOREIGN KEY (id_medico) 
        REFERENCES hospital.Medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 7. TABLA: hospital.Consulta
-- Registro de atención clínica real, signos vitales y notas del médico.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Consulta (
    id_consulta SERIAL PRIMARY KEY,
    id_cita INT NOT NULL,
    fecha_hora_atencion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    motivo VARCHAR(200) NOT NULL,
    presion_arterial VARCHAR(10),
    temperatura DECIMAL(4,2),
    pulso INT,
    notas_clinicas TEXT,
    tipo_consulta VARCHAR(20) NOT NULL DEFAULT 'ordinaria',
    CONSTRAINT chk_consulta_tipo CHECK (tipo_consulta IN ('ordinaria', 'emergencia', 'seguimiento')),
    CONSTRAINT fk_consulta_cita FOREIGN KEY (id_cita) 
        REFERENCES hospital.Cita(id_cita) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 8. TABLA: hospital.Diagnostico
-- Diagnósticos clínicos fundamentados en CIE-10 (integridad transaccional con la consulta).
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Diagnostico (
    id_diagnostico SERIAL PRIMARY KEY,
    id_consulta INT NOT NULL,
    codigo_cie10 VARCHAR(10) NOT NULL,
    descripcion VARCHAR(300) NOT NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'principal',
    fecha_diagnostico DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT chk_diagnostico_tipo CHECK (tipo IN ('principal', 'secundario')),
    CONSTRAINT fk_diagnostico_consulta FOREIGN KEY (id_consulta) 
        REFERENCES hospital.Consulta(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 9. TABLA: hospital.Tratamiento
-- Tratamientos médicos indicados en respuesta a diagnósticos.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Tratamiento (
    id_tratamiento SERIAL PRIMARY KEY,
    id_diagnostico INT NOT NULL,
    descripcion VARCHAR(300) NOT NULL,
    fecha_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_fin DATE,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    indicaciones TEXT,
    CONSTRAINT chk_tratamiento_estado CHECK (estado IN ('activo', 'finalizado', 'suspendido')),
    CONSTRAINT fk_tratamiento_diagnostico FOREIGN KEY (id_diagnostico) 
        REFERENCES hospital.Diagnostico(id_diagnostico) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 10. TABLA: hospital.Medicamento
-- Catálogo de medicamentos farmacéuticos del hospital.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Medicamento (
    id_medicamento SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    presentacion VARCHAR(50) NOT NULL,
    unidad_medida VARCHAR(20) NOT NULL
);

-- ----------------------------------------------------------------------------
-- 11. TABLA: hospital.Receta
-- Prescripción farmacológica ligada a un tratamiento médico activo.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Receta (
    id_receta SERIAL PRIMARY KEY,
    id_tratamiento INT NOT NULL,
    id_medicamento INT NOT NULL,
    dosis VARCHAR(50) NOT NULL,
    frecuencia VARCHAR(50) NOT NULL,
    duracion_dias INT NOT NULL,
    via_administracion VARCHAR(30) NOT NULL,
    fecha_emision DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT fk_receta_tratamiento FOREIGN KEY (id_tratamiento) 
        REFERENCES hospital.Tratamiento(id_tratamiento) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_receta_medicamento FOREIGN KEY (id_medicamento) 
        REFERENCES hospital.Medicamento(id_medicamento) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 12. TABLA: hospital.Hospitalizacion
-- Gestión estricta de ingresos a encamamiento hospitalario, camas/habitaciones y egresos.
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Hospitalizacion (
    id_hospitalizacion SERIAL PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_consulta INT NOT NULL,
    fecha_ingreso TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_egreso TIMESTAMP,
    numero_habitacion VARCHAR(10) NOT NULL,
    motivo_ingreso VARCHAR(200) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ingresado',
    CONSTRAINT chk_hosp_estado CHECK (estado IN ('ingresado', 'alta', 'referido')),
    CONSTRAINT fk_hospitalizacion_paciente FOREIGN KEY (id_paciente) 
        REFERENCES hospital.Paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_hospitalizacion_consulta FOREIGN KEY (id_consulta) 
        REFERENCES hospital.Consulta(id_consulta) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ============================================================================
-- DATOS SEMILLA / SEED DATA PARA HOSPITAL GENERAL
-- ============================================================================

INSERT INTO hospital.Especialidad (nombre_especialidad, descripcion) VALUES
('Medicina Interna', 'Atención integral del adulto, diagnóstico de enfermedades sistémicas'),
('Cirugía General', 'Intervenciones quirúrgicas del aparato digestivo y traumatismos'),
('Cardiología', 'Enfermedades cardiovasculares, infartos e hipertensión compleja'),
('Traumatología', 'Lesiones óseas, fracturas y afecciones del aparato locomotor');

INSERT INTO hospital.Medico (nombre, numero_colegiado, telefono, correo_electronico, estado) VALUES
('Dr. Carlos Roberto Mendoza', 'COL-12450', '5551-0101', 'cmendoza@hospitalgeneral.gob.gt', 'activo'),
('Dra. Laura Sofia Estrada', 'COL-14820', '5551-0102', 'lestrada@hospitalgeneral.gob.gt', 'activo'),
('Dr. Jorge Mario Alvarado', 'COL-09871', '5551-0103', 'jalvarado@hospitalgeneral.gob.gt', 'activo');

INSERT INTO hospital.Medico_Especialidad (id_medico, id_especialidad) VALUES
(1, 1),
(2, 2),
(3, 3);

INSERT INTO hospital.Medicamento (nombre, presentacion, unidad_medida) VALUES
('Amoxicilina + Ácido Clavulánico', 'Tabletas 875/125mg', 'Tableta'),
('Omeprazol', 'Cápsulas 20mg', 'Cápsula'),
('Enoxaparina Sódica', 'Jeringa prellenada 40mg/0.4ml', 'Jeringa'),
('Paracetamol IV', 'Frasco solución 1g/100ml', 'Frasco');

-- Paciente 1: Hospitalizado por Colecistitis Aguda
INSERT INTO hospital.Paciente (nombres, apellidos, fecha_nacimiento, sexo, dpi, direccion, telefono, correo_electronico, tipo_sangre, contacto_emergencia_nombre, contacto_emergencia_telefono, estado_salud)
VALUES ('Manuel Antonio', 'Pérez Morales', '1982-05-14', 'M', '2456789010101', 'Zona 1, Quetzaltenango', '4123-8899', 'mperez@gmail.com', 'O+', 'Ana Gómez de Pérez', '4988-7711', 'hospitalizado');

INSERT INTO hospital.Historial_Clinico (id_paciente, fecha_apertura, estado)
VALUES (1, '2026-01-10', 'activo');

INSERT INTO hospital.Cita (id_paciente, id_medico, fecha_hora_programada, motivo_consulta, estado_cita)
VALUES (1, 2, '2026-03-01 08:30:00', 'Dolor abdominal agudo e ictericia', 'atendida');

INSERT INTO hospital.Consulta (id_cita, fecha_hora_atencion, motivo, presion_arterial, temperatura, pulso, notas_clinicas, tipo_consulta)
VALUES (1, '2026-03-01 08:45:00', 'Dolor intenso en hipocondrio derecho Murphy positivo', '135/85', 38.4, 92, 'Paciente requiere manejo quirúrgico e internamiento inmediato', 'emergencia');

INSERT INTO hospital.Diagnostico (id_consulta, codigo_cie10, descripcion, tipo)
VALUES (1, 'K80.0', 'Cálculo de la vesícula biliar con colecistitis aguda', 'principal');

INSERT INTO hospital.Tratamiento (id_diagnostico, descripcion, fecha_inicio, estado, indicaciones)
VALUES (1, 'Antibioticoterapia prequirúrgica y laparoscopía', '2026-03-01', 'activo', 'Nada por vía oral, canalizar vía periférica y control hemodinámico horario');

INSERT INTO hospital.Receta (id_tratamiento, id_medicamento, dosis, frecuencia, duracion_dias, via_administracion)
VALUES (1, 1, '1 tableta', 'Cada 8 horas', 7, 'Oral');

INSERT INTO hospital.Hospitalizacion (id_paciente, id_consulta, fecha_ingreso, numero_habitacion, motivo_ingreso, estado)
VALUES (1, 1, '2026-03-01 09:30:00', 'HAB-304', 'Monitoreo pre y post operatorio de colecistectomía', 'ingresado');

