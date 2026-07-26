from rum.diff import calculate_diff


def test_diff_engine_calculates_correctly():
    desired_users = {"jane", "new"}
    desired_roles = {"analyst"}
    desired_user_roles = {
        ("jane", "analyst"),
        ("new", "analyst"),
    }
    desired_role_grants = {
        ("analyst", "table", "sales.*", "SELECT"),
        ("analyst", "schema", "analytics", "USAGE"),
        ("analyst", "database", "producer_data", "USAGE"),
    }

    live_users = {"jane", "old"}
    live_roles = {"analyst", "old"}
    live_user_roles = {("jane", "analyst"), ("old", "old")}
    live_role_grants = {
        (
            "analyst",
            "table",
            "sales.events",
            "SELECT",
        ),  # Should NOT be revoked because desired has sales.*
        (
            "analyst",
            "schema",
            "sales",
            "USAGE",
        ),  # Will be kept via implicit schema grant from diff engine
        ("old", "table", "old.*", "SELECT"),
        ("old", "database", "old_db", "USAGE"),
    }

    diff = calculate_diff(
        desired_users,
        desired_roles,
        desired_user_roles,
        desired_role_grants,
        live_users,
        live_roles,
        live_user_roles,
        live_role_grants,
    )

    # Re-evaluating actual results logically:
    # new user is created.
    # old user/role is dropped.
    actual_diff = set(diff)

    assert (
        'ALTER DEFAULT PRIVILEGES IN SCHEMA "old" REVOKE SELECT ON TABLES FROM "old";'
        in actual_diff
    )
    assert 'REVOKE SELECT ON ALL TABLES IN SCHEMA "old" FROM "old";' in actual_diff
    assert 'REVOKE USAGE ON DATABASE "old_db" FROM "old";' in actual_diff
    assert 'REVOKE ROLE "old" FROM "old";' in actual_diff
    assert 'DROP USER "old";' in actual_diff
    assert 'DROP ROLE "old";' in actual_diff

    create_users = [s for s in diff if s.startswith("CREATE USER")]
    assert len(create_users) == 1
    assert "new" in create_users[0]

    assert 'GRANT ROLE "analyst" TO "new";' in actual_diff

    assert 'GRANT USAGE ON SCHEMA "analytics" TO "analyst";' in actual_diff
    assert 'GRANT USAGE ON DATABASE "producer_data" TO "analyst";' in actual_diff
    # Implicit schema grants are only added if NOT present in live state. sales was already in live state.
    assert 'GRANT USAGE ON SCHEMA "sales" TO "analyst";' not in actual_diff
    assert 'GRANT SELECT ON ALL TABLES IN SCHEMA "sales" TO "analyst";' in actual_diff
    assert (
        'ALTER DEFAULT PRIVILEGES IN SCHEMA "sales" GRANT SELECT ON TABLES TO "analyst";'
        in actual_diff
    )

    # We should NOT be revoking sales.events
    assert not any('REVOKE SELECT ON TABLE "sales"."events"' in s for s in diff)
