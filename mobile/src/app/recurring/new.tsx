import { router } from 'expo-router';

import { RecurringForm } from '@/components/RecurringForm';
import { useCreateRecurring } from '@/hooks/queries';

export default function NewRecurringScreen() {
  const create = useCreateRecurring();
  return (
    <RecurringForm
      submitLabel="Zapisz"
      submitting={create.isPending}
      serverError={create.error?.message}
      onSubmit={(input) => create.mutate(input, { onSuccess: () => router.back() })}
    />
  );
}
