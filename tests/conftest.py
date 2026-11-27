from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "samples"))

import generate_samples  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def samples_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("samples")
    generate_samples.main(str(out))
    return out


@pytest.fixture(scope="session")
def complex_bytes(samples_dir) -> bytes:
    return (samples_dir / "suivi_achats_2019.xlsm").read_bytes()


@pytest.fixture(scope="session")
def simple_bytes(samples_dir) -> bytes:
    return (samples_dir / "planning_equipe.xlsx").read_bytes()


@pytest.fixture(scope="session")
def legacy_bytes(samples_dir) -> bytes:
    return (samples_dir / "inventaire_2004.xls").read_bytes()


def openpyxl_bytes(build) -> bytes:
    """Construit un classeur openpyxl via `build(wb)` et renvoie ses octets."""
    from openpyxl import Workbook

    wb = Workbook()
    build(wb)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def xlsxwriter_bytes(build, vba: bool = False) -> bytes:
    import xlsxwriter

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    build(wb)
    if vba:
        wb.add_vba_project(str(FIXTURES / "vbaProject.bin"))
    wb.close()
    return buf.getvalue()
