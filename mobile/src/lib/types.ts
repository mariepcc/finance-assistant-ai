
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
  parent_id: string | null;
  description: string | null;
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
  source: 'manual' | 'assistant' | 'recurring';
  recurring_id: string | null;
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

export type Frequency = 'monthly' | 'yearly';

export interface RecurringRule {
  id: string;
  type: TransactionType;
  amount: string;
  currency: string;
  category_id: string;
  name: string;
  frequency: Frequency;
  day_of_month: number;
  month: number | null;
  next_due_on: string;
  active: boolean;
  monthly_amount: string;
}

export interface RecurringList {
  items: RecurringRule[];
  monthly_expense: string;
  monthly_income: string;
}

export interface RecurringInput {
  type: TransactionType;
  amount: string;
  category_id: string;
  name: string;
  frequency: Frequency;
  day_of_month: number;
  month: number | null;
}

export interface ProposedItem {
  type: TransactionType;
  amount: string;
  currency: string;
  category: string;
  subcategory: string | null;
  occurred_on: string;
  note: string | null;
}

export type Proposal =
  | {
      kind: 'transaction';
      proposal_id: string;
      expires_at: string;
      items: ProposedItem[];
    }
  | {
      kind: 'budget';
      proposal_id: string;
      expires_at: string;
      category: string;
      currency: string;
      amount: string;
      previous_amount: string | null;
    }
  | {
      kind: 'recurring';
      proposal_id: string;
      expires_at: string;
      name: string;
      type: TransactionType;
      amount: string;
      currency: string;
      category: string;
      subcategory: string | null;
      frequency: Frequency;
      day_of_month: number;
      month: number | null;
      first_payment_on: string;
      monthly_amount: string;
    };

export type ProposalEdits =
  | { items: TransactionInput[] }
  | { amount: string }
  | { recurring: Omit<RecurringInput, 'type'> };

export interface ConfirmResult {
  transactions: Transaction[];
}

export interface ChatDone {
  categories: string[];
  verified: boolean;
  steps: number;
  input_tokens: number;
  output_tokens: number;
}

export type ChatEvent =
  | { type: 'status'; data: { text: string } }
  | { type: 'proposal'; data: Proposal }
  | { type: 'token'; data: { text: string } }
  | { type: 'done'; data: ChatDone }
  | { type: 'error'; data: { message: string } };

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  message: string;
  history: ChatTurn[];
  previous_categories: string[];
}
