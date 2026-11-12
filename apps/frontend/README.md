# Frontend

Espaco reservado para a interface web de pesquisas e comparacoes do CAGED.
O framework sera escolhido posteriormente. Nao ha aplicacao web implementada.

A interface consumira o backend por HTTP e nao devera acessar diretamente as
planilhas. Processamento e regras de analise pertencem ao pacote Python
`packages/analytics`, exposto pela API em `apps/backend`.

Ao implementar a interface, defina tambem os contratos de consulta e a politica
de CORS do backend para as origens permitidas.