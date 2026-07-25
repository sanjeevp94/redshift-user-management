from unittest.mock import MagicMock
from rum.redshift import fetch_live_state


def test_fetch_live_state():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Simulate DB rows returned for 6 queries
    def fetchall_side_effect():
        # 1. query pg_user
        yield [("john",)]
        # 2. query svv_roles
        yield [("engineer",)]
        # 3. query svv_role_grants
        yield [("john", "engineer")]
        # 4. query svv_relation_privileges
        yield [("engineer", "engineering", "deployments", "INSERT")]
        # 5. query svv_default_privileges
        yield [("engineer", "engineering", "SELECT", "table")]
        # 6. query svv_schema_privileges
        yield [("engineer", "engineering", "USAGE")]

    mock_cur.fetchall.side_effect = fetchall_side_effect()

    users, roles, user_roles, role_grants = fetch_live_state(mock_conn)

    assert users == {"john"}
    assert roles == {"engineer"}
    assert user_roles == {("john", "engineer")}
    assert role_grants == {
        ("engineer", "table", "engineering.deployments", "INSERT"),
        ("engineer", "table", "engineering.*", "SELECT"),
        ("engineer", "schema", "engineering", "USAGE"),
    }
