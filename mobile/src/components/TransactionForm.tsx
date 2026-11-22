import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { daysAgo, isValidIsoDate, normalizeAmount, today } from '@/lib/format';
import type { TransactionInput, TransactionType } from '@/lib/types';

import { CategoryPicker } from './CategoryPicker';
import { colors, spacing } from './theme';
import { Button, Chip, ErrorText, Field } from './ui';

interface Props {
  initial?: TransactionInput;
  submitLabel: string;
  submitting: boolean;
  serverError?: string;
  onSubmit: (input: TransactionInput) => void;
}

export function TransactionForm({ initial, submitLabel, submitting, serverError, onSubmit }: Props) {
  const [type, setType] = useState<TransactionType>(initial?.type ?? 'expense');
  const [amount, setAmount] = useState(initial?.amount.replace('.', ',') ?? '');
  const [categoryId, setCategoryId] = useState<string | null>(initial?.category_id ?? null);
  const [date, setDate] = useState(initial?.occurred_on ?? today());
  const [note, setNote] = useState(initial?.note ?? '');
  const [errors, setErrors] = useState<Record<string, string>>({});

  function changeType(next: TransactionType) {
    if (next === type) return;
    setType(next);
    setCategoryId(null);
  }

  function submit() {
    const normalized = normalizeAmount(amount);
    const next: Record<string, string> = {};
    if (!normalized) next.amount = 'Podaj kwotę większą od zera, np. 4,40';
    if (!categoryId) next.category = 'Wybierz kategorię';
    if (!isValidIsoDate(date)) next.date = 'Data w formacie RRRR-MM-DD';
    setErrors(next);
    if (Object.keys(next).length > 0 || !normalized || !categoryId) return;
    onSubmit({
      type,
      amount: normalized,
      category_id: categoryId,
      occurred_on: date,
      note: note.trim() || null,
    });
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.row}>
        <Chip
          label="Wydatek"
          selected={type === 'expense'}
          color={colors.expense}
          onPress={() => changeType('expense')}
        />
        <Chip
          label="Przychód"
          selected={type === 'income'}
          color={colors.income}
          onPress={() => changeType('income')}
        />
      </View>

      <Field
        label="Kwota"
        value={amount}
        onChangeText={setAmount}
        keyboardType="decimal-pad"
        placeholder="0,00"
        error={errors.amount}
      />

      <Text style={styles.label}>Kategoria</Text>
      <CategoryPicker
        kind={type}
        value={categoryId}
        onChange={(picked) => setCategoryId(picked.id)}
        error={errors.category}
      />

      <Text style={styles.label}>Data</Text>
      <View style={styles.row}>
        <Chip label="Dziś" selected={date === today()} onPress={() => setDate(today())} />
        <Chip label="Wczoraj" selected={date === daysAgo(1)} onPress={() => setDate(daysAgo(1))} />
      </View>
      <Field
        label="lub wpisz datę"
        value={date}
        onChangeText={setDate}
        placeholder="RRRR-MM-DD"
        autoCorrect={false}
        error={errors.date}
      />

      <Field
        label="Notatka (opcjonalnie)"
        value={note}
        onChangeText={setNote}
        maxLength={500}
        placeholder="np. zakupy w Biedronce"
      />

      <ErrorText>{serverError}</ErrorText>
      <Button title={submitLabel} onPress={submit} loading={submitting} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.md },
  row: { flexDirection: 'row', gap: spacing.sm },
  label: { fontSize: 14, color: colors.muted, fontWeight: '500' },
});
