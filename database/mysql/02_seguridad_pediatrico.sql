-- ============================================================================
-- SEGURIDAD - CENTRO MÉDICO PEDIÁTRICO (MySQL)
-- Usuario de la aplicación con mínimo privilegio:
--   * SELECT, INSERT, UPDATE sobre centro_pediatrico.
--   * Sin DELETE: los expedientes se archivan, no se borran.
--   * Sin privilegios de DDL ni acceso a otras bases.
-- Cambie la contraseña en producción y colóquela en el archivo .env
-- ============================================================================

CREATE USER IF NOT EXISTS 'app_pediatrico'@'%' IDENTIFIED BY 'PediatricoApp2026!';
GRANT SELECT, INSERT, UPDATE ON centro_pediatrico.* TO 'app_pediatrico'@'%';
FLUSH PRIVILEGES;
