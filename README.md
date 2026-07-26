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
We provide a `Makefile` to quickly bootstrap your local environment.

```bash
# Installs uv, prek, and python dependencies locally
make setup

# Run pre-commit formatters
make lint

# Run the pytest suite
make test
```

---

## Managing Permissions (The `config.yaml` Schema)

The RUM engine parses an environment's `config.yaml` to identify discrete targets and their intended states. The engine parses users and roles explicitly exactly as defined and will automatically mirror the catalog state accurately to them. **Note: Because the engine tracks absolute state, any active users or roles missing from your config.yaml will be dropped automatically.**

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

### Supported Privileges
The framework securely wraps SQL generation against your provided `config.yaml` permissions blocks. The following resource types and native privileges are generally applicable:

| Resource Type | Available Privileges | Notes |
|---------------|----------------------|-------|
| `table`       | `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, `REFERENCES`, `ALL` | Applicable to individual tables or schema wildcards (`.*`). |
| `schema`      | `USAGE`, `CREATE`, `ALL` | The engine implicitly injects `USAGE` when parsing any enclosed table/model resources natively to prevent Redshift lockups. |
| `model`       | `EXECUTE`, `ALL` | Useful for explicitly isolating Redshift ML modeling endpoints from standard analytical access constraints. |

---

## Ad-Hoc DDL Migrations (Liquibase)

Liquibase manages structural deployments by consuming `.sql` scripts from the `deploy/<env>/migrations/` directory.

### Liquibase Contexts (Targeted Cluster Execution)

In multi-cluster environments (e.g., establishing a Data Sharing architecture with isolated **Producer** and **Consumer** workloads), it is critical to execute specific SQL migrations against a subset of clusters rather than shotgunning scripts universally. You can achieve this perfectly using **Liquibase Contexts**.

#### 1. Assigning Contexts to Targets
Inside your `config.yaml`, declare `liquibase_contexts` as a comma-separated list of tags denoting the cluster's purpose. If omitted, the context implicitly defaults to the target's `host` string (allowing you to explicitly single out clusters natively).

```yaml
clusters:
  # The Producer handles heavy DBT transformations and modeling
  - target:
      host: "dev-producer.abcdefg.us-east-1.redshift.amazonaws.com"
      port: 5439
      database: "dev_db"
      liquibase_contexts: "producer"

  # The Consumer safely hosts BI queries against shared data
  - target:
      host: "dev-consumer.abcdefg.us-east-1.redshift.amazonaws.com"
      port: 5439
      database: "dev_db"
      liquibase_contexts: "consumer"
```

#### 2. Tagging Migration Files
By default, a Liquibase script runs on **all** targets unless constrained by a context tag in its header. You map a script to a specific cluster type by appending `context:<tag>`:

**Example A: Global Deployment** (Runs on both clusters)
```sql
--liquibase formatted sql
--changeset author:1

CREATE DATASHARE dev_sales_share;
```

**Example B: Targeted Deployment** (Runs ONLY on the Consumer because of `consumer`)
```sql
--liquibase formatted sql
--changeset author:2 context:consumer

-- Mounts the data share created on the producer safely onto the consumer cluster
CREATE DATABASE producer_data FROM DATASHARE ${datashare_name} OF NAMESPACE 'producer-namespace-uuid';
```
*Note: We natively support variable substitution (like `${environment_name}`) mapped directly from the `changelog.yaml` file.*

---

## Execution Workflow

The CI/CD Jenkinsfiles natively automate execution. However, if running locally or debugging:

**1. Run Liquibase:**
```bash
export REDSHIFT_USER="postgres"
export REDSHIFT_PASSWORD="password"
export ACTION="plan"  # Set to "apply" to execute natively, "plan" for updateSQL

# Run across all clusters in dev
uv run python scripts/run_liquibase.py deploy/dev/config.yaml deploy/dev/changelog.yaml

# Run targeting ONLY dev-cluster-1
uv run python scripts/run_liquibase.py deploy/dev/config.yaml deploy/dev/changelog.yaml --target=dev-cluster-1
```

**2. Run RUM Permissions Engine:**
```bash
# Preview the declarative Set Math diff (Defaults to dev)
make plan

# Apply the diff (Defaults to dev, prompts for approval)
make apply

# Target a different environment and a specific cluster
make plan ENV=uat TARGET=uat-cluster
```

**3. Syncing Live State (Reverse Compilation):**
If you have existing users/roles natively in Redshift or lost your configuration, you can completely reverse-engineer the live Redshift catalog privileges directly back into a declarative `config.yaml`.
```bash
# Overwrites deploy/dev/config.yaml with the live database privileges automatically
make sync

# Overwrites a targeted cluster within UAT specifically
make sync ENV=uat TARGET=uat-cluster
```
*Note: Because this directly overwrites your configuration file, ensure you have committed any intended changes to Git first or are running this strictly to baseline an initial configuration.*