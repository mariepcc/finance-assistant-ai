import { env } from './env';
import { supabase } from './supabase';
import type {
  Category,
  ConfirmResult,
  Profile,
  Transaction,
  TransactionFilters,
  TransactionInput,
  TransactionPage,
  TransactionType,
} from './types';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export function detailMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return 'Nieprawidłowe dane formularza';
  return `Błąd serwera (${status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const res = await fetch(`${env.apiUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (res.status === 204) return undefined as T;
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailMessage(body, res.status));
  return body as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    (e): e is [string, string | number] => e[1] !== undefined && e[1] !== '',
  );
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : '';
}

export const api = {
  me: () => request<Profile>('/me'),
  acceptConsent: (default_currency: string) =>
    request<Profile>('/me/consent', {
      method: 'POST',
      body: JSON.stringify({ accepted: true, default_currency }),
    }),
  categories: (kind?: TransactionType) => request<Category[]>(`/categories${query({ kind })}`),
  transactions: (filters: TransactionFilters, cursor?: string) =>
    request<TransactionPage>(`/transactions${query({ ...filters, cursor, limit: 50 })}`),
  transaction: (id: string) => request<Transaction>(`/transactions/${id}`),
  createTransaction: (input: TransactionInput) =>
    request<Transaction>('/transactions', { method: 'POST', body: JSON.stringify(input) }),
  updateTransaction: (id: string, input: Partial<TransactionInput>) =>
    request<Transaction>(`/transactions/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
  deleteTransaction: (id: string) => request<void>(`/transactions/${id}`, { method: 'DELETE' }),
  confirmProposal: (id: string) =>
    request<ConfirmResult>(`/proposals/${id}/confirm`, { method: 'POST' }),
  rejectProposal: (id: string) => request<unknown>(`/proposals/${id}/reject`, { method: 'POST' }),
};
