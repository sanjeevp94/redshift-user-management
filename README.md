# Declarative Redshift User Manager (RUM) & Liquibase Infrastructure Automation

This repository provides a comprehensive, declarative Infrastructure-as-Code (IaC) framework for managing Amazon Redshift. It is composed of two natively integrated pipelines:

1. **Liquibase (Imperative DDL):** Executes ad-hoc structural changes (e.g., `CREATE TABLE`, `CREATE MODEL`, `CREATE EXTERNAL SCHEMA`).
2. **RUM (Declarative State):** A custom Python CLI that calculates exact set-based diffs between a desired `config.yaml` state and the live Redshift catalog to safely manage users, roles, and granular privileges.

By executing Liquibase migrations first, and the RUM declarative CLI second, this repository ensures that newly deployed tables and models immediately receive correct access bindings without manual intervention.

---

## Directory Structure
The repository is segmented by environment into the `deploy/` directory to facilitate isolated Jenkins pipelines.

```text
.
├── pyproject.toml              # UV python dependency constraints and project metadata
├── scripts/
│   └── run_liquibase.py        # Python wrapper orchestrating Jenkins parameters to Liquibase contexts
├── src/rum/                    # Source code for the declarative RUM diffing engine
├── tests/                      # Pytest suite validating CLI and engine logic
└── deploy/
    ├── dev/
    │   ├── Jenkinsfile         # CI/CD definition for the DEV environment
    │   ├── changelog.yaml      # Master Liquibase execution sequence & property injection
    │   ├── config.yaml         # Declarative target clusters, users, roles, and permissions
    │   └── migrations/         # Raw SQL scripts for structural DDL changes
    ├── uat/
    └── prod/
```

---

## Tooling & Prerequisites
- **Language**: Python 3.10+
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (An extremely fast Python package installer)
- **Formatting/Linting**: `ruff` executed via `prek` (a Rust-powered replacement for `pre-commit`).

### Setup
```bash
# Install uv and prek
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install prek

# Sync dependencies and run hooks
uv sync
prek run --all-files

# Run tests
uv pip install -e ".[dev]"
pytest tests/
```

---

## Managing Permissions (The `config.yaml` Schema)

The RUM engine parses an environment's `config.yaml` to identify discrete targets and their intended states. **Crucially**, the engine strictly operates within a `rum_user_` and `rum_role_` namespace, guaranteeing it will not touch or drop external enterprise resources.

### Schema Example
A `config.yaml` file contains an array of `clusters`. Each cluster acts as a completely isolated boundary.

```yaml
clusters:
  - target:
      host: "dev-cluster-1.us-east-1.redshift.amazonaws.com"
      port: 5439
      database: "dev_db"
      liquibase_contexts: "core,reporting"  # Optional: For targeted SQL migrations

    users:
      jane_doe:
        roles:
          - marketing_analyst

    roles:
      marketing_analyst:
        permissions:
          - read_campaigns
          - access_models

    permissions:
      read_campaigns:
        resource_type: table
        privileges:
          - SELECT
        entities:
          - "marketing.campaigns"   # Grant access to a specific table
          - "sales.*"               # Wildcard: Grant access to ALL current AND future tables in schema

      access_models:
        resource_type: model
        privileges:
          - EXECUTE
        entities:
          - "ml.*"
```

### Wildcards (`.*`)
When the engine detects `schema.*`, it natively deduces the optimal outcome:
- It issues `GRANT {privilege} ON ALL TABLES IN SCHEMA {schema}` for current objects.
- It concurrently issues `ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}` to handle future objects automatically.

---

## Ad-Hoc DDL Migrations (Liquibase)

Liquibase manages structural deployments by consuming `.sql` scripts from the `deploy/<env>/migrations/` directory.

### Contexts (Targeted Execution)
If an environment possesses multiple clusters (e.g., `dev-cluster-1` and `dev-cluster-2`), you can prevent specific SQL scripts from running everywhere by leveraging **Liquibase Contexts**.

Define your contexts in the `config.yaml` (e.g., `liquibase_contexts: "core,reporting"`). If omitted, the context implicitly defaults to the target's `host` string.

In your migration file header, tag the context:

```sql
--liquibase formatted sql
--changeset jules:1 context:reporting

CREATE EXTERNAL SCHEMA spectrum_schema
FROM DATA CATALOG
DATABASE 'spectrum_db_${environment_name}'
IAM_ROLE default;
```
*Note: We natively support variable substitution (like `${environment_name}`) mapped directly from the `changelog.yaml`.*

---

## Execution Workflow

The CI/CD Jenkinsfiles natively automate execution. However, if running locally or debugging:

**1. Run Liquibase:**
```bash
export REDSHIFT_USER="postgres"
export REDSHIFT_PASSWORD="password"
export ACTION="plan"  # Set to "apply" to execute natively, "plan" for updateSQL

# Run across all clusters in dev
python3 scripts/run_liquibase.py deploy/dev/config.yaml deploy/dev/changelog.yaml

# Run targeting ONLY dev-cluster-1
python3 scripts/run_liquibase.py deploy/dev/config.yaml deploy/dev/changelog.yaml --target=dev-cluster-1
```

**2. Run RUM Permissions Engine:**
```bash
# Preview the declarative Set Math diff
uv run rum plan --config=deploy/dev/config.yaml

# Apply the diff
uv run rum apply --config=deploy/dev/config.yaml --auto_approve=True

# Apply the diff ONLY to a specific cluster
uv run rum apply --config=deploy/dev/config.yaml --target=dev-cluster-1
```