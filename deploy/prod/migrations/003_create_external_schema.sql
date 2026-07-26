--liquibase formatted sql
--changeset jules:3 context:consumer

CREATE EXTERNAL SCHEMA spectrum_schema
FROM DATA CATALOG
DATABASE 'spectrum_db_${environment_name}'
IAM_ROLE default
CREATE EXTERNAL DATABASE IF NOT EXISTS;

--rollback DROP EXTERNAL SCHEMA spectrum_schema;
