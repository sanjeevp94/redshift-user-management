#!/usr/bin/env python3
import os
import sys
import yaml
import subprocess
import argparse


def run_liquibase(config_path, changelog_path, action, target_host=None):
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

        if target_host and host != target_host:
            continue

        port = target_info.get("port", "5439")
        db = target_info.get("database")

        contexts = target_info.get("liquibase_contexts")
        if not contexts:
            # Fallback to the host name itself if no explicit context was provided,
            # allowing scripts to target specific clusters cleanly.
            contexts = host

        if not host or not db:
            print("Missing host or database in config.")
            continue

        url = f"jdbc:redshift://{host}:{port}/{db}"

        print(f"\n--- Running Liquibase {action} on {host} (Contexts: {contexts}) ---")

        cmd = [
            "liquibase",
            f"--url={url}",
            f"--username={username}",
            f"--password={password}",
            f"--changeLogFile={changelog_path}",
            f"--contexts={contexts}",
            action,
        ]

        try:
            # We don't want to capture output here if we want it to stream to jenkins logs
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Liquibase command failed for {host}")
            sys.exit(e.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Liquibase migrations for Redshift clusters.")
    parser.add_argument("config_path", help="Path to config.yaml")
    parser.add_argument("changelog_path", help="Path to changelog.yaml")
    parser.add_argument(
        "--target", help="Specific target host to run migrations against", default=None
    )

    args = parser.parse_args()

    # In jenkins ACTION is typically 'plan' or 'apply'
    jenkins_action = os.environ.get("ACTION", "plan")

    # Map jenkins actions to liquibase commands
    if jenkins_action == "apply":
        lb_action = "update"
    else:
        lb_action = "updateSQL"  # Dry run equivalent in liquibase

    run_liquibase(args.config_path, args.changelog_path, lb_action, args.target)
