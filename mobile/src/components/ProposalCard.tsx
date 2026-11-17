import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { ProposalState } from '@/hooks/useChat';
import { useCategories, useConfirmProposal, useRejectProposal } from '@/hooks/queries';
import { ApiError } from '@/lib/api';
import { joinLabel } from '@/lib/categories';
import {
  daysAgo,
  formatDayHeader,
  formatMoney,
  isValidIsoDate,
  normalizeAmount,
  today,
} from '@/lib/format';
import type { Proposal, ProposalEdits, ProposedItem, TransactionType } from '@/lib/types';

import { CategoryPicker } from './CategoryPicker';
import { colors, radius, spacing } from './theme';
import { Button, Chip, ErrorText, Field } from './ui';

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
        {proposal.kind === 'transaction' ? 'Do zapisania' : 'Zmiana budżetu'}
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
