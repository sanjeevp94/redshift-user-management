from unittest.mock import patch
import tempfile
import os

# We need to import the script directly. Since it's not a python module, we can use runpy or importlib.
# Alternatively, since we can't easily import from `scripts/`, let's wrap its execution in a unit test.


def test_run_liquibase_script_multiple_clusters():
    config_content = """
clusters:
  - target:
      host: "dev-cluster-1"
      port: 5439
      database: "dev_db_1"
      liquibase_contexts: "core,reporting"
  - target:
      host: "dev-cluster-2"
      port: 5439
      database: "dev_db_2"
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("run_liquibase", "scripts/run_liquibase.py")
        run_liquibase_module = importlib.util.module_from_spec(spec)

        # We need to mock os.environ and subprocess.run before executing the function inside the module
        with patch.dict(
            os.environ, {"REDSHIFT_USER": "test_user", "REDSHIFT_PASSWORD": "test_password"}
        ):
            with patch("subprocess.run") as mock_run:
                spec.loader.exec_module(run_liquibase_module)

                # Call the function directly
                run_liquibase_module.run_liquibase(temp_path, "dummy_changelog.yaml", "update")

                assert mock_run.call_count == 2

                # Check call 1
                cmd1 = mock_run.call_args_list[0][0][0]
                assert cmd1 == [
                    "liquibase",
                    "--url=jdbc:redshift://dev-cluster-1:5439/dev_db_1",
                    "--username=test_user",
                    "--password=test_password",
                    "--changeLogFile=dummy_changelog.yaml",
                    "--contexts=core,reporting",
                    "update",
                ]

                # Check call 2
                cmd2 = mock_run.call_args_list[1][0][0]
                assert cmd2 == [
                    "liquibase",
                    "--url=jdbc:redshift://dev-cluster-2:5439/dev_db_2",
                    "--username=test_user",
                    "--password=test_password",
                    "--changeLogFile=dummy_changelog.yaml",
                    "--contexts=dev-cluster-2",
                    "update",
                ]
    finally:
        os.remove(temp_path)


def test_run_liquibase_script_targeted_cluster():
    config_content = """
clusters:
  - target:
      host: "dev-cluster-1"
      port: 5439
      database: "dev_db_1"
  - target:
      host: "dev-cluster-2"
      port: 5439
      database: "dev_db_2"
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
        f.write(config_content)
        temp_path = f.name

    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("run_liquibase", "scripts/run_liquibase.py")
        run_liquibase_module = importlib.util.module_from_spec(spec)

        with patch.dict(
            os.environ, {"REDSHIFT_USER": "test_user", "REDSHIFT_PASSWORD": "test_password"}
        ):
            with patch("subprocess.run") as mock_run:
                spec.loader.exec_module(run_liquibase_module)

                # Call the function directly with target
                run_liquibase_module.run_liquibase(
                    temp_path, "dummy_changelog.yaml", "update", "dev-cluster-2"
                )

                assert mock_run.call_count == 1

                # Check it only called dev-cluster-2
                cmd1 = mock_run.call_args_list[0][0][0]
                assert cmd1 == [
                    "liquibase",
                    "--url=jdbc:redshift://dev-cluster-2:5439/dev_db_2",
                    "--username=test_user",
                    "--password=test_password",
                    "--changeLogFile=dummy_changelog.yaml",
                    "--contexts=dev-cluster-2",
                    "update",
                ]
    finally:
        os.remove(temp_path)
