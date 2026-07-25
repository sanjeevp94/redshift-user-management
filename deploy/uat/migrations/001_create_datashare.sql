--liquibase formatted sql
--changeset jules:1 context:core

-- Use liquibase property substitution
CREATE DATASHARE ${datashare_name};
ALTER DATASHARE ${datashare_name} ADD SCHEMA public;

--rollback DROP DATASHARE ${datashare_name};
