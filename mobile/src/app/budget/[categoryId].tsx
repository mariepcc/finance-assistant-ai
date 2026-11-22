import { router, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Alert, StyleSheet, View } from 'react-native';

import { BudgetForm } from '@/components/BudgetForm';
import { spacing } from '@/components/theme';
import { Button, Centered, ErrorText } from '@/components/ui';
import {
  useBudgets,
  useBudgetSuggestions,
  useDeleteBudget,
  useSaveBudget,
} from '@/hooks/queries';
import { monthKey } from '@/lib/format';

export default function BudgetDetailsScreen() {
  const { categoryId } = useLocalSearchParams<{ categoryId: string }>();
  const suggestions = useBudgetSuggestions();
  const budgets = useBudgets(monthKey());
  const save = useSaveBudget();
  const remove = useDeleteBudget();

  if (suggestions.isPending || budgets.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  const item = budgets.data?.items.find((b) => b.category_id === categoryId);
  if (suggestions.isError || budgets.isError || !item) {
    return (
      <Centered>
        <ErrorText>
          {suggestions.error?.message ?? budgets.error?.message ?? 'Nie znaleziono budżetu'}
        </ErrorText>
      </Centered>
    );
  }

  function confirmDelete() {
    Alert.alert('Usunąć budżet?', 'Transakcje zostaną bez zmian.', [
      { text: 'Anuluj', style: 'cancel' },
      {
        text: 'Usuń',
        style: 'destructive',
        onPress: () => remove.mutate(categoryId, { onSuccess: () => router.back() }),
      },
    ]);
  }

  return (
    <View style={{ flex: 1 }}>
      <BudgetForm
        categories={suggestions.data ?? []}
        initialCategoryId={categoryId}
        initialAmount={item.limit}
        currency={budgets.data?.currency ?? 'PLN'}
        submitLabel="Zapisz zmiany"
        submitting={save.isPending}
        serverError={save.error?.message ?? remove.error?.message}
        onSubmit={(input) => save.mutate(input, { onSuccess: () => router.back() })}
      />
      <View style={styles.footer}>
        <Button
          title="Usuń budżet"
          variant="danger"
          loading={remove.isPending}
          onPress={confirmDelete}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({ footer: { padding: spacing.md } });
