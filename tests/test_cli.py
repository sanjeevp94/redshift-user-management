from unittest.mock import patch, MagicMock
from rum.cli import RumCLI


@patch("rum.cli.compile_state")
@patch("rum.cli.get_connection")
@patch("rum.cli.fetch_live_state")
@patch("rum.cli.calculate_diff")
def test_cli_plan_redacts_password(mock_calc, mock_fetch, mock_conn, mock_compile, capsys):
    mock_compile.return_value = [
        {
            "target_info": {"host": "fake_cluster"},
            "desired_users": set(),
            "desired_roles": set(),
            "desired_user_roles": set(),
            "desired_role_grants": set(),
        }
    ]

    mock_conn_inst = MagicMock()
    mock_conn.return_value = mock_conn_inst

    mock_fetch.return_value = (set(), set(), set(), set())

    mock_calc.return_value = ["CREATE USER \"rum_user_john\" PASSWORD 'S3cr3tP@ssw0rd!';"]

    cli = RumCLI()
    cli.plan("dummy.yaml")

    captured = capsys.readouterr()
    assert "PASSWORD '***REDACTED***'" in captured.out
    assert "S3cr3t" not in captured.out


@patch("rum.cli.compile_state")
@patch("rum.cli.get_connection")
@patch("rum.cli.fetch_live_state")
@patch("rum.cli.calculate_diff")
def test_cli_apply_auto_approve(mock_calc, mock_fetch, mock_conn, mock_compile):
    mock_compile.return_value = [
        {
            "target_info": {"host": "fake_cluster"},
            "desired_users": set(),
            "desired_roles": set(),
            "desired_user_roles": set(),
            "desired_role_grants": set(),
        }
    ]

    mock_conn_inst = MagicMock()
    mock_cur_inst = MagicMock()
    mock_conn_inst.cursor.return_value.__enter__.return_value = mock_cur_inst
    mock_conn.return_value = mock_conn_inst

    mock_fetch.return_value = (set(), set(), set(), set())

    mock_calc.return_value = ['GRANT ROLE "rum_role_a" TO "rum_user_b";']

    cli = RumCLI()
    cli.apply("dummy.yaml", auto_approve=True)

    mock_cur_inst.execute.assert_called_with('GRANT ROLE "rum_role_a" TO "rum_user_b";')
    mock_conn_inst.commit.assert_called_once()
    mock_conn_inst.close.assert_called()
