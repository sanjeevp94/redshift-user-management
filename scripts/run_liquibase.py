#!/usr/bin/env python3
import os
import sys
import yaml
import subprocess


def run_liquibase(config_path, changelog_path, action):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    clusters = config.get("clusters", [])
    if not clusters:
        clusters = [config]

    username = os.environ.get("REDSHIFT_USER", "postgres")
    password = os.environ.get("REDSHIFT_PASSWORD", "postgres")

    for cluster_block in clusters:
        target_info = cluster_block.get("target", {})
        if not target_info and "targets" in cluster_block and cluster_block["targets"]:
            target_info = cluster_block["targets"][0]

        host = target_info.get("host")
        port = target_info.get("port", "5439")
        db = target_info.get("database")

        if not host or not db:
            print("Missing host or database in config.")
            continue

        url = f"jdbc:redshift://{host}:{port}/{db}"

        print(f"\n--- Running Liquibase {action} on {host} ---")

        cmd = [
            "liquibase",
            f"--url={url}",
            f"--username={username}",
            f"--password={password}",
            f"--changeLogFile={changelog_path}",
            action,
        ]

        try:
            # We don't want to capture output here if we want it to stream to jenkins logs
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Liquibase command failed for {host}")
            sys.exit(e.returncode)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: run_liquibase.py <config_path> <changelog_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    changelog_path = sys.argv[2]

    # In jenkins ACTION is typically 'plan' or 'apply'
    jenkins_action = os.environ.get("ACTION", "plan")

    # Map jenkins actions to liquibase commands
    if jenkins_action == "apply":
        lb_action = "update"
    else:
        lb_action = "updateSQL"  # Dry run equivalent in liquibase

    run_liquibase(config_path, changelog_path, lb_action)
