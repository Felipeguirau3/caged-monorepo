"""Leitura, validacao e normalizacao das planilhas do CAGED.

Uso principal:

    from caged_analytics.pipeline import load_normalized

    result = load_normalized("data/raw")          # um arquivo ou uma pasta
    result.data      # DataFrame normalizado (colunas de schema.CANONICAL_COLUMNS)
    result.issues    # lista de problemas encontrados (arquivo, linha, coluna...)

Os arquivos em data/raw sao somente LIDOS, nunca alterados.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from . import normalize as nz
from .schema import (
    CANONICAL_COLUMNS,
    COLUMN_ALIASES,
    MUNICIPIO_COLUMNS,
    REQUIRED_DIMENSIONS,
    SETORES,
)

log = logging.getLogger(__name__)

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
CSV_EXTENSIONS = {".csv", ".txt"}
SUPPORTED_EXTENSIONS = EXCEL_EXTENSIONS | CSV_EXTENSIONS
HEADER_SEARCH_ROWS = 15

# codigos de problema
FILE_NOT_FOUND = "ARQUIVO_NAO_ENCONTRADO"
UNSUPPORTED_FORMAT = "FORMATO_NAO_SUPORTADO"
READ_ERROR = "ERRO_DE_LEITURA"
EMPTY_FILE = "ARQUIVO_VAZIO"
HEADER_NOT_FOUND = "CABECALHO_NAO_ENCONTRADO"
MISSING_COLUMNS = "COLUNAS_AUSENTES"
INVALID_VALUE = "VALOR_INVALIDO"
DUPLICATE_KEY = "CHAVE_DUPLICADA"
INCONSISTENT_SALDO = "SALDO_INCONSISTENTE"


@dataclass(frozen=True)
class IngestionIssue:
    file: str
    code: str
    message: str
    severity: str = "error"  # "error" (linha/arquivo descartado) ou "warning"
    sheet: str | None = None
    row: int | None = None  # linha na planilha (1 = primeira linha)
    column: str | None = None


@dataclass
class IngestionResult:
    data: pd.DataFrame
    issues: list[IngestionIssue] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    files_failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def issues_frame(self) -> pd.DataFrame:
        cols = ["file", "sheet", "row", "column", "severity", "code", "message"]
        return pd.DataFrame([asdict(i) for i in self.issues], columns=cols)


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in CANONICAL_COLUMNS}).astype(
        {"admissoes": "Int64", "desligamentos": "Int64", "saldo": "Int64"}
    )


# --- leitura bruta -----------------------------------------------------------
def _read_raw(path: Path, sheet_name: str | int) -> pd.DataFrame:
    """Le tudo como objeto, sem cabecalho (a deteccao do cabecalho vem depois)."""
    ext = path.suffix.lower()
    if ext in EXCEL_EXTENSIONS:
        return pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=object)
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(
                path, header=None, dtype=object, sep=None, engine="python", encoding=encoding
            )
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error  # type: ignore[misc]


def _map_header(cells: list[object]) -> dict[int, str]:
    """posicao da coluna -> nome canonico (primeira ocorrencia vence)."""
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for pos, cell in enumerate(cells):
        if pd.isna(cell):
            continue
        key = nz.slug(cell)
        for canonical, aliases in COLUMN_ALIASES.items():
            if key in aliases and canonical not in used:
                mapping[pos] = canonical
                used.add(canonical)
                break
    return mapping


def _find_header(raw: pd.DataFrame) -> tuple[int, dict[int, str]] | None:
    best: tuple[int, dict[int, str]] | None = None
    for idx in range(min(HEADER_SEARCH_ROWS, len(raw))):
        mapping = _map_header(raw.iloc[idx].tolist())
        if len(mapping) >= 3 and (best is None or len(mapping) > len(best[1])):
            best = (idx, mapping)
    return best


# --- normalizacao de um arquivo ---------------------------------------------
def _normalize_frame(
    table: pd.DataFrame, file: str, sheet: str | None, issues: list[IngestionIssue]
) -> pd.DataFrame:
    has_codigo = "municipio_codigo" in table.columns
    rows: list[dict] = []

    def fail(row_no: int, column: str, exc: Exception) -> None:
        issues.append(IngestionIssue(file, INVALID_VALUE, str(exc), "error", sheet, row_no, column))

    for row_no, rec in table.iterrows():
        row_no = int(row_no) + 1  # linha 1-based como aparece no Excel
        if rec.isna().all():
            continue  # linha totalmente em branco
        out: dict[str, object] = {}
        errors = 0

        def step(column: str, func, *args):
            nonlocal errors
            try:
                return func(*args)
            except nz.NormalizationError as exc:
                errors += 1
                fail(row_no, column, exc)
                return None

        out["competencia"] = step("competencia", nz.normalize_competencia, rec.get("competencia"))
        out["setor_codigo"] = step("setor", nz.normalize_setor, rec.get("setor"))

        codigo = nome = None
        errors_before = errors
        raw_cod = rec.get("municipio_codigo") if has_codigo else None
        raw_nome = rec.get("municipio") if "municipio" in table.columns else None
        if not nz._is_blank(raw_cod):
            codigo = step("municipio_codigo", nz.normalize_municipio_codigo, raw_cod)
        elif nz.looks_like_codigo(raw_nome):  # coluna "municipio" trazendo o codigo
            codigo = step("municipio", nz.normalize_municipio_codigo, raw_nome)
            raw_nome = None
        if not nz._is_blank(raw_nome):
            nome = step("municipio", nz.normalize_municipio_nome, raw_nome)
        if codigo is None and nome is None and errors == errors_before:
            errors += 1
            fail(row_no, "municipio", nz.NormalizationError("municipio nao informado"))
        out["municipio_codigo"] = codigo
        out["municipio"] = nome
        out["municipio_chave"] = nz.municipio_chave(nome) if nome else None

        try:
            out["uf"] = nz.normalize_uf(rec.get("uf")) if "uf" in table.columns else None
        except nz.NormalizationError as exc:
            out["uf"] = None
            issues.append(
                IngestionIssue(file, INVALID_VALUE, str(exc), "warning", sheet, row_no, "uf")
            )

        nums = {}
        for col in ("admissoes", "desligamentos", "saldo"):
            nums[col] = step(col, nz.normalize_int, rec.get(col)) if col in table.columns else None
        if (
            nums["saldo"] is None
            and nums["admissoes"] is not None
            and nums["desligamentos"] is not None
        ):
            nums["saldo"] = nums["admissoes"] - nums["desligamentos"]
        elif (
            None not in (nums["saldo"], nums["admissoes"], nums["desligamentos"])
            and nums["saldo"] != nums["admissoes"] - nums["desligamentos"]
        ):
            issues.append(
                IngestionIssue(
                    file,
                    INCONSISTENT_SALDO,
                    "saldo diferente de admissoes - desligamentos",
                    "warning",
                    sheet,
                    row_no,
                    "saldo",
                )
            )
        if nums["saldo"] is None and errors == 0:
            errors += 1
            fail(row_no, "saldo", nz.NormalizationError("saldo nao informado nem calculavel"))
        out.update(nums)

        if errors == 0:
            rows.append(out)

    if not rows:
        return empty_frame()
    frame = pd.DataFrame(rows)
    frame["setor"] = frame["setor_codigo"].map(SETORES)
    frame = frame.reindex(columns=list(CANONICAL_COLUMNS))
    for col in ("admissoes", "desligamentos", "saldo"):
        frame[col] = frame[col].astype("Int64")
    return frame


def _load_one(
    path: Path, sheet_name: str | int, issues: list[IngestionIssue]
) -> pd.DataFrame | None:
    name = path.name
    if not path.is_file():
        issues.append(IngestionIssue(name, FILE_NOT_FOUND, f"arquivo nao encontrado: {path}"))
        return None
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        issues.append(
            IngestionIssue(
                name,
                UNSUPPORTED_FORMAT,
                f"formato {path.suffix or '(sem extensao)'} nao suportado; "
                f"use {sorted(SUPPORTED_EXTENSIONS)}",
            )
        )
        return None
    try:
        raw = _read_raw(path, sheet_name)
    except Exception as exc:  # arquivo corrompido, aba inexistente, senha, etc.
        issues.append(IngestionIssue(name, READ_ERROR, f"{type(exc).__name__}: {exc}"))
        return None

    sheet = str(sheet_name) if path.suffix.lower() in EXCEL_EXTENSIONS else None
    raw = raw.dropna(how="all")
    if raw.empty:
        issues.append(IngestionIssue(name, EMPTY_FILE, "arquivo sem dados", sheet=sheet))
        return None

    found = _find_header(raw)
    if found is None:
        issues.append(
            IngestionIssue(
                name,
                HEADER_NOT_FOUND,
                f"nenhum cabecalho com colunas conhecidas nas primeiras "
                f"{HEADER_SEARCH_ROWS} linhas",
                sheet=sheet,
            )
        )
        return None
    header_pos, mapping = found
    present = set(mapping.values())

    missing = [c for c in REQUIRED_DIMENSIONS if c not in present]
    if not present.intersection(MUNICIPIO_COLUMNS):
        missing.append("municipio (ou municipio_codigo)")
    if "saldo" not in present and not {"admissoes", "desligamentos"} <= present:
        missing.append("saldo (ou admissoes + desligamentos)")
    if missing:
        issues.append(
            IngestionIssue(
                name,
                MISSING_COLUMNS,
                f"colunas obrigatorias ausentes: {', '.join(missing)}",
                sheet=sheet,
            )
        )
        return None

    table = raw.iloc[header_pos + 1 :, list(mapping)]
    table.columns = [mapping[p] for p in mapping]
    return _normalize_frame(table, name, sheet, issues)


# --- API publica -------------------------------------------------------------
def load_normalized(
    path: str | Path, *, sheet_name: str | int = 0, recursive: bool = False
) -> IngestionResult:
    """Le um arquivo ou todos os arquivos suportados de uma pasta e devolve os dados
    normalizados + a lista de problemas. Nunca levanta excecao por causa dos dados."""
    target = Path(path)
    issues: list[IngestionIssue] = []
    frames: list[pd.DataFrame] = []
    read: list[str] = []
    failed: list[str] = []

    if target.is_dir():
        pattern = "**/*" if recursive else "*"
        files = sorted(
            p
            for p in target.glob(pattern)
            if p.is_file()
            and p.suffix.lower() in SUPPORTED_EXTENSIONS
            and not p.name.startswith(("~$", "."))
        )
        if not files:
            issues.append(
                IngestionIssue(str(target), EMPTY_FILE, "nenhuma planilha suportada na pasta")
            )
    else:
        files = [target]

    for file in files:
        frame = _load_one(file, sheet_name, issues)
        if frame is None:
            failed.append(file.name)
        else:
            frames.append(frame)
            read.append(file.name)

    data = (
        pd.concat([f for f in frames if not f.empty], ignore_index=True)
        if any(not f.empty for f in frames)
        else empty_frame()
    )

    if not data.empty:
        key = ["competencia", "municipio_codigo", "municipio_chave", "setor_codigo"]
        dup = data.duplicated(subset=key, keep=False)
        if dup.any():
            issues.append(
                IngestionIssue(
                    ", ".join(read),
                    DUPLICATE_KEY,
                    f"{int(dup.sum())} linhas com a mesma competencia/municipio/setor (mantidas)",
                    "warning",
                )
            )
        data = data.sort_values(
            ["competencia", "municipio_chave", "setor_codigo"], ignore_index=True
        )

    for issue in issues:
        log.warning("%s [%s] %s (linha %s)", issue.file, issue.code, issue.message, issue.row)
    return IngestionResult(data, issues, read, failed)


def write_processed(
    result: IngestionResult, out_dir: str | Path, name: str = "caged_normalizado"
) -> Path:
    """Grava Parquet em data/processed e o relatorio de problemas em CSV."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result.issues_frame().to_csv(out / f"{name}_problemas.csv", index=False)
    parquet = out / f"{name}.parquet"
    result.data.to_parquet(parquet, index=False)
    return parquet
