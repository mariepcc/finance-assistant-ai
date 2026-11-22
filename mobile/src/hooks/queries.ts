import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type {
  RecurringInput,
  TransactionFilters,
  TransactionInput,
  TransactionType,
} from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';

export const keys = {
  me: ['me'] as const,
  categories: (kind?: TransactionType) => ['categories', kind ?? 'all'] as const,
  transactions: (filters: TransactionFilters) => ['transactions', filters] as const,
  transaction: (id: string) => ['transaction', id] as const,
  recurringList: ['recurring', 'list'] as const,
  dashboard: (month: string) => ['dashboard', month] as const,
  budgets: (month: string) => ['budgets', month] as const,
  budgetSuggestions: ['budgets', 'suggestions'] as const,
  recurring: (id: string) => ['recurring', id] as const,
};

export function useMe() {
  const { session } = useAuth();
  return useQuery({ queryKey: keys.me, queryFn: api.me, enabled: !!session });
}

export function useAcceptConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.acceptConsent,
    onSuccess: (profile) => {
      qc.setQueryData(keys.me, profile);
      void qc.invalidateQueries({ queryKey: ['categories'] });
    },
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateMe,
    onSuccess: (profile) => qc.setQueryData(keys.me, profile),
  });
}

export function useCategories(kind?: TransactionType) {
  return useQuery({
    queryKey: keys.categories(kind),
    queryFn: () => api.categories(kind),
    staleTime: 5 * 60_000,
  });
}

export function useTransactions(filters: TransactionFilters) {
  return useInfiniteQuery({
    queryKey: keys.transactions(filters),
    queryFn: ({ pageParam }) => api.transactions(filters, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

export function useTransaction(id: string) {
  return useQuery({ queryKey: keys.transaction(id), queryFn: () => api.transaction(id) });
}

export function useDashboard(month: string) {
  return useQuery({
    queryKey: keys.dashboard(month),
    queryFn: () => api.dashboard(month),
    placeholderData: (previous) => previous,
  });
}

export function useBudgets(month: string) {
  return useQuery({
    queryKey: keys.budgets(month),
    queryFn: () => api.budgets(month),
    placeholderData: (previous) => previous,
  });
}

export function useBudgetSuggestions() {
  return useQuery({ queryKey: keys.budgetSuggestions, queryFn: api.budgetSuggestions });
}

function useInvalidateBudgets() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['budgets'] }),
      qc.invalidateQueries({ queryKey: ['dashboard'] }),
    ]);
}

export function useSaveBudget() {
  const invalidate = useInvalidateBudgets();
  return useMutation({ mutationFn: api.saveBudget, onSuccess: invalidate });
}

export function useDeleteBudget() {
  const invalidate = useInvalidateBudgets();
  return useMutation({ mutationFn: api.deleteBudget, onSuccess: invalidate });
}

function useInvalidateTransactions() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['transactions'] }),
      qc.invalidateQueries({ queryKey: ['dashboard'] }),
      qc.invalidateQueries({ queryKey: ['budgets'] }),
    ]);
}

export function useCreateTransaction() {
  const invalidate = useInvalidateTransactions();
  return useMutation({ mutationFn: api.createTransaction, onSuccess: invalidate });
}

export function useUpdateTransaction(id: string) {
  const qc = useQueryClient();
  const invalidate = useInvalidateTransactions();
  return useMutation({
    mutationFn: (input: Partial<TransactionInput>) => api.updateTransaction(id, input),
    onSuccess: (tx) => {
      qc.setQueryData(keys.transaction(id), tx);
      return invalidate();
    },
  });
}

export function useDeleteTransaction() {
  const qc = useQueryClient();
  const invalidate = useInvalidateTransactions();
  return useMutation({
    mutationFn: api.deleteTransaction,
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: keys.transaction(id) });
      return invalidate();
    },
  });
}

export function useConfirmProposal() {
  const invalidate = useInvalidateRecurring();
  return useMutation({ mutationFn: api.confirmProposal, onSuccess: invalidate });
}

export function useRecurringList() {
  return useQuery({ queryKey: keys.recurringList, queryFn: api.recurringList });
}

export function useRecurring(id: string) {
  return useQuery({ queryKey: keys.recurring(id), queryFn: () => api.recurring(id) });
}

type RecurringPatch = Partial<RecurringInput> & { active?: boolean };

function useInvalidateRecurring() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['recurring'] }),
      qc.invalidateQueries({ queryKey: ['transactions'] }),
      qc.invalidateQueries({ queryKey: ['dashboard'] }),
      qc.invalidateQueries({ queryKey: ['budgets'] }),
    ]);
}

export function useCreateRecurring() {
  const invalidate = useInvalidateRecurring();
  return useMutation({ mutationFn: api.createRecurring, onSuccess: invalidate });
}

export function useUpdateRecurring() {
  const invalidate = useInvalidateRecurring();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: RecurringPatch }) =>
      api.updateRecurring(id, input),
    onSuccess: invalidate,
  });
}

export function useDeleteRecurring() {
  const invalidate = useInvalidateRecurring();
  return useMutation({ mutationFn: api.deleteRecurring, onSuccess: invalidate });
}

export function useRejectProposal() {
  return useMutation({ mutationFn: api.rejectProposal });
}
