import { useDeferredValue, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, NavLink, Navigate, Route, Routes, useSearchParams } from 'react-router';
import {
  ArrowDownLeft, ArrowDownToLine, ArrowRightLeft, ArrowUpRight, ChartNoAxesCombined,
  Check, ChevronRight, Database, ExternalLink, LayoutDashboard, Menu, RotateCcw,
  Search, SlidersHorizontal, X,
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  cities, defaultFilters, queryLabor, sectors, summarize, toCsv, totals,
  type Filters, type Summary,
} from './data/labor';
import styles from './App.module.css';

const number = new Intl.NumberFormat('pt-BR');
const compact = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 });
const monthFormat = new Intl.DateTimeFormat('pt-BR', { month: 'short', timeZone: 'UTC' });
const monthLabel = (month: string) => monthFormat.format(new Date(`${month}-01T00:00:00Z`)).replace('.', '');
const signed = (value: number) => `${value > 0 ? '+' : ''}${number.format(value)}`;

function exportRows(rows: Summary[]) {
  const url = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8;' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'caged-demonstrativo.csv';
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Dashboard({ comparison = false }: { comparison?: boolean }) {
  const [params, setParams] = useSearchParams();
  const [mobileMenu, setMobileMenu] = useState(false);
  const [metric, setMetric] = useState<'balance' | 'movement'>('balance');
  const [dimension, setDimension] = useState<'city' | 'sector'>('city');
  const [search, setSearch] = useState('');
  const [selectedCities, setSelectedCities] = useState<string[]>(['Campinas', 'Sao Paulo']);
  const deferredSearch = useDeferredValue(search);
  const filters: Filters = {
    start: params.get('start') || defaultFilters.start,
    end: params.get('end') || defaultFilters.end,
    city: comparison ? 'all' : params.get('city') || 'all',
    sector: params.get('sector') || 'all',
  };
  const validMonth = /^\d{4}-(0[1-9]|1[0-2])$/;
  const invalidPeriod = !validMonth.test(filters.start) || !validMonth.test(filters.end)
    || filters.start > filters.end;
  const { data = [], isPending, isError, refetch } = useQuery({
    queryKey: ['labor', filters],
    queryFn: ({ signal }) => queryLabor(filters, signal),
    enabled: !invalidPeriod,
  });
  const records = comparison ? data.filter((row) => selectedCities.includes(row.city)) : data;
  const total = totals(records);
  const monthly = summarize(records, 'month');
  const grouped = summarize(records, comparison ? 'city' : dimension)
    .sort((first, second) => second.balance - first.balance);
  const tableRows = grouped.filter((row) => row.name.toLocaleLowerCase('pt-BR')
    .includes(deferredSearch.toLocaleLowerCase('pt-BR')));
  const period = `${monthLabel(filters.start.match(validMonth) ? filters.start : '2025-01')}/${filters.start.slice(0, 4)} a ${monthLabel(filters.end.match(validMonth) ? filters.end : '2025-12')}/${filters.end.slice(0, 4)}`;

  function setFilter(key: keyof Filters, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  return (
    <div className={styles.app}>
      {mobileMenu && <button className={styles.scrim} aria-label="Fechar navegacao" onClick={() => setMobileMenu(false)} />}
      <aside className={`${styles.sidebar} ${mobileMenu ? styles.sidebarOpen : ''}`}>
        <Link className={styles.brand} to="/"><ChartNoAxesCombined size={29} /><span>CAGED<span className={styles.brandSub}>OBSERVATORIO DO TRABALHO</span></span></Link>
        <div className={styles.workspace}><span className={styles.workspaceIcon}><Database size={17} /></span><div>Mercado de trabalho<small>Brasil / Sao Paulo</small></div></div>
        <p className={styles.navLabel}>EXPLORAR</p>
        <nav aria-label="Navegacao principal">
          <NavLink end to={{ pathname: '/', search: params.toString() }} onClick={() => setMobileMenu(false)} className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}><LayoutDashboard size={18} />Visao geral</NavLink>
          <NavLink to={{ pathname: '/comparar', search: params.toString() }} onClick={() => setMobileMenu(false)} className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}><ArrowRightLeft size={18} />Comparar municipios</NavLink>
        </nav>
        <div className={styles.sidebarBottom}>
          <a href="https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/novo-caged" target="_blank" rel="noreferrer"><ExternalLink size={16} />Fonte oficial do CAGED</a>
          <div className={styles.projectMark}><span>CG</span><div>Projeto CAGED<small>Programacao II / Unicamp</small></div></div>
        </div>
      </aside>

      <div className={styles.page}>
        <header className={styles.topbar}>
          <button className={styles.menuButton} title="Abrir navegacao" aria-label="Abrir navegacao" onClick={() => setMobileMenu(true)}><Menu size={21} /></button>
          <div className={styles.breadcrumb}>Workspace<ChevronRight size={14} /><span>{comparison ? 'Comparacao' : 'Visao geral'}</span></div>
          <span className={styles.demoBadge}><span />Dados simulados</span>
        </header>

        <main className={styles.main}>
          <div className={styles.heading}>
            <div><p className={styles.eyebrow}>EMPREGO FORMAL / SAO PAULO</p><h1>{comparison ? 'Compare os municipios' : 'Mercado de trabalho'}</h1><p className={styles.subtitle}>{comparison ? 'Diferentes localidades, um mesmo recorte.' : 'Um olhar sobre os movimentos do emprego formal.'}</p></div>
            <button className={styles.exportButton} onClick={() => exportRows(tableRows)} disabled={!tableRows.length || invalidPeriod || isError}><ArrowDownToLine size={17} />Exportar CSV</button>
          </div>

          <div className={styles.demoNotice}><Database size={16} /><span>Base demonstrativa <strong>2025</strong><span className={styles.noticeDetail}> / Valores ficticios. Nao representam estatisticas oficiais do CAGED.</span></span></div>

          <section aria-label="Filtros da consulta" className={styles.filters}>
            <div className={styles.filterTitle}><SlidersHorizontal size={17} /><span>Filtros</span><button title="Limpar filtros" aria-label="Limpar filtros" onClick={() => { setParams({}); setSearch(''); }}><RotateCcw size={15} /></button></div>
            <label>De<input aria-label="Periodo inicial" type="month" value={filters.start} onChange={(event) => setFilter('start', event.target.value)} /></label>
            <label>Ate<input aria-label="Periodo final" type="month" value={filters.end} onChange={(event) => setFilter('end', event.target.value)} /></label>
            {!comparison && <label>Municipio<select aria-label="Municipio" value={filters.city} onChange={(event) => setFilter('city', event.target.value)}><option value="all">Todos os municipios</option>{cities.map((city) => <option key={city}>{city}</option>)}</select></label>}
            <label>Atividade economica<select aria-label="Atividade economica" value={filters.sector} onChange={(event) => setFilter('sector', event.target.value)}><option value="all">Todos os setores</option>{sectors.map((sector) => <option key={sector}>{sector}</option>)}</select></label>
          </section>

          {comparison && <fieldset className={styles.cityPicker}><legend>Municipios na comparacao</legend>{cities.map((city) => <label key={city}><input type="checkbox" checked={selectedCities.includes(city)} onChange={(event) => setSelectedCities(event.target.checked ? [...selectedCities, city] : selectedCities.filter((value) => value !== city))} /><span>{city}</span></label>)}</fieldset>}

          {invalidPeriod ? <div role="alert" className={styles.empty}>Informe um periodo valido, com a data inicial anterior ou igual a final.</div>
            : isError ? <div role="alert" className={styles.empty}>Nao foi possivel carregar os dados.<button onClick={() => void refetch()}>Tentar novamente</button></div>
            : isPending ? <div role="status" className={styles.empty}>Carregando indicadores...</div>
            : !records.length ? <div className={styles.empty}><Database size={30} /><h2>Nenhum resultado neste recorte</h2><p>{comparison && !selectedCities.length ? 'Nenhum municipio selecionado.' : 'A base demonstrativa contem dados de janeiro a dezembro de 2025.'}</p><button onClick={() => { setParams({}); setSelectedCities(['Campinas', 'Sao Paulo']); }}>Restaurar consulta</button></div>
            : <>
              <div className={styles.resultMeta}><span><span className={styles.liveDot} />{period}</span><span>{comparison ? selectedCities.length : filters.city === 'all' ? cities.length : 1} municipios <span className={styles.metaDivider}>/</span> {filters.sector === 'all' ? '5 setores' : filters.sector}</span></div>
              <section className={styles.metrics} aria-label="Indicadores do periodo">
                <article className={`${styles.metric} ${styles.balanceMetric}`}><div className={styles.metricLabel}>Saldo de empregos<span><ChartNoAxesCombined size={19} /></span></div><strong>{signed(total.balance)}</strong><small>Admissoes menos desligamentos</small><span className={styles.metricFoot}><Check size={14} />Resultado do periodo</span></article>
                <article className={styles.metric}><div className={styles.metricLabel}>Admissoes<span className={styles.admissionIcon}><ArrowUpRight size={20} /></span></div><strong>{number.format(total.admissions)}</strong><small>Vinculos de trabalho iniciados</small><span className={styles.neutralFoot}>Acumulado no periodo selecionado</span></article>
                <article className={styles.metric}><div className={styles.metricLabel}>Desligamentos<span className={styles.dismissalIcon}><ArrowDownLeft size={20} /></span></div><strong>{number.format(total.dismissals)}</strong><small>Vinculos de trabalho encerrados</small><span className={styles.neutralFoot}>Acumulado no periodo selecionado</span></article>
              </section>

              <section className={styles.chartSection} aria-labelledby="chart-title">
                <div className={styles.sectionHeading}><div><h2 id="chart-title">{comparison ? 'Saldo por municipio' : 'O emprego ao longo do ano'}</h2><p>{comparison ? 'Resultado acumulado no mesmo periodo' : 'Evolucao mensal / vinculos de trabalho'}</p></div>{!comparison && <div className={styles.segmented} aria-label="Indicador do grafico"><button aria-pressed={metric === 'balance'} onClick={() => setMetric('balance')}>Saldo</button><button aria-pressed={metric === 'movement'} onClick={() => setMetric('movement')}>Movimentacoes</button></div>}</div>
                <div className={styles.chart} role="img" aria-label={comparison ? 'Grafico de saldo por municipio; valores disponiveis na tabela abaixo' : 'Grafico de evolucao mensal do emprego; tabela mensal disponivel abaixo'}>
                  <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                    {comparison ? <BarChart data={grouped} margin={{ top: 16, right: 12, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="#e9edeb" strokeDasharray="4 4" /><XAxis dataKey="name" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} interval={0} /><YAxis tickFormatter={(value: number) => compact.format(value)} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={48} /><Tooltip formatter={(value) => number.format(Number(value))} /><ReferenceLine y={0} stroke="#b6c4bd" /><Bar name="Saldo" dataKey="balance" fill="#218565" radius={[4, 4, 0, 0]} maxBarSize={60} /></BarChart>
                      : <LineChart data={monthly} margin={{ top: 16, right: 16, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="#e9edeb" strokeDasharray="4 4" /><XAxis dataKey="name" tickFormatter={monthLabel} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={20} /><YAxis tickFormatter={(value: number) => compact.format(value)} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={48} /><Tooltip labelFormatter={(value) => monthLabel(String(value))} formatter={(value) => number.format(Number(value))} /><ReferenceLine y={0} stroke="#b6c4bd" />{metric === 'balance' ? <Line name="Saldo" dataKey="balance" stroke="#218565" strokeWidth={2.5} dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 5 }} /> : <><Legend iconType="circle" iconSize={7} /><Line name="Admissoes" dataKey="admissions" stroke="#218565" strokeWidth={2.5} dot={false} /><Line name="Desligamentos" dataKey="dismissals" stroke="#dc785c" strokeWidth={2.5} dot={false} /></>}</LineChart>}
                  </ResponsiveContainer>
                </div>
                {!comparison && <details className={styles.accessibleData}><summary>Dados mensais</summary><div className={styles.tableScroll}><table><caption className={styles.srOnly}>Valores mensais do grafico</caption><thead><tr><th>Mes</th><th>Admissoes</th><th>Desligamentos</th><th>Saldo</th></tr></thead><tbody>{monthly.map((row) => <tr key={row.name}><th scope="row">{row.name}</th><td>{number.format(row.admissions)}</td><td>{number.format(row.dismissals)}</td><td>{signed(row.balance)}</td></tr>)}</tbody></table></div></details>}
              </section>

              <section className={styles.tableSection} aria-labelledby="table-title"><div className={styles.sectionHeading}><div><h2 id="table-title">{comparison ? 'Municipios lado a lado' : 'O recorte em detalhe'}<span className={styles.count}>{grouped.length}</span></h2><p>Valores acumulados / {period}</p></div>{!comparison && <div className={styles.segmented} aria-label="Agrupar tabela"><button aria-pressed={dimension === 'city'} onClick={() => setDimension('city')}>Municipios</button><button aria-pressed={dimension === 'sector'} onClick={() => setDimension('sector')}>Setores</button></div>}</div>
                <div className={styles.tableToolbar}><label className={styles.search}><Search size={16} /><input aria-label="Pesquisar na tabela" placeholder={dimension === 'sector' && !comparison ? 'Buscar setor...' : 'Buscar municipio...'} value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button title="Limpar pesquisa" aria-label="Limpar pesquisa" onClick={() => setSearch('')}><X size={14} /></button>}</label><span>Ordenado por saldo</span></div>
                <div className={styles.tableScroll}><table><caption className={styles.srOnly}>Dados demonstrativos agregados por {dimension === 'sector' && !comparison ? 'setor' : 'municipio'}</caption><thead><tr><th>{dimension === 'sector' && !comparison ? 'Atividade economica' : 'Municipio'}</th><th>Admissoes</th><th>Desligamentos</th><th>Saldo</th><th>Saldo / admissoes</th></tr></thead><tbody>{tableRows.map((row, index) => <tr key={row.name}><th scope="row"><span className={styles.rowIndex}>{String(index + 1).padStart(2, '0')}</span>{row.name}</th><td>{number.format(row.admissions)}</td><td>{number.format(row.dismissals)}</td><td><span className={row.balance >= 0 ? styles.positive : styles.negative}>{signed(row.balance)}</span></td><td><span className={styles.shareBar}><span style={{ width: `${Math.min(100, Math.abs(row.balance / row.admissions * 100))}%` }} /></span>{(row.balance / row.admissions * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</td></tr>)}</tbody></table>{!tableRows.length && <p className={styles.noMatches}>Nenhum resultado para "{search}".</p>}</div>
                <div className={styles.tableFooter}>{tableRows.length} de {grouped.length} resultados<span>Base simulada / sem dados oficiais</span></div>
              </section>
            </>}
          <footer className={styles.footer}><span>CAGED<span className={styles.metaDivider}>/</span>Observatorio do trabalho</span><span>Projeto academico<span className={styles.metaDivider}>/</span>2025</span></footer>
        </main>
      </div>
    </div>
  );
}

export function App() {
  return <Routes><Route path="/" element={<Dashboard />} /><Route path="/comparar" element={<Dashboard comparison />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes>;
}