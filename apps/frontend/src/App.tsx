import { useDeferredValue, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { NavLink, Navigate, Route, Routes, useSearchParams } from 'react-router';
import {
  ArrowDownToLine, ArrowRightLeft, ChartNoAxesCombined, ChevronRight, Database,
  ExternalLink, Info, LayoutDashboard, LogOut, Menu,
  RotateCcw, Search, UserRound, X,
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
  const [accountPanel, setAccountPanel] = useState<'profile' | 'logout' | null>(null);
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
  const byCity = summarize(records, 'city').sort((first, second) => second.balance - first.balance);
  const bySector = summarize(records, 'sector').sort((first, second) => second.balance - first.balance);
  const grouped = (comparison || dimension === 'city' ? byCity : bySector);
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
        <div className={styles.brand} aria-label="CAGED"><ChartNoAxesCombined size={18} /><span>CAGED</span></div>
        <nav className={styles.railNav} aria-label="Navegacao principal">
          <NavLink end title="Visao geral" aria-label="Visao geral" to={{ pathname: '/', search: params.toString() }} onClick={() => setMobileMenu(false)} className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}><LayoutDashboard size={19} /><span>Visao geral</span></NavLink>
          <NavLink title="Comparar municipios" aria-label="Comparar municipios" to={{ pathname: '/comparar', search: params.toString() }} onClick={() => setMobileMenu(false)} className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}><ArrowRightLeft size={19} /><span>Comparar municipios</span></NavLink>
          <a className={styles.navLink} title="Fonte oficial do CAGED" aria-label="Fonte oficial do CAGED" href="https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/novo-caged" target="_blank" rel="noreferrer"><ExternalLink size={18} /><span>Fonte oficial</span></a>
          <button className={styles.navLink} type="button" title="Exportar CSV" aria-label="Exportar CSV" onClick={() => exportRows(tableRows)} disabled={!tableRows.length || invalidPeriod || isError}><ArrowDownToLine size={18} /><span>Exportar CSV</span></button>
        </nav>
        <div className={styles.sidebarBottom}>
          <button className={styles.navLink} title="Sair" aria-label="Sair" onClick={() => setAccountPanel('logout')}><LogOut size={18} /><span>Sair</span></button>
        </div>
      </aside>

      <div className={styles.page}>
        <header className={styles.topbar}>
          <button className={styles.menuButton} title="Abrir navegacao" aria-label="Abrir navegacao" onClick={() => setMobileMenu(true)}><Menu size={21} /></button>
          <div className={styles.breadcrumb}>Workspace<ChevronRight size={14} /><span>{comparison ? 'Comparacao' : 'Visao geral'}</span></div>
          <button className={styles.profileButton} title="Perfil" aria-label="Perfil" aria-expanded={accountPanel === 'profile'} onClick={() => setAccountPanel(accountPanel === 'profile' ? null : 'profile')}><UserRound size={19} /></button>
          {accountPanel && <div className={styles.accountPopover} role="status"><span>{accountPanel === 'profile' ? 'Autenticacao de perfil ainda nao configurada.' : 'Nenhuma sessao autenticada para encerrar.'}</span><button aria-label="Fechar aviso" onClick={() => setAccountPanel(null)}><X size={15} /></button></div>}
        </header>

        <main className={styles.main}>
          <div className={styles.dashboardHeader}>
            <div className={styles.heading}>
              <p className={styles.eyebrow}>EMPREGO FORMAL / SAO PAULO</p>
              <div className={styles.titleRow}><h1>{comparison ? 'Compare os municipios' : 'Mercado de trabalho'}</h1>{!comparison && <span className={styles.infoWrap}><button className={styles.infoButton} aria-label="Informacoes sobre a base de dados" aria-describedby="data-info-tooltip"><Info size={16} /></button><span id="data-info-tooltip" role="tooltip" className={styles.infoTooltip}>Base demonstrativa 2025. Valores ficticios; nao representam estatisticas oficiais do CAGED.</span></span>}</div>
              <p className={styles.subtitle}>{comparison ? 'Diferentes localidades, um mesmo recorte.' : 'Um olhar sobre os movimentos do emprego formal.'}</p>
            </div>
          </div>

          <div className={styles.filterAnalyticsRow}>
            <section aria-label="Filtros da consulta" className={styles.filters}>
              <div className={styles.filterTitle}><span>Filtros</span><button title="Limpar filtros" aria-label="Limpar filtros" onClick={() => { setParams({}); setSearch(''); }}><RotateCcw size={15} /></button></div>
              <div className={styles.filterFields}>
                <div className={styles.dateFilters}>
                  <label>De<input aria-label="Periodo inicial" type="month" value={filters.start} onChange={(event) => setFilter('start', event.target.value)} /></label>
                  <label>Ate<input aria-label="Periodo final" type="month" value={filters.end} onChange={(event) => setFilter('end', event.target.value)} /></label>
                </div>
                <div className={`${styles.categoryFilters} ${comparison ? styles.singleCategory : ''}`}>
                  {!comparison && <label>Municipio<select aria-label="Municipio" value={filters.city} onChange={(event) => setFilter('city', event.target.value)}><option value="all">Todos os municipios</option>{cities.map((city) => <option key={city}>{city}</option>)}</select></label>}
                  <label>Atividade economica<select aria-label="Atividade economica" value={filters.sector} onChange={(event) => setFilter('sector', event.target.value)}><option value="all">Todos os setores</option>{sectors.map((sector) => <option key={sector}>{sector}</option>)}</select></label>
                </div>
              </div>
            </section>
            <section className={styles.metricStrip} aria-label="Indicadores do periodo">
              <article className={styles.metricSummary}><span>Saldo de empregos</span><strong>{signed(total.balance)}</strong></article>
              <article className={styles.metricSummary}><span>Admissoes</span><strong>{number.format(total.admissions)}</strong></article>
              <article className={styles.metricSummary}><span>Desligamentos</span><strong>{number.format(total.dismissals)}</strong></article>
            </section>
          </div>

          {comparison && <fieldset className={styles.cityPicker}><legend>Municipios na comparacao</legend>{cities.map((city) => <label key={city}><input type="checkbox" checked={selectedCities.includes(city)} onChange={(event) => setSelectedCities(event.target.checked ? [...selectedCities, city] : selectedCities.filter((value) => value !== city))} /><span>{city}</span></label>)}</fieldset>}

          {invalidPeriod ? <div role="alert" className={styles.empty}>Informe um periodo valido, com a data inicial anterior ou igual a final.</div>
            : isError ? <div role="alert" className={styles.empty}>Nao foi possivel carregar os dados.<button onClick={() => void refetch()}>Tentar novamente</button></div>
            : isPending ? <div role="status" className={styles.empty}>Carregando indicadores...</div>
            : !records.length ? <div className={styles.empty}><Database size={30} /><h2>Nenhum resultado neste recorte</h2><p>{comparison && !selectedCities.length ? 'Nenhum municipio selecionado.' : 'A base demonstrativa contem dados de janeiro a dezembro de 2025.'}</p><button onClick={() => { setParams({}); setSelectedCities(['Campinas', 'Sao Paulo']); }}>Restaurar consulta</button></div>
            : <>
              <div className={styles.resultMeta}><span><span className={styles.liveDot} />{period}</span><span>{comparison ? selectedCities.length : filters.city === 'all' ? cities.length : 1} municipios <span className={styles.metaDivider}>/</span> {filters.sector === 'all' ? '5 setores' : filters.sector}</span></div>
              <div className={styles.dashboardGrid}>
                <div className={styles.dashboardColumn}>
                  <section className={`${styles.chartSection} ${styles.panelCard}`} aria-labelledby="city-chart-title">
                    <div className={styles.sectionHeading}><div><h2 id="city-chart-title">Saldo por municipio</h2><p>Comparacao no mesmo periodo</p></div></div>
                    <div className={styles.chart} role="img" aria-label="Grafico de saldo por municipio; valores detalhados na tabela">
                      <ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={byCity} margin={{ top: 14, right: 8, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="#dedede" strokeDasharray="4 4" /><XAxis dataKey="name" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} interval={0} /><YAxis tickFormatter={(value: number) => compact.format(value)} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={43} /><Tooltip formatter={(value) => number.format(Number(value))} /><ReferenceLine y={0} stroke="#999" /><Bar name="Saldo" dataKey="balance" fill="#1a1a1a" radius={[4, 4, 0, 0]} maxBarSize={48} /></BarChart></ResponsiveContainer>
                    </div>
                  </section>

                  <section className={`${styles.tableSection} ${styles.panelCard}`} aria-labelledby="table-title">
                    <div className={styles.sectionHeading}><div><h2 id="table-title">{comparison ? 'Municipios lado a lado' : 'O recorte em detalhe'}<span className={styles.count}>{grouped.length}</span></h2><p>Valores acumulados / {period}</p></div>{!comparison && <div className={styles.segmented} aria-label="Agrupar tabela"><button aria-pressed={dimension === 'city'} onClick={() => setDimension('city')}>Municipios</button><button aria-pressed={dimension === 'sector'} onClick={() => setDimension('sector')}>Setores</button></div>}</div>
                    <div className={styles.tableToolbar}><label className={styles.search}><Search size={16} /><input aria-label="Pesquisar na tabela" placeholder={dimension === 'sector' && !comparison ? 'Buscar setor...' : 'Buscar municipio...'} value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button title="Limpar pesquisa" aria-label="Limpar pesquisa" onClick={() => setSearch('')}><X size={14} /></button>}</label><span>Ordenado por saldo</span></div>
                    <div className={styles.tableScroll}><table><caption className={styles.srOnly}>Dados demonstrativos agregados por {dimension === 'sector' && !comparison ? 'setor' : 'municipio'}</caption><thead><tr><th>{dimension === 'sector' && !comparison ? 'Atividade economica' : 'Municipio'}</th><th>Admissoes</th><th>Desligamentos</th><th>Saldo</th><th>Saldo / admissoes</th></tr></thead><tbody>{tableRows.map((row, index) => <tr key={row.name}><th scope="row"><span className={styles.rowIndex}>{String(index + 1).padStart(2, '0')}</span>{row.name}</th><td>{number.format(row.admissions)}</td><td>{number.format(row.dismissals)}</td><td><span className={row.balance >= 0 ? styles.positive : styles.negative}>{signed(row.balance)}</span></td><td><span className={styles.shareBar}><span style={{ width: `${Math.min(100, Math.abs(row.balance / row.admissions * 100))}%` }} /></span>{(row.balance / row.admissions * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%</td></tr>)}</tbody></table>{!tableRows.length && <p className={styles.noMatches}>Nenhum resultado para "{search}".</p>}</div>
                    <div className={styles.tableFooter}>{tableRows.length} de {grouped.length} resultados<span>Base simulada / sem dados oficiais</span></div>
                  </section>
                </div>

                <div className={styles.dashboardColumn}>
                  <section className={`${styles.chartSection} ${styles.panelCard}`} aria-labelledby="sector-chart-title">
                    <div className={styles.sectionHeading}><div><h2 id="sector-chart-title">Movimentacoes por setor</h2><p>Admissoes e desligamentos acumulados</p></div></div>
                    <div className={`${styles.chart} ${styles.sectorChart}`} role="img" aria-label="Grafico de movimentacoes por setor; tabela detalhada abaixo">
                      <ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={bySector} layout="vertical" margin={{ top: 10, right: 12, left: 2, bottom: 0 }}><CartesianGrid horizontal={false} stroke="#dedede" strokeDasharray="4 4" /><XAxis type="number" tickFormatter={(value: number) => compact.format(value)} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} /><YAxis type="category" dataKey="name" width={91} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip formatter={(value) => number.format(Number(value))} /><Legend iconType="circle" iconSize={7} /><Bar name="Admissoes" dataKey="admissions" fill="#1a1a1a" radius={[0, 4, 4, 0]} maxBarSize={14} /><Bar name="Desligamentos" dataKey="dismissals" fill="#a0a0a0" radius={[0, 4, 4, 0]} maxBarSize={14} /></BarChart></ResponsiveContainer>
                    </div>
                  </section>

                  <section className={`${styles.chartSection} ${styles.panelCard}`} aria-labelledby="monthly-chart-title">
                    <div className={styles.sectionHeading}><div><h2 id="monthly-chart-title">{comparison ? 'Evolucao conjunta' : 'O emprego ao longo do ano'}</h2><p>{comparison ? 'Movimentacao mensal das localidades selecionadas' : 'Movimentacao mensal no periodo'}</p></div>{!comparison && <div className={styles.segmented} aria-label="Indicador do grafico"><button aria-pressed={metric === 'balance'} onClick={() => setMetric('balance')}>Saldo</button><button aria-pressed={metric === 'movement'} onClick={() => setMetric('movement')}>Movimentacoes</button></div>}</div>
                    <div className={styles.chart} role="img" aria-label="Grafico de movimentacao mensal; valores detalhados abaixo">
                      <ResponsiveContainer width="100%" height="100%" minWidth={0}><LineChart data={monthly} margin={{ top: 16, right: 12, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="#dedede" strokeDasharray="4 4" /><XAxis dataKey="name" tickFormatter={monthLabel} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={18} /><YAxis tickFormatter={(value: number) => compact.format(value)} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={43} /><Tooltip labelFormatter={(value) => monthLabel(String(value))} formatter={(value) => number.format(Number(value))} /><ReferenceLine y={0} stroke="#999" />{metric === 'balance' ? <Line name="Saldo" dataKey="balance" stroke="#1a1a1a" strokeWidth={2.5} dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 5 }} /> : <><Legend iconType="circle" iconSize={7} /><Line name="Admissoes" dataKey="admissions" stroke="#1a1a1a" strokeWidth={2.5} dot={false} /><Line name="Desligamentos" dataKey="dismissals" stroke="#8a8a8a" strokeWidth={2.5} dot={false} /></>}</LineChart></ResponsiveContainer>
                    </div>
                    <details className={styles.accessibleData}><summary>Dados mensais</summary><div className={styles.tableScroll}><table><caption className={styles.srOnly}>Valores mensais do grafico</caption><thead><tr><th>Mes</th><th>Admissoes</th><th>Desligamentos</th><th>Saldo</th></tr></thead><tbody>{monthly.map((row) => <tr key={row.name}><th scope="row">{row.name}</th><td>{number.format(row.admissions)}</td><td>{number.format(row.dismissals)}</td><td>{signed(row.balance)}</td></tr>)}</tbody></table></div></details>
                  </section>
                </div>
              </div>
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