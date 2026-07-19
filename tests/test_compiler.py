import tempfile
import os
from src.rum.compiler import compile_state


def test_compiler_extracts_target_and_prefixes_correctly():
    config_content = """
target:
  host: "test-host"
  port: 5439
  database: "test_db"

users:
  jane:
    roles:
      - analyst

roles:
  analyst:
    permissions:
      - read_data

permissions:
  read_data:
    resource_type: table
    privileges:
      - SELECT
    entities:
      - "sales.*"
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        target, users, roles, user_roles, role_grants = compile_state(temp_path)

        assert target == {"host": "test-host", "port": 5439, "database": "test_db"}
        assert users == {"rum_user_jane"}
        assert roles == {"rum_role_analyst"}
        assert user_roles == {("rum_user_jane", "rum_role_analyst")}
        assert role_grants == {("rum_role_analyst", "table", "sales.*", "SELECT")}
    finally:
        os.remove(temp_path)


def test_compiler_empty_config():
    config_content = ""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        target, users, roles, user_roles, role_grants = compile_state(temp_path)

        assert target == {}
        assert users == set()
        assert roles == set()
        assert user_roles == set()
        assert role_grants == set()
    finally:
        os.remove(temp_path)
