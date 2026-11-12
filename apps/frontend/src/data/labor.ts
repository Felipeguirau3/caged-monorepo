export const cities = ['Campinas', 'Sao Paulo', 'Santos', 'Ribeirao Preto'] as const;
export const sectors = ['Servicos', 'Comercio', 'Industria', 'Construcao', 'Agropecuaria'] as const;

export interface Filters {
  start: string;
  end: string;
  city: string;
  sector: string;
}

export interface LaborRecord {
  month: string;
  city: string;
  sector: string;
  admissions: number;
  dismissals: number;
  balance: number;
}

export interface Summary {
  name: string;
  admissions: number;
  dismissals: number;
  balance: number;
}

export interface PeriodTrend {
  direction: 'up' | 'down' | 'flat';
  percentage: number;
  start: string;
  end: string;
}

export const defaultFilters: Filters = {
  start: '2025-01', end: '2025-12', city: 'all', sector: 'all',
};

export const demoRecords: LaborRecord[] = Array.from({ length: 12 }, (_, monthIndex) =>
  cities.flatMap((city, cityIndex) => sectors.map((sector, sectorIndex) => {
    const scale = [1, 7, 0.45, 0.7][cityIndex];
    const admissions = Math.round((840 + sectorIndex * 183 + monthIndex * 37
      + ((monthIndex * 7 + sectorIndex * 11) % 13) * 29) * scale);
    const dismissals = Math.round(admissions * (monthIndex === 11 ? 1.14 :
      0.76 + ((monthIndex + sectorIndex * 3) % 7) * 0.027));
    return {
      month: `2025-${String(monthIndex + 1).padStart(2, '0')}`,
      city, sector, admissions, dismissals, balance: admissions - dismissals,
    };
  })),
).flat();

export function filterRecords(records: LaborRecord[], filters: Filters): LaborRecord[] {
  return records.filter((record) => record.month >= filters.start && record.month <= filters.end
    && (filters.city === 'all' || record.city === filters.city)
    && (filters.sector === 'all' || record.sector === filters.sector));
}

export function summarize(records: LaborRecord[], group: 'month' | 'city' | 'sector'): Summary[] {
  const grouped = new Map<string, Summary>();
  for (const record of records) {
    const name = record[group];
    const summary = grouped.get(name) ?? { name, admissions: 0, dismissals: 0, balance: 0 };
    summary.admissions += record.admissions;
    summary.dismissals += record.dismissals;
    summary.balance += record.balance;
    grouped.set(name, summary);
  }
  return [...grouped.values()].sort((first, second) => first.name.localeCompare(second.name));
}

export function comparePeriodTrend(
  rows: Summary[],
  metric: keyof Omit<Summary, 'name'>,
): PeriodTrend | null {
  if (rows.length < 2) return null;

  const first = rows[0];
  const last = rows[rows.length - 1];
  if (first[metric] === 0) return null;

  const difference = last[metric] - first[metric];
  return {
    direction: difference > 0 ? 'up' : difference < 0 ? 'down' : 'flat',
    percentage: Math.abs(difference / Math.abs(first[metric])),
    start: first.name,
    end: last.name,
  };
}

export function totals(records: LaborRecord[]): Omit<Summary, 'name'> {
  return records.reduce((total, record) => ({
    admissions: total.admissions + record.admissions,
    dismissals: total.dismissals + record.dismissals,
    balance: total.balance + record.balance,
  }), { admissions: 0, dismissals: 0, balance: 0 });
}

export async function queryLabor(filters: Filters, signal?: AbortSignal): Promise<LaborRecord[]> {
  signal?.throwIfAborted();
  return filterRecords(demoRecords, filters);
}

export function toCsv(rows: Summary[]): string {
  const header = 'Localidade;Admissoes;Desligamentos;Saldo';
  return '\uFEFF' + [header, ...rows.map((row) =>
    `"${row.name.replaceAll('"', '""')}";${row.admissions};${row.dismissals};${row.balance}`,
  )].join('\r\n');
}