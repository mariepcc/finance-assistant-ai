import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { normalizeAmount } from '@/lib/format';
import { parseDay } from '@/lib/recurring';
import type { RecurringInput, TransactionType } from '@/lib/types';

import { CategoryPicker } from './CategoryPicker';
import { type Schedule, ScheduleFields } from './ScheduleFields';
import { colors, spacing } from './theme';
import { Button, Chip, ErrorText, Field } from './ui';

interface Props {
  initial?: RecurringInput;
  submitLabel: string;
  submitting: boolean;
  serverError?: string;
  onSubmit: (input: RecurringInput) => void;
}

export function RecurringForm({ initial, submitLabel, submitting, serverError, onSubmit }: Props) {
  const [type, setType] = useState<TransactionType>(initial?.type ?? 'expense');
  const [name, setName] = useState(initial?.name ?? '');
  const [amount, setAmount] = useState(initial?.amount.replace('.', ',') ?? '');
  const [categoryId, setCategoryId] = useState<string | null>(initial?.category_id ?? null);
  const [schedule, setSchedule] = useState<Schedule>({
    frequency: initial?.frequency ?? 'monthly',
    day: String(initial?.day_of_month ?? new Date().getDate()),
    month: initial?.month ?? null,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  function changeType(next: TransactionType) {
    if (next === type) return;
    setType(next);
    setCategoryId(null);
  }

  function submit() {
    const normalized = normalizeAmount(amount);
    const day = parseDay(schedule.day);
    const month = schedule.frequency === 'yearly' ? schedule.month : null;
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = 'Podaj nazwę, np. Spotify';
    if (!normalized) next.amount = 'Podaj kwotę większą od zera, np. 23,99';
    if (!categoryId) next.category = 'Wybierz kategorię';
    if (!day) next.day = 'Dzień od 1 do 31';
    if (schedule.frequency === 'yearly' && !month) next.month = 'Wybierz miesiąc';
    setErrors(next);
    if (Object.keys(next).length > 0 || !normalized || !categoryId || !day) return;
    onSubmit({
      type,
      amount: normalized,
      category_id: categoryId,
      name: name.trim(),
      frequency: schedule.frequency,
      day_of_month: day,
      month,
    });
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      {initial ? null : (
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
      )}

      <Field
        label="Nazwa"
        value={name}
        onChangeText={setName}
        maxLength={100}
        placeholder="np. Spotify, czynsz, pensja"
        error={errors.name}
      />

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

      <ScheduleFields
        value={schedule}
        onChange={setSchedule}
        dayError={errors.day}
        monthError={errors.month}
      />

      <Text style={styles.hint}>
        Transakcja zapisze się sama w dniu każdej płatności. Jeśli dzień płatności to dziś,
        pierwsza zapisze się od razu.
      </Text>

      <ErrorText>{serverError}</ErrorText>
      <Button title={submitLabel} onPress={submit} loading={submitting} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.md },
  row: { flexDirection: 'row', gap: spacing.sm },
  label: { fontSize: 14, color: colors.muted, fontWeight: '500' },
  hint: { fontSize: 13, color: colors.muted },
});
