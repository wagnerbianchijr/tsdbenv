-- Keep the standard PostgreSQL superuser available for on-premises testing.
ALTER ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';
-- Match the managed Tiger Cloud administrator role attributes.
CREATE ROLE tsdbadmin WITH LOGIN NOSUPERUSER CREATEDB CREATEROLE REPLICATION PASSWORD :'password';
-- Set default search_path for tsdbadmin
ALTER ROLE tsdbadmin SET search_path = public, pg_catalog;
