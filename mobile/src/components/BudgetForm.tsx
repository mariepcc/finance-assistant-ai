import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { formatMoney, normalizeAmount } from '@/lib/format';
import type { BudgetSuggestion } from '@/lib/types';

import { colors, radius, spacing } from './theme';
import { Button, Chip, ErrorText, Field } from './ui';

interface Props {
  categories: BudgetSuggestion[];
  initialCategoryId?: string;
  initialAmount?: string;
  currency: string;
  submitLabel: string;
  submitting: boolean;
  serverError?: string;
  onSubmit: (input: { categoryId: string; amount: string }) => void;
}

function roundTo50(value: number): string {
  return String(Math.max(50, Math.round(value / 50) * 50));
}

export function BudgetForm({
  categories,
  initialCategoryId,
  initialAmount,
  currency,
  submitLabel,
  submitting,
  serverError,
  onSubmit,
}: Props) {
  const [categoryId, setCategoryId] = useState<string | null>(initialCategoryId ?? null);
  const [amount, setAmount] = useState(initialAmount?.replace('.', ',') ?? '');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const selected = categories.find((c) => c.category_id === categoryId);
  const average = selected?.average_monthly ? Number(selected.average_monthly) : null;

  function submit() {
    const normalized = normalizeAmount(amount);
    const next: Record<string, string> = {};
    if (!categoryId) next.category = 'Wybierz kategorię';
    if (!normalized) next.amount = 'Podaj kwotę większą od zera, np. 1200';
    setErrors(next);
    if (!categoryId || !normalized) return;
    onSubmit({ categoryId, amount: normalized });
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      {initialCategoryId ? (
        <View style={styles.header}>
          <View style={[styles.dot, { backgroundColor: selected?.color ?? colors.muted }]} />
          <Text style={styles.title}>{selected?.category ?? 'Budżet'}</Text>
        </View>
      ) : (
        <>
          <Text style={styles.label}>Kategoria</Text>
          <View style={styles.wrap}>
            {categories.map((c) => (
              <Chip
                key={c.category_id}
                label={c.category}
                color={c.color ?? undefined}
                selected={categoryId === c.category_id}
                onPress={() => setCategoryId(c.category_id)}
              />
            ))}
          </View>
          <ErrorText>{errors.category}</ErrorText>
        </>
      )}

      <Field
        label="Miesięczny limit"
        value={amount}
        onChangeText={setAmount}
        keyboardType="decimal-pad"
        placeholder="0,00"
        error={errors.amount}
      />

      {average !== null && average > 0 ? (
        <View style={styles.hint}>
          <Text style={styles.hintText}>
            Średnio wydajesz {formatMoney(average.toFixed(2), currency)} miesięcznie w tej
            kategorii (ostatnie miesiące).
          </Text>
          <View style={styles.wrap}>
            <Chip
              label={`Ustaw ${formatMoney(roundTo50(average), currency)}`}
              selected={false}
              onPress={() => setAmount(roundTo50(average))}
            />
            <Chip
              label={`10% mniej: ${formatMoney(roundTo50(average * 0.9), currency)}`}
              selected={false}
              onPress={() => setAmount(roundTo50(average * 0.9))}
            />
          </View>
        </View>
      ) : null}

      <Text style={styles.note}>
        Limit obejmuje kategorię razem z jej podkategoriami i odnawia się co miesiąc.
      </Text>

      <ErrorText>{serverError}</ErrorText>
      <Button title={submitLabel} onPress={submit} loading={submitting} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.md },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  dot: { width: 14, height: 14, borderRadius: 7 },
  title: { fontSize: 22, fontWeight: '700', color: colors.text },
  label: { fontSize: 14, color: colors.muted, fontWeight: '500' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  hint: {
    backgroundColor: '#EEF2FF',
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  hintText: { fontSize: 14, color: colors.text, lineHeight: 20 },
  note: { fontSize: 13, color: colors.muted },
});
