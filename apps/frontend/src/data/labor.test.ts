import { describe, expect, it } from 'vitest';
import {
  comparePeriodTrend, defaultFilters, demoRecords, filterRecords, queryLabor, summarize, toCsv, totals,
} from './labor';

describe('consultas demonstrativas', () => {
  it('combina periodo, municipio e setor', () => {
    const rows = filterRecords(demoRecords, {
      start: '2025-03', end: '2025-05', city: 'Campinas', sector: 'Industria',
    });
    expect(rows).toHaveLength(3);
    expect(rows.every((row) => row.city === 'Campinas' && row.sector === 'Industria')).toBe(true);
    expect(rows.map((row) => row.month)).toEqual(['2025-03', '2025-04', '2025-05']);
  });

  it('mantem o saldo consistente em todas as agregacoes', () => {
    const total = totals(demoRecords);
    expect(total.balance).toBe(total.admissions - total.dismissals);
    const cities = summarize(demoRecords, 'city');
    expect(cities).toHaveLength(4);
    expect(cities.reduce((sum, city) => sum + city.balance, 0)).toBe(total.balance);
    expect(summarize(demoRecords, 'month')).toHaveLength(12);
  });

  it('compara a primeira e ultima competencia sem inventar uma base para periodos curtos', () => {
    const rows = [
      { name: '2025-01', admissions: 100, dismissals: 80, balance: 20 },
      { name: '2025-02', admissions: 120, dismissals: 90, balance: 30 },
      { name: '2025-03', admissions: 80, dismissals: 100, balance: -20 },
    ];

    expect(comparePeriodTrend(rows, 'admissions')).toEqual({
      direction: 'down', percentage: 0.2, start: '2025-01', end: '2025-03',
    });
    expect(comparePeriodTrend(rows, 'balance')).toEqual({
      direction: 'down', percentage: 2, start: '2025-01', end: '2025-03',
    });
    expect(comparePeriodTrend(rows.slice(0, 1), 'admissions')).toBeNull();
    expect(comparePeriodTrend([
      { name: '2025-01', admissions: 0, dismissals: 0, balance: 0 }, rows[1],
    ], 'admissions')).toBeNull();
  });

  it('retorna vazio sem inventar resultados fora do periodo', async () => {
    const rows = await queryLabor({ ...defaultFilters, start: '2026-01', end: '2026-12' });
    expect(rows).toEqual([]);
    expect(totals(rows)).toEqual({ admissions: 0, dismissals: 0, balance: 0 });
  });

  it('respeita o cancelamento de uma consulta', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(queryLabor(defaultFilters, controller.signal)).rejects.toThrow();
  });

  it('exporta valores e escapa aspas no CSV', () => {
    const csv = toCsv([{ name: 'Local "A"', admissions: 20, dismissals: 12, balance: 8 }]);
    expect(csv).toContain('"Local ""A""";20;12;8');
    expect(csv.startsWith('\uFEFF')).toBe(true);
  });
});