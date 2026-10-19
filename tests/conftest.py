"""Shared test setup.

The `built` fixture generates fresh synthetic data and runs the whole
pipeline inside a temporary folder, so tests never overwrite the files
committed in data/ and reports/.
"""

import pytest

from src import generate_data, pipeline


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("build")
    raw_dir = base / "raw"
    processed_dir = base / "processed"
    db_path = base / "warehouse.db"
    report_path = base / "data_quality_report.md"

    generate_data.generate(raw_dir)
    result = pipeline.run_pipeline(raw_dir, processed_dir, db_path, report_path, verbose=False)

    result["raw_dir"] = raw_dir
    result["processed_dir"] = processed_dir
    result["db_path"] = db_path
    result["report_path"] = report_path
    return result
