import os
import psycopg2
from typing import Set, Tuple, Dict, Any


def get_connection(target_info: Dict[str, Any]):
    return psycopg2.connect(
        host=target_info.get("host", os.environ.get("REDSHIFT_HOST", "localhost")),
        database=target_info.get("database", os.environ.get("REDSHIFT_DB", "dev")),
        user=os.environ.get("REDSHIFT_USER", "postgres"),
        password=os.environ.get("REDSHIFT_PASSWORD", "postgres"),
        port=target_info.get("port", os.environ.get("REDSHIFT_PORT", "5432")),
    )


def fetch_live_state(
    conn,
) -> Tuple[Set[str], Set[str], Set[Tuple[str, str]], Set[Tuple[str, str, str, str]]]:
    live_users: Set[str] = set()
    live_roles: Set[str] = set()
    live_user_roles: Set[Tuple[str, str]] = set()
    live_role_grants: Set[Tuple[str, str, str, str]] = set()

    with conn.cursor() as cur:
        # 1. Fetch live users
        # Exclude system default internal users to prevent accidental drops of master accounts.
        cur.execute("SELECT usename FROM pg_user WHERE usename NOT IN ('rdsdb', 'postgres')")
        for row in cur.fetchall():
            live_users.add(row[0])

        # 2. Fetch live roles
        # Exclude system defaults if applicable, but fetch all available roles normally
        cur.execute(
            "SELECT role_name FROM svv_roles WHERE role_name NOT IN ('sys:superuser', 'sys:secadmin')"
        )
        for row in cur.fetchall():
            live_roles.add(row[0])

        # 3. Fetch user roles (assigned roles)
        cur.execute("""
            SELECT user_name, role_name
            FROM svv_role_grants
        """)
        for row in cur.fetchall():
            # Ensure we only track assignments for users/roles we manage
            if row[0] not in ("rdsdb", "postgres") and row[1] not in (
                "sys:superuser",
                "sys:secadmin",
            ):
                live_user_roles.add((row[0], row[1]))

        # 4. Fetch role grants (svv_relation_privileges) for tables
        cur.execute("""
            SELECT role_name, namespace_name, relation_name, privilege_type
            FROM svv_relation_privileges
            WHERE relation_name IS NOT NULL
        """)
        for row in cur.fetchall():
            role_name, schema_name, table_name, privilege = row
            if role_name not in ("sys:superuser", "sys:secadmin"):
                entity = f"{schema_name}.{table_name}"
                live_role_grants.add((role_name, "table", entity, privilege.upper()))

        # 5. Fetch default privileges (mapping to `schema.*`)
        cur.execute("""
            SELECT d.grantee, n.nspname, d.privilege_type, d.object_type
            FROM svv_default_privileges d
            JOIN pg_namespace n ON d.namespace_id = n.oid
        """)
        for row in cur.fetchall():
            role_name, schema_name, privilege, object_type = row
            if role_name not in ("sys:superuser", "sys:secadmin"):
                entity = f"{schema_name}.*"
                resource_type = "table" if object_type.lower() == "table" else object_type.lower()
                live_role_grants.add((role_name, resource_type, entity, privilege.upper()))

        # 6. Fetch schema privileges
        cur.execute("""
            SELECT grantee, namespace_name, privilege_type
            FROM svv_schema_privileges
            WHERE namespace_name IS NOT NULL
        """)
        for row in cur.fetchall():
            role_name, schema_name, privilege = row
            if role_name not in ("sys:superuser", "sys:secadmin"):
                live_role_grants.add((role_name, "schema", schema_name, privilege.upper()))

    return live_users, live_roles, live_user_roles, live_role_grants
