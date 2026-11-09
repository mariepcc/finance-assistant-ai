import type { TransactionType } from './types';

const pad = (n: number) => String(n).padStart(2, '0');

export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function today(): string {
  return isoDate(new Date());
}

export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDate(d);
}

export function monthRange(offset = 0): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const last = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  return { from: isoDate(first), to: isoDate(last) };
}

export function isValidIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split('-').map(Number) as [number, number, number];
  const date = new Date(y, m - 1, d);
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d;
}

export function normalizeAmount(input: string): string | null {
  const cleaned = input.replace(/\s/g, '').replace(',', '.');
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(cleaned)) return null;
  const value = Number(cleaned);
  return value > 0 ? value.toFixed(2) : null;
}

const moneyFormatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(amount: string, currency: string, type?: TransactionType): string {
  let fmt = moneyFormatters.get(currency);
  if (!fmt) {
    fmt = new Intl.NumberFormat('pl-PL', { style: 'currency', currency });
    moneyFormatters.set(currency, fmt);
  }
  const sign = type === 'expense' ? '−' : type === 'income' ? '+' : '';
  return `${sign}${fmt.format(Number(amount))}`;
}

export function formatDayHeader(iso: string): string {
  if (iso === today()) return 'Dziś';
  if (iso === daysAgo(1)) return 'Wczoraj';
  const [y, m, d] = iso.split('-').map(Number) as [number, number, number];
  return new Date(y, m - 1, d).toLocaleDateString('pl-PL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
}
