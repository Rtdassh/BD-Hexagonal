-- ============================================================================
-- SEGURIDAD - HOSPITAL GENERAL (PostgreSQL)
-- Usuario de la aplicación con mínimo privilegio.
--   * Puede leer, insertar y actualizar.
--   * NO puede borrar: un historial clínico nunca se elimina, solo se archiva.
--   * NO puede crear ni alterar tablas (DDL).
-- Cambie la contraseña en producción y colóquela en el archivo .env
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_hospital') THEN
        CREATE ROLE app_hospital LOGIN PASSWORD 'HospitalApp2026!';
    END IF;
END
$$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE hospital_db TO app_hospital;
GRANT USAGE ON SCHEMA hospital TO app_hospital;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA hospital TO app_hospital;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA hospital TO app_hospital;
ALTER ROLE app_hospital SET search_path TO hospital, public;
