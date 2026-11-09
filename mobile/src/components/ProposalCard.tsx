import { StyleSheet, Text, View } from 'react-native';

import type { ProposalState } from '@/hooks/useChat';
import { useConfirmProposal, useRejectProposal } from '@/hooks/queries';
import { ApiError } from '@/lib/api';
import { formatDayHeader, formatMoney } from '@/lib/format';
import type { Proposal } from '@/lib/types';

import { colors, radius, spacing } from './theme';
import { Button, ErrorText } from './ui';

const STATE_LABEL: Record<Exclude<ProposalState, 'pending'>, string> = {
  saved: 'Zapisano',
  rejected: 'Odrzucono, napisz poprawkę w wiadomości',
  expired: 'Propozycja wygasła, poproś asystenta jeszcze raz',
  handled: 'Ta propozycja została już rozpatrzona',
};

function stateFromError(err: unknown): ProposalState | null {
  if (err instanceof ApiError && err.status === 410) return 'expired';
  if (err instanceof ApiError && err.status === 409) return 'handled';
  return null;
}

export function ProposalCard({
  proposal,
  state,
  onStateChange,
  onCorrect,
}: {
  proposal: Proposal;
  state: ProposalState;
  onStateChange: (state: ProposalState) => void;
  onCorrect: () => void;
}) {
  const confirm = useConfirmProposal();
  const reject = useRejectProposal();
  const busy = confirm.isPending || reject.isPending;
  const failure = confirm.error ?? reject.error;
  const failureText = failure && !stateFromError(failure) ? failure.message : null;

  const handle = (action: 'confirm' | 'reject') => {
    const mutation = action === 'confirm' ? confirm : reject;
    mutation.mutate(proposal.proposal_id, {
      onSuccess: () => {
        onStateChange(action === 'confirm' ? 'saved' : 'rejected');
        if (action === 'reject') onCorrect();
      },
      onError: (err) => {
        const next = stateFromError(err);
        if (next) onStateChange(next);
      },
    });
  };

  return (
    <View style={styles.card}>
      <Text style={styles.title}>
        {proposal.kind === 'transaction' ? 'Do zapisania' : 'Zmiana budżetu'}
      </Text>
      {proposal.kind === 'transaction' ? (
        proposal.items.map((item, i) => (
          <View key={i} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.primary}>{item.note || item.category}</Text>
              <Text style={styles.secondary}>
                {item.category} · {formatDayHeader(item.occurred_on)}
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
      {state === 'pending' ? (
        <View style={styles.actions}>
          <View style={{ flex: 1 }}>
            <Button
              title="Zapisz"
              onPress={() => handle('confirm')}
              loading={confirm.isPending}
              disabled={busy}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              title="Popraw"
              variant="secondary"
              onPress={() => handle('reject')}
              loading={reject.isPending}
              disabled={busy}
            />
          </View>
        </View>
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
  primary: { fontSize: 15, color: colors.text, fontWeight: '500' },
  secondary: { fontSize: 13, color: colors.muted },
  amount: { fontSize: 15, fontWeight: '600', color: colors.text },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  state: { fontSize: 14, color: colors.muted, fontWeight: '500' },
});
