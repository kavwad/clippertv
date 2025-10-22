import io
from pathlib import Path

import pandas as pd

from clippertv.config import config
from clippertv.pdf import processor


def test_persist_pdf_from_path(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \nstartxref\n0\n%%EOF\n")
    destination = processor._persist_pdf(str(source), tmp_path / "cache", "001")

    assert destination.exists()
    assert destination.read_bytes().startswith(b"%PDF-1.4")


def test_persist_pdf_from_filelike(tmp_path):
    buffer = io.BytesIO(b"%PDF-1.4\nstub\n%%EOF\n")
    buffer.name = "uploaded.pdf"

    destination = processor._persist_pdf(buffer, tmp_path / "cache", "002")

    assert destination.exists()
    assert destination.read_bytes().startswith(b"%PDF-1.4")


def test_process_pdf_statements_from_path(monkeypatch, tmp_path):
    pdf_path = tmp_path / "download.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nstub\n%%EOF\n")

    sample_df = pd.DataFrame(
        {
            "Transaction Date": [pd.Timestamp("2024-06-01 10:00", tz="US/Pacific")],
            "Location": ["ACT bus"],
            "Transaction Type": ["Threshold auto-load at a TransLink Device"],
            "Route": ["NONE"],
            "Category": [None],
            "Debit": [None],
            "Credit": [None],
            "Balance": [None],
        }
    )

    def fake_extract(path: str):
        assert Path(path).exists()
        return sample_df.copy()

    def fake_cleanup(df: pd.DataFrame):
        return df

    class DummyStore:
        def __init__(self):
            self.added = None

        def load_data(self, rider_id):
            return pd.DataFrame()

        def add_transactions(self, rider_id, df: pd.DataFrame):
            self.added = df
            return df

    dummy_store = DummyStore()

    monkeypatch.setattr(processor, "extract_trips_from_pdf", fake_extract)
    monkeypatch.setattr(processor, "clean_up_extracted_data", fake_cleanup)
    monkeypatch.setattr(processor, "get_data_store", lambda: dummy_store)

    original_cache_dir = config.pdf_local_cache_dir
    config.pdf_local_cache_dir = str(tmp_path / "cache")

    try:
        result = processor.process_pdf_statements([str(pdf_path)], "B")
    finally:
        config.pdf_local_cache_dir = original_cache_dir

    assert result is dummy_store.added
    assert len(result) == 1
    assert result["Category"].iloc[0] == "Reload"
    assert getattr(result["Transaction Date"].dtype, "tz", None) is None

    stored_files = list((tmp_path / "cache").glob("*.pdf"))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes().startswith(b"%PDF")


def test_process_pdf_statements_handles_extraction_error(monkeypatch, tmp_path, capsys):
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nstub\n%%EOF\n")

    def boom(path: str):
        raise RuntimeError("parse failure")

    monkeypatch.setattr(processor, "extract_trips_from_pdf", boom)
    monkeypatch.setattr(processor, "clean_up_extracted_data", lambda df: df)
    monkeypatch.setattr(processor, "get_data_store", lambda: None)

    result = processor.process_pdf_statements([str(pdf_path)], "B")
    assert result is None

    captured = capsys.readouterr()
    assert "Failed to extract data" in captured.err
