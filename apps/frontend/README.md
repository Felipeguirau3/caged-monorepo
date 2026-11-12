# Frontend

Painel React + TypeScript + Vite para consultas e comparacoes do CAGED.
Os dados atuais sao simulados, gerados de forma deterministica, e nao sao
estatisticas oficiais. A demonstracao cobre os 12 meses de 2025, quatro
municipios de Sao Paulo e cinco setores economicos.

## Execucao

Use Node.js 24 LTS. Na raiz do monorepo:

```powershell
npm ci
npm run dev
npm test
npm run build
```

O servidor local fica em http://127.0.0.1:5173, usando outra porta automaticamente
se necessario. Para escolher uma porta explicitamente:

```powershell
npm run dev --workspace @caged/frontend -- --port 5174
```

## Organizacao

- `src/main.tsx`: providers do TanStack Query e React Router.
- `src/App.tsx`: rotas `/` e `/comparar`, filtros, indicadores, graficos e tabelas.
- `src/App.module.css`: estilos responsivos e fontes locais.
- `src/data/labor.ts`: contrato dos dados, consultas simuladas e agregacoes.
- `src/data/labor.test.ts`: testes de filtros, saldo, cancelamento e CSV.

Os filtros de periodo, municipio e setor ficam na URL. A selecao dos municipios
na comparacao, a pesquisa na tabela e o modo dos graficos ficam em memoria.
A exportacao CSV respeita os filtros e a pesquisa da tabela, com codificacao
UTF-8 e separador ponto e virgula. O backend nao e necessario para a demonstracao.

## Integracao Futura

Substitua `queryLabor` pela chamada HTTP aos endpoints definidos com o backend,
preservando cancelamento e validacao dos dados recebidos. Defina o contrato real
a partir das planilhas antes de conectar as consultas. Nao remova o aviso de
dados simulados ate que a origem oficial esteja efetivamente integrada.

A interface nao deve ler as planilhas diretamente. Processamento e regras
de negocio pertencem ao pacote Python `packages/analytics`, exposto pela API
em `apps/backend`. Defina as origens permitidas no CORS do backend nessa etapa;
nao ha CORS ou endpoints novos no backend neste incremento.

## Publicacao

O build gera `apps/frontend/dist`. Configure a hospedagem para servir
`index.html` nas rotas do cliente, incluindo `/comparar`. As fontes sao
empacotadas localmente; nao ha dependencia de servicos externos de fontes.