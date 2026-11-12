# Dados

- `raw/`: planilhas originais recebidas da pessoa responsavel pelo CAGED.
- `processed/`: dados tratados, tabelas intermediarias e exportacoes Parquet.

Preserve os originais. Transformacoes devem gerar novos arquivos em `processed/`.
Registre a origem oficial, competencia, data de obtencao e descricao das colunas
quando um conjunto de dados for disponibilizado.

## Entrega dos Arquivos

Os conteudos de `raw/` e `processed/` estao ignorados no Git para evitar commits
acidentais de dados grandes ou informacoes que nao devam ser publicadas.

Se os originais precisarem ser enviados pelo repositorio:

1. Confirme a permissao de redistribuicao e a ausencia de dados restritos.
2. Instale e configure Git LFS no repositorio e no servico de hospedagem.
3. Rastreie os formatos originais com Git LFS, como `data/raw/*.xlsx` e
   `data/raw/*.xls`, e versione o arquivo `.gitattributes` gerado.
4. Remova a regra `data/raw/*` do `.gitignore`, mantendo os processados ignorados.
5. Adicione e versione os originais somente depois dessa configuracao.

Git LFS nao esta configurado nesta estrutura inicial. Uma alternativa e manter
os arquivos em armazenamento externo e registrar aqui o procedimento de obtencao.