import { isoDate } from './format';
import type { Frequency } from './types';

export function parseDay(text: string): number | null {
  if (!/^\d{1,2}$/.test(text.trim())) return null;
  const day = Number(text);
  return day >= 1 && day <= 31 ? day : null;
}

function clamped(year: number, monthIndex: number, day: number): Date {
  const last = new Date(year, monthIndex + 1, 0).getDate();
  return new Date(year, monthIndex, Math.min(day, last));
}

export function firstDue(frequency: Frequency, day: number, month: number | null): string {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (frequency === 'yearly' && month) {
    const candidate = clamped(start.getFullYear(), month - 1, day);
    const next = candidate >= start ? candidate : clamped(start.getFullYear() + 1, month - 1, day);
    return isoDate(next);
  }
  const candidate = clamped(start.getFullYear(), start.getMonth(), day);
  const next =
    candidate >= start ? candidate : clamped(start.getFullYear(), start.getMonth() + 1, day);
  return isoDate(next);
}
