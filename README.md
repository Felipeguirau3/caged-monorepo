# CAGED

Monorepo para extracao de planilhas, manipulacao e analise de dados do CAGED,
com uma API para futuras pesquisas e comparacoes pelo frontend.

## Estrutura

```text
apps/
  backend/                 API FastAPI e seus testes
    src/caged_api/
    tests/
  frontend/                Espaco reservado para a interface web
packages/
  analytics/               Pacote Python compartilhado de dados e analises
    src/caged_analytics/
    tests/
data/
  raw/                     Arquivos originais, sem alteracoes
  processed/               Dados tratados e exportacoes
notebooks/                 Analises exploratorias
.github/workflows/          Validacao automatica
```

## Requisitos

- Python 3.11 ou superior.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) para dependencias
  e gerenciamento do workspace.

Execute os comandos abaixo na raiz do repositorio:

```powershell
python -m pip install --user uv
uv sync --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

O arquivo `uv.lock` fixa as versoes resolvidas e deve ser versionado. Depois de
clonar o projeto, use `uv sync --all-packages --locked` para reproduzir o ambiente.
O ambiente virtual `.venv` e compartilhado pelos pacotes Python do workspace.

## Backend

```powershell
uv run uvicorn caged_api.main:app --reload --host 127.0.0.1 --port 8000
```

- API: http://127.0.0.1:8000
- Documentacao: http://127.0.0.1:8000/docs
- Verificacao de saude: http://127.0.0.1:8000/health

A API inicial disponibiliza somente a verificacao de saude. Os endpoints de
pesquisa e comparacao serao implementados apos definir o esquema dos dados.
Nao ha upload HTTP, banco de dados ou autenticacao nesta estrutura inicial.

## Pacote de Dados

`caged-analytics` concentra a logica reutilizavel, sem depender de FastAPI.
Inclui pandas, matplotlib, openpyxl, xlrd e pyarrow para planilhas, analises,
graficos e armazenamento colunar. O backend depende desse pacote pelo workspace.

```python
from caged_analytics.ingestion import load_excel

frame = load_excel("data/raw/caged.xlsx")
print(frame.head())
```

O leitor carrega uma unica aba, por indice ou nome (`sheet_name=0` por padrao).
Ele ainda nao valida colunas, normaliza valores ou aplica regras do CAGED.
Planilhas grandes sao carregadas em memoria; a estrategia de processamento
devera ser definida a partir do volume real dos arquivos.

## Dados do CAGED

Consulte [data/README.md](data/README.md) antes de adicionar arquivos. Os dados
originais e processados ficam fora do Git por padrao. Para entrega pelo proprio
repositorio, configure Git LFS antes de liberar o versionamento dos originais.

## Frontend e Exploracao

`apps/frontend` esta reservado para a interface, sem impor um framework neste
momento. `notebooks` recebe exploracoes; logica reutilizavel deve ir para
`packages/analytics`. Jupyter e dependencias de frontend ainda nao sao instalados.

## Validacao

A integracao continua executa os testes e o Ruff em Python 3.11 e 3.14.
Os testes criam planilhas temporarias e nao dependem dos arquivos reais do CAGED.