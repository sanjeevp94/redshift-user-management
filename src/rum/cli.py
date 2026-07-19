import fire
from rich.console import Console
from rich.prompt import Confirm
from rum.compiler import compile_state
from rum.redshift import get_connection, fetch_live_state
from rum.diff import calculate_diff

console = Console()


class RumCLI:
    def _get_plan(self, config: str):
        # 1. Compile Desired State
        console.print(f"[bold blue]Loading configuration from {config}...[/bold blue]")
        target_info, desired_users, desired_roles, desired_user_roles, desired_role_grants = (
            compile_state(config)
        )

        # 2. Fetch Live State
        console.print("[bold blue]Connecting to Redshift and fetching live state...[/bold blue]")
        conn = get_connection(target_info)
        try:
            live_users, live_roles, live_user_roles, live_role_grants = fetch_live_state(conn)
        finally:
            conn.close()

        # 3. Calculate Diff
        console.print("[bold blue]Calculating diff...[/bold blue]")
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

        return target_info, sql_statements

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

    def plan(self, config: str = "config.yaml"):
        """Show the generated SQL plan based on config against live state."""
        target_info, sql_statements = self._get_plan(config)

        if not sql_statements:
            console.print(
                "[bold green]No changes needed. The live state matches the desired state.[/bold green]"
            )
            return

        console.print("[bold yellow]Plan:[/bold yellow]")
        for stmt in sql_statements:
            self._print_statement(stmt)

    def apply(self, config: str = "config.yaml", auto_approve: bool = False):
        """Apply the generated SQL plan to the database."""
        target_info, sql_statements = self._get_plan(config)

        if not sql_statements:
            console.print(
                "[bold green]No changes needed. The live state matches the desired state.[/bold green]"
            )
            return

        console.print("[bold yellow]Plan to apply:[/bold yellow]")
        for stmt in sql_statements:
            self._print_statement(stmt)

        if not auto_approve:
            if not Confirm.ask("[bold yellow]Do you want to apply these changes?[/bold yellow]"):
                console.print("[bold red]Apply cancelled.[/bold red]")
                return

        console.print("[bold blue]Applying changes to Redshift...[/bold blue]")
        conn = get_connection(target_info)
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                for stmt in sql_statements:
                    cur.execute(stmt)
            conn.commit()
            console.print("[bold green]Successfully applied all changes![/bold green]")
        except Exception as e:
            conn.rollback()
            console.print(
                f"[bold red]Error applying changes, rolled back transaction: {e}[/bold red]"
            )
        finally:
            conn.close()


def main():
    fire.Fire(RumCLI)


if __name__ == "__main__":
    main()
