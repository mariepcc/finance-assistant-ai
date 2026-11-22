import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, Text, View } from 'react-native';

import { formatMoney, formatPct, MONTHS } from '@/lib/format';
import type { Dashboard } from '@/lib/types';

import { colors, radius, spacing } from '../theme';

const IN_MONTH = [
  'styczniu',
  'lutym',
  'marcu',
  'kwietniu',
  'maju',
  'czerwcu',
  'lipcu',
  'sierpniu',
  'wrześniu',
  'październiku',
  'listopadzie',
  'grudniu',
];

function comparison(d: Dashboard): { text: string; up: boolean } | null {
  if (d.expense_change_pct === null) return null;
  const [, m] = d.previous_month.split('-').map(Number) as [number, number];
  const pct = Number(d.expense_change_pct);
  const when = d.is_current
    ? `w dniach 1–${d.days_elapsed} ${MONTHS[m - 1] ?? ''}`
    : `w ${IN_MONTH[m - 1] ?? ''}`;
  if (pct === 0) return { text: `tyle samo co ${when}`, up: false };
  const word = pct > 0 ? 'więcej' : 'mniej';
  return { text: `o ${formatPct(Math.abs(pct).toFixed(1))} ${word} niż ${when}`, up: pct > 0 };
}

export function BalanceCard({ data }: { data: Dashboard }) {
  const change = comparison(data);
  const negative = Number(data.balance) < 0;
  return (
    <View style={styles.card}>
      <Text style={styles.label}>Saldo miesiąca</Text>
      <Text
        style={styles.balance}
        adjustsFontSizeToFit
        numberOfLines={1}
        accessibilityLabel={`Saldo miesiąca ${formatMoney(data.balance, data.currency)}`}
      >
        {negative ? '−' : ''}
        {formatMoney(String(Math.abs(Number(data.balance))), data.currency)}
      </Text>
      <View style={styles.tiles}>
        <View style={styles.tile}>
          <View style={styles.tileHead}>
            <Ionicons name="arrow-down-circle" size={16} color={colors.income} />
            <Text style={styles.tileLabel}>Przychody</Text>
          </View>
          <Text style={styles.tileValue}>{formatMoney(data.income, data.currency)}</Text>
        </View>
        <View style={styles.tile}>
          <View style={styles.tileHead}>
            <Ionicons name="arrow-up-circle" size={16} color={colors.expense} />
            <Text style={styles.tileLabel}>Wydatki</Text>
          </View>
          <Text style={styles.tileValue}>{formatMoney(data.expense, data.currency)}</Text>
        </View>
      </View>
      {change ? (
        <View style={styles.change}>
          <Ionicons
            name={change.up ? 'trending-up' : 'trending-down'}
            size={16}
            color={colors.primaryText}
          />
          <Text style={styles.changeText}>Wydatki: {change.text}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  label: { fontSize: 14, fontWeight: '600', color: '#C7D2FE' },
  balance: {
    fontSize: 40,
    fontWeight: '800',
    color: colors.primaryText,
    fontVariant: ['tabular-nums'],
  },
  tiles: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  tile: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: radius.sm,
    padding: 12,
    gap: spacing.xs,
  },
  tileHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.card,
    alignSelf: 'flex-start',
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  tileLabel: { fontSize: 12, fontWeight: '600', color: colors.text },
  tileValue: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.primaryText,
    fontVariant: ['tabular-nums'],
  },
  change: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  changeText: { fontSize: 13, color: colors.primaryText },
});
