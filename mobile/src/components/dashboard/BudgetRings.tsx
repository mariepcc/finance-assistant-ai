import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { mix } from '@/lib/colors';
import { formatMoney, formatPct } from '@/lib/format';
import type { Dashboard, DashboardBudget } from '@/lib/types';

import { BudgetRing } from '../BudgetRing';
import { colors, radius, spacing, status } from '../theme';

const SIZE = 96;
const AHEAD_MARGIN = 10;
const FALLBACK = '#94A3B8';

type Pace = 'ok' | 'ahead' | 'exceeded' | 'near';

const PACE: Record<
  Pace,
  { label: string; icon: ComponentProps<typeof Ionicons>['name']; color: string }
> = {
  ok: { label: 'W tempie', icon: 'checkmark-circle', color: status.ok },
  near: { label: 'Blisko limitu', icon: 'alert-circle', color: status.warning },
  ahead: { label: 'Szybciej niż plan', icon: 'alert-circle', color: status.warning },
  exceeded: { label: 'Przekroczony', icon: 'close-circle', color: status.exceeded },
};

function paceOf(b: DashboardBudget, expected: number | null): Pace {
  if (b.status === 'exceeded') return 'exceeded';
  if (expected === null) return b.status === 'warning' ? 'near' : 'ok';
  return Number(b.used_pct) > expected + AHEAD_MARGIN ? 'ahead' : 'ok';
}

export function BudgetRings({ data }: { data: Dashboard }) {
  const { budgets, currency } = data;
  if (budgets.length === 0) {
    return (
      <Text style={styles.empty}>
        Nie masz jeszcze budżetów. Napisz na czacie np. „ustaw budżet na jedzenie 1200 zł”.
      </Text>
    );
  }
  const expected = data.is_current ? (data.days_elapsed / data.days_in_month) * 100 : null;
  const daysLeft = data.days_in_month - data.days_elapsed + 1;

  return (
    <View style={{ gap: spacing.md }}>
      <View style={styles.grid}>
        {budgets.map((b) => {
          const pace = paceOf(b, expected);
          const p = PACE[pace];
          const color = b.color ?? FALLBACK;
          const remaining = Number(b.remaining);
          const perDay = data.is_current && remaining > 0 ? remaining / daysLeft : null;
          return (
            <View
              key={b.category_id}
              style={[styles.tile, { backgroundColor: mix(color, 0.93) }]}
              accessible
              accessibilityLabel={`${b.category}: wykorzystano ${formatPct(b.used_pct)} z ${
                formatMoney(b.limit, currency)
              }, ${p.label}`}
            >
              <View style={styles.ringWrap}>
                <BudgetRing
                  id={b.category_id}
                  used={Number(b.used_pct)}
                  expected={expected}
                  color={color}
                />
                <View style={styles.ringCenter}>
                  <Text style={styles.pct}>
                    {Math.round(Number(b.used_pct))}
                    <Text style={styles.pctSign}>%</Text>
                  </Text>
                </View>
              </View>
              <Text style={styles.name} numberOfLines={1}>
                {b.category}
              </Text>
              <View style={styles.pill}>
                <Ionicons name={p.icon} size={12} color={p.color} />
                <Text style={styles.pillText}>{p.label}</Text>
              </View>
              <Text style={styles.detail}>
                {remaining >= 0
                  ? `zostało ${formatMoney(b.remaining, currency)}`
                  : `ponad limit ${formatMoney(String(-remaining), currency)}`}
              </Text>
              {perDay !== null ? (
                <Text style={styles.detailSoft}>
                  ~{formatMoney(perDay.toFixed(2), currency)} dziennie
                </Text>
              ) : null}
            </View>
          );
        })}
      </View>
      {expected !== null ? (
        <View style={styles.legend}>
          <View style={styles.tickSwatch} />
          <Text style={styles.legendText}>
            równe tempo na dziś ({data.days_elapsed}. dzień z {data.days_in_month})
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 10 },
  tile: {
    width: '48.5%',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
  },
  ringWrap: { width: SIZE, height: SIZE, marginBottom: 2 },
  ringCenter: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pct: {
    fontSize: 22,
    fontWeight: '300',
    color: colors.text,
    fontVariant: ['tabular-nums'],
    letterSpacing: -0.5,
  },
  pctSign: { fontSize: 13, fontWeight: '400', color: colors.muted },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
    backgroundColor: 'rgba(255,255,255,0.75)',
  },
  pillText: { fontSize: 11, fontWeight: '600', color: colors.text },
  detail: { fontSize: 12, color: colors.text, fontVariant: ['tabular-nums'] },
  detailSoft: { fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  legend: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, justifyContent: 'center' },
  tickSwatch: {
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: colors.muted,
    backgroundColor: colors.card,
  },
  legendText: { fontSize: 12, color: colors.muted },
  empty: { fontSize: 14, color: colors.muted, lineHeight: 20, marginTop: -spacing.xs },
});
