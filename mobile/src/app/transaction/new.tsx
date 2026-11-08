import { router } from 'expo-router';

import { TransactionForm } from '@/components/TransactionForm';
import { useCreateTransaction } from '@/hooks/queries';

export default function NewTransactionScreen() {
  const create = useCreateTransaction();
  return (
    <TransactionForm
      submitLabel="Zapisz"
      submitting={create.isPending}
      serverError={create.error?.message}
      onSubmit={(input) => create.mutate(input, { onSuccess: () => router.back() })}
    />
  );
}
