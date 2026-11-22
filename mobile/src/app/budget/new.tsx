import { router } from 'expo-router';
import { ActivityIndicator } from 'react-native';

import { BudgetForm } from '@/components/BudgetForm';
import { Centered, ErrorText } from '@/components/ui';
import { useBudgetSuggestions, useMe, useSaveBudget } from '@/hooks/queries';

export default function NewBudgetScreen() {
  const suggestions = useBudgetSuggestions();
  const me = useMe();
  const save = useSaveBudget();

  if (suggestions.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (suggestions.isError) {
    return (
      <Centered>
        <ErrorText>{suggestions.error.message}</ErrorText>
      </Centered>
    );
  }

  const available = suggestions.data.filter((s) => !s.has_budget);
  if (available.length === 0) {
    return (
      <Centered>
        <ErrorText>Wszystkie kategorie mają już budżet.</ErrorText>
      </Centered>
    );
  }

  return (
    <BudgetForm
      categories={available}
      currency={me.data?.default_currency ?? 'PLN'}
      submitLabel="Zapisz"
      submitting={save.isPending}
      serverError={save.error?.message}
      onSubmit={(input) => save.mutate(input, { onSuccess: () => router.back() })}
    />
  );
}
