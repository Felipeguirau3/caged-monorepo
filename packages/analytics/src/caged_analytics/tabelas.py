"""Leitor da planilha oficial "Tabelas" do Novo CAGED (MTE) em formato largo.

A planilha traz varias abas; usamos as series mensais (2020 em diante):

    com ajustes (padrao)    sem ajustes
    Tabela 6.1  por setor     Tabela 6   (setor x mes)
    Tabela 7.1  por UF        Tabela 7   (regiao/UF x mes)
    Tabela 8.1  por municipio Tabela 8   (municipio x mes)

Cada aba tem um cabecalho em dois niveis ("Janeiro/2020" -> Estoque, Admissoes,
Desligamentos, Saldos...). Aqui ela e convertida para tabelas "longas" (uma linha
por mes x entidade) e validada. Os blocos "Acumulado do Ano" e "Ultimos 12 Meses"
e a coluna "Variacao Relativa" sao derivados e ficam de fora.

ATENCAO: a planilha NAO cruza municipio com setor. Sao tres series independentes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import normalize as nz
from .pipeline import (
    EMPTY_FILE,
    FILE_NOT_FOUND,
    HEADER_NOT_FOUND,
    MISSING_COLUMNS,
    READ_ERROR,
    UNSUPPORTED_FORMAT,
    IngestionIssue,
)

log = logging.getLogger(__name__)

SHEET_MISSING = "ABA_AUSENTE"
NON_NUMERIC = "VALOR_NAO_NUMERICO"
TOTAL_MISMATCH = "TOTAL_NAO_CONFERE"
UNKNOWN_LABEL = "ROTULO_DESCONHECIDO"

SHEETS = {  # (com ajustes, sem ajustes)
    "municipio": ("Tabela 8.1", "Tabela 8"),
    "setor": ("Tabela 6.1", "Tabela 6"),
    "uf": ("Tabela 7.1", "Tabela 7"),
}
METRICS = ("estoque", "admissoes", "desligamentos", "saldo")
_SUBHEADERS = {
    "estoque": "estoque",
    "admissoes": "admissoes",
    "desligamentos": "desligamentos",
    "saldos": "saldo",
    "saldo": "saldo",
}
_MONTH_CELL = re.compile(r"^\s*[A-Za-zÀ-ÿ]{3,}\s*/\s*\d{4}\s*$")
_HEADER_SEARCH_ROWS = 15

# --- setores (rotulos da planilha) -> (codigo, nivel, pai) --------------------
# Os rotulos formam uma hierarquia; somar todas as linhas conta em dobro!
_SETORES: dict[str, tuple[str, int, str | None]] = {
    "total": ("TOTAL", 0, None),
    "agricultura_pecuaria_producao_florestal_pesca_e_aquicultura": ("A", 1, "TOTAL"),
    "industria_geral": ("IND", 1, "TOTAL"),
    "industrias_extrativas": ("B", 2, "IND"),
    "industrias_de_transformacao": ("C", 2, "IND"),
    "eletricidade_e_gas": ("D", 2, "IND"),
    "agua_esgoto_atividades_de_gestao_de_residuos_e_descontaminacao": ("E", 2, "IND"),
    "construcao": ("F", 1, "TOTAL"),
    "comercio_reparacao_de_veiculos_automotores_e_motocicletas": ("G", 1, "TOTAL"),
    "servicos": ("SERV", 1, "TOTAL"),
    "transporte_armazenagem_e_correio": ("H", 2, "SERV"),
    "alojamento_e_alimentacao": ("I", 2, "SERV"),
    "informacao_comunicacao_e_atividades_financeiras_imobiliarias_profissionais_e_administrativas": (  # noqa: E501
        "SERV_INFO",
        2,
        "SERV",
    ),
    "informacao_e_comunicacao": ("J", 3, "SERV_INFO"),
    "atividades_financeiras_de_seguros_e_servicos_relacionados": ("K", 3, "SERV_INFO"),
    "atividades_imobiliarias": ("L", 3, "SERV_INFO"),
    "atividades_profissionais_cientificas_e_tecnicas": ("M", 3, "SERV_INFO"),
    "atividades_administrativas_e_servicos_complementares": ("N", 3, "SERV_INFO"),
    "administracao_publica_defesa_e_seguridade_social_educacao_saude_humana_e_servicos_sociais": (
        "SERV_ADM",
        2,
        "SERV",
    ),
    "administracao_publica_defesa_e_seguridade_social": ("O", 3, "SERV_ADM"),
    "educacao": ("P", 3, "SERV_ADM"),
    "saude_humana_e_servicos_sociais": ("Q", 3, "SERV_ADM"),
    "servicos_domesticos": ("T", 2, "SERV"),
    "outros_servicos": ("SERV_OUTROS", 2, "SERV"),
    "artes_cultura_esporte_e_recreacao": ("R", 3, "SERV_OUTROS"),
    "outras_atividades_de_servicos": ("S", 3, "SERV_OUTROS"),
    "organismos_internacionais_e_outras_instituicoes_extraterritoriais": ("U", 3, "SERV_OUTROS"),
    "nao_identificado": ("NI", 1, "TOTAL"),
}

_REGIOES = {"Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"}
_UF_SIGLA = {
    "Rondônia": "RO",
    "Acre": "AC",
    "Amazonas": "AM",
    "Roraima": "RR",
    "Pará": "PA",
    "Amapá": "AP",
    "Tocantins": "TO",
    "Maranhão": "MA",
    "Piauí": "PI",
    "Ceará": "CE",
    "Rio Grande do Norte": "RN",
    "Paraíba": "PB",
    "Pernambuco": "PE",
    "Alagoas": "AL",
    "Sergipe": "SE",
    "Bahia": "BA",
    "Minas Gerais": "MG",
    "Espírito Santo": "ES",
    "Rio de Janeiro": "RJ",
    "São Paulo": "SP",
    "Paraná": "PR",
    "Santa Catarina": "SC",
    "Rio Grande do Sul": "RS",
    "Mato Grosso do Sul": "MS",
    "Mato Grosso": "MT",
    "Goiás": "GO",
    "Distrito Federal": "DF",
}
_UF_REGIAO = {}
for _reg, _ufs in {
    "Norte": "RO AC AM RR PA AP TO",
    "Nordeste": "MA PI CE RN PB PE AL SE BA",
    "Sudeste": "MG ES RJ SP",
    "Sul": "PR SC RS",
    "Centro-Oeste": "MS MT GO DF",
}.items():
    for _u in _ufs.split():
        _UF_REGIAO[_u] = _reg


@dataclass
class TabelasResult:
    municipio: pd.DataFrame
    setor: pd.DataFrame
    uf: pd.DataFrame
    issues: list[IngestionIssue] = field(default_factory=list)
    com_ajustes: bool = True

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def issues_frame(self) -> pd.DataFrame:
        from dataclasses import asdict

        cols = ["file", "sheet", "row", "column", "severity", "code", "message"]
        return pd.DataFrame([asdict(i) for i in self.issues], columns=cols)


def _empty(extra: list[str]) -> pd.DataFrame:
    cols = ["competencia", *extra, *METRICS]
    frame = pd.DataFrame({c: pd.Series(dtype="object") for c in cols})
    return frame.astype({m: "Int64" for m in METRICS})


# --- leitura generica de uma aba larga --------------------------------------
def _wide_to_long(raw: pd.DataFrame, file: str, sheet: str, issues: list[IngestionIssue]):
    """Devolve (chaves: DataFrame, longo: DataFrame, linha_total: dict|None) ou None."""
    hdr_row = None
    for i in range(min(_HEADER_SEARCH_ROWS, len(raw))):
        if any(isinstance(c, str) and _MONTH_CELL.match(c) for c in raw.iloc[i].tolist()):
            hdr_row = i
            break
    if hdr_row is None:
        issues.append(
            IngestionIssue(
                file, HEADER_NOT_FOUND, "nenhum cabecalho 'Mes/Ano' encontrado", sheet=sheet
            )
        )
        return None
    hdr, sub = raw.iloc[hdr_row].tolist(), raw.iloc[hdr_row + 1].tolist()
    first_month = next(p for p, c in enumerate(hdr) if isinstance(c, str) and _MONTH_CELL.match(c))
    key_pos = [p for p in range(first_month) if pd.notna(hdr[p])]
    key_names = [nz.slug(hdr[p]) for p in key_pos]

    # blocos de mes: posicao inicial -> competencia
    starts = [p for p, c in enumerate(hdr) if pd.notna(c) and p >= first_month]
    blocks = []
    for k, p in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(hdr)
        cell = hdr[p]
        if not (isinstance(cell, str) and _MONTH_CELL.match(cell)):
            continue  # Acumulado do ano / Ultimos 12 meses
        try:
            comp = nz.normalize_competencia(cell)
        except nz.NormalizationError as exc:
            issues.append(IngestionIssue(file, INVALID, f"{exc}", "error", sheet, hdr_row + 1))
            continue
        cols = {}
        for q in range(p, end):
            name = _SUBHEADERS.get(nz.slug(sub[q])) if pd.notna(sub[q]) else None
            if name and name not in cols:
                cols[name] = q
        blocks.append((comp, cols))
    if not blocks:
        issues.append(
            IngestionIssue(file, HEADER_NOT_FOUND, "nenhum bloco mensal valido", sheet=sheet)
        )
        return None
    for need in ("admissoes", "desligamentos", "saldo"):
        if any(need not in c for _, c in blocks):
            issues.append(
                IngestionIssue(
                    file,
                    MISSING_COLUMNS,
                    f"coluna '{need}' ausente em algum bloco mensal",
                    "error",
                    sheet,
                )
            )
            return None

    body = raw.iloc[hdr_row + 2 :]
    first_key = body[key_pos[0]]
    stop = first_key.astype(str).str.startswith("Fonte").to_numpy().nonzero()[0]
    if len(stop):
        body = body.iloc[: stop[0]]
    body = body[body[key_pos].notna().any(axis=1)]
    keys = body[key_pos].copy()
    keys.columns = key_names
    keys["_linha"] = keys.index + 1  # linha na planilha (1-based)

    pieces, bad = [], {}
    for comp, cols in blocks:
        part = pd.DataFrame({"_idx": range(len(body))})
        part["competencia"] = comp
        for m in METRICS:
            if m in cols:
                col = body[cols[m]].reset_index(drop=True)
                num = pd.to_numeric(col, errors="coerce")
                weird = col[
                    num.isna() & col.notna() & ~col.astype(str).str.strip().str.fullmatch(r"-+")
                ]
                if len(weird):
                    bad.setdefault((m), []).extend(weird.astype(str).head(3).tolist())
                part[m] = (
                    num.astype("Int64")
                    if num.dropna().eq(num.dropna().round()).all()
                    else num.round().astype("Int64")
                )
            else:
                part[m] = pd.array([pd.NA] * len(body), dtype="Int64")
        pieces.append(part)
    for m, examples in bad.items():
        issues.append(
            IngestionIssue(
                file,
                NON_NUMERIC,
                f"valores nao numericos em '{m}': {examples[:3]}",
                "warning",
                sheet,
                column=m,
            )
        )
    long = pd.concat(pieces, ignore_index=True)
    return keys.reset_index(drop=True), long, key_names


INVALID = "VALOR_INVALIDO"


def _read_sheet(path: Path, sheet: str, issues: list[IngestionIssue]) -> pd.DataFrame | None:
    try:
        return pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    except ValueError as exc:
        code = SHEET_MISSING if "Worksheet" in str(exc) or "not found" in str(exc) else READ_ERROR
        issues.append(IngestionIssue(path.name, code, f"{sheet}: {exc}", sheet=sheet))
    except Exception as exc:  # noqa: BLE001 - arquivo corrompido etc.
        issues.append(
            IngestionIssue(path.name, READ_ERROR, f"{type(exc).__name__}: {exc}", sheet=sheet)
        )
    return None


def _assemble(
    keys: pd.DataFrame, long: pd.DataFrame, extra: pd.DataFrame, cols: list[str]
) -> pd.DataFrame:
    out = long.merge(extra.assign(_idx=range(len(extra))), on="_idx", how="left").drop(
        columns="_idx"
    )
    out = out[["competencia", *cols, *METRICS]]
    return out.sort_values(["competencia", *cols], ignore_index=True)


# --- tres tabelas -----------------------------------------------------------
def _municipio(raw, file, sheet, issues):
    res = _wide_to_long(raw, file, sheet, issues)
    if res is None:
        return _empty(["uf", "municipio_codigo", "municipio", "municipio_identificado"]), None
    keys, long, names = res
    if not {"uf", "codigo_do_municipio", "municipio"} <= set(names):
        issues.append(
            IngestionIssue(
                file,
                MISSING_COLUMNS,
                "esperado: UF, Codigo do Municipio, Municipio",
                "error",
                sheet,
            )
        )
        return _empty(["uf", "municipio_codigo", "municipio", "municipio_identificado"]), None
    total_row = keys[keys["uf"].astype(str).str.strip() == "Total"]
    ok = keys["codigo_do_municipio"].astype(str).str.fullmatch(r"\d{6}(\.0)?")

    for _, r in keys[~ok & ~keys.index.isin(total_row.index)].iterrows():
        issues.append(
            IngestionIssue(
                file,
                INVALID,
                f"linha sem codigo de municipio valido: {r['uf']!r}",
                "warning",
                sheet,
                int(r["_linha"]),
                "codigo_do_municipio",
            )
        )
    det = keys[ok].copy()
    det["municipio_codigo"] = det["codigo_do_municipio"].map(nz.normalize_municipio_codigo)
    ident = det["municipio_codigo"] != "999999"
    det["municipio_identificado"] = ident
    det["uf"] = pd.Series(
        [nz.normalize_uf(u) if i else None for u, i in zip(det["uf"], ident)],
        index=det.index,
        dtype="object",
    )
    nomes = []
    for uf, nome in zip(det["uf"], det["municipio"]):
        base = re.sub(r"^[A-Za-z]{2}-", "", str(nome).strip())  # "Ro-Ariquemes" -> "Ariquemes"
        nomes.append(nz.normalize_municipio_nome(base))
    det["municipio"] = nomes
    dup = det["municipio_codigo"].duplicated()
    if dup.any():
        issues.append(
            IngestionIssue(
                file,
                "CHAVE_DUPLICADA",
                f"{int(dup.sum())} codigos de municipio repetidos",
                "warning",
                sheet,
            )
        )
    long = long[long["_idx"].isin([keys.index.get_loc(i) for i in det.index])]
    pos = {keys.index.get_loc(i): n for n, i in enumerate(det.index)}
    long = long.assign(_idx=long["_idx"].map(pos))
    extra = det[["uf", "municipio_codigo", "municipio", "municipio_identificado"]].reset_index(
        drop=True
    )
    out = _assemble(keys, long, extra, list(extra.columns))
    return out, None


def _setor(raw, file, sheet, issues):
    res = _wide_to_long(raw, file, sheet, issues)
    cols = ["setor_codigo", "setor", "setor_nivel", "setor_pai"]
    if res is None:
        return _empty(cols)
    keys, long, names = res
    rows = []
    for _, r in keys.iterrows():
        label = re.sub(r"[\*\s]+$", "", str(r[names[0]]).strip())
        meta = _SETORES.get(nz.slug(label))
        if meta is None:
            issues.append(
                IngestionIssue(
                    file,
                    UNKNOWN_LABEL,
                    f"setor desconhecido: {label!r}",
                    "warning",
                    sheet,
                    int(r["_linha"]),
                )
            )
            meta = (None, None, None)
        rows.append(
            {"setor_codigo": meta[0], "setor": label, "setor_nivel": meta[1], "setor_pai": meta[2]}
        )
    extra = pd.DataFrame(rows)
    extra["setor_nivel"] = extra["setor_nivel"].astype("Int64")
    return _assemble(keys, long, extra, cols)


def _uf(raw, file, sheet, issues):
    res = _wide_to_long(raw, file, sheet, issues)
    cols = ["territorio", "nivel", "uf", "regiao"]
    if res is None:
        return _empty(cols)
    keys, long, names = res
    rows = []
    for _, r in keys.iterrows():
        nome = re.sub(r"[\*\s]+$", "", str(r[names[0]]).strip())
        if nome == "Brasil":
            nivel, uf, reg = "brasil", None, None
        elif nome in _REGIOES:
            nivel, uf, reg = "regiao", None, nome
        elif nome in _UF_SIGLA:
            uf = _UF_SIGLA[nome]
            nivel, reg = "uf", _UF_REGIAO[uf]
        elif nz.slug(nome) == "nao_identificado":
            nivel, uf, reg = "nao_identificado", None, None
        else:
            issues.append(
                IngestionIssue(
                    file,
                    UNKNOWN_LABEL,
                    f"territorio desconhecido: {nome!r}",
                    "warning",
                    sheet,
                    int(r["_linha"]),
                )
            )
            nivel, uf, reg = None, None, None
        rows.append({"territorio": nome, "nivel": nivel, "uf": uf, "regiao": reg})
    return _assemble(keys, long, pd.DataFrame(rows), cols)


# --- conferencia entre tabelas ----------------------------------------------
def _check_totals(res: TabelasResult, file: str) -> None:
    """Soma dos municipios e dos setores raiz deve bater com o total Brasil."""
    if res.uf.empty:
        return
    brasil = res.uf[res.uf["nivel"] == "brasil"].set_index("competencia")
    checks = []
    if not res.municipio.empty:
        checks.append(
            ("municipio", res.municipio.groupby("competencia")[list(METRICS[1:])].sum(min_count=1))
        )
    if not res.setor.empty:
        raiz = res.setor[res.setor["setor_codigo"] == "TOTAL"].set_index("competencia")
        checks.append(("setor (linha Total)", raiz[list(METRICS[1:])]))
    for name, soma in checks:
        for metric in METRICS[1:]:
            diff = (soma[metric].astype("float") - brasil[metric].astype("float")).abs()
            bad = diff[diff > 0].dropna()
            if len(bad):
                res.issues.append(
                    IngestionIssue(
                        file,
                        TOTAL_MISMATCH,
                        f"{name}: '{metric}' difere do total Brasil "
                        f"em {len(bad)} meses (ex.: {bad.index[0]})",
                        "warning",
                        column=metric,
                    )
                )


# --- API publica -------------------------------------------------------------
def load_tabelas(
    path: str | Path,
    *,
    com_ajustes: bool = True,
    tabelas: tuple[str, ...] = ("municipio", "setor", "uf"),
    verificar_totais: bool = True,
) -> TabelasResult:
    """Le a planilha oficial e devolve as series mensais normalizadas.

    com_ajustes=True usa as abas 6.1/7.1/8.1; False usa 6/7/8 (sem ajustes).

    Colunas de saida:
      municipio: competencia, uf, municipio_codigo (6 digitos), municipio,
                 municipio_identificado, estoque, admissoes, desligamentos, saldo
      setor:     competencia, setor_codigo, setor, setor_nivel, setor_pai, + metricas
      uf:        competencia, territorio, nivel, uf, regiao, + metricas

    SOMA DE SETORES: os setores formam uma hierarquia. Para somar, use apenas
    setor_nivel == 1 (grandes grupos) ou a linha setor_codigo == "TOTAL";
    somar todas as linhas conta em dobro. "Nao identificado" (NI) fica nos dados.
    Nunca levanta excecao por problemas de arquivo/formato: veja `result.issues`.
    """
    file = Path(path)
    issues: list[IngestionIssue] = []
    res = TabelasResult(
        _empty(["uf", "municipio_codigo", "municipio", "municipio_identificado"]),
        _empty(["setor_codigo", "setor", "setor_nivel", "setor_pai"]),
        _empty(["territorio", "nivel", "uf", "regiao"]),
        issues,
        com_ajustes,
    )
    if not file.is_file():
        issues.append(IngestionIssue(file.name, FILE_NOT_FOUND, f"arquivo nao encontrado: {file}"))
        return res
    if file.suffix.lower() not in {".xlsx", ".xlsm"}:
        issues.append(
            IngestionIssue(
                file.name, UNSUPPORTED_FORMAT, f"esperado .xlsx, recebido {file.suffix!r}"
            )
        )
        return res

    funcs = {"municipio": _municipio, "setor": _setor, "uf": _uf}
    for tabela in tabelas:
        sheet = SHEETS[tabela][0 if com_ajustes else 1]
        raw = _read_sheet(file, sheet, issues)
        if raw is None:
            continue
        raw = raw.dropna(how="all")
        if raw.empty:
            issues.append(IngestionIssue(file.name, EMPTY_FILE, "aba vazia", sheet=sheet))
            continue
        out = funcs[tabela](raw, file.name, sheet, issues)
        setattr(res, tabela, out[0] if isinstance(out, tuple) else out)
    if verificar_totais:
        _check_totals(res, file.name)
    for i in issues:
        log.warning("%s [%s] %s", i.file, i.code, i.message)
    return res
