import { router, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Alert, StyleSheet, View } from 'react-native';

import { RecurringForm } from '@/components/RecurringForm';
import { spacing } from '@/components/theme';
import { Button, Centered, ErrorText } from '@/components/ui';
import { useDeleteRecurring, useRecurring, useUpdateRecurring } from '@/hooks/queries';

export default function RecurringDetailsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const rule = useRecurring(id);
  const update = useUpdateRecurring();
  const remove = useDeleteRecurring();

  if (rule.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (rule.isError) {
    return (
      <Centered>
        <ErrorText>{rule.error.message}</ErrorText>
      </Centered>
    );
  }

  function confirmDelete() {
    Alert.alert(
      'Usunąć stałą płatność?',
      'Nowe transakcje przestaną się zapisywać. Już zapisane zostaną na liście.',
      [
        { text: 'Anuluj', style: 'cancel' },
        {
          text: 'Usuń',
          style: 'destructive',
          onPress: () => remove.mutate(id, { onSuccess: () => router.back() }),
        },
      ],
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <RecurringForm
        initial={rule.data}
        submitLabel="Zapisz zmiany"
        submitting={update.isPending}
        serverError={update.error?.message ?? remove.error?.message}
        onSubmit={({ type: _type, ...input }) =>
          update.mutate({ id, input }, { onSuccess: () => router.back() })
        }
      />
      <View style={styles.footer}>
        <Button
          title="Usuń stałą płatność"
          variant="danger"
          loading={remove.isPending}
          onPress={confirmDelete}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({ footer: { padding: spacing.md } });
