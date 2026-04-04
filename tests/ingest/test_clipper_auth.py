"""Tests for Clipper credential validation and card discovery."""

from unittest.mock import patch

from clippertv.ingest.clipper import validate_and_discover

_SAMPLE_CSV = (
    "ACCOUNT NUMBER,START DATE/TIME,END DATE/TIME,"
    "START LOCATION,END LOCATION,FARE,OPERATOR,PASS,TRIP ID\n"
    "100005510894,02/28/2026 21:16:16,02/28/2026 22:00:43,"
    "Fruitvale,16th Street / Mission,$5.35,BART,Cash Value,11047705\n"
    "100005510902,02/28/2026 21:16:16,02/28/2026 22:00:43,"
    "Powell,Embarcadero,$2.50,Muni,Cash Value,11047706\n"
)


@patch("clippertv.ingest.clipper.download_csv")
@patch("clippertv.ingest.clipper.login")
def test_validate_success_with_cards(mock_login, mock_download):
    """Successful validation returns sorted account numbers."""
    mock_download.return_value = _SAMPLE_CSV

    result = validate_and_discover("user@example.com", "password")

    assert result == ["100005510894", "100005510902"]
    mock_login.assert_called_once()


@patch("clippertv.ingest.clipper.login")
def test_validate_login_failure(mock_login):
    """Failed Clipper login returns None."""
    mock_login.side_effect = RuntimeError("bad creds")

    result = validate_and_discover("user@example.com", "wrong")
    assert result is None


@patch("clippertv.ingest.clipper.download_csv")
@patch("clippertv.ingest.clipper.login")
def test_validate_empty_csv(mock_login, mock_download):
    """Login succeeds but no transactions in either window returns empty list."""
    mock_download.return_value = ""

    result = validate_and_discover("user@example.com", "password")
    assert result == []
    # Should have tried both 7-day and 30-day windows
    assert mock_download.call_count == 2


@patch("clippertv.ingest.clipper.download_csv")
@patch("clippertv.ingest.clipper.login")
def test_validate_csv_download_failure(mock_login, mock_download):
    """Login succeeds but CSV download fails returns empty list (not None)."""
    mock_download.side_effect = RuntimeError("504 timeout")

    result = validate_and_discover("user@example.com", "password")
    assert result == []


@patch("clippertv.ingest.clipper.download_csv")
@patch("clippertv.ingest.clipper.login")
def test_validate_deduplicates_accounts(mock_login, mock_download):
    """Multiple transactions for same account return one entry."""
    csv = (
        "ACCOUNT NUMBER,START DATE/TIME,END DATE/TIME,"
        "START LOCATION,END LOCATION,FARE,OPERATOR,PASS,TRIP ID\n"
        "1234,02/28/2026 21:16:16,02/28/2026 22:00:43,"
        "Fruitvale,16th Street / Mission,$5.35,BART,Cash Value,11047705\n"
        "1234,02/27/2026 08:00:00,02/27/2026 08:30:00,"
        "Powell,Embarcadero,$2.50,BART,Cash Value,11047706\n"
    )
    mock_download.return_value = csv

    result = validate_and_discover("user@example.com", "password")
    assert result == ["1234"]
