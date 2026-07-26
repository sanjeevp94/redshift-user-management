--liquibase formatted sql
--changeset jules:4 context:consumer

CREATE DATABASE producer_data FROM DATASHARE ${datashare_name} OF NAMESPACE 'producer-namespace-uuid';

--rollback DROP DATABASE producer_data;
