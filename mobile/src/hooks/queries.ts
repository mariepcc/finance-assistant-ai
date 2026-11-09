import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type { TransactionFilters, TransactionInput, TransactionType } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';

export const keys = {
  me: ['me'] as const,
  categories: (kind?: TransactionType) => ['categories', kind ?? 'all'] as const,
  transactions: (filters: TransactionFilters) => ['transactions', filters] as const,
  transaction: (id: string) => ['transaction', id] as const,
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

function useInvalidateTransactions() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ['transactions'] });
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
  const invalidate = useInvalidateTransactions();
  return useMutation({ mutationFn: api.confirmProposal, onSuccess: invalidate });
}

export function useRejectProposal() {
  return useMutation({ mutationFn: api.rejectProposal });
}
