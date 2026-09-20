-- Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
-- Created: 2026-08-19
-- Initialize tsdbadmin user and configuration

-- Match the managed Tiger Cloud administrator role attributes.
CREATE ROLE tsdbadmin WITH LOGIN NOSUPERUSER CREATEDB CREATEROLE REPLICATION PASSWORD :password;
-- Set default search_path for tsdbadmin
ALTER ROLE tsdbadmin SET search_path = public, pg_catalog;
