import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, Text, View } from 'react-native';

import { formatMoney, shortDate } from '@/lib/format';
import type { UpcomingPayment } from '@/lib/types';

import { colors, radius, spacing } from '../theme';

function inDays(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number) as [number, number, number];
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((new Date(y, m - 1, d).getTime() - today.getTime()) / 86_400_000);
  if (days <= 1) return 'jutro';
  return `za ${days} dni`;
}

export function UpcomingPayments({ payments }: { payments: UpcomingPayment[] }) {
  return (
    <View style={{ gap: 12 }}>
      {payments.slice(0, 3).map((p) => (
        <View key={p.id} style={styles.row}>
          <View style={styles.icon}>
            <Ionicons name="repeat" size={16} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>{p.name}</Text>
            <Text style={styles.when}>
              {shortDate(p.due_on)} · {inDays(p.due_on)}
            </Text>
          </View>
          <Text
            style={[
              styles.amount,
              { color: p.type === 'expense' ? colors.expense : colors.income },
            ]}
          >
            {formatMoney(p.amount, p.currency, p.type)}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  icon: {
    width: 32,
    height: 32,
    borderRadius: radius.sm,
    backgroundColor: '#EEF2FF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  name: { fontSize: 15, color: colors.text, fontWeight: '500' },
  when: { fontSize: 13, color: colors.muted, marginTop: spacing.xs / 2 },
  amount: { fontSize: 15, fontWeight: '600', fontVariant: ['tabular-nums'] },
});
