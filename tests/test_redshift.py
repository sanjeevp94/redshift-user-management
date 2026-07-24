from unittest.mock import MagicMock
from rum.redshift import fetch_live_state


def test_fetch_live_state():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Simulate DB rows returned for 6 queries
    def fetchall_side_effect():
        # 1. query pg_user
        yield [("rum_user_john",)]
        # 2. query svv_roles
        yield [("rum_role_engineer",)]
        # 3. query svv_role_grants
        yield [("rum_user_john", "rum_role_engineer")]
        # 4. query svv_relation_privileges
        yield [("rum_role_engineer", "engineering", "deployments", "INSERT")]
        # 5. query svv_default_privileges
        yield [("rum_role_engineer", "engineering", "SELECT", "table")]
        # 6. query svv_schema_privileges
        yield [("rum_role_engineer", "engineering", "USAGE")]

    mock_cur.fetchall.side_effect = fetchall_side_effect()

    users, roles, user_roles, role_grants = fetch_live_state(mock_conn)

    assert users == {"rum_user_john"}
    assert roles == {"rum_role_engineer"}
    assert user_roles == {("rum_user_john", "rum_role_engineer")}
    assert role_grants == {
        ("rum_role_engineer", "table", "engineering.deployments", "INSERT"),
        ("rum_role_engineer", "table", "engineering.*", "SELECT"),
        ("rum_role_engineer", "schema", "engineering", "USAGE"),
    }
