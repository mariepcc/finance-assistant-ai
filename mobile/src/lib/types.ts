
export type TransactionType = 'expense' | 'income';

export interface Profile {
  id: string;
  display_name: string | null;
  default_currency: string;
  gdpr_consent_at: string | null;
}

export interface Category {
  id: string;
  name: string;
  kind: TransactionType;
  icon: string | null;
  color: string | null;
  is_default: boolean;
}

export interface Transaction {
  id: string;
  type: TransactionType;
  amount: string;
  currency: string;
  category_id: string;
  occurred_on: string;
  note: string | null;
  source: 'manual' | 'assistant';
  created_at: string;
}

export interface TransactionPage {
  items: Transaction[];
  next_cursor: string | null;
}

export interface TransactionInput {
  type: TransactionType;
  amount: string;
  category_id: string;
  occurred_on: string;
  note: string | null;
}

export interface TransactionFilters {
  from?: string;
  to?: string;
  type?: TransactionType;
  category_id?: string;
  q?: string;
}
