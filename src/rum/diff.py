from typing import Set, Tuple, List
import secrets
import string


def _quote_ident(ident: str) -> str:
    """Safely quote identifiers."""
    # Note: If it's something like `schema.table`, we want `"schema"."table"`
    parts = ident.split(".")
    return ".".join(f'"{p}"' for p in parts)


def generate_random_password(length=15):
    # Redshift passwords cannot contain ', ", \, /, @, or space.
    safe_punctuation = (
        string.punctuation.replace("'", "")
        .replace('"', "")
        .replace("\\", "")
        .replace("/", "")
        .replace("@", "")
    )
    alphabet = string.ascii_letters + string.digits + safe_punctuation
    while True:
        password = "".join(secrets.choice(alphabet) for i in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and sum(c.isdigit() for c in password) >= 1
        ):
            break
    return password


def calculate_diff(
    desired_users: Set[str],
    desired_roles: Set[str],
    desired_user_roles: Set[Tuple[str, str]],
    desired_role_grants: Set[Tuple[str, str, str, str]],
    live_users: Set[str],
    live_roles: Set[str],
    live_user_roles: Set[Tuple[str, str]],
    live_role_grants: Set[Tuple[str, str, str, str]],
) -> List[str]:
    sql_statements: List[str] = []

    # Implicitly add SCHEMA USAGE for every schema referenced in table/model desired grants.
    # We shouldn't grant usage if the role is going to be dropped, but adding it to desired_role_grants
    # prevents it from being revoked incorrectly.
    implicit_schema_grants = set()
    for grant in desired_role_grants:
        role, resource_type, entity, _ = grant
        if resource_type in ("table", "model"):
            schema = entity.split(".")[0]
            implicit_schema_grants.add((role, "schema", schema, "USAGE"))

    desired_role_grants = desired_role_grants.union(implicit_schema_grants)

    # Calculate sets
    users_to_drop = live_users - desired_users
    roles_to_drop = live_roles - desired_roles
    user_roles_to_revoke = live_user_roles - desired_user_roles

    raw_role_grants_to_revoke = live_role_grants - desired_role_grants
    # Filter revokes to prevent dropping individual tables if a wildcard exists in desired.
    role_grants_to_revoke = set()
    for grant in raw_role_grants_to_revoke:
        role, resource_type, entity, privilege = grant
        if resource_type in ("table", "model") and "." in entity:
            schema = entity.split(".")[0]
            wildcard_grant = (role, resource_type, f"{schema}.*", privilege)
            if wildcard_grant in desired_role_grants:
                continue  # Skip revoking the individual entity because the wildcard covers it
        role_grants_to_revoke.add(grant)

    users_to_create = desired_users - live_users
    roles_to_create = desired_roles - live_roles
    user_roles_to_grant = desired_user_roles - live_user_roles
    role_grants_to_grant = desired_role_grants - live_role_grants

    # We need to order operations precisely:
    # 1. Revoke default privileges (future tables).
    # 2. Revoke current table privileges.
    # 3. Revoke roles from users.
    # 4. Drop users.
    # 5. Drop roles.
    # 6. Create users (generate randomized 15-char passwords for them).
    # 7. Create roles.
    # 8. Grant roles to users.
    # 9. Grant usage on schemas.
    # 10. Grant table privileges (and alter default privileges for .* entities).

    # 1. Revoke default privileges (future tables).
    for role, resource_type, entity, privilege in role_grants_to_revoke:
        if entity.endswith(".*"):
            schema = entity.split(".")[0]
            # Assumes table or model
            obj_type = "TABLES" if resource_type == "table" else "MODELS"
            sql_statements.append(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA {_quote_ident(schema)} REVOKE {privilege} ON {obj_type} FROM "{role}";'
            )

    # 2. Revoke current privileges.
    for role, resource_type, entity, privilege in role_grants_to_revoke:
        if resource_type == "database":
            sql_statements.append(
                f'REVOKE {privilege} ON DATABASE {_quote_ident(entity)} FROM "{role}";'
            )
        elif resource_type == "schema":
            sql_statements.append(
                f'REVOKE {privilege} ON SCHEMA {_quote_ident(entity)} FROM "{role}";'
            )
        elif entity.endswith(".*"):
            schema = entity.split(".")[0]
            obj_type = "ALL TABLES" if resource_type == "table" else "ALL MODELS"
            sql_statements.append(
                f'REVOKE {privilege} ON {obj_type} IN SCHEMA {_quote_ident(schema)} FROM "{role}";'
            )
        else:
            obj_type = "TABLE" if resource_type == "table" else "MODEL"
            sql_statements.append(
                f'REVOKE {privilege} ON {obj_type} {_quote_ident(entity)} FROM "{role}";'
            )

    # 3. Revoke roles from users.
    for user, role in user_roles_to_revoke:
        sql_statements.append(f'REVOKE ROLE "{role}" FROM "{user}";')

    # 4. Drop users.
    for user in users_to_drop:
        sql_statements.append(f'DROP USER "{user}";')

    # 5. Drop roles.
    for role in roles_to_drop:
        sql_statements.append(f'DROP ROLE "{role}";')

    # 6. Create users.
    for user in users_to_create:
        password = generate_random_password()
        sql_statements.append(f"CREATE USER \"{user}\" PASSWORD '{password}';")

    # 7. Create roles.
    for role in roles_to_create:
        sql_statements.append(f'CREATE ROLE "{role}";')

    # 8. Grant roles to users.
    for user, role in user_roles_to_grant:
        sql_statements.append(f'GRANT ROLE "{role}" TO "{user}";')

    # 9. Grant database & schema privileges (including implicitly added USAGE).
    for role, resource_type, entity, privilege in role_grants_to_grant:
        if resource_type == "database":
            sql_statements.append(
                f'GRANT {privilege} ON DATABASE {_quote_ident(entity)} TO "{role}";'
            )
        elif resource_type == "schema":
            sql_statements.append(
                f'GRANT {privilege} ON SCHEMA {_quote_ident(entity)} TO "{role}";'
            )

    # 10. Grant privileges (and alter default privileges for .* entities).
    for role, resource_type, entity, privilege in role_grants_to_grant:
        if resource_type in ("schema", "database"):
            continue
        elif entity.endswith(".*"):
            schema = entity.split(".")[0]
            obj_type = "ALL TABLES" if resource_type == "table" else "ALL MODELS"
            sql_statements.append(
                f'GRANT {privilege} ON {obj_type} IN SCHEMA {_quote_ident(schema)} TO "{role}";'
            )

            if resource_type == "table":
                sql_statements.append(
                    f'ALTER DEFAULT PRIVILEGES IN SCHEMA {_quote_ident(schema)} GRANT {privilege} ON TABLES TO "{role}";'
                )
        else:
            obj_type = "TABLE" if resource_type == "table" else "MODEL"
            sql_statements.append(
                f'GRANT {privilege} ON {obj_type} {_quote_ident(entity)} TO "{role}";'
            )

    # Deduplicate preserving the first occurrence
    seen = set()
    deduped_sql_statements = []
    for stmt in sql_statements:
        if stmt not in seen:
            seen.add(stmt)
            deduped_sql_statements.append(stmt)

    return deduped_sql_statements
