-- ============================================================================
-- HOSPITAL GENERAL - CIRUGÍAS Y ENFERMERÍA (PostgreSQL)
-- Se ejecuta después de 01_init_hospital.sql y antes de 03_seguridad_hospital.sql.
--
-- Reglas que garantiza la propia base de datos (no solo la aplicación):
--   * Un quirófano no puede tener dos cirugías activas que se traslapen en el tiempo.
--   * Un cirujano no puede estar en dos cirugías activas a la misma hora.
--     (restricciones EXCLUDE con rangos de tiempo: algo propio de PostgreSQL)
--   * Un enfermero cuida como máximo 6 pacientes por turno, y solo pacientes
--     que siguen ingresados (trigger).
-- ============================================================================

SET search_path TO hospital, public;

-- Necesaria para combinar "=" con "&&" (traslape de rangos) en una restricción EXCLUDE
CREATE EXTENSION IF NOT EXISTS btree_gist;

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
