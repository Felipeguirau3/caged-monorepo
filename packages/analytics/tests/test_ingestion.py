from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from caged_analytics.ingestion import load_excel


@pytest.mark.parametrize("sheet_name", [0, "dados"])
def test_load_excel(tmp_path: Path, sheet_name: str | int) -> None:
    expected = pd.DataFrame({"municipio": ["Campinas"], "saldo": [10]})
    path = tmp_path / "caged.xlsx"
    expected.to_excel(path, sheet_name="dados", index=False)

    result = load_excel(path, sheet_name=sheet_name)

    assert_frame_equal(result, expected)


def test_load_excel_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_excel(tmp_path / "missing.xlsx")
