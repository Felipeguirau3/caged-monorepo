"""Funcoes puras de normalizacao (data, municipio, setor, numeros)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

import pandas as pd

from .schema import DIVISAO_PARA_SECAO, SETORES, UFS

_MESES = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}
_PEQUENAS = {"de", "da", "do", "das", "dos", "e"}


class NormalizationError(ValueError):
    """Valor que nao pode ser normalizado (vira um registro de erro)."""


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def slug(text: object) -> str:
    """'Código do Município ' -> 'codigo_do_municipio' (usado em cabecalhos)."""
    base = strip_accents(str(text)).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


def _is_blank(value: object) -> bool:
    return (
        value is None
        or (not isinstance(value, str) and pd.isna(value))
        or (isinstance(value, str) and not value.strip())
    )


# --- competencia -------------------------------------------------------------
def normalize_competencia(value: object) -> str:
    """Converte para 'YYYY-MM'. Aceita datetime, 202501, '2025-01', '01/2025',
    '2025/01', 'jan/25', 'jan/2025', '2025-01-31'."""
    if _is_blank(value):
        raise NormalizationError("competencia vazia")
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) != int(value):
            raise NormalizationError(f"competencia invalida: {value!r}")
        text = str(int(value))
    else:
        text = str(value).strip()

    t = strip_accents(text).lower()
    patterns = [
        (
            r"^(\d{4})[-/.]?(\d{1,2})(?:[-/.]\d{1,2})?(?:[ t]\d.*)?$",
            "ym",
        ),  # 2025-01, 202501, 2025-01-31
        (r"^(\d{1,2})[-/.](\d{4})$", "my"),  # 01/2025
        (r"^([a-z]{3})[a-z]*[-/. ]+(\d{2}|\d{4})$", "name"),  # jan/25, janeiro/2025
    ]
    year = month = None
    for pattern, kind in patterns:
        m = re.match(pattern, t)
        if not m:
            continue
        if kind == "ym":
            year, month = int(m[1]), int(m[2])
        elif kind == "my":
            month, year = int(m[1]), int(m[2])
        else:
            month = _MESES.get(m[1])
            year = int(m[2]) + (2000 if len(m[2]) == 2 else 0)
        break
    if year is None or month is None or not (1 <= month <= 12) or not (1900 <= year <= 2100):
        raise NormalizationError(f"competencia invalida: {value!r}")
    return f"{year:04d}-{month:02d}"


# --- municipio ---------------------------------------------------------------
def normalize_municipio_codigo(value: object) -> str:
    """Codigo IBGE de 7 digitos (ou 6) -> 6 digitos (padrao do CAGED)."""
    if _is_blank(value):
        raise NormalizationError("codigo de municipio vazio")
    if isinstance(value, float) and value == int(value):
        value = int(value)
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 7:
        digits = digits[:6]
    if len(digits) != 6:
        raise NormalizationError(f"codigo de municipio invalido: {value!r}")
    return digits


def looks_like_codigo(value: object) -> bool:
    return not _is_blank(value) and bool(re.fullmatch(r"\d{6,7}(\.0)?", str(value).strip()))


def normalize_municipio_nome(value: object) -> str:
    if _is_blank(value):
        raise NormalizationError("municipio vazio")
    words = re.sub(r"\s+", " ", str(value).strip()).lower().split(" ")
    out = [w if (i > 0 and w in _PEQUENAS) else w.capitalize() for i, w in enumerate(words)]
    return " ".join(out)


def municipio_chave(nome: str) -> str:
    return strip_accents(nome).upper()


def normalize_uf(value: object) -> str | None:
    if _is_blank(value):
        return None
    uf = str(value).strip().upper()
    if uf not in UFS:
        raise NormalizationError(f"UF invalida: {value!r}")
    return uf


# --- setor -------------------------------------------------------------------
_NOME_PARA_SECAO = {slug(nome): letra for letra, nome in SETORES.items()}


def normalize_setor(value: object) -> str:
    """Devolve a letra da secao CNAE (A..U).

    Aceita: 'C', 'C - Industrias de transformacao', '47' (divisao),
    '4711301' (subclasse/classe) ou o nome da secao.
    """
    if _is_blank(value):
        raise NormalizationError("setor vazio")
    text = str(value).strip()

    m = re.match(r"^([A-Za-z])\s*([-–:.)]|$)", text)
    if m and m[1].upper() in SETORES:
        return m[1].upper()

    digits = re.sub(r"\D", "", text)
    if digits and re.fullmatch(r"[\d.\-/\s]+", text):
        divisao = int(digits[:2]) if len(digits) >= 2 else int(digits)
        if len(digits) == 1:
            divisao = int(digits)
        if divisao in DIVISAO_PARA_SECAO:
            return DIVISAO_PARA_SECAO[divisao]
        raise NormalizationError(f"divisao CNAE desconhecida: {value!r}")

    key = slug(re.sub(r"^[A-Za-z]\s*[-–:.)]\s*", "", text))
    if key in _NOME_PARA_SECAO:
        return _NOME_PARA_SECAO[key]
    for nome_key, letra in _NOME_PARA_SECAO.items():  # prefixo (nomes truncados)
        if len(key) >= 6 and (nome_key.startswith(key) or key.startswith(nome_key)):
            return letra
    raise NormalizationError(f"setor desconhecido: {value!r}")


# --- numeros -----------------------------------------------------------------
def normalize_int(value: object) -> int | None:
    """Inteiro; aceita '1.234', '1234,0', '-5'. Vazio -> None."""
    if _is_blank(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) != int(value):
            raise NormalizationError(f"numero nao inteiro: {value!r}")
        return int(value)
    text = str(value).strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", text):
        text = text.replace(".", "")
    text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError as exc:
        raise NormalizationError(f"numero invalido: {value!r}") from exc
    if number != int(number):
        raise NormalizationError(f"numero nao inteiro: {value!r}")
    return int(number)
