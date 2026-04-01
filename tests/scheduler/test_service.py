"""Tests for the scheduler service."""

from unittest.mock import MagicMock, patch

import pandas as pd

from clippertv.scheduler.service import IngestionResult, main, run_ingestion

_SAMPLE_CONFIG = {
    "accounts": [
        {
            "name": "alice",
            "email": "alice@example.com",
            "password": "secret",
            "cards": ["1234"],
        },
    ],
}

_SAMPLE_CSV = (
    "ACCOUNT NUMBER,START DATE/TIME,END DATE/TIME,"
    "START LOCATION,END LOCATION,FARE,OPERATOR,PASS,TRIP ID\n"
    "1234,02/28/2026 21:16:16,02/28/2026 22:00:43,"
    "Fruitvale,16th Street / Mission,$5.35,BART,Cash Value,11047705\n"
)


@patch("clippertv.data.turso_store.TursoStore")
@patch("clippertv.scheduler.service.download_transactions")
@patch("clippertv.scheduler.service.login")
@patch("clippertv.scheduler.service._load_config", return_value=_SAMPLE_CONFIG)
def test_run_ingestion_success(
    mock_config, mock_login, mock_download, mock_store
):
    """Successful ingestion returns row count."""
    mock_download.return_value = [{"path": "test.csv", "content": _SAMPLE_CSV}]
    mock_store.return_value.save_csv_transactions.return_value = 1

    results = run_ingestion(days=30)

    assert len(results) == 1
    assert results[0].account == "alice"
    assert results[0].new_rows == 1
    assert results[0].error is None


@patch("clippertv.data.turso_store.TursoStore")
@patch("clippertv.scheduler.service.login")
@patch("clippertv.scheduler.service._load_config", return_value=_SAMPLE_CONFIG)
def test_run_ingestion_login_failure(mock_config, mock_login, mock_store):
    """Login failure is captured as an error, not raised."""
    mock_login.side_effect = RuntimeError("bad credentials")

    results = run_ingestion(days=30)

    assert len(results) == 1
    assert results[0].error == "bad credentials"
    assert results[0].new_rows == 0


@patch("clippertv.scheduler.service.login")
@patch("clippertv.scheduler.service._load_config", return_value=_SAMPLE_CONFIG)
def test_run_ingestion_dry_run(mock_config, mock_login):
    """Dry run validates login but skips download and store."""
    results = run_ingestion(dry_run=True)

    assert len(results) == 1
    assert results[0].new_rows == 0
    assert results[0].error is None
    mock_login.assert_called_once()


@patch("clippertv.scheduler.service._load_config", return_value={"accounts": []})
def test_run_ingestion_no_accounts(mock_config):
    """Empty config returns empty results."""
    results = run_ingestion()
    assert results == []


@patch("clippertv.scheduler.service.run_ingestion")
def test_cli_exit_code_success(mock_run):
    """CLI returns 0 when all accounts succeed."""
    mock_run.return_value = [IngestionResult(account="alice", new_rows=5)]
    assert main(["--days", "7"]) == 0


@patch("clippertv.scheduler.service.run_ingestion")
def test_cli_exit_code_failure(mock_run):
    """CLI returns 1 when any account fails."""
    mock_run.return_value = [
        IngestionResult(account="alice", new_rows=0, error="timeout"),
    ]
    assert main(["--days", "7"]) == 1
