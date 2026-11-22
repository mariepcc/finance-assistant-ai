import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';

import { mix, shade } from '@/lib/colors';
import { formatMoney, formatPct } from '@/lib/format';
import type { Dashboard, DashboardBudget } from '@/lib/types';

import { colors, radius, spacing, status } from '../theme';

const SIZE = 96;
const STROKE = 7;
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

function Ring({
  id,
  used,
  expected,
  color,
}: {
  id: string;
  used: number;
  expected: number | null;
  color: string;
}) {
  const r = (SIZE - STROKE) / 2 - 3;
  const c = SIZE / 2;
  const circumference = 2 * Math.PI * r;
  const filled = Math.min(used, 100) / 100;
  const overflow = Math.min(Math.max(used - 100, 0), 100) / 100;
  const tick = expected !== null ? (Math.min(expected, 100) / 100) * Math.PI * 2 : null;
  const gradient = `ring-${id}`;
  return (
    <Svg width={SIZE} height={SIZE}>
      <Defs>
        <LinearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={mix(color, 0.45)} />
          <Stop offset="1" stopColor={color} />
        </LinearGradient>
      </Defs>
      <Circle cx={c} cy={c} r={r} stroke={mix(color, 0.86)} strokeWidth={STROKE} fill="none" />
      {filled > 0 ? (
        <Circle
          cx={c}
          cy={c}
          r={r}
          stroke={`url(#${gradient})`}
          strokeWidth={STROKE}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference * filled} ${circumference}`}
          transform={`rotate(-90 ${c} ${c})`}
        />
      ) : null}
      {overflow > 0 ? (
        <Circle
          cx={c}
          cy={c}
          r={r}
          stroke={shade(color, 0.35)}
          strokeWidth={STROKE}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference * overflow} ${circumference}`}
          transform={`rotate(-90 ${c} ${c})`}
        />
      ) : null}
      {tick !== null ? (
        <Circle
          cx={c + r * Math.sin(tick)}
          cy={c - r * Math.cos(tick)}
          r={3.5}
          fill={colors.card}
          stroke={colors.muted}
          strokeWidth={1.5}
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
          const color = b.color ?? FALLBACK;
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
                <Ring
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
  grid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: spacing.lg },
  tile: { width: '50%', alignItems: 'center', gap: 4, paddingHorizontal: spacing.xs },
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
    backgroundColor: colors.bg,
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
