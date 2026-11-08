-- ============================================================================
-- HOSPITAL GENERAL - CAJA: ARANCELES, FACTURAS Y PAGOS (PostgreSQL)
--
-- Se ejecuta después de 02_cirugias_enfermeria.sql y antes de 03_seguridad
-- (los permisos del rol app_hospital se dan a todas las tablas del esquema).
--
-- Reglas que garantiza la base de datos:
--   * El total de la factura es siempre la suma de su detalle (trigger).
--   * El subtotal de cada línea es una columna calculada (GENERATED).
--   * Un pago no puede ser mayor que el saldo ni ir a una factura anulada
--     (trigger con bloqueo FOR UPDATE: dos cajeros no pueden cobrar de más).
--   * El saldo y el estado (pendiente / parcial / pagada) se actualizan solos.
--   * Una factura con pagos no se anula.
-- ============================================================================
SET search_path TO hospital;

DROP TABLE IF EXISTS hospital.Pago CASCADE;
DROP TABLE IF EXISTS hospital.Detalle_Factura CASCADE;
DROP TABLE IF EXISTS hospital.Factura CASCADE;
DROP TABLE IF EXISTS hospital.Arancel CASCADE;

-- Precio de cada medicamento por unidad aplicada
ALTER TABLE hospital.Medicamento ADD COLUMN IF NOT EXISTS precio_unitario NUMERIC(10, 2) NOT NULL DEFAULT 20.00;
ALTER TABLE hospital.Medicamento ADD CONSTRAINT chk_medicamento_precio CHECK (precio_unitario >= 0);
UPDATE hospital.Medicamento SET precio_unitario = CASE nombre
    WHEN 'Amoxicilina + Ácido Clavulánico' THEN 12.50
    WHEN 'Omeprazol' THEN 8.00
    WHEN 'Enoxaparina Sódica' THEN 85.00
    WHEN 'Paracetamol IV' THEN 35.00
    ELSE precio_unitario END;

-- ----------------------------------------------------------------------------
-- Catálogo de precios
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Arancel (
    codigo VARCHAR(15) PRIMARY KEY,
    descripcion VARCHAR(120) NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    precio NUMERIC(10, 2) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_arancel_precio CHECK (precio >= 0 AND precio <= 100000),
    CONSTRAINT chk_arancel_codigo CHECK (codigo ~ '^[A-Z0-9-]{3,15}$'),
    CONSTRAINT chk_arancel_categoria CHECK (categoria IN ('consulta', 'hospitalizacion', 'cirugia', 'medicamento', 'procedimiento', 'otro'))
);

INSERT INTO hospital.Arancel (codigo, descripcion, categoria, precio) VALUES
('CONSULTA', 'Consulta médica general', 'consulta', 150.00),
('CONSULTA-ESP', 'Consulta de especialidad', 'consulta', 300.00),
('EMERGENCIA', 'Atención en emergencia', 'consulta', 450.00),
('CAMA-COMP', 'Día de estancia en habitación compartida', 'hospitalizacion', 350.00),
('CAMA-INDI', 'Día de estancia en habitación individual', 'hospitalizacion', 600.00),
('CAMA-AISL', 'Día de estancia en aislamiento', 'hospitalizacion', 500.00),
('CAMA-UCI', 'Día de estancia en cuidados intensivos', 'hospitalizacion', 1500.00),
('CX-QUIRO', 'Derecho de quirófano', 'cirugia', 1500.00),
('CX-HORA', 'Hora de cirugía (equipo quirúrgico)', 'cirugia', 1200.00),
('CURACION', 'Curación de herida', 'procedimiento', 120.00),
('RAYOS-X', 'Radiografía simple', 'procedimiento', 250.00);

-- ----------------------------------------------------------------------------
-- Factura, detalle y pagos
-- ----------------------------------------------------------------------------
CREATE TABLE hospital.Factura (
    id_factura SERIAL PRIMARY KEY,
    numero_factura VARCHAR(20) NOT NULL UNIQUE,
    id_paciente INT NOT NULL,
    nit VARCHAR(15) NOT NULL DEFAULT 'CF',
    nombre_facturacion VARCHAR(120) NOT NULL,
    fecha_emision TIMESTAMP NOT NULL DEFAULT LOCALTIMESTAMP,
    monto_total NUMERIC(12, 2) NOT NULL DEFAULT 0,
    monto_pagado NUMERIC(12, 2) NOT NULL DEFAULT 0,
    estado VARCHAR(15) NOT NULL DEFAULT 'pendiente',
    origen_tipo VARCHAR(20) NOT NULL DEFAULT 'manual',
    origen_id INT,
    motivo_anulacion VARCHAR(200),
    CONSTRAINT fk_factura_paciente FOREIGN KEY (id_paciente)
        REFERENCES hospital.Paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_factura_montos CHECK (monto_total >= 0 AND monto_pagado >= 0 AND monto_pagado <= monto_total),
    CONSTRAINT chk_factura_estado CHECK (estado IN ('pendiente', 'parcial', 'pagada', 'anulada')),
    CONSTRAINT chk_factura_nit CHECK (nit = 'CF' OR nit ~ '^[0-9]{1,12}-?[0-9K]$'),
    CONSTRAINT chk_factura_origen CHECK (origen_tipo IN ('manual', 'consulta', 'internamiento', 'cirugia'))
);
-- Un internamiento o una consulta se facturan una sola vez (salvo que la factura se anule)
CREATE UNIQUE INDEX uq_factura_origen ON hospital.Factura (origen_tipo, origen_id)
    WHERE origen_id IS NOT NULL AND estado <> 'anulada';

CREATE TABLE hospital.Detalle_Factura (
    id_detalle SERIAL PRIMARY KEY,
    id_factura INT NOT NULL,
    codigo_arancel VARCHAR(15),
    concepto VARCHAR(150) NOT NULL,
    cantidad NUMERIC(8, 2) NOT NULL,
    precio_unitario NUMERIC(10, 2) NOT NULL,
    subtotal NUMERIC(12, 2) GENERATED ALWAYS AS (round(cantidad * precio_unitario, 2)) STORED,
    CONSTRAINT fk_detalle_factura FOREIGN KEY (id_factura)
        REFERENCES hospital.Factura(id_factura) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_arancel FOREIGN KEY (codigo_arancel)
        REFERENCES hospital.Arancel(codigo) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_detalle_cantidad CHECK (cantidad > 0 AND cantidad <= 1000),
    CONSTRAINT chk_detalle_precio CHECK (precio_unitario >= 0)
);

CREATE TABLE hospital.Pago (
    id_pago SERIAL PRIMARY KEY,
    id_factura INT NOT NULL,
    numero_recibo VARCHAR(20) NOT NULL UNIQUE,
    fecha_pago TIMESTAMP NOT NULL DEFAULT LOCALTIMESTAMP,
    monto NUMERIC(12, 2) NOT NULL,
    metodo_pago VARCHAR(15) NOT NULL,
    referencia VARCHAR(40),
    recibido_por VARCHAR(100) NOT NULL,
    CONSTRAINT fk_pago_factura FOREIGN KEY (id_factura)
        REFERENCES hospital.Factura(id_factura) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_pago_monto CHECK (monto > 0),
    CONSTRAINT chk_pago_metodo CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'cheque')),
    CONSTRAINT chk_pago_referencia CHECK (metodo_pago = 'efectivo' OR referencia IS NOT NULL)
);
CREATE INDEX idx_factura_paciente ON hospital.Factura (id_paciente, fecha_emision DESC);
CREATE INDEX idx_pago_factura ON hospital.Pago (id_factura);

-- El total de la factura sigue a su detalle
CREATE OR REPLACE FUNCTION hospital.recalcular_total_factura() RETURNS TRIGGER AS $$
DECLARE
    v_id INT := COALESCE(NEW.id_factura, OLD.id_factura);
BEGIN
    UPDATE hospital.Factura
       SET monto_total = (SELECT COALESCE(SUM(subtotal), 0) FROM hospital.Detalle_Factura WHERE id_factura = v_id)
     WHERE id_factura = v_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_total_factura
    AFTER INSERT OR UPDATE OR DELETE ON hospital.Detalle_Factura
    FOR EACH ROW EXECUTE FUNCTION hospital.recalcular_total_factura();

-- Antes de un pago: la factura existe, no está anulada y el monto no supera el saldo
CREATE OR REPLACE FUNCTION hospital.validar_pago() RETURNS TRIGGER AS $$
DECLARE
    f hospital.Factura%ROWTYPE;
BEGIN
    SELECT * INTO f FROM hospital.Factura WHERE id_factura = NEW.id_factura FOR UPDATE;
    IF f.estado = 'anulada' THEN
        RAISE EXCEPTION 'La factura % está anulada', f.numero_factura USING ERRCODE = 'check_violation';
    END IF;
    IF f.estado = 'pagada' THEN
        RAISE EXCEPTION 'La factura % ya está pagada', f.numero_factura USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.monto > f.monto_total - f.monto_pagado THEN
        RAISE EXCEPTION 'El pago (Q%) supera el saldo de la factura (Q%)', NEW.monto, f.monto_total - f.monto_pagado
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_pago
    BEFORE INSERT ON hospital.Pago
    FOR EACH ROW EXECUTE FUNCTION hospital.validar_pago();

-- Después de un pago: suma lo pagado y cambia el estado
CREATE OR REPLACE FUNCTION hospital.aplicar_pago() RETURNS TRIGGER AS $$
BEGIN
    UPDATE hospital.Factura
       SET monto_pagado = monto_pagado + NEW.monto,
           estado = CASE WHEN monto_pagado + NEW.monto >= monto_total THEN 'pagada' ELSE 'parcial' END
     WHERE id_factura = NEW.id_factura;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_aplicar_pago
    AFTER INSERT ON hospital.Pago
    FOR EACH ROW EXECUTE FUNCTION hospital.aplicar_pago();

-- Una factura con pagos no se anula
CREATE OR REPLACE FUNCTION hospital.validar_anulacion() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.estado = 'anulada' AND OLD.estado <> 'anulada' AND OLD.monto_pagado > 0 THEN
        RAISE EXCEPTION 'La factura % tiene pagos por Q%; no se puede anular', OLD.numero_factura, OLD.monto_pagado
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_anulacion
    BEFORE UPDATE OF estado ON hospital.Factura
    FOR EACH ROW EXECUTE FUNCTION hospital.validar_anulacion();

-- ----------------------------------------------------------------------------
-- Cuenta de un internamiento: la calcula la base de datos con lo que realmente pasó
--   días de estancia x tarifa del tipo de habitación
--   + dosis aplicadas x precio del medicamento
--   + cirugías realizadas (derecho de quirófano + horas)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION hospital.cuenta_internamiento(p_id_hospitalizacion INT)
RETURNS TABLE (codigo_arancel VARCHAR, concepto VARCHAR, cantidad NUMERIC, precio_unitario NUMERIC) AS $$
    -- Estancia (mínimo un día)
    SELECT a.codigo, (a.descripcion || ' · ' || h.numero_habitacion)::VARCHAR,
           GREATEST(1, CEIL(EXTRACT(EPOCH FROM (COALESCE(h.fecha_egreso, LOCALTIMESTAMP) - h.fecha_ingreso)) / 86400))::NUMERIC,
           a.precio
      FROM hospital.Hospitalizacion h
      JOIN hospital.Habitacion hb ON hb.codigo = h.numero_habitacion
      JOIN hospital.Arancel a ON a.codigo = CASE hb.tipo WHEN 'individual' THEN 'CAMA-INDI' WHEN 'aislamiento' THEN 'CAMA-AISL'
                                                         WHEN 'intensivo' THEN 'CAMA-UCI' ELSE 'CAMA-COMP' END
     WHERE h.id_hospitalizacion = p_id_hospitalizacion
    UNION ALL
    -- Medicamentos efectivamente aplicados
    SELECT NULL::VARCHAR, (m.nombre || ' ' || o.dosis || ' (' || o.via_administracion || ')')::VARCHAR,
           COUNT(*)::NUMERIC, m.precio_unitario
      FROM hospital.Administracion_Medicamento ad
      JOIN hospital.Orden_Medicacion o ON o.id_orden = ad.id_orden
      JOIN hospital.Medicamento m ON m.id_medicamento = o.id_medicamento
     WHERE o.id_hospitalizacion = p_id_hospitalizacion AND ad.estado = 'aplicada'
     GROUP BY m.nombre, o.dosis, o.via_administracion, m.precio_unitario
    UNION ALL
    -- Cirugías realizadas durante el internamiento
    SELECT 'CX-QUIRO'::VARCHAR, ('Derecho de quirófano · ' || c.procedimiento)::VARCHAR, 1::NUMERIC,
           (SELECT precio FROM hospital.Arancel WHERE codigo = 'CX-QUIRO')
      FROM hospital.Cirugia c
     WHERE c.id_hospitalizacion = p_id_hospitalizacion AND c.estado = 'realizada'
    UNION ALL
    SELECT 'CX-HORA'::VARCHAR, ('Horas de cirugía · ' || c.procedimiento)::VARCHAR,
           GREATEST(1, CEIL(EXTRACT(EPOCH FROM (COALESCE(c.fecha_hora_fin, c.fecha_hora_inicio + c.duracion_estimada_min * INTERVAL '1 minute')
                                                 - c.fecha_hora_inicio)) / 3600))::NUMERIC,
           (SELECT precio FROM hospital.Arancel WHERE codigo = 'CX-HORA')
      FROM hospital.Cirugia c
     WHERE c.id_hospitalizacion = p_id_hospitalizacion AND c.estado = 'realizada' AND c.fecha_hora_inicio IS NOT NULL
$$ LANGUAGE sql STABLE;

-- ----------------------------------------------------------------------------
-- Datos de ejemplo: una consulta pagada y otra pendiente
-- ----------------------------------------------------------------------------
INSERT INTO hospital.Factura (numero_factura, id_paciente, nit, nombre_facturacion, fecha_emision, origen_tipo, origen_id)
SELECT 'HG-000001', p.id_paciente, 'CF', p.nombres || ' ' || p.apellidos, LOCALTIMESTAMP - INTERVAL '2 days', 'manual', NULL
  FROM hospital.Paciente p ORDER BY p.id_paciente LIMIT 1;
INSERT INTO hospital.Detalle_Factura (id_factura, codigo_arancel, concepto, cantidad, precio_unitario)
VALUES (1, 'CONSULTA-ESP', 'Consulta de especialidad', 1, 300.00), (1, 'RAYOS-X', 'Radiografía simple', 1, 250.00);
INSERT INTO hospital.Pago (id_factura, numero_recibo, fecha_pago, monto, metodo_pago, referencia, recibido_por)
VALUES (1, 'R-HG-000001', LOCALTIMESTAMP - INTERVAL '2 days', 300.00, 'efectivo', NULL, 'Caja central');
