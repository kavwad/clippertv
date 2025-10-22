from pathlib import Path

import pandas as pd

from clippertv.pdf import downloader


def test_group_pdfs_by_rider_matches_accounts():
    saved_files = [
        {"path": "/tmp/a.pdf", "card": {"serial": "111", "nickname": "A"}},
        {"path": "/tmp/b.pdf", "card": {"serial": "222", "nickname": "B"}},
        {"path": "/tmp/c.pdf", "card": {"serial": "333", "nickname": "C"}},
    ]
    rider_accounts = {"X": ["111", "999"], "Y": ["222"]}

    grouped, unmatched = downloader.group_pdfs_by_rider(saved_files, rider_accounts)

    assert grouped["X"] == ["/tmp/a.pdf"]
    assert grouped["Y"] == ["/tmp/b.pdf"]
    assert unmatched == ["333"]


def test_process_downloaded_pdfs_calls_processor(monkeypatch, tmp_path):
    pdf1 = tmp_path / "clipper-111.pdf"
    pdf2 = tmp_path / "clipper-222.pdf"
    pdf1.write_text("pdf1")
    pdf2.write_text("pdf2")

    saved_files = [
        {"path": str(pdf1), "card": {"serial": "111", "nickname": "A"}},
        {"path": str(pdf2), "card": {"serial": "222", "nickname": "B"}},
    ]
    rider_accounts = {"X": ["111"], "Y": ["222"]}

    calls = []

    def fake_process(paths, rider_id):
        calls.append((rider_id, tuple(paths)))
        return pd.DataFrame({"Transaction Date": [pd.Timestamp("2024-01-01")]})

    monkeypatch.setattr(downloader, "process_pdf_statements", fake_process)

    downloader.process_downloaded_pdfs(saved_files, rider_accounts)

    assert ("X", (str(pdf1),)) in calls
    assert ("Y", (str(pdf2),)) in calls
