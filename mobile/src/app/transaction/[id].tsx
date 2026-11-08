import { router, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Alert, StyleSheet, View } from 'react-native';

import { spacing } from '@/components/theme';
import { TransactionForm } from '@/components/TransactionForm';
import { Button, Centered, ErrorText } from '@/components/ui';
import { useDeleteTransaction, useTransaction, useUpdateTransaction } from '@/hooks/queries';

export default function TransactionDetailsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const tx = useTransaction(id);
  const update = useUpdateTransaction(id);
  const remove = useDeleteTransaction();

  if (tx.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (tx.isError) {
    return (
      <Centered>
        <ErrorText>{tx.error.message}</ErrorText>
      </Centered>
    );
  }

  function confirmDelete() {
    Alert.alert('Usunąć transakcję?', 'Tej operacji nie można cofnąć.', [
      { text: 'Anuluj', style: 'cancel' },
      {
        text: 'Usuń',
        style: 'destructive',
        onPress: () => remove.mutate(id, { onSuccess: () => router.back() }),
      },
    ]);
  }

  return (
    <View style={{ flex: 1 }}>
      <TransactionForm
        initial={tx.data}
        submitLabel="Zapisz zmiany"
        submitting={update.isPending}
        serverError={update.error?.message ?? remove.error?.message}
        onSubmit={(input) => update.mutate(input, { onSuccess: () => router.back() })}
      />
      <View style={styles.footer}>
        <Button
          title="Usuń transakcję"
          variant="danger"
          loading={remove.isPending}
          onPress={confirmDelete}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({ footer: { padding: spacing.md } });
