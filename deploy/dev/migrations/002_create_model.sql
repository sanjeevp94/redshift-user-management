--liquibase formatted sql
--changeset jules:2

CREATE MODEL ml.customer_churn_model
FROM (SELECT customer_id, age, tenure, is_active, churn FROM public.customer_data)
TARGET churn
FUNCTION predict_churn
IAM_ROLE default
SETTINGS (
  S3_BUCKET 'my-s3-bucket-ml-${environment_name}',
  MAX_CELLS 1000000
);

--rollback DROP MODEL ml.customer_churn_model;
