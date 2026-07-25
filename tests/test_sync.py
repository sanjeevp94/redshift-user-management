from src.rum.sync import build_cluster_yaml_block


def test_sync_build_cluster_yaml_block():
    target_info = {"host": "test-cluster", "port": 5439, "database": "dev"}
    live_users = {"john", "jane"}
    live_roles = {"analyst", "admin"}
    live_user_roles = {("john", "analyst"), ("jane", "admin")}
    live_role_grants = {
        ("analyst", "table", "sales.events", "SELECT"),
        ("analyst", "schema", "sales", "USAGE"),
        ("admin", "model", "ml.*", "ALL"),
    }

    yaml_dict = build_cluster_yaml_block(
        target_info, live_users, live_roles, live_user_roles, live_role_grants
    )

    # Validate target
    assert yaml_dict["target"] == target_info

    # Validate users mapped to roles correctly
    assert yaml_dict["users"]["john"]["roles"] == ["analyst"]
    assert yaml_dict["users"]["jane"]["roles"] == ["admin"]

    # Validate roles mapped to generated permission names
    assert "table_sales_events" in yaml_dict["roles"]["analyst"]["permissions"]
    assert "schema_sales" in yaml_dict["roles"]["analyst"]["permissions"]
    assert "model_ml_all" in yaml_dict["roles"]["admin"]["permissions"]

    # Validate permissions generated blocks natively
    assert yaml_dict["permissions"]["table_sales_events"] == {
        "resource_type": "table",
        "privileges": ["SELECT"],
        "entities": ["sales.events"],
    }

    assert yaml_dict["permissions"]["schema_sales"] == {
        "resource_type": "schema",
        "privileges": ["USAGE"],
        "entities": ["sales"],
    }

    assert yaml_dict["permissions"]["model_ml_all"] == {
        "resource_type": "model",
        "privileges": ["ALL"],
        "entities": ["ml.*"],
    }
