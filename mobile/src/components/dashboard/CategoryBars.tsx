import Ionicons from '@expo/vector-icons/Ionicons';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { formatMoney, formatPct } from '@/lib/format';
import type { DashboardCategory } from '@/lib/types';

import { colors, spacing, status } from '../theme';

const VISIBLE = 6;

function fold(categories: DashboardCategory[]): DashboardCategory[] {
  if (categories.length <= VISIBLE + 1) return categories;
  const rest = categories.slice(VISIBLE);
  const amount = rest.reduce((sum, c) => sum + Number(c.amount), 0);
  const share = rest.reduce((sum, c) => sum + Number(c.share_pct), 0);
  return [
    ...categories.slice(0, VISIBLE),
    {
      category_id: 'rest',
      name: 'Pozostałe kategorie',
      color: colors.muted,
      amount: amount.toFixed(2),
      share_pct: share.toFixed(1),
      transaction_count: rest.reduce((sum, c) => sum + c.transaction_count, 0),
      subcategories: rest.map((c) => ({
        category_id: c.category_id,
        name: c.name,
        amount: c.amount,
        share_pct: ((Number(c.amount) / amount) * 100).toFixed(1),
      })),
    },
  ];
}

function Bar({ ratio, height, opacity = 1 }: { ratio: number; height: number; opacity?: number }) {
  return (
    <View style={[styles.track, { height, borderRadius: height / 2 }]}>
      <View
        style={{
          width: `${Math.max(ratio * 100, ratio > 0 ? 2 : 0)}%`,
          height,
          borderRadius: height / 2,
          backgroundColor: colors.primary,
          opacity,
        }}
      />
    </View>
  );
}

export function CategoryBars({
  categories,
  currency,
}: {
  categories: DashboardCategory[];
  currency: string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = fold(categories);
  const max = Math.max(...rows.map((c) => Number(c.amount)), 1);

  if (rows.length === 0) {
    return <Text style={styles.empty}>Brak wydatków w tym miesiącu.</Text>;
  }

  return (
    <View style={{ gap: 14 }}>
      {rows.map((c) => {
        const expanded = open === c.category_id;
        const subMax = Math.max(...c.subcategories.map((s) => Number(s.amount)), 1);
        return (
          <View key={c.category_id} style={{ gap: spacing.sm }}>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ expanded }}
              accessibilityLabel={`${c.name}: ${formatMoney(c.amount, currency)}, ${formatPct(
                c.share_pct,
              )} wydatków`}
              disabled={c.subcategories.length === 0}
              onPress={() => setOpen(expanded ? null : c.category_id)}
              style={{ gap: 6 }}
            >
              <View style={styles.row}>
                <View style={[styles.dot, { backgroundColor: c.color ?? colors.muted }]} />
                <Text style={styles.name} numberOfLines={1}>
                  {c.name}
                </Text>
                {c.subcategories.length > 0 ? (
                  <Ionicons
                    name={expanded ? 'chevron-up' : 'chevron-down'}
                    size={14}
                    color={colors.muted}
                  />
                ) : null}
                <Text style={styles.amount}>{formatMoney(c.amount, currency)}</Text>
                <Text style={styles.share}>{formatPct(c.share_pct)}</Text>
              </View>
              <Bar ratio={Number(c.amount) / max} height={8} />
            </Pressable>
            {expanded ? (
              <View style={styles.subs}>
                {c.subcategories.map((s) => (
                  <View key={s.category_id ?? 'other'} style={{ gap: 4 }}>
                    <View style={styles.row}>
                      <Text style={styles.subName} numberOfLines={1}>
                        {s.name}
                      </Text>
                      <Text style={styles.subAmount}>{formatMoney(s.amount, currency)}</Text>
                      <Text style={styles.share}>{formatPct(s.share_pct)}</Text>
                    </View>
                    <Bar ratio={Number(s.amount) / subMax} height={6} opacity={0.5} />
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  dot: { width: 10, height: 10, borderRadius: 5 },
  name: { flex: 1, fontSize: 15, color: colors.text, fontWeight: '500' },
  amount: { fontSize: 15, fontWeight: '600', color: colors.text, fontVariant: ['tabular-nums'] },
  share: {
    width: 48,
    textAlign: 'right',
    fontSize: 13,
    color: colors.muted,
    fontVariant: ['tabular-nums'],
  },
  track: { backgroundColor: status.track, overflow: 'hidden' },
  subs: {
    marginLeft: 18,
    paddingLeft: spacing.sm,
    borderLeftWidth: 2,
    borderLeftColor: status.track,
    gap: 10,
  },
  subName: { flex: 1, fontSize: 14, color: colors.text },
  subAmount: { fontSize: 14, color: colors.text, fontVariant: ['tabular-nums'] },
  empty: { fontSize: 14, color: colors.muted },
});
