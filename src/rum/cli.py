import fire
from rich.console import Console
from rich.prompt import Confirm
from rum.compiler import compile_state
from rum.redshift import get_connection, fetch_live_state
from rum.diff import calculate_diff

console = Console()


class RumCLI:
    def _get_plan(self, config: str, target: str = None):
        # 1. Compile Desired State
        target_msg = f" for target {target}" if target else ""
        console.print(f"[bold blue]Loading configuration from {config}{target_msg}...[/bold blue]")
        cluster_configs = compile_state(config, target_host=target)

        target_plans = []

        if not cluster_configs:
            console.print("[bold yellow]No target clusters configured![/bold yellow]")
            return target_plans

        for cluster_config in cluster_configs:
            target_info = cluster_config["target_info"]
            desired_users = cluster_config["desired_users"]
            desired_roles = cluster_config["desired_roles"]
            desired_user_roles = cluster_config["desired_user_roles"]
            desired_role_grants = cluster_config["desired_role_grants"]

            target_name = target_info.get("host", "Unknown Target")
            console.print(f"[bold blue]Connecting to Redshift target: {target_name}[/bold blue]")

            # 2. Fetch Live State
            conn = get_connection(target_info)
            try:
                live_users, live_roles, live_user_roles, live_role_grants = fetch_live_state(conn)
            finally:
                conn.close()

            # 3. Calculate Diff
            console.print(f"[bold blue]Calculating diff for {target_name}...[/bold blue]")
            sql_statements = calculate_diff(
                desired_users,
                desired_roles,
                desired_user_roles,
                desired_role_grants,
                live_users,
                live_roles,
                live_user_roles,
                live_role_grants,
            )

            target_plans.append({"target_info": target_info, "sql_statements": sql_statements})

        return target_plans

    def _print_statement(self, stmt: str):
        import re

        # Redact password if it's a CREATE USER statement
        display_stmt = stmt
        if display_stmt.startswith("CREATE USER") and "PASSWORD" in display_stmt:
            display_stmt = re.sub(r"PASSWORD '.*'", "PASSWORD '***REDACTED***'", display_stmt)

        if (
            display_stmt.startswith("REVOKE")
            or display_stmt.startswith("DROP")
            or (
                display_stmt.startswith("ALTER DEFAULT PRIVILEGES IN SCHEMA")
                and "REVOKE" in display_stmt
            )
        ):
            console.print(f"[bold red]  {display_stmt}[/bold red]")
        else:
            console.print(f"[bold green]  {display_stmt}[/bold green]")

    def plan(self, config: str = "config.yaml", target: str = None):
        """Show the generated SQL plan based on config against live state."""
        target_plans = self._get_plan(config, target)

        for plan_data in target_plans:
            target_name = plan_data["target_info"].get("host", "Unknown Target")
            sql_statements = plan_data["sql_statements"]

            console.print(f"\n[bold yellow]--- Plan for Target: {target_name} ---[/bold yellow]")

            if not sql_statements:
                console.print(
                    "[bold green]No changes needed. The live state matches the desired state.[/bold green]"
                )
                continue

            for stmt in sql_statements:
                self._print_statement(stmt)

    def apply(self, config: str = "config.yaml", auto_approve: bool = False, target: str = None):
        """Apply the generated SQL plan to the database."""
        target_plans = self._get_plan(config, target)

        # Print all plans first
        has_changes = False
        for plan_data in target_plans:
            target_name = plan_data["target_info"].get("host", "Unknown Target")
            sql_statements = plan_data["sql_statements"]

            console.print(
                f"\n[bold yellow]--- Plan to apply for Target: {target_name} ---[/bold yellow]"
            )

            if not sql_statements:
                console.print(
                    "[bold green]No changes needed. The live state matches the desired state.[/bold green]"
                )
                continue

            has_changes = True
            for stmt in sql_statements:
                self._print_statement(stmt)

        if not has_changes:
            return

        if not auto_approve:
            if not Confirm.ask(
                "\n[bold yellow]Do you want to apply these changes to all targeted clusters?[/bold yellow]"
            ):
                console.print("[bold red]Apply cancelled.[/bold red]")
                return

        for plan_data in target_plans:
            target_info = plan_data["target_info"]
            sql_statements = plan_data["sql_statements"]
            target_name = target_info.get("host", "Unknown Target")

            if not sql_statements:
                continue

            console.print(
                f"[bold blue]Applying changes to Redshift target: {target_name}...[/bold blue]"
            )
            conn = get_connection(target_info)
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    for stmt in sql_statements:
                        cur.execute(stmt)
                conn.commit()
                console.print(
                    f"[bold green]Successfully applied all changes to {target_name}![/bold green]"
                )
            except Exception as e:
                conn.rollback()
                console.print(
                    f"[bold red]Error applying changes to {target_name}, rolled back transaction: {e}[/bold red]"
                )
            finally:
                conn.close()


def main():
    fire.Fire(RumCLI)


if __name__ == "__main__":
    main()
