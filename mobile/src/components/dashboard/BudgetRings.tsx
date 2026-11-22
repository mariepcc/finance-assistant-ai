import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';

import { formatMoney, formatPct } from '@/lib/format';
import type { Dashboard, DashboardBudget } from '@/lib/types';

import { colors, spacing, status } from '../theme';

const SIZE = 92;
const STROKE = 10;
const AHEAD_MARGIN = 10;

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

function Ring({ used, expected, color }: { used: number; expected: number | null; color: string }) {
  const r = (SIZE - STROKE) / 2;
  const c = SIZE / 2;
  const circumference = 2 * Math.PI * r;
  const filled = Math.min(used, 100) / 100;
  const tick = expected !== null ? (Math.min(expected, 100) / 100) * Math.PI * 2 : null;
  const inner = r - STROKE / 2 - 2;
  const outer = r + STROKE / 2 + 2;
  return (
    <Svg width={SIZE} height={SIZE}>
      <Circle cx={c} cy={c} r={r} stroke={status.track} strokeWidth={STROKE} fill="none" />
      {filled > 0 ? (
        <Circle
          cx={c}
          cy={c}
          r={r}
          stroke={color}
          strokeWidth={STROKE}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference * filled} ${circumference}`}
          transform={`rotate(-90 ${c} ${c})`}
        />
      ) : null}
      {tick !== null ? (
        <Line
          x1={c + inner * Math.sin(tick)}
          y1={c - inner * Math.cos(tick)}
          x2={c + outer * Math.sin(tick)}
          y2={c - outer * Math.cos(tick)}
          stroke={colors.text}
          strokeWidth={2}
          strokeLinecap="round"
        />
      ) : null}
    </Svg>
  );
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
          const remaining = Number(b.remaining);
          const perDay = data.is_current && remaining > 0 ? remaining / daysLeft : null;
          return (
            <View
              key={b.category_id}
              style={styles.tile}
              accessible
              accessibilityLabel={`${b.category}: wykorzystano ${formatPct(b.used_pct)} z ${
                formatMoney(b.limit, currency)
              }, ${p.label}`}
            >
              <View style={styles.ringWrap}>
                <Ring used={Number(b.used_pct)} expected={expected} color={p.color} />
                <View style={styles.ringCenter}>
                  <Text style={styles.pct}>{Math.round(Number(b.used_pct))}%</Text>
                </View>
              </View>
              <Text style={styles.name} numberOfLines={1}>
                {b.category}
              </Text>
              <View style={styles.status}>
                <Ionicons name={p.icon} size={14} color={p.color} />
                <Text style={styles.statusText}>{p.label}</Text>
              </View>
              <Text style={styles.detail}>
                {remaining >= 0
                  ? `zostało ${formatMoney(b.remaining, currency)}`
                  : `ponad limit ${formatMoney(String(-remaining), currency)}`}
              </Text>
              {perDay !== null ? (
                <Text style={styles.detail}>
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
            kreska = równe tempo na dziś ({data.days_elapsed}. dzień z {data.days_in_month})
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: spacing.lg },
  tile: { width: '50%', alignItems: 'center', gap: 3, paddingHorizontal: spacing.xs },
  ringWrap: { width: SIZE, height: SIZE, marginBottom: spacing.xs },
  ringCenter: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pct: { fontSize: 18, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  status: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statusText: { fontSize: 12, color: colors.text },
  detail: { fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  legend: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, justifyContent: 'center' },
  tickSwatch: { width: 2, height: 12, borderRadius: 1, backgroundColor: colors.text },
  legendText: { fontSize: 12, color: colors.muted },
  empty: { fontSize: 14, color: colors.muted, lineHeight: 20, marginTop: -spacing.xs },
});
