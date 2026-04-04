"""Tests for the scheduler service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from clippertv.data.models import ClipperCard
from clippertv.scheduler.service import IngestionResult, main, run_ingestion

_SAMPLE_CARD = ClipperCard(
    id="card-1",
    user_id="user-1",
    account_number="1234",
    card_serial=None,
    rider_name="Alice Card",
    credentials_encrypted="encrypted-data",
    is_primary=True,
    created_at=datetime.now(),
)

_SAMPLE_CSV = (
    "ACCOUNT NUMBER,START DATE/TIME,END DATE/TIME,"
    "START LOCATION,END LOCATION,FARE,OPERATOR,PASS,TRIP ID\n"
    "1234,02/28/2026 21:16:16,02/28/2026 22:00:43,"
    "Fruitvale,16th Street / Mission,$5.35,BART,Cash Value,11047705\n"
)


def _mock_user_store():
    """Build a mock UserStore with one card."""
    store = MagicMock()
    store.get_all_cards_with_credentials.return_value = [_SAMPLE_CARD]
    store.get_decrypted_credentials.return_value = {
        "username": "alice@example.com",
        "password": "secret",
    }
    return store


@patch("clippertv.data.turso_store.TursoStore")
@patch("clippertv.scheduler.service.download_transactions")
@patch("clippertv.scheduler.service.login")
@patch("clippertv.scheduler.service._build_user_store")
def test_run_ingestion_success(mock_build, mock_login, mock_download, mock_turso):
    """Successful ingestion returns row count."""
    mock_build.return_value = _mock_user_store()
    mock_download.return_value = [{"path": "test.csv", "content": _SAMPLE_CSV}]
    mock_turso.return_value.save_csv_transactions.return_value = 1

    results = run_ingestion(days=30)

    assert len(results) == 1
    assert results[0].account == "alice@example.com"
    assert results[0].new_rows == 1
    assert results[0].error is None


@patch("clippertv.data.turso_store.TursoStore")
@patch("clippertv.scheduler.service.login")
@patch("clippertv.scheduler.service._build_user_store")
def test_run_ingestion_login_failure(mock_build, mock_login, mock_turso):
    """Login failure is captured as an error, not raised."""
    mock_build.return_value = _mock_user_store()
    mock_login.side_effect = RuntimeError("bad credentials")

    results = run_ingestion(days=30)

    assert len(results) == 1
    assert results[0].error == "bad credentials"
    assert results[0].new_rows == 0


@patch("clippertv.scheduler.service.login")
@patch("clippertv.scheduler.service._build_user_store")
def test_run_ingestion_dry_run(mock_build, mock_login):
    """Dry run validates login but skips download and store."""
    mock_build.return_value = _mock_user_store()

    results = run_ingestion(dry_run=True)

    assert len(results) == 1
    assert results[0].new_rows == 0
    assert results[0].error is None
    mock_login.assert_called_once()


@patch("clippertv.scheduler.service._build_user_store")
def test_run_ingestion_no_cards(mock_build):
    """No cards with credentials returns empty results."""
    store = MagicMock()
    store.get_all_cards_with_credentials.return_value = []
    mock_build.return_value = store

    results = run_ingestion()
    assert results == []


@patch("clippertv.scheduler.service.run_ingestion")
def test_cli_exit_code_success(mock_run):
    """CLI returns 0 when all accounts succeed."""
    mock_run.return_value = [IngestionResult(account="alice@example.com", new_rows=5)]
    assert main(["--days", "7"]) == 0


@patch("clippertv.scheduler.service.run_ingestion")
def test_cli_exit_code_failure(mock_run):
    """CLI returns 1 when any account fails."""
    mock_run.return_value = [
        IngestionResult(account="alice@example.com", new_rows=0, error="timeout"),
    ]
    assert main(["--days", "7"]) == 1
