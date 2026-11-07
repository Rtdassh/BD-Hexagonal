-- ============================================================================
-- HOSPITAL GENERAL - CIRUGÍAS, ENFERMERÍA, HABITACIONES Y MEDICACIÓN (PostgreSQL)
-- Se ejecuta después de 01_init_hospital.sql y antes de 03_seguridad_hospital.sql.
--
-- Reglas que garantiza la propia base de datos (no solo la aplicación):
--   * Un quirófano no puede tener dos cirugías activas que se traslapen en el tiempo.
--   * Un cirujano no puede estar en dos cirugías activas a la misma hora.
--     (restricciones EXCLUDE con rangos de tiempo: algo propio de PostgreSQL)
--   * Un enfermero cuida como máximo 6 pacientes por turno, y solo pacientes
--     que siguen ingresados (trigger).
--   * Una habitación no recibe más pacientes ingresados que camas tiene (trigger).
--   * Una dosis solo se aplica una vez, por un enfermero activo, a un paciente
--     ingresado y con la orden de medicación vigente (trigger + CHECK).
-- ============================================================================

SET search_path TO hospital, public;

-- Necesaria para combinar "=" con "&&" (traslape de rangos) en una restricción EXCLUDE
CREATE EXTENSION IF NOT EXISTS btree_gist;

DROP TABLE IF EXISTS hospital.Administracion_Medicamento CASCADE;
DROP TABLE IF EXISTS hospital.Orden_Medicacion CASCADE;
DROP TABLE IF EXISTS hospital.Habitacion CASCADE;
DROP TABLE IF EXISTS hospital.Departamento CASCADE;
DROP TABLE IF EXISTS hospital.Asignacion_Turno CASCADE;
DROP TABLE IF EXISTS hospital.Enfermero CASCADE;
DROP TABLE IF EXISTS hospital.Cirugia CASCADE;
DROP TABLE IF EXISTS hospital.Quirofano CASCADE;

-- ----------------------------------------------------------------------------
-- Quirófanos (catálogo)
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Quirofano (
    codigo VARCHAR(10) PRIMARY KEY,
    descripcion VARCHAR(100) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'disponible',
    CONSTRAINT chk_quirofano_estado CHECK (estado IN ('disponible', 'mantenimiento'))
);

-- ----------------------------------------------------------------------------
-- Cirugías
--   programada -> en_curso -> realizada
--   programada -> cancelada
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Cirugia (
    id_cirugia SERIAL PRIMARY KEY,
    id_paciente INT NOT NULL,
    id_medico INT NOT NULL,                       -- cirujano responsable
    id_hospitalizacion INT,                       -- internamiento al que pertenece (si aplica)
    procedimiento VARCHAR(200) NOT NULL,
    codigo_quirofano VARCHAR(10) NOT NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'electiva',
    fecha_hora_programada TIMESTAMP NOT NULL,
    duracion_estimada_min INT NOT NULL,
    fecha_hora_inicio TIMESTAMP,
    fecha_hora_fin TIMESTAMP,
    estado VARCHAR(20) NOT NULL DEFAULT 'programada',
    notas_operatorias TEXT,
    motivo_cancelacion VARCHAR(200),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cirugia_paciente FOREIGN KEY (id_paciente)
        REFERENCES hospital.Paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cirugia_medico FOREIGN KEY (id_medico)
        REFERENCES hospital.Medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cirugia_hospitalizacion FOREIGN KEY (id_hospitalizacion)
        REFERENCES hospital.Hospitalizacion(id_hospitalizacion) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cirugia_quirofano FOREIGN KEY (codigo_quirofano)
        REFERENCES hospital.Quirofano(codigo) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_cirugia_estado CHECK (estado IN ('programada', 'en_curso', 'realizada', 'cancelada')),
    CONSTRAINT chk_cirugia_tipo CHECK (tipo IN ('electiva', 'urgencia')),
    CONSTRAINT chk_cirugia_duracion CHECK (duracion_estimada_min BETWEEN 15 AND 720),
    CONSTRAINT chk_cirugia_tiempos CHECK (fecha_hora_fin IS NULL OR fecha_hora_inicio IS NULL OR fecha_hora_fin > fecha_hora_inicio),
    -- Mismo quirófano + horarios que se traslapan = rechazado (solo cirugías activas)
    CONSTRAINT excl_quirofano_ocupado EXCLUDE USING gist (
        codigo_quirofano WITH =,
        tsrange(fecha_hora_programada, fecha_hora_programada + duracion_estimada_min * INTERVAL '1 minute') WITH &&
    ) WHERE (estado IN ('programada', 'en_curso')),
    -- Mismo cirujano + horarios que se traslapan = rechazado
    CONSTRAINT excl_cirujano_ocupado EXCLUDE USING gist (
        id_medico WITH =,
        tsrange(fecha_hora_programada, fecha_hora_programada + duracion_estimada_min * INTERVAL '1 minute') WITH &&
    ) WHERE (estado IN ('programada', 'en_curso'))
);

CREATE INDEX idx_cirugia_fecha ON hospital.Cirugia(fecha_hora_programada);
CREATE INDEX idx_cirugia_paciente ON hospital.Cirugia(id_paciente);

-- ----------------------------------------------------------------------------
-- Enfermería
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Enfermero (
    id_enfermero SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    numero_colegiado VARCHAR(20) NOT NULL UNIQUE,
    area VARCHAR(60),
    telefono VARCHAR(15),
    correo_electronico VARCHAR(100),
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    CONSTRAINT chk_enfermero_estado CHECK (estado IN ('activo', 'inactivo'))
);

-- Turnos: mañana 07:00-15:00, tarde 15:00-23:00, noche 23:00-07:00 (del día siguiente)
CREATE TABLE hospital.Asignacion_Turno (
    id_asignacion SERIAL PRIMARY KEY,
    id_enfermero INT NOT NULL,
    id_hospitalizacion INT NOT NULL,
    fecha DATE NOT NULL,
    turno VARCHAR(10) NOT NULL,
    observaciones VARCHAR(200),
    estado VARCHAR(10) NOT NULL DEFAULT 'activa',   -- 'anulada' en lugar de borrar
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_turno_enfermero FOREIGN KEY (id_enfermero)
        REFERENCES hospital.Enfermero(id_enfermero) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_turno_hospitalizacion FOREIGN KEY (id_hospitalizacion)
        REFERENCES hospital.Hospitalizacion(id_hospitalizacion) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_turno CHECK (turno IN ('manana', 'tarde', 'noche')),
    CONSTRAINT chk_turno_estado CHECK (estado IN ('activa', 'anulada'))
);

-- El mismo enfermero no se asigna dos veces al mismo paciente en el mismo turno
CREATE UNIQUE INDEX uq_turno_activo ON hospital.Asignacion_Turno (id_enfermero, id_hospitalizacion, fecha, turno)
    WHERE estado = 'activa';
CREATE INDEX idx_turno_fecha ON hospital.Asignacion_Turno (fecha, turno);

-- Trigger: máximo 6 pacientes por enfermero por turno y solo pacientes ingresados
CREATE OR REPLACE FUNCTION hospital.validar_asignacion_turno() RETURNS TRIGGER AS $$
DECLARE
    v_estado_hosp VARCHAR(20);
    v_estado_enf VARCHAR(20);
    v_carga INT;
BEGIN
    IF NEW.estado <> 'activa' THEN
        RETURN NEW;
    END IF;

    SELECT estado INTO v_estado_hosp FROM hospital.Hospitalizacion WHERE id_hospitalizacion = NEW.id_hospitalizacion;
    IF v_estado_hosp IS DISTINCT FROM 'ingresado' THEN
        RAISE EXCEPTION 'Solo se asignan enfermeros a pacientes ingresados (la hospitalización está %)', v_estado_hosp
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT estado INTO v_estado_enf FROM hospital.Enfermero WHERE id_enfermero = NEW.id_enfermero;
    IF v_estado_enf IS DISTINCT FROM 'activo' THEN
        RAISE EXCEPTION 'El enfermero está inactivo' USING ERRCODE = 'check_violation';
    END IF;

    SELECT COUNT(*) INTO v_carga FROM hospital.Asignacion_Turno
     WHERE id_enfermero = NEW.id_enfermero AND fecha = NEW.fecha AND turno = NEW.turno
       AND estado = 'activa' AND id_asignacion IS DISTINCT FROM NEW.id_asignacion;
    IF v_carga >= 6 THEN
        RAISE EXCEPTION 'El enfermero ya tiene 6 pacientes en ese turno (máximo permitido)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_asignacion_turno
    BEFORE INSERT OR UPDATE ON hospital.Asignacion_Turno
    FOR EACH ROW EXECUTE FUNCTION hospital.validar_asignacion_turno();

-- ----------------------------------------------------------------------------
-- Datos semilla
-- ----------------------------------------------------------------------------
INSERT INTO hospital.Quirofano (codigo, descripcion) VALUES
('QX-1', 'Quirófano 1 - Cirugía general y laparoscopía'),
('QX-2', 'Quirófano 2 - Traumatología y ortopedia'),
('QX-3', 'Quirófano 3 - Urgencias');

INSERT INTO hospital.Enfermero (nombre, numero_colegiado, area, telefono, correo_electronico) VALUES
('Enf. María José Tzul', 'ENF-3301', 'Encamamiento de cirugía', '5551-0201', 'mtzul@hospitalgeneral.gob.gt'),
('Enf. Pedro Antonio Xicará', 'ENF-3415', 'Encamamiento de cirugía', '5551-0202', 'pxicara@hospitalgeneral.gob.gt'),
('Enf. Rosa Elena Batz', 'ENF-3522', 'Sala de operaciones', '5551-0203', 'rbatz@hospitalgeneral.gob.gt');

-- Cirugía programada para mañana del paciente hospitalizado (colecistectomía)
INSERT INTO hospital.Cirugia (id_paciente, id_medico, id_hospitalizacion, procedimiento, codigo_quirofano, tipo,
                              fecha_hora_programada, duracion_estimada_min, notas_operatorias)
VALUES (1, 2, 1, 'Colecistectomía laparoscópica', 'QX-1', 'electiva',
        (CURRENT_DATE + 1) + TIME '08:00', 90, 'Ayuno desde las 00:00. Profilaxis antibiótica 30 min antes.');

-- Enfermeros que cuidan hoy al paciente hospitalizado
INSERT INTO hospital.Asignacion_Turno (id_enfermero, id_hospitalizacion, fecha, turno, observaciones) VALUES
(1, 1, CURRENT_DATE, 'manana', 'Control de signos vitales cada 4 horas'),
(2, 1, CURRENT_DATE, 'tarde', 'Preparación prequirúrgica'),
(2, 1, CURRENT_DATE, 'noche', 'Vigilar ayuno');


-- ============================================================================
-- DEPARTAMENTOS Y HABITACIONES
-- ============================================================================
CREATE TABLE hospital.Departamento (
    id_departamento SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    piso SMALLINT NOT NULL,
    extension VARCHAR(10)
);

CREATE TABLE hospital.Habitacion (
    codigo VARCHAR(10) PRIMARY KEY,
    id_departamento INT NOT NULL,
    camas SMALLINT NOT NULL,
    tipo VARCHAR(20) NOT NULL DEFAULT 'compartida',
    estado VARCHAR(20) NOT NULL DEFAULT 'disponible',
    CONSTRAINT fk_habitacion_departamento FOREIGN KEY (id_departamento)
        REFERENCES hospital.Departamento(id_departamento) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_habitacion_camas CHECK (camas BETWEEN 1 AND 6),
    CONSTRAINT chk_habitacion_tipo CHECK (tipo IN ('individual', 'compartida', 'aislamiento', 'intensivo')),
    CONSTRAINT chk_habitacion_estado CHECK (estado IN ('disponible', 'mantenimiento'))
);

INSERT INTO hospital.Departamento (nombre, piso, extension) VALUES
('Medicina Interna', 1, '110'),
('Cardiología', 2, '210'),
('Traumatología', 2, '220'),
('Cirugía General', 3, '310'),
('Cuidados Intensivos', 4, '410');

INSERT INTO hospital.Habitacion (codigo, id_departamento, camas, tipo) VALUES
('MI-101', 1, 2, 'compartida'), ('MI-102', 1, 2, 'compartida'), ('MI-103', 1, 1, 'aislamiento'),
('CA-201', 2, 1, 'individual'), ('CA-202', 2, 2, 'compartida'),
('TR-205', 3, 2, 'compartida'), ('TR-206', 3, 2, 'compartida'),
('CG-301', 4, 2, 'compartida'), ('CG-302', 4, 2, 'compartida'), ('CG-304', 4, 1, 'individual'),
('UCI-01', 5, 1, 'intensivo'), ('UCI-02', 5, 1, 'intensivo');

-- Toda hospitalización ocupa una habitación existente
ALTER TABLE hospital.Hospitalizacion
    ADD CONSTRAINT fk_hospitalizacion_habitacion FOREIGN KEY (numero_habitacion)
        REFERENCES hospital.Habitacion(codigo) ON UPDATE CASCADE ON DELETE RESTRICT;

-- Trigger: no más pacientes ingresados que camas, ni habitaciones en mantenimiento
CREATE OR REPLACE FUNCTION hospital.validar_capacidad_habitacion() RETURNS TRIGGER AS $$
DECLARE
    v_camas SMALLINT;
    v_estado VARCHAR(20);
    v_ocupadas INT;
BEGIN
    IF NEW.estado <> 'ingresado' THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.numero_habitacion = NEW.numero_habitacion AND OLD.estado = 'ingresado' THEN
        RETURN NEW;   -- no cambió de habitación
    END IF;
    SELECT camas, estado INTO v_camas, v_estado FROM hospital.Habitacion WHERE codigo = NEW.numero_habitacion;
    IF v_estado = 'mantenimiento' THEN
        RAISE EXCEPTION 'La habitación % está en mantenimiento', NEW.numero_habitacion USING ERRCODE = 'check_violation';
    END IF;
    SELECT COUNT(*) INTO v_ocupadas FROM hospital.Hospitalizacion
     WHERE numero_habitacion = NEW.numero_habitacion AND estado = 'ingresado'
       AND id_hospitalizacion IS DISTINCT FROM NEW.id_hospitalizacion;
    IF v_ocupadas >= v_camas THEN
        RAISE EXCEPTION 'La habitación % está llena (% de % camas ocupadas)', NEW.numero_habitacion, v_ocupadas, v_camas
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_capacidad_habitacion
    BEFORE INSERT OR UPDATE OF numero_habitacion, estado ON hospital.Hospitalizacion
    FOR EACH ROW EXECUTE FUNCTION hospital.validar_capacidad_habitacion();

-- ============================================================================
-- MEDICACIÓN DEL INTERNAMIENTO (KÁRDEX)
--   Orden_Medicacion: lo que indica el médico (medicamento, dosis, vía, cada cuántas horas).
--   Administracion_Medicamento: cada dosis programada y quién la aplicó.
-- ============================================================================
CREATE TABLE hospital.Orden_Medicacion (
    id_orden SERIAL PRIMARY KEY,
    id_hospitalizacion INT NOT NULL,
    id_medicamento INT NOT NULL,
    id_medico INT NOT NULL,
    dosis VARCHAR(50) NOT NULL,
    via_administracion VARCHAR(30) NOT NULL DEFAULT 'Oral',
    frecuencia_horas SMALLINT NOT NULL,
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP NOT NULL,
    indicaciones VARCHAR(200),
    estado VARCHAR(15) NOT NULL DEFAULT 'activa',
    motivo_suspension VARCHAR(200),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orden_hospitalizacion FOREIGN KEY (id_hospitalizacion)
        REFERENCES hospital.Hospitalizacion(id_hospitalizacion) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_orden_medicamento FOREIGN KEY (id_medicamento)
        REFERENCES hospital.Medicamento(id_medicamento) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_orden_medico FOREIGN KEY (id_medico)
        REFERENCES hospital.Medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_orden_frecuencia CHECK (frecuencia_horas BETWEEN 1 AND 72),
    CONSTRAINT chk_orden_fechas CHECK (fecha_fin > fecha_inicio),
    CONSTRAINT chk_orden_estado CHECK (estado IN ('activa', 'suspendida', 'finalizada'))
);

CREATE TABLE hospital.Administracion_Medicamento (
    id_administracion SERIAL PRIMARY KEY,
    id_orden INT NOT NULL,
    fecha_hora_programada TIMESTAMP NOT NULL,
    estado VARCHAR(15) NOT NULL DEFAULT 'pendiente',
    id_enfermero INT,                       -- quién la aplicó (o quién la omitió)
    fecha_hora_aplicada TIMESTAMP,
    observaciones VARCHAR(200),
    CONSTRAINT fk_admin_orden FOREIGN KEY (id_orden)
        REFERENCES hospital.Orden_Medicacion(id_orden) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_admin_enfermero FOREIGN KEY (id_enfermero)
        REFERENCES hospital.Enfermero(id_enfermero) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_admin_dosis UNIQUE (id_orden, fecha_hora_programada),
    CONSTRAINT chk_admin_estado CHECK (estado IN ('pendiente', 'aplicada', 'omitida', 'cancelada')),
    CONSTRAINT chk_admin_aplicada CHECK (estado <> 'aplicada' OR (id_enfermero IS NOT NULL AND fecha_hora_aplicada IS NOT NULL)),
    CONSTRAINT chk_admin_omitida CHECK (estado <> 'omitida' OR observaciones IS NOT NULL)
);
CREATE INDEX idx_admin_programada ON hospital.Administracion_Medicamento (fecha_hora_programada);

-- Turno al que pertenece una hora (para saber qué enfermero es el encargado de la dosis)
CREATE OR REPLACE FUNCTION hospital.turno_de(ts TIMESTAMP) RETURNS VARCHAR AS $$
    SELECT CASE WHEN ts::time >= TIME '07:00' AND ts::time < TIME '15:00' THEN 'manana'
                WHEN ts::time >= TIME '15:00' AND ts::time < TIME '23:00' THEN 'tarde'
                ELSE 'noche' END
$$ LANGUAGE sql IMMUTABLE;

CREATE OR REPLACE FUNCTION hospital.fecha_turno(ts TIMESTAMP) RETURNS DATE AS $$
    SELECT CASE WHEN ts::time < TIME '07:00' THEN ts::date - 1 ELSE ts::date END
$$ LANGUAGE sql IMMUTABLE;

-- Trigger: una dosis se registra una sola vez, con orden vigente, paciente ingresado y enfermero activo
CREATE OR REPLACE FUNCTION hospital.validar_administracion() RETURNS TRIGGER AS $$
DECLARE
    v_orden VARCHAR(15);
    v_hosp VARCHAR(20);
    v_enf VARCHAR(20);
BEGIN
    IF NEW.estado NOT IN ('aplicada', 'omitida') THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.estado <> 'pendiente' THEN
        RAISE EXCEPTION 'Esta dosis ya fue registrada como %', OLD.estado USING ERRCODE = 'check_violation';
    END IF;
    SELECT o.estado, h.estado INTO v_orden, v_hosp
      FROM hospital.Orden_Medicacion o JOIN hospital.Hospitalizacion h ON h.id_hospitalizacion = o.id_hospitalizacion
     WHERE o.id_orden = NEW.id_orden;
    IF v_orden <> 'activa' THEN
        RAISE EXCEPTION 'La orden de medicación está %', v_orden USING ERRCODE = 'check_violation';
    END IF;
    IF v_hosp <> 'ingresado' THEN
        RAISE EXCEPTION 'El paciente ya no está ingresado' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.id_enfermero IS NOT NULL THEN
        SELECT estado INTO v_enf FROM hospital.Enfermero WHERE id_enfermero = NEW.id_enfermero;
        IF v_enf <> 'activo' THEN
            RAISE EXCEPTION 'El enfermero está inactivo' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_administracion
    BEFORE INSERT OR UPDATE ON hospital.Administracion_Medicamento
    FOR EACH ROW EXECUTE FUNCTION hospital.validar_administracion();

-- Medicación de ejemplo del paciente hospitalizado (desde hoy a las 06:00)
INSERT INTO hospital.Orden_Medicacion (id_hospitalizacion, id_medicamento, id_medico, dosis, via_administracion,
                                       frecuencia_horas, fecha_inicio, fecha_fin, indicaciones) VALUES
(1, 4, 2, '1 g', 'Intravenosa', 8, CURRENT_DATE + TIME '06:00', CURRENT_DATE + TIME '06:00' + INTERVAL '3 days',
 'Pasar en 15 minutos. Suspender si temperatura < 37.5 °C'),
(1, 3, 2, '40 mg', 'Subcutánea', 24, CURRENT_DATE + TIME '09:00', CURRENT_DATE + TIME '09:00' + INTERVAL '5 days',
 'Profilaxis tromboembólica');

-- Las dosis se generan con generate_series a partir de la frecuencia
INSERT INTO hospital.Administracion_Medicamento (id_orden, fecha_hora_programada)
SELECT o.id_orden, gs
  FROM hospital.Orden_Medicacion o,
       generate_series(o.fecha_inicio, o.fecha_fin - INTERVAL '1 second', o.frecuencia_horas * INTERVAL '1 hour') AS gs;

-- La primera dosis ya la aplicó el enfermero del turno de noche
UPDATE hospital.Administracion_Medicamento
   SET estado = 'aplicada', id_enfermero = 2, fecha_hora_aplicada = fecha_hora_programada + INTERVAL '5 minutes',
       observaciones = 'Sin reacciones'
 WHERE id_orden = 1 AND fecha_hora_programada = CURRENT_DATE + TIME '06:00';
