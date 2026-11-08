-- ============================================================================
-- CENTRO MÉDICO PEDIÁTRICO - CAJA: ARANCELES, FACTURAS Y PAGOS (MySQL 8)
--
-- Mismas reglas que el hospital, escritas a la manera de MySQL:
--   * subtotal como columna generada (STORED)
--   * CHECK para montos, métodos de pago y NIT
--   * triggers con SIGNAL para no cobrar de más, no pagar facturas anuladas
--     y no anular facturas con pagos
-- El usuario app_pediatrico ya tiene permisos sobre centro_pediatrico.* (02_seguridad).
-- ============================================================================
SET NAMES utf8mb4;
USE centro_pediatrico;

DROP TABLE IF EXISTS pago;
DROP TABLE IF EXISTS detalle_factura;
DROP TABLE IF EXISTS factura;
DROP TABLE IF EXISTS arancel;

CREATE TABLE arancel (
    codigo VARCHAR(15) PRIMARY KEY,
    descripcion VARCHAR(120) NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_arancel_precio CHECK (precio >= 0 AND precio <= 100000),
    CONSTRAINT chk_arancel_codigo CHECK (codigo REGEXP '^[A-Z0-9-]{3,15}$'),
    CONSTRAINT chk_arancel_categoria CHECK (categoria IN ('consulta', 'vacunacion', 'procedimiento', 'medicamento', 'otro'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO arancel (codigo, descripcion, categoria, precio) VALUES
('CONSULTA', 'Consulta pediátrica', 'consulta', 175.00),
('CONTROL-NS', 'Control de niño sano', 'consulta', 125.00),
('EMERGENCIA', 'Atención pediátrica de emergencia', 'consulta', 350.00),
('VACUNA-APL', 'Aplicación de vacuna', 'vacunacion', 40.00),
('NEBULIZA', 'Nebulización', 'procedimiento', 60.00),
('CURACION', 'Curación', 'procedimiento', 80.00),
('TAMIZAJE', 'Tamizaje neonatal', 'procedimiento', 220.00);

CREATE TABLE factura (
    id_factura INT AUTO_INCREMENT PRIMARY KEY,
    numero_factura VARCHAR(20) NOT NULL UNIQUE,
    id_paciente INT NOT NULL,
    nit VARCHAR(15) NOT NULL DEFAULT 'CF',
    nombre_facturacion VARCHAR(120) NOT NULL,
    fecha_emision DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    monto_total DECIMAL(12, 2) NOT NULL DEFAULT 0,
    monto_pagado DECIMAL(12, 2) NOT NULL DEFAULT 0,
    estado VARCHAR(15) NOT NULL DEFAULT 'pendiente',
    origen_tipo VARCHAR(20) NOT NULL DEFAULT 'manual',
    origen_id INT NULL,
    motivo_anulacion VARCHAR(200) NULL,
    CONSTRAINT fk_factura_paciente FOREIGN KEY (id_paciente) REFERENCES paciente_pediatrico(id_paciente)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_factura_montos CHECK (monto_total >= 0 AND monto_pagado >= 0 AND monto_pagado <= monto_total),
    CONSTRAINT chk_factura_estado CHECK (estado IN ('pendiente', 'parcial', 'pagada', 'anulada')),
    CONSTRAINT chk_factura_nit CHECK (nit = 'CF' OR nit REGEXP '^[0-9]{1,12}-?[0-9K]$'),
    CONSTRAINT chk_factura_origen CHECK (origen_tipo IN ('manual', 'consulta')),
    INDEX idx_factura_paciente (id_paciente, fecha_emision)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE detalle_factura (
    id_detalle INT AUTO_INCREMENT PRIMARY KEY,
    id_factura INT NOT NULL,
    codigo_arancel VARCHAR(15) NULL,
    concepto VARCHAR(150) NOT NULL,
    cantidad DECIMAL(8, 2) NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(12, 2) GENERATED ALWAYS AS (ROUND(cantidad * precio_unitario, 2)) STORED,
    CONSTRAINT fk_detalle_factura FOREIGN KEY (id_factura) REFERENCES factura(id_factura)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_arancel FOREIGN KEY (codigo_arancel) REFERENCES arancel(codigo)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_detalle_cantidad CHECK (cantidad > 0 AND cantidad <= 1000),
    CONSTRAINT chk_detalle_precio CHECK (precio_unitario >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE pago (
    id_pago INT AUTO_INCREMENT PRIMARY KEY,
    id_factura INT NOT NULL,
    numero_recibo VARCHAR(20) NOT NULL UNIQUE,
    fecha_pago DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    monto DECIMAL(12, 2) NOT NULL,
    metodo_pago VARCHAR(15) NOT NULL,
    referencia VARCHAR(40) NULL,
    recibido_por VARCHAR(100) NOT NULL,
    CONSTRAINT fk_pago_factura FOREIGN KEY (id_factura) REFERENCES factura(id_factura)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_pago_monto CHECK (monto > 0),
    CONSTRAINT chk_pago_metodo CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'cheque')),
    CONSTRAINT chk_pago_referencia CHECK (metodo_pago = 'efectivo' OR referencia IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER $$
-- El total de la factura sigue a su detalle
CREATE TRIGGER trg_detalle_ins AFTER INSERT ON detalle_factura FOR EACH ROW
BEGIN
    UPDATE factura SET monto_total = (SELECT COALESCE(SUM(subtotal), 0) FROM detalle_factura WHERE id_factura = NEW.id_factura)
     WHERE id_factura = NEW.id_factura;
END$$

-- Antes de un pago: factura vigente y monto dentro del saldo (con bloqueo de la fila)
CREATE TRIGGER trg_pago_validar BEFORE INSERT ON pago FOR EACH ROW
BEGIN
    DECLARE v_estado VARCHAR(15);
    DECLARE v_saldo DECIMAL(12, 2);
    SELECT estado, monto_total - monto_pagado INTO v_estado, v_saldo
      FROM factura WHERE id_factura = NEW.id_factura FOR UPDATE;
    IF v_estado = 'anulada' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La factura está anulada';
    END IF;
    IF v_estado = 'pagada' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La factura ya está pagada';
    END IF;
    IF NEW.monto > v_saldo THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El pago supera el saldo de la factura';
    END IF;
END$$

-- Después de un pago: suma lo pagado y cambia el estado
CREATE TRIGGER trg_pago_aplicar AFTER INSERT ON pago FOR EACH ROW
BEGIN
    UPDATE factura
       SET estado = IF(monto_pagado + NEW.monto >= monto_total, 'pagada', 'parcial'),
           monto_pagado = monto_pagado + NEW.monto
     WHERE id_factura = NEW.id_factura;
END$$

-- Una factura con pagos no se anula
CREATE TRIGGER trg_factura_anular BEFORE UPDATE ON factura FOR EACH ROW
BEGIN
    IF NEW.estado = 'anulada' AND OLD.estado <> 'anulada' AND OLD.monto_pagado > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La factura tiene pagos; no se puede anular';
    END IF;
END$$
DELIMITER ;

-- Ejemplo: control de niño sano con vacuna, pagado
INSERT INTO factura (numero_factura, id_paciente, nit, nombre_facturacion, fecha_emision, origen_tipo)
SELECT 'CP-000001', id_paciente, 'CF', nombre_tutor, NOW() - INTERVAL 3 DAY, 'manual'
  FROM paciente_pediatrico ORDER BY id_paciente LIMIT 1;
INSERT INTO detalle_factura (id_factura, codigo_arancel, concepto, cantidad, precio_unitario) VALUES
(1, 'CONTROL-NS', 'Control de niño sano', 1, 125.00),
(1, 'VACUNA-APL', 'Aplicación de vacuna', 1, 40.00);
INSERT INTO pago (id_factura, numero_recibo, fecha_pago, monto, metodo_pago, referencia, recibido_por)
VALUES (1, 'R-CP-000001', NOW() - INTERVAL 3 DAY, 165.00, 'tarjeta', 'AUT-552190', 'Recepción');
