--liquibase formatted sql
--changeset jules:1 context:producer

-- Use liquibase property substitution
CREATE DATASHARE ${datashare_name};
ALTER DATASHARE ${datashare_name} ADD SCHEMA public;
ALTER DATASHARE ${datashare_name} ADD TABLE public.customer_data;

--rollback DROP DATASHARE ${datashare_name};
