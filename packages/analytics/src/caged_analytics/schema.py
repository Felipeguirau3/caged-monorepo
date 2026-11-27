"""Esquema canonico dos dados do CAGED usados pelo projeto.

Cada linha representa: uma competencia (mes) x um municipio x um setor,
com os totais de admissoes, desligamentos e saldo.
"""

from __future__ import annotations

# Colunas da saida normalizada, na ordem final.
CANONICAL_COLUMNS: tuple[str, ...] = (
    "competencia",  # str "YYYY-MM"
    "municipio_codigo",  # str com 6 digitos (codigo IBGE sem digito verificador) ou <NA>
    "municipio",  # nome padronizado (Title Case)
    "municipio_chave",  # nome sem acento, MAIUSCULO (chave para junções/filtros)
    "uf",  # sigla com 2 letras ou <NA>
    "setor_codigo",  # secao CNAE: letra A..U
    "setor",  # nome da secao CNAE
    "admissoes",  # Int64
    "desligamentos",  # Int64
    "saldo",  # Int64 (admissoes - desligamentos, se nao vier na planilha)
)

# Nomes alternativos aceitos para cada coluna canonica (ja normalizados:
# minusculo, sem acento, com "_" no lugar de espacos/pontuacao).
COLUMN_ALIASES: dict[str, set[str]] = {
    "competencia": {
        "competencia",
        "competenciamov",
        "competencia_movimentacao",
        "competencia_declarada",
        "mes",
        "mes_ano",
        "periodo",
        "data",
        "ano_mes",
    },
    "municipio_codigo": {
        "municipio_codigo",
        "codigo_municipio",
        "cod_municipio",
        "codmun",
        "cod_ibge",
        "codigo_ibge",
        "cd_municipio",
        "id_municipio",
        "codigo_do_municipio",
        "cod_do_municipio",
        "codigo_municipio_ibge",
        "municipio_ibge",
    },
    "municipio": {"municipio", "nome_municipio", "municipio_nome", "cidade"},
    "uf": {"uf", "sigla_uf", "estado", "unidade_federativa"},
    "setor": {
        "setor",
        "secao",
        "secao_cnae",
        "cnae_secao",
        "setor_atividade",
        "atividade_economica",
        "grupamento_de_atividade",
        "subclasse",
        "cnae",
    },
    "admissoes": {"admissoes", "admitidos", "admissao", "total_admissoes"},
    "desligamentos": {
        "desligamentos",
        "desligados",
        "demissoes",
        "desligamento",
        "total_desligamentos",
    },
    "saldo": {"saldo", "saldomovimentacao", "saldo_movimentacao", "saldo_empregos"},
}

# Para validar o cabecalho: obrigatorias (municipio pode vir como codigo OU nome).
REQUIRED_DIMENSIONS = ("competencia", "setor")
MUNICIPIO_COLUMNS = ("municipio_codigo", "municipio")

# --- Setores: secoes da CNAE 2.0 -------------------------------------------
SETORES: dict[str, str] = {
    "A": "Agricultura, pecuária, produção florestal, pesca e aquicultura",
    "B": "Indústrias extrativas",
    "C": "Indústrias de transformação",
    "D": "Eletricidade e gás",
    "E": "Água, esgoto, gestão de resíduos e descontaminação",
    "F": "Construção",
    "G": "Comércio; reparação de veículos automotores e motocicletas",
    "H": "Transporte, armazenagem e correio",
    "I": "Alojamento e alimentação",
    "J": "Informação e comunicação",
    "K": "Atividades financeiras, de seguros e serviços relacionados",
    "L": "Atividades imobiliárias",
    "M": "Atividades profissionais, científicas e técnicas",
    "N": "Atividades administrativas e serviços complementares",
    "O": "Administração pública, defesa e seguridade social",
    "P": "Educação",
    "Q": "Saúde humana e serviços sociais",
    "R": "Artes, cultura, esporte e recreação",
    "S": "Outras atividades de serviços",
    "T": "Serviços domésticos",
    "U": "Organismos internacionais e outras instituições extraterritoriais",
}

# Divisao CNAE (2 primeiros digitos) -> secao.
_DIVISOES = [
    (1, 3, "A"),
    (5, 9, "B"),
    (10, 33, "C"),
    (35, 35, "D"),
    (36, 39, "E"),
    (41, 43, "F"),
    (45, 47, "G"),
    (49, 53, "H"),
    (55, 56, "I"),
    (58, 63, "J"),
    (64, 66, "K"),
    (68, 68, "L"),
    (69, 75, "M"),
    (77, 82, "N"),
    (84, 84, "O"),
    (85, 85, "P"),
    (86, 88, "Q"),
    (90, 93, "R"),
    (94, 96, "S"),
    (97, 97, "T"),
    (99, 99, "U"),
]
DIVISAO_PARA_SECAO: dict[int, str] = {d: s for lo, hi, s in _DIVISOES for d in range(lo, hi + 1)}

UFS = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)
