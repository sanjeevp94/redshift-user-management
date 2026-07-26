#!/usr/bin/env python3
import os
import sys
import yaml
import subprocess
import fire


def run_liquibase(config_path: str, changelog_path: str, target: str = None):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    # In jenkins ACTION is typically 'plan' or 'apply'
    jenkins_action = os.environ.get("ACTION", "plan")

    # Map jenkins actions to liquibase commands
    if jenkins_action == "apply":
        action = "update"
    else:
        action = "updateSQL"  # Dry run equivalent in liquibase

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

        if target and host != target:
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


def main():
    fire.Fire(run_liquibase)


if __name__ == "__main__":
    main()
