import tempfile
import os
from rum.compiler import compile_state


def test_compiler_extracts_clusters_and_prefixes_correctly():
    config_content = """
clusters:
  - target:
      host: "test-host-1"
      port: 5439
      database: "test_db_1"
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
  - target:
      host: "test-host-2"
      port: 5439
      database: "test_db_2"
    users:
      bob:
        roles:
          - engineer
    roles:
      engineer:
        permissions:
          - write_data
    permissions:
      write_data:
        resource_type: table
        privileges:
          - INSERT
        entities:
          - "marketing.events"
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        cluster_configs = compile_state(temp_path)

        assert len(cluster_configs) == 2

        # Check Cluster 1
        c1 = cluster_configs[0]
        assert c1["target_info"] == {"host": "test-host-1", "port": 5439, "database": "test_db_1"}
        assert c1["desired_users"] == {"rum_user_jane"}
        assert c1["desired_roles"] == {"rum_role_analyst"}
        assert c1["desired_user_roles"] == {("rum_user_jane", "rum_role_analyst")}
        assert c1["desired_role_grants"] == {("rum_role_analyst", "table", "sales.*", "SELECT")}

        # Check Cluster 2
        c2 = cluster_configs[1]
        assert c2["target_info"] == {"host": "test-host-2", "port": 5439, "database": "test_db_2"}
        assert c2["desired_users"] == {"rum_user_bob"}
        assert c2["desired_roles"] == {"rum_role_engineer"}
        assert c2["desired_user_roles"] == {("rum_user_bob", "rum_role_engineer")}
        assert c2["desired_role_grants"] == {
            ("rum_role_engineer", "table", "marketing.events", "INSERT")
        }

    finally:
        os.remove(temp_path)


def test_compiler_targeted_cluster():
    config_content = """
clusters:
  - target:
      host: "dev-cluster-1"
      port: 5439
      database: "dev_db_1"
    users:
      jane:
        roles:
          - analyst
  - target:
      host: "dev-cluster-2"
      port: 5439
      database: "dev_db_2"
    users:
      bob:
        roles:
          - analyst
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        cluster_configs = compile_state(temp_path, target_host="dev-cluster-2")

        # It should filter out cluster-1 and only compile cluster-2
        assert len(cluster_configs) == 1

        c = cluster_configs[0]
        assert c["target_info"] == {"host": "dev-cluster-2", "port": 5439, "database": "dev_db_2"}
        assert c["desired_users"] == {"rum_user_bob"}
    finally:
        os.remove(temp_path)


def test_compiler_empty_config():
    config_content = ""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        cluster_configs = compile_state(temp_path)

        assert len(cluster_configs) == 1
        c = cluster_configs[0]
        assert c["target_info"] == {}
        assert c["desired_users"] == set()
        assert c["desired_roles"] == set()
        assert c["desired_user_roles"] == set()
        assert c["desired_role_grants"] == set()
    finally:
        os.remove(temp_path)
