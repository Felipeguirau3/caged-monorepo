"""Testes do leitor da planilha oficial 'Tabelas' (formato largo) com planilhas minimas."""

import hashlib
import os
from pathlib import Path

import pytest
from openpyxl import Workbook

from caged_analytics.tabelas import load_tabelas

NOTAS = ["Fonte: Novo Caged – MTE.", "* nota de rodape"]


def _sheet(wb, name, titulo, keys, rows, *, with_stock_dash=False):
    """Replica o layout real: margem na coluna A, titulo, cabecalho em 2 niveis,
    bloco Jan (4 colunas), Fev (5 colunas, com Variacao Relativa) e 'Acumulado'."""
    ws = wb.create_sheet(name)
    ws.cell(2, 2, titulo)
    for j, k in enumerate(keys):
        ws.cell(5, 2 + j, k)
    c0 = 2 + len(keys)
    ws.cell(5, c0, "Janeiro/2020")
    for j, s in enumerate(["Estoque", "Admissões", "Desligamentos", "Saldos"]):
        ws.cell(6, c0 + j, s)
    ws.cell(5, c0 + 4, "Fevereiro/2020")
    for j, s in enumerate(
        ["Estoque", "Admissões", "Desligamentos", "Saldos", "Variação Relativa (%)"]
    ):
        ws.cell(6, c0 + 4 + j, s)
    ws.cell(5, c0 + 9, "Acumulado do Ano (2026) - com ajustes")
    for j, s in enumerate(["Admissões", "Desligamentos", "Saldos", "Variação Relativa (%)"]):
        ws.cell(6, c0 + 9 + j, s)
    r = 7
    for row in rows:
        labels, jan, fev = row
        for j, v in enumerate(labels):
            ws.cell(r, 2 + j, v)
        for j, v in enumerate(jan):
            ws.cell(r, c0 + j, v)
        for j, v in enumerate(fev):
            ws.cell(r, c0 + 4 + j, v)
        for j in range(4):
            ws.cell(r, c0 + 9 + j, 999)  # bloco derivado: deve ser ignorado
        r += 1
    r += 2
    for n in NOTAS:
        ws.cell(r, 2, n)
        r += 1


def _workbook(path, ajustes=True, sem=()):
    wb = Workbook()
    wb.remove(wb.active)
    nm = (
        ("Tabela 8.1", "Tabela 6.1", "Tabela 7.1")
        if ajustes
        else ("Tabela 8", "Tabela 6", "Tabela 7")
    )
    if "municipio" not in sem:
        _sheet(
            wb,
            nm[0],
            "T8",
            ["\nUF", "\nCódigo do Município", "\nMunicípio"],
            [
                (
                    ["RO", 110001, "Ro-Alta Floresta D Oeste"],
                    [1000, 30, 20, 10],
                    [1010, 40, 30, 10, 1.0],
                ),
                (["AC", 120040, "Ac-Rio Branco"], [5000, 60, 35, 25], [5035, 70, 35, 35, 0.7]),
                (
                    ["Não identificado", 999999, "Não identificado"],
                    ["---", 10, 5, 5],
                    ["---", 10, 5, 5, None],
                ),
                (["Total", None, None], [6000, 100, 60, 40], [6045, 120, 70, 50, 0.7]),
            ],
        )
    if "setor" not in sem:
        _sheet(
            wb,
            nm[1],
            "T6",
            ["Grupamento de Atividades Econômicas e Seção CNAE 2.0"],
            [
                (["Total"], [6000, 100, 60, 40], [6045, 120, 70, 50, 0.7]),
                (
                    ["Agricultura, pecuária, produção florestal, pesca e aquicultura"],
                    [900, 40, 25, 15],
                    [920, 50, 30, 20, 2.0],
                ),
                (["Construção"], [5100, 55, 32, 23], [5125, 65, 38, 27, 0.5]),
                (["Não identificado***"], ["-", 5, 3, 2], ["-", 5, 2, 3, None]),
            ],
        )
    if "uf" not in sem:
        _sheet(
            wb,
            nm[2],
            "T7",
            ["Região e UF"],
            [
                (["Brasil"], [6000, 100, 60, 40], [6045, 120, 70, 50, 0.7]),
                (["Norte"], [1000, 30, 20, 10], [1010, 40, 30, 10, 1.0]),
                (["Rondônia"], [1000, 30, 20, 10], [1010, 40, 30, 10, 1.0]),
                (["Sudeste"], [5000, 60, 35, 25], [5035, 70, 35, 35, 0.7]),
                (["Minas Gerais"], [5000, 60, 35, 25], [5035, 70, 35, 35, 0.7]),
                (["Não identificado"], ["-", 10, 5, 5], ["-", 10, 5, 5, None]),
            ],
        )
    wb.save(path)
    return path


def _codes(res):
    return {i.code for i in res.issues}


def test_municipio(tmp_path):
    res = load_tabelas(_workbook(tmp_path / "t.xlsx"))
    m = res.municipio
    assert res.ok and not res.issues
    assert len(m) == 3 * 2  # 3 municipios (sem a linha Total) x 2 meses
    assert sorted(m["competencia"].unique()) == ["2020-01", "2020-02"]
    row = m[(m.competencia == "2020-02") & (m.municipio_codigo == "110001")].iloc[0]
    assert row["municipio"] == "Alta Floresta D Oeste"  # prefixo "Ro-" removido
    assert row["uf"] == "RO"
    assert (row["admissoes"], row["desligamentos"], row["saldo"], row["estoque"]) == (
        40,
        30,
        10,
        1010,
    )
    ni = m[m.municipio_codigo == "999999"]
    assert not ni["municipio_identificado"].any() and ni["estoque"].isna().all()
    assert "municipio_chave" not in m.columns


def test_bloco_acumulado_e_total_nao_entram(tmp_path):
    res = load_tabelas(_workbook(tmp_path / "t.xlsx"))
    assert (res.municipio["admissoes"] != 999).all()
    assert "Total" not in set(res.municipio["municipio"])


def test_setor_hierarquia(tmp_path):
    s = load_tabelas(_workbook(tmp_path / "t.xlsx")).setor
    agri = s[(s.setor_codigo == "A") & (s.competencia == "2020-01")].iloc[0]
    assert (agri["setor_nivel"], agri["setor_pai"], agri["saldo"]) == (1, "TOTAL", 15)
    assert set(s["setor_codigo"]) == {"TOTAL", "A", "F", "NI"}
    ni = s[s.setor_codigo == "NI"]
    assert ni["setor"].iloc[0] == "Não identificado"  # asteriscos removidos
    assert ni["estoque"].isna().all()  # "-" vira vazio sem gerar erro


def test_uf_niveis(tmp_path):
    u = load_tabelas(_workbook(tmp_path / "t.xlsx")).uf
    jan = u[u.competencia == "2020-01"].set_index("territorio")
    assert jan.loc["Brasil", "nivel"] == "brasil"
    assert jan.loc["Norte", "nivel"] == "regiao"
    assert (jan.loc["Minas Gerais", "uf"], jan.loc["Minas Gerais", "regiao"]) == ("MG", "Sudeste")
    assert jan.loc["Não identificado", "nivel"] == "nao_identificado"


def test_totais_conferem_quando_os_dados_estao_certos(tmp_path):
    res = load_tabelas(_workbook(tmp_path / "a.xlsx"))
    assert "TOTAL_NAO_CONFERE" not in _codes(res)


def test_divergencia_municipio_vs_brasil(tmp_path):
    f = _workbook(tmp_path / "c.xlsx")
    from openpyxl import load_workbook

    wb = load_workbook(f)
    wb["Tabela 8.1"].cell(7, 6, 31)  # Jan admissoes de Alta Floresta: 30 -> 31
    wb.save(f)
    res = load_tabelas(f)
    assert "TOTAL_NAO_CONFERE" in _codes(res) and res.ok


def test_valor_nao_numerico_vira_vazio_com_aviso(tmp_path):
    from openpyxl import load_workbook

    f = _workbook(tmp_path / "n.xlsx")
    wb = load_workbook(f)
    wb["Tabela 8.1"].cell(8, 6, "abc")  # Jan, admissoes de Rio Branco
    wb.save(f)
    res = load_tabelas(f, tabelas=("municipio",), verificar_totais=False)
    assert "VALOR_NAO_NUMERICO" in _codes(res) and res.ok
    rb = res.municipio[
        (res.municipio.competencia == "2020-01") & (res.municipio.municipio_codigo == "120040")
    ].iloc[0]
    assert rb["admissoes"] is not None and str(rb["admissoes"]) == "<NA>" and rb["saldo"] == 25


def test_sem_ajustes_usa_outras_abas(tmp_path):
    res = load_tabelas(_workbook(tmp_path / "s.xlsx", ajustes=False), com_ajustes=False)
    assert res.ok and not res.issues
    assert res.com_ajustes is False and len(res.municipio) == 6
    assert load_tabelas(
        tmp_path / "s.xlsx", com_ajustes=True
    ).municipio.empty  # abas 8.1 nao existem


def test_aba_ausente_nao_derruba_as_outras(tmp_path):
    res = load_tabelas(_workbook(tmp_path / "x.xlsx", sem=("setor",)))
    assert "ABA_AUSENTE" in _codes(res)
    assert res.setor.empty and len(res.municipio) == 6 and len(res.uf) > 0


def test_arquivo_inexistente_formato_e_corrompido(tmp_path):
    assert "ARQUIVO_NAO_ENCONTRADO" in _codes(load_tabelas(tmp_path / "nao.xlsx"))
    pdf = tmp_path / "a.pdf"
    pdf.write_text("x")
    assert "FORMATO_NAO_SUPORTADO" in _codes(load_tabelas(pdf))
    ruim = tmp_path / "ruim.xlsx"
    ruim.write_bytes(b"nao e excel")
    res = load_tabelas(ruim)
    assert "ERRO_DE_LEITURA" in _codes(res) and res.municipio.empty


def test_aba_sem_cabecalho_mensal(tmp_path):
    wb = Workbook()
    wb.active.title = "Tabela 8.1"
    wb.active.cell(5, 2, "algo")
    wb.active.cell(6, 2, "qualquer")
    f = tmp_path / "v.xlsx"
    wb.save(f)
    assert "CABECALHO_NAO_ENCONTRADO" in _codes(load_tabelas(f, tabelas=("municipio",)))


def test_original_nao_e_alterado(tmp_path):
    f = _workbook(tmp_path / "o.xlsx")
    antes = hashlib.sha256(f.read_bytes()).hexdigest()
    load_tabelas(f)
    assert hashlib.sha256(f.read_bytes()).hexdigest() == antes


# ---- planilha real (opcional: defina CAGED_XLSX ou coloque em data/raw) ----
REAL = Path(os.environ.get("CAGED_XLSX", "data/raw/3-tabelas_Agosto de 2026.xlsx"))


def test_planilha_real_valores_conhecidos():
    if not REAL.is_file():
        pytest.skip("planilha real nao disponivel")
    res = load_tabelas(REAL)
    assert res.ok and not res.issues
    assert res.municipio["competencia"].nunique() == 80  # 2020-01 .. 2026-08
    assert len(res.municipio) == 5572 * 80
    m = res.municipio
    alta = m[(m.competencia == "2020-01") & (m.municipio_codigo == "110001")].iloc[0]
    assert (alta["admissoes"], alta["desligamentos"], alta["saldo"]) == (62, 74, -12)
    tot = res.setor[
        (res.setor.setor_codigo == "TOTAL") & (res.setor.competencia == "2020-01")
    ].iloc[0]
    assert tot["admissoes"] == 1510012
    br = res.uf[(res.uf.nivel == "brasil") & (res.uf.competencia == "2020-01")].iloc[0]
    assert br["saldo"] == 112087
