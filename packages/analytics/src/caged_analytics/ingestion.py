from pathlib import Path

import pandas as pd


def load_excel(path: str | Path, *, sheet_name: str | int = 0) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name)
