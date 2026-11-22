import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { ProposalState } from '@/hooks/useChat';
import { useCategories, useConfirmProposal, useRejectProposal } from '@/hooks/queries';
import { ApiError } from '@/lib/api';
import { joinLabel } from '@/lib/categories';
import {
  daysAgo,
  formatDate,
  formatDayHeader,
  formatMoney,
  formatSchedule,
  isValidIsoDate,
  normalizeAmount,
  today,
} from '@/lib/format';
import { firstDue, parseDay } from '@/lib/recurring';
import type { Proposal, ProposalEdits, ProposedItem, TransactionType } from '@/lib/types';

import { CategoryPicker } from './CategoryPicker';
import { type Schedule, ScheduleFields } from './ScheduleFields';
import { colors, radius, spacing } from './theme';
import { Button, Chip, ErrorText, Field } from './ui';

const TITLE: Record<Proposal['kind'], string> = {
  transaction: 'Do zapisania',
  budget: 'Zmiana budżetu',
  recurring: 'Stała płatność',
};

const STATE_LABEL: Record<Exclude<ProposalState, 'pending'>, string> = {
  saved: 'Zapisano',
  rejected: 'Odrzucono',
  expired: 'Propozycja wygasła, poproś asystenta jeszcze raz',
  handled: 'Ta propozycja została już rozpatrzona',
};

interface ItemDraft {
  type: TransactionType;
  amount: string;
  categoryId: string | null;
  category: string;
  subcategory: string | null;
  date: string;
  note: string;
}

type ItemErrors = Partial<Record<'amount' | 'category' | 'date', string>>;

type RecurringProposal = Extract<Proposal, { kind: 'recurring' }>;

interface RecurringDraft {
  name: string;
  amount: string;
  categoryId: string | null;
  category: string;
  subcategory: string | null;
  schedule: Schedule;
}

type RecurringErrors = Partial<Record<'name' | 'amount' | 'category' | 'day' | 'month', string>>;

function stateFromError(err: unknown): ProposalState | null {
  if (err instanceof ApiError && err.status === 410) return 'expired';
  if (err instanceof ApiError && err.status === 409) return 'handled';
  return null;
}

function toDraft(item: ProposedItem): ItemDraft {
  return {
    type: item.type,
    amount: item.amount.replace('.', ','),
    categoryId: null,
    category: item.category,
    subcategory: item.subcategory,
    date: item.occurred_on,
    note: item.note ?? '',
  };
}

function ItemEditor({
  draft,
  errors,
  onChange,
  onRemove,
}: {
  draft: ItemDraft;
  errors: ItemErrors;
  onChange: (next: ItemDraft) => void;
  onRemove?: () => void;
}) {
  const categories = useCategories(draft.type);
  const set = (patch: Partial<ItemDraft>) => onChange({ ...draft, ...patch });

  useEffect(() => {
    if (draft.categoryId || !categories.data) return;
    const name = draft.subcategory ?? draft.category;
    const match = categories.data.find((c) => c.name === name);
    if (match) onChange({ ...draft, categoryId: match.id });
  }, [categories.data, draft, onChange]);

  return (
    <View style={styles.editor}>
      <View style={styles.wrap}>
        <Chip
          label="Wydatek"
          selected={draft.type === 'expense'}
          color={colors.expense}
          onPress={() =>
            draft.type !== 'expense' &&
            set({ type: 'expense', categoryId: null, category: '', subcategory: null })
          }
        />
        <Chip
          label="Przychód"
          selected={draft.type === 'income'}
          color={colors.income}
          onPress={() =>
            draft.type !== 'income' &&
            set({ type: 'income', categoryId: null, category: '', subcategory: null })
          }
        />
      </View>
      <Field
        label="Kwota"
        value={draft.amount}
        onChangeText={(amount) => set({ amount })}
        keyboardType="decimal-pad"
        error={errors.amount}
      />
      <Text style={styles.label}>Kategoria</Text>
      <CategoryPicker
        kind={draft.type}
        value={draft.categoryId}
        onChange={(picked) =>
          set({
            categoryId: picked.id,
            category: picked.category,
            subcategory: picked.subcategory,
          })
        }
        error={errors.category}
      />
      <View style={styles.wrap}>
        <Chip label="Dziś" selected={draft.date === today()} onPress={() => set({ date: today() })} />
        <Chip
          label="Wczoraj"
          selected={draft.date === daysAgo(1)}
          onPress={() => set({ date: daysAgo(1) })}
        />
      </View>
      <Field
        label="Data"
        value={draft.date}
        onChangeText={(date) => set({ date })}
        placeholder="RRRR-MM-DD"
        autoCorrect={false}
        error={errors.date}
      />
      <Field
        label="Notatka"
        value={draft.note}
        onChangeText={(note) => set({ note })}
        maxLength={500}
      />
      {onRemove ? (
        <Pressable accessibilityRole="button" onPress={onRemove}>
          <Text style={styles.link}>Usuń tę pozycję</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function toRecurringDraft(p: RecurringProposal): RecurringDraft {
  return {
    name: p.name,
    amount: p.amount.replace('.', ','),
    categoryId: null,
    category: p.category,
    subcategory: p.subcategory,
    schedule: { frequency: p.frequency, day: String(p.day_of_month), month: p.month },
  };
}

function RecurringEditor({
  kind,
  draft,
  errors,
  onChange,
}: {
  kind: TransactionType;
  draft: RecurringDraft;
  errors: RecurringErrors;
  onChange: (next: RecurringDraft) => void;
}) {
  const categories = useCategories(kind);
  const set = (patch: Partial<RecurringDraft>) => onChange({ ...draft, ...patch });

  useEffect(() => {
    if (draft.categoryId || !categories.data) return;
    const name = draft.subcategory ?? draft.category;
    const match = categories.data.find((c) => c.name === name);
    if (match) onChange({ ...draft, categoryId: match.id });
  }, [categories.data, draft, onChange]);

  return (
    <View style={styles.editor}>
      <Field
        label="Nazwa"
        value={draft.name}
        onChangeText={(name) => set({ name })}
        maxLength={100}
        error={errors.name}
      />
      <Field
        label="Kwota"
        value={draft.amount}
        onChangeText={(amount) => set({ amount })}
        keyboardType="decimal-pad"
        error={errors.amount}
      />
      <Text style={styles.label}>Kategoria</Text>
      <CategoryPicker
        kind={kind}
        value={draft.categoryId}
        onChange={(picked) =>
          set({ categoryId: picked.id, category: picked.category, subcategory: picked.subcategory })
        }
        error={errors.category}
      />
      <ScheduleFields
        value={draft.schedule}
        onChange={(schedule) => set({ schedule })}
        dayError={errors.day}
        monthError={errors.month}
      />
    </View>
  );
}

function validateRecurring(
  p: RecurringProposal,
  d: RecurringDraft,
): { errors: RecurringErrors; edits?: ProposalEdits; updated?: Proposal } {
  const errors: RecurringErrors = {};
  const amount = normalizeAmount(d.amount);
  const day = parseDay(d.schedule.day);
  const month = d.schedule.frequency === 'yearly' ? d.schedule.month : null;
  if (!d.name.trim()) errors.name = 'Podaj nazwę, np. Spotify';
  if (!amount) errors.amount = 'Podaj kwotę większą od zera, np. 23,99';
  if (!d.categoryId) errors.category = 'Wybierz kategorię';
  if (!day) errors.day = 'Dzień od 1 do 31';
  if (d.schedule.frequency === 'yearly' && !month) errors.month = 'Wybierz miesiąc';
  if (!amount || !day || !d.categoryId || Object.keys(errors).length > 0) return { errors };
  const fields = {
    name: d.name.trim(),
    amount,
    category_id: d.categoryId,
    frequency: d.schedule.frequency,
    day_of_month: day,
    month,
  };
  return {
    errors,
    edits: { recurring: fields },
    updated: {
      ...p,
      name: fields.name,
      amount,
      category: d.category,
      subcategory: d.subcategory,
      frequency: fields.frequency,
      day_of_month: day,
      month,
      first_payment_on: firstDue(fields.frequency, day, month),
      monthly_amount:
        fields.frequency === 'yearly'
          ? (Math.round((Number(amount) * 100) / 12) / 100).toFixed(2)
          : amount,
    },
  };
}

function validateItems(drafts: ItemDraft[]): { errors: ItemErrors[]; edits?: ProposalEdits } {
  const errors = drafts.map((d) => {
    const e: ItemErrors = {};
    if (!normalizeAmount(d.amount)) e.amount = 'Podaj kwotę większą od zera, np. 4,40';
    if (!d.categoryId) e.category = 'Wybierz kategorię';
    if (!isValidIsoDate(d.date)) e.date = 'Data w formacie RRRR-MM-DD';
    return e;
  });
  if (errors.some((e) => Object.keys(e).length > 0)) return { errors };
  return {
    errors,
    edits: {
      items: drafts.map((d) => ({
        type: d.type,
        amount: normalizeAmount(d.amount) ?? '',
        category_id: d.categoryId ?? '',
        occurred_on: d.date,
        note: d.note.trim() || null,
      })),
    },
  };
}

export function ProposalCard({
  proposal,
  state,
  onStateChange,
}: {
  proposal: Proposal;
  state: ProposalState;
  onStateChange: (state: ProposalState, updated?: Proposal) => void;
}) {
  const confirm = useConfirmProposal();
  const reject = useRejectProposal();
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<ItemDraft[]>([]);
  const [itemErrors, setItemErrors] = useState<ItemErrors[]>([]);
  const [budgetAmount, setBudgetAmount] = useState('');
  const [budgetError, setBudgetError] = useState<string>();
  const [recurring, setRecurring] = useState<RecurringDraft | null>(null);
  const [recurringErrors, setRecurringErrors] = useState<RecurringErrors>({});
  const busy = confirm.isPending || reject.isPending;
  const failure = confirm.error ?? reject.error;
  const failureText = failure && !stateFromError(failure) ? failure.message : null;

  const fail = (err: unknown) => {
    const next = stateFromError(err);
    if (next) onStateChange(next);
  };

  const startEditing = () => {
    confirm.reset();
    if (proposal.kind === 'transaction') {
      setDrafts(proposal.items.map(toDraft));
      setItemErrors([]);
    } else if (proposal.kind === 'recurring') {
      setRecurring(toRecurringDraft(proposal));
      setRecurringErrors({});
    } else {
      setBudgetAmount(proposal.amount.replace('.', ','));
      setBudgetError(undefined);
    }
    setEditing(true);
  };

  const save = () => {
    if (!editing) {
      confirm.mutate(
        { id: proposal.proposal_id },
        { onSuccess: () => onStateChange('saved'), onError: fail },
      );
      return;
    }
    let edits: ProposalEdits;
    let updated: Proposal;
    if (proposal.kind === 'transaction') {
      const result = validateItems(drafts);
      setItemErrors(result.errors);
      if (!result.edits || !('items' in result.edits)) return;
      edits = result.edits;
      updated = {
        ...proposal,
        items: result.edits.items.map((item, i) => ({
          type: item.type,
          amount: item.amount,
          currency: proposal.items[0]?.currency ?? 'PLN',
          category: drafts[i]?.category ?? '',
          subcategory: drafts[i]?.subcategory ?? null,
          occurred_on: item.occurred_on,
          note: item.note,
        })),
      };
    } else if (proposal.kind === 'recurring') {
      if (!recurring) return;
      const result = validateRecurring(proposal, recurring);
      setRecurringErrors(result.errors);
      if (!result.edits || !result.updated) return;
      edits = result.edits;
      updated = result.updated;
    } else {
      const amount = normalizeAmount(budgetAmount);
      setBudgetError(amount ? undefined : 'Podaj kwotę większą od zera, np. 500');
      if (!amount) return;
      edits = { amount };
      updated = { ...proposal, amount };
    }
    confirm.mutate(
      { id: proposal.proposal_id, edits },
      {
        onSuccess: () => {
          setEditing(false);
          onStateChange('saved', updated);
        },
        onError: fail,
      },
    );
  };

  const discard = () =>
    reject.mutate(proposal.proposal_id, {
      onSuccess: () => {
        setEditing(false);
        onStateChange('rejected');
      },
      onError: fail,
    });

  const updateDraft = (index: number) => (next: ItemDraft) =>
    setDrafts((prev) => prev.map((d, i) => (i === index ? next : d)));

  const removeDraft = (index: number) => {
    setDrafts((prev) => prev.filter((_, i) => i !== index));
    setItemErrors((prev) => prev.filter((_, i) => i !== index));
  };

  const pending = state === 'pending';

  return (
    <View style={styles.card}>
      <Text style={styles.title}>
        {TITLE[proposal.kind]}
      </Text>
      {pending && editing ? (
        proposal.kind === 'transaction' ? (
          drafts.map((draft, i) => (
            <ItemEditor
              key={i}
              draft={draft}
              errors={itemErrors[i] ?? {}}
              onChange={updateDraft(i)}
              onRemove={drafts.length > 1 ? () => removeDraft(i) : undefined}
            />
          ))
        ) : proposal.kind === 'recurring' ? (
          recurring ? (
            <RecurringEditor
              kind={proposal.type}
              draft={recurring}
              errors={recurringErrors}
              onChange={setRecurring}
            />
          ) : null
        ) : (
          <View style={styles.editor}>
            <Text style={styles.primary}>{proposal.category}</Text>
            <Field
              label="Miesięczny limit"
              value={budgetAmount}
              onChangeText={setBudgetAmount}
              keyboardType="decimal-pad"
              error={budgetError}
            />
          </View>
        )
      ) : proposal.kind === 'transaction' ? (
        proposal.items.map((item, i) => (
          <View key={i} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.primary}>
                {item.note || joinLabel(item.category, item.subcategory)}
              </Text>
              <Text style={styles.secondary}>
                {joinLabel(item.category, item.subcategory)} · {formatDayHeader(item.occurred_on)}
              </Text>
            </View>
            <Text
              style={[
                styles.amount,
                { color: item.type === 'expense' ? colors.expense : colors.income },
              ]}
            >
              {formatMoney(item.amount, item.currency, item.type)}
            </Text>
          </View>
        ))
      ) : proposal.kind === 'recurring' ? (
        <RecurringSummary proposal={proposal} saved={state === 'saved'} />
      ) : (
        <View style={styles.row}>
          <Text style={[styles.primary, { flex: 1 }]}>{proposal.category}</Text>
          <Text style={styles.amount}>
            {proposal.previous_amount
              ? `${formatMoney(proposal.previous_amount, proposal.currency)} → `
              : ''}
            {formatMoney(proposal.amount, proposal.currency)}
          </Text>
        </View>
      )}
      {pending ? (
        <>
          <View style={styles.actions}>
            <View style={{ flex: 1 }}>
              <Button title="Zapisz" onPress={save} loading={confirm.isPending} disabled={busy} />
            </View>
            <View style={{ flex: 1 }}>
              <Button
                title={editing ? 'Anuluj' : 'Popraw'}
                variant="secondary"
                onPress={editing ? () => setEditing(false) : startEditing}
                disabled={busy}
              />
            </View>
          </View>
          {editing ? (
            <Pressable accessibilityRole="button" onPress={discard} disabled={busy}>
              <Text style={[styles.link, styles.center]}>Odrzuć całą propozycję</Text>
            </Pressable>
          ) : null}
        </>
      ) : (
        <Text style={[styles.state, state === 'saved' && { color: colors.income }]}>
          {STATE_LABEL[state]}
        </Text>
      )}
      <ErrorText>{failureText}</ErrorText>
    </View>
  );
}

function RecurringSummary({ proposal, saved }: { proposal: RecurringProposal; saved: boolean }) {
  const first = proposal.first_payment_on;
  const firstText =
    first === today()
      ? saved
        ? 'Pierwsza płatność: dziś, już zapisana'
        : 'Pierwsza płatność: dziś, zapisze się od razu'
      : `Pierwsza płatność: ${formatDate(first)}`;
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <Text style={styles.primary}>{proposal.name}</Text>
        <Text style={styles.secondary}>
          {joinLabel(proposal.category, proposal.subcategory)} ·{' '}
          {formatSchedule(proposal.frequency, proposal.day_of_month, proposal.month)}
        </Text>
        <Text style={styles.secondary}>{firstText}</Text>
      </View>
      <View style={{ alignItems: 'flex-end' }}>
        <Text
          style={[
            styles.amount,
            { color: proposal.type === 'expense' ? colors.expense : colors.income },
          ]}
        >
          {formatMoney(proposal.amount, proposal.currency, proposal.type)}
        </Text>
        {proposal.frequency === 'yearly' ? (
          <Text style={styles.secondary}>
            ≈ {formatMoney(proposal.monthly_amount, proposal.currency)} / mies.
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  title: { fontSize: 13, fontWeight: '600', color: colors.muted, textTransform: 'uppercase' },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  editor: {
    gap: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  label: { fontSize: 14, color: colors.muted, fontWeight: '500' },
  primary: { fontSize: 15, color: colors.text, fontWeight: '500' },
  secondary: { fontSize: 13, color: colors.muted },
  amount: { fontSize: 15, fontWeight: '600', color: colors.text },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  state: { fontSize: 14, color: colors.muted, fontWeight: '500' },
  link: { fontSize: 14, color: colors.danger, fontWeight: '500' },
  center: { textAlign: 'center', paddingVertical: spacing.xs },
});
