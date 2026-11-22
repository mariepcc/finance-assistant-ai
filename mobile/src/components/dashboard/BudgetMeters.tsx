import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { formatMoney, formatPct } from '@/lib/format';
import type { BudgetStatus, DashboardBudget } from '@/lib/types';

import { colors, spacing, status } from '../theme';

const STATUS: Record<
  BudgetStatus,
  { label: string; icon: ComponentProps<typeof Ionicons>['name']; color: string }
> = {
  ok: { label: 'W normie', icon: 'checkmark-circle', color: status.ok },
  warning: { label: 'Blisko limitu', icon: 'alert-circle', color: status.warning },
  exceeded: { label: 'Przekroczony', icon: 'close-circle', color: status.exceeded },
};

export function BudgetMeters({
  budgets,
  currency,
}: {
  budgets: DashboardBudget[];
  currency: string;
}) {
  if (budgets.length === 0) {
    return (
      <Text style={styles.empty}>
        Nie masz jeszcze budżetów. Napisz na czacie np. „ustaw budżet na jedzenie 1200 zł”.
      </Text>
    );
  }
  return (
    <View style={{ gap: 14 }}>
      {budgets.map((b) => {
        const s = STATUS[b.status];
        const used = Math.min(Number(b.used_pct), 100);
        return (
          <View key={b.category_id} style={{ gap: 6 }}>
            <View style={styles.row}>
              <Text style={styles.name}>{b.category}</Text>
              <Ionicons name={s.icon} size={15} color={s.color} />
              <Text style={styles.status}>{s.label}</Text>
            </View>
            <View style={styles.track}>
              <View style={[styles.fill, { width: `${used}%`, backgroundColor: s.color }]} />
            </View>
            <View style={styles.row}>
              <Text style={styles.detail}>
                {formatMoney(b.spent, currency)} z {formatMoney(b.limit, currency)}
              </Text>
              <Text style={styles.detailRight}>
                {Number(b.remaining) >= 0
                  ? `zostało ${formatMoney(b.remaining, currency)}`
                  : `ponad limit ${formatMoney(String(-Number(b.remaining)), currency)}`}{' '}
                · {formatPct(b.used_pct)}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  name: { flex: 1, fontSize: 15, fontWeight: '500', color: colors.text },
  status: { fontSize: 13, color: colors.text },
  track: { height: 8, borderRadius: 4, backgroundColor: status.track, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4 },
  detail: { flex: 1, fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  detailRight: { fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  empty: { fontSize: 14, color: colors.muted, lineHeight: 20, marginTop: -spacing.xs },
});
