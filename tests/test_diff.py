from rum.diff import calculate_diff


def test_diff_engine_calculates_correctly():
    desired_users = {"rum_user_jane", "rum_user_new"}
    desired_roles = {"rum_role_analyst"}
    desired_user_roles = {
        ("rum_user_jane", "rum_role_analyst"),
        ("rum_user_new", "rum_role_analyst"),
    }
    desired_role_grants = {
        ("rum_role_analyst", "table", "sales.*", "SELECT"),
        ("rum_role_analyst", "schema", "analytics", "USAGE"),
    }

    live_users = {"rum_user_jane", "rum_user_old"}
    live_roles = {"rum_role_analyst", "rum_role_old"}
    live_user_roles = {("rum_user_jane", "rum_role_analyst"), ("rum_user_old", "rum_role_old")}
    live_role_grants = {
        (
            "rum_role_analyst",
            "table",
            "sales.events",
            "SELECT",
        ),  # Should NOT be revoked because desired has sales.*
        (
            "rum_role_analyst",
            "schema",
            "sales",
            "USAGE",
        ),  # Will be kept via implicit schema grant from diff engine
        ("rum_role_old", "table", "old.*", "SELECT"),
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
        'ALTER DEFAULT PRIVILEGES IN SCHEMA "old" REVOKE SELECT ON TABLES FROM "rum_role_old";'
        in actual_diff
    )
    assert 'REVOKE SELECT ON ALL TABLES IN SCHEMA "old" FROM "rum_role_old";' in actual_diff
    assert 'REVOKE ROLE "rum_role_old" FROM "rum_user_old";' in actual_diff
    assert 'DROP USER "rum_user_old";' in actual_diff
    assert 'DROP ROLE "rum_role_old";' in actual_diff

    create_users = [s for s in diff if s.startswith("CREATE USER")]
    assert len(create_users) == 1
    assert "rum_user_new" in create_users[0]

    assert 'GRANT ROLE "rum_role_analyst" TO "rum_user_new";' in actual_diff

    assert 'GRANT USAGE ON SCHEMA "analytics" TO "rum_role_analyst";' in actual_diff
    # Implicit schema grants are only added if NOT present in live state. sales was already in live state.
    assert 'GRANT USAGE ON SCHEMA "sales" TO "rum_role_analyst";' not in actual_diff
    assert 'GRANT SELECT ON ALL TABLES IN SCHEMA "sales" TO "rum_role_analyst";' in actual_diff
    assert (
        'ALTER DEFAULT PRIVILEGES IN SCHEMA "sales" GRANT SELECT ON TABLES TO "rum_role_analyst";'
        in actual_diff
    )

    # We should NOT be revoking sales.events
    assert not any('REVOKE SELECT ON TABLE "sales"."events"' in s for s in diff)


def test_sql_injection_prevention():
    malicious_user = 'rum_user_bad" OR 1=1 --'
    malicious_role = 'rum_role_bad"; DROP TABLE users; --'

    desired_users = {malicious_user}
    desired_roles = {malicious_role}
    desired_user_roles = {(malicious_user, malicious_role)}
    desired_role_grants = {
        (malicious_role, "table", 'sales".events', "SELECT"),
    }

    diff = calculate_diff(
        desired_users,
        desired_roles,
        desired_user_roles,
        desired_role_grants,
        set(),
        set(),
        set(),
        set(),
    )

    actual_diff = set(diff)

    # Check that double quotes are correctly escaped as ""
    expected_user = '"rum_user_bad"" OR 1=1 --"'
    expected_role = '"rum_role_bad""; DROP TABLE users; --"'
    expected_table = '"sales"""."events"'

    create_users = [s for s in diff if s.startswith("CREATE USER")]
    assert len(create_users) == 1
    assert expected_user in create_users[0]

    assert f"CREATE ROLE {expected_role};" in actual_diff
    assert f"GRANT ROLE {expected_role} TO {expected_user};" in actual_diff
    assert f"GRANT SELECT ON TABLE {expected_table} TO {expected_role};" in actual_diff
