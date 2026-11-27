import hashlib
from datetime import datetime

import pandas as pd

from caged_analytics import normalize as nz
from caged_analytics.pipeline import load_normalized
from caged_analytics.schema import CANONICAL_COLUMNS


def _xlsx(path, rows, columns, title_rows=0):
    frame = pd.DataFrame(rows, columns=columns)
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, index=False, startrow=title_rows)
    return path


def _codes(result):
    return {i.code for i in result.issues}


# ---------- funcoes de normalizacao ----------
def test_competencia_formatos():
    for value in (
        "2025-01",
        "01/2025",
        "202501",
        202501,
        "jan/25",
        "Janeiro/2025",
        "2025-01-31",
        datetime(2025, 1, 15),
        pd.Timestamp("2025-01-01"),
    ):
        assert nz.normalize_competencia(value) == "2025-01", value


def test_competencia_invalida():
    for value in ("2025-13", "abc", "", None, "13/2025", 2025.5):
        try:
            nz.normalize_competencia(value)
        except nz.NormalizationError:
            continue
        raise AssertionError(f"deveria falhar: {value!r}")


def test_municipio():
    assert nz.normalize_municipio_codigo(3538709) == "353870"
    assert nz.normalize_municipio_codigo("353870") == "353870"
    assert nz.normalize_municipio_nome("  são   JOSÉ dos campos ") == "São José dos Campos"
    assert nz.municipio_chave("São José dos Campos") == "SAO JOSE DOS CAMPOS"


def test_setor():
    assert nz.normalize_setor("C") == "C"
    assert nz.normalize_setor("g - Comércio") == "G"
    assert nz.normalize_setor("4711301") == "G"
    assert nz.normalize_setor("85") == "P"
    assert nz.normalize_setor("Construção") == "F"
    assert nz.normalize_setor("Indústrias de Transformação") == "C"


def test_numeros():
    assert nz.normalize_int("1.234") == 1234
    assert nz.normalize_int("-5") == -5
    assert nz.normalize_int(7.0) == 7
    assert nz.normalize_int("") is None


# ---------- leitura de planilhas ----------
def test_planilha_valida_com_apelidos_e_acentos(tmp_path):
    f = _xlsx(
        tmp_path / "caged_2025_01.xlsx",
        [
            [
                datetime(2025, 1, 1),
                3538709,
                "PIRACICABA",
                "SP",
                "C - Indústrias de transformação",
                100,
                80,
            ],
            ["02/2025", "353870", "piracicaba", "sp", "G", 50, 60],
        ],
        [
            "Competência",
            "Código do Município",
            "Município",
            "UF",
            "Seção",
            "Admissões",
            "Desligamentos",
        ],
    )
    result = load_normalized(f)
    assert result.ok and not result.issues
    assert list(result.data.columns) == list(CANONICAL_COLUMNS)
    assert result.data["competencia"].tolist() == ["2025-01", "2025-02"]
    assert result.data["municipio"].tolist() == ["Piracicaba", "Piracicaba"]
    assert result.data["municipio_codigo"].tolist() == ["353870", "353870"]
    assert result.data["saldo"].tolist() == [20, -10]  # calculado
    assert result.data["setor_codigo"].tolist() == ["C", "G"]


def test_cabecalho_apos_linhas_de_titulo(tmp_path):
    f = _xlsx(
        tmp_path / "tabela.xlsx",
        [["202503", "Campinas", "F", 10, 4, 6]],
        ["competenciamov", "municipio", "secao", "admissoes", "desligamentos", "saldo"],
        title_rows=3,
    )
    result = load_normalized(f)
    assert result.ok
    assert result.data.iloc[0]["competencia"] == "2025-03"


def test_coluna_municipio_com_codigo(tmp_path):
    f = _xlsx(
        tmp_path / "a.xlsx",
        [["2025-01", 3509502, "A", 5]],
        ["competencia", "municipio", "setor", "saldo"],
    )
    result = load_normalized(f)
    assert result.ok
    assert result.data.iloc[0]["municipio_codigo"] == "350950"


def test_colunas_ausentes_registra_erro_de_arquivo(tmp_path):
    f = _xlsx(
        tmp_path / "ruim.xlsx",
        [["2025-01", "Campinas", "C"]],
        ["competencia", "municipio", "setor"],
    )
    result = load_normalized(f)
    assert result.data.empty and "COLUNAS_AUSENTES" in _codes(result)
    assert result.files_failed == ["ruim.xlsx"]


def test_linhas_invalidas_sao_descartadas_e_registradas(tmp_path):
    f = _xlsx(
        tmp_path / "mista.xlsx",
        [
            ["2025-01", "Campinas", "C", 10, 5],
            ["2025-99", "Campinas", "C", 10, 5],  # competencia invalida
            ["2025-02", "", "C", 10, 5],  # municipio vazio
            ["2025-02", "Campinas", "ZZZ", 10, 5],  # setor desconhecido
            ["2025-02", "Campinas", "C", "dez", 5],  # numero invalido
        ],
        ["competencia", "municipio", "setor", "admissoes", "desligamentos"],
    )
    result = load_normalized(f)
    assert len(result.data) == 1
    errors = [i for i in result.issues if i.severity == "error"]
    assert {i.column for i in errors} == {"competencia", "municipio", "setor", "admissoes"}
    assert all(i.row is not None for i in errors)


def test_formato_nao_suportado_e_arquivo_inexistente(tmp_path):
    txt = tmp_path / "x.pdf"
    txt.write_text("nada")
    assert "FORMATO_NAO_SUPORTADO" in _codes(load_normalized(txt))
    assert "ARQUIVO_NAO_ENCONTRADO" in _codes(load_normalized(tmp_path / "nao_existe.xlsx"))


def test_arquivo_corrompido(tmp_path):
    f = tmp_path / "quebrado.xlsx"
    f.write_bytes(b"isto nao e um xlsx")
    result = load_normalized(f)
    assert "ERRO_DE_LEITURA" in _codes(result) and result.data.empty


def test_csv_latin1_com_ponto_e_virgula(tmp_path):
    f = tmp_path / "dados.csv"
    f.write_bytes(
        "competencia;município;seção;saldo\n2025-01;São Paulo;J;1.500\n".encode("latin-1")
    )
    result = load_normalized(f)
    assert result.ok
    assert result.data.iloc[0]["municipio"] == "São Paulo"
    assert result.data.iloc[0]["saldo"] == 1500


def test_pasta_mistura_arquivos_bons_e_ruins(tmp_path):
    _xlsx(
        tmp_path / "ok.xlsx",
        [["2025-01", "Campinas", "C", 3]],
        ["competencia", "municipio", "setor", "saldo"],
    )
    (tmp_path / "lixo.xlsx").write_bytes(b"x")
    result = load_normalized(tmp_path)
    assert result.files_read == ["ok.xlsx"] and result.files_failed == ["lixo.xlsx"]
    assert len(result.data) == 1


def test_original_nao_e_alterado(tmp_path):
    f = _xlsx(
        tmp_path / "raw.xlsx",
        [["2025-01", "Campinas", "C", 3]],
        ["competencia", "municipio", "setor", "saldo"],
    )
    before = hashlib.sha256(f.read_bytes()).hexdigest()
    load_normalized(f)
    assert hashlib.sha256(f.read_bytes()).hexdigest() == before


def test_saldo_inconsistente_gera_aviso(tmp_path):
    f = _xlsx(
        tmp_path / "s.xlsx",
        [["2025-01", "Campinas", "C", 10, 4, 99]],
        ["competencia", "municipio", "setor", "admissoes", "desligamentos", "saldo"],
    )
    result = load_normalized(f)
    assert len(result.data) == 1 and "SALDO_INCONSISTENTE" in _codes(result) and result.ok
