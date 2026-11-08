-- ============================================================================
-- SEGURIDAD - CENTRO MÉDICO PEDIÁTRICO Y CLÍNICA ODONTOLÓGICA (MySQL)
-- Usuarios de la aplicación con mínimo privilegio:
--   * SELECT, INSERT, UPDATE sobre sus respectivas bases de datos.
--   * Sin DELETE: los expedientes se archivan, no se borran.
--   * Sin privilegios de DDL ni acceso a otras bases.
-- ============================================================================

CREATE USER IF NOT EXISTS 'app_pediatrico'@'%' IDENTIFIED BY 'PediatricoApp2026!';
GRANT SELECT, INSERT, UPDATE ON centro_pediatrico.* TO 'app_pediatrico'@'%';

CREATE USER IF NOT EXISTS 'app_odontologia'@'%' IDENTIFIED BY 'OdontologiaApp2026!';
GRANT SELECT, INSERT, UPDATE ON clinica_odontologica.* TO 'app_odontologia'@'%';

FLUSH PRIVILEGES;
