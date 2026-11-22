import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { type ComponentProps, memo, useState } from 'react';
import {
  ActivityIndicator,
  type LayoutChangeEvent,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { BudgetRing } from '@/components/BudgetRing';
import { colors, radius, spacing, status } from '@/components/theme';
import { Button, Centered, ErrorText } from '@/components/ui';
import { useBudgets, useBudgetSuggestions } from '@/hooks/queries';
import { mix } from '@/lib/colors';
import { formatMoney, formatPct, monthKey, monthTitle, shiftMonth } from '@/lib/format';
import type { BudgetItem, BudgetsOverview } from '@/lib/types';

const RING = 76;
const AHEAD_MARGIN = 10;
const FALLBACK = '#94A3B8';

type Pace = 'ok' | 'near' | 'ahead' | 'exceeded';

const PACE: Record<
  Pace,
  { label: string; icon: ComponentProps<typeof Ionicons>['name']; color: string }
> = {
  ok: { label: 'W tempie', icon: 'checkmark-circle', color: status.ok },
  near: { label: 'Blisko limitu', icon: 'alert-circle', color: status.warning },
  ahead: { label: 'Szybciej niż plan', icon: 'alert-circle', color: status.warning },
  exceeded: { label: 'Przekroczony', icon: 'close-circle', color: status.exceeded },
};

function expectedPct(data: BudgetsOverview): number | null {
  return data.is_current ? (data.days_elapsed / data.days_in_month) * 100 : null;
}

function paceOf(item: BudgetItem, expected: number | null): Pace {
  if (item.status === 'exceeded') return 'exceeded';
  if (expected === null) return item.status === 'warning' ? 'near' : 'ok';
  return Number(item.used_pct) > expected + AHEAD_MARGIN ? 'ahead' : 'ok';
}

const INK = colors.text;
const INK_SOFT = '#5B6478';

const Backdrop = memo(function Backdrop({ width, height }: { width: number; height: number }) {
  if (width === 0 || height === 0) return null;
  return (
    <Svg style={styles.backdrop} width={width} height={height}>
      <Defs>
        <LinearGradient
          id="soft"
          x1="0"
          y1="0"
          x2={width}
          y2={height}
          gradientUnits="userSpaceOnUse"
        >
          <Stop offset="0" stopColor="#E6E9FF" />
          <Stop offset="0.55" stopColor="#F1ECFF" />
          <Stop offset="1" stopColor="#FFEFE6" />
        </LinearGradient>
      </Defs>
      <Rect x={0} y={0} width={width} height={height} fill="url(#soft)" />
    </Svg>
  );
});

function Summary({ data }: { data: BudgetsOverview }) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const limit = Number(data.total_limit);
  const spent = Number(data.total_spent);
  const scale = Math.max(limit, spent, 1);
  const expected = expectedPct(data);
  const remaining = limit - spent;
  const daysLeft = data.days_in_month - data.days_elapsed + 1;
  const counts = { ok: 0, warn: 0, exceeded: 0 };
  for (const item of data.items) {
    const pace = paceOf(item, expected);
    if (pace === 'exceeded') counts.exceeded += 1;
    else if (pace === 'ok') counts.ok += 1;
    else counts.warn += 1;
  }
  const within = Math.min(spent, limit) / scale;
  const over = Math.max(spent - limit, 0) / scale;
  const paceAmount = expected !== null ? (limit * Math.min(expected, 100)) / 100 : null;
  const paceLeft = paceAmount !== null ? paceAmount / scale : null;
  const exceeded = spent > limit;

  const onLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    if (width !== size.width || height !== size.height) setSize({ width, height });
  };

  return (
    <View style={styles.summary} onLayout={onLayout}>
      <Backdrop width={size.width} height={size.height} />
      <Text style={styles.summaryLabel}>
        {monthTitle(data.month)} · {data.items.length}{' '}
        {data.items.length === 1 ? 'budżet' : data.items.length < 5 ? 'budżety' : 'budżetów'}
      </Text>
      <Text style={styles.summaryValue}>{formatMoney(data.total_spent, data.currency)}</Text>
      <Text style={styles.summaryOf}>
        wydano z {formatMoney(data.total_limit, data.currency)} łącznego limitu
      </Text>

      <View style={styles.bigTrack}>
        <View style={[styles.within, { width: `${within * 100}%` }]} />
        {over > 0 ? <View style={[styles.over, { width: `${over * 100}%` }]} /> : null}
        {exceeded ? (
          <View style={[styles.limitMark, { left: `${(limit / scale) * 100}%` }]} />
        ) : null}
        {paceLeft !== null ? (
          <View style={[styles.paceMark, { left: `${paceLeft * 100}%` }]} />
        ) : null}
      </View>

      <View style={styles.markLegend}>
        <View style={styles.markItem}>
          <View style={[styles.swatchBar, { backgroundColor: colors.primary }]} />
          <Text style={styles.markText}>wydano</Text>
        </View>
        {exceeded ? (
          <View style={styles.markItem}>
            <View style={[styles.swatchBar, { backgroundColor: status.exceeded }]} />
            <Text style={styles.markText}>ponad limit</Text>
          </View>
        ) : null}
        {exceeded ? (
          <View style={styles.markItem}>
            <View style={styles.swatchLimit} />
            <Text style={styles.markText}>koniec limitu</Text>
          </View>
        ) : null}
        {paceAmount !== null ? (
          <View style={styles.markItem}>
            <View style={styles.swatchPace} />
            <Text style={styles.markText}>
              równe tempo na dziś: {formatMoney(paceAmount.toFixed(2), data.currency)}
            </Text>
          </View>
        ) : null}
      </View>

      <Text style={styles.summaryDetail}>
        {remaining >= 0
          ? `Zostało ${formatMoney(remaining.toFixed(2), data.currency)}`
          : `Ponad limit o ${formatMoney((-remaining).toFixed(2), data.currency)}`}
        {data.is_current && remaining > 0
          ? ` · ~${formatMoney((remaining / daysLeft).toFixed(2), data.currency)} dziennie`
          : ''}
      </Text>
      <View style={styles.counts}>
        <View style={styles.count}>
          <Ionicons name="checkmark-circle" size={14} color={status.ok} />
          <Text style={styles.countText}>{counts.ok} w tempie</Text>
        </View>
        <View style={styles.count}>
          <Ionicons name="alert-circle" size={14} color={status.warning} />
          <Text style={styles.countText}>{counts.warn} uwaga</Text>
        </View>
        <View style={styles.count}>
          <Ionicons name="close-circle" size={14} color={status.exceeded} />
          <Text style={styles.countText}>{counts.exceeded} przekroczone</Text>
        </View>
      </View>
    </View>
  );
}

function BudgetCard({ item, data }: { item: BudgetItem; data: BudgetsOverview }) {
  const expected = expectedPct(data);
  const pace = PACE[paceOf(item, expected)];
  const color = item.color ?? FALLBACK;
  const remaining = Number(item.remaining);
  const daysLeft = data.days_in_month - data.days_elapsed + 1;
  const forecast = item.forecast_typical !== null ? Number(item.forecast_typical) : null;
  const limit = Number(item.limit);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.category}: ${formatPct(item.used_pct)} limitu, ${pace.label}`}
      onPress={() =>
        router.push({ pathname: '/budget/[categoryId]', params: { categoryId: item.category_id } })
      }
      style={({ pressed }) => [
        styles.card,
        { backgroundColor: mix(color, 0.93) },
        pressed && { opacity: 0.8 },
      ]}
    >
      <View style={styles.ringWrap}>
        <BudgetRing
          id={`b-${item.category_id}`}
          used={Number(item.used_pct)}
          expected={expected}
          color={color}
          size={RING}
          stroke={6}
        />
        <View style={styles.ringCenter}>
          <Text style={styles.pct}>
            {Math.round(Number(item.used_pct))}
            <Text style={styles.pctSign}>%</Text>
          </Text>
        </View>
      </View>
      <View style={styles.cardBody}>
        <View style={styles.cardHead}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {item.category}
          </Text>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </View>
        <Text style={styles.cardAmount}>
          {formatMoney(item.spent, data.currency)}
          <Text style={styles.cardOf}> z {formatMoney(item.limit, data.currency)}</Text>
        </Text>
        <View style={styles.pill}>
          <Ionicons name={pace.icon} size={12} color={pace.color} />
          <Text style={styles.pillText}>{pace.label}</Text>
        </View>
        <Text style={styles.cardDetail}>
          {remaining >= 0
            ? `zostało ${formatMoney(item.remaining, data.currency)}`
            : `ponad limit ${formatMoney(String(-remaining), data.currency)}`}
          {data.is_current && remaining > 0
            ? ` · ~${formatMoney((remaining / daysLeft).toFixed(2), data.currency)}/dzień`
            : ''}
        </Text>
        {forecast !== null ? (
          <Text style={styles.cardForecast}>
            Prognoza na koniec: ~{formatMoney(forecast.toFixed(2), data.currency)}
            {forecast > limit
              ? ` · ponad limit o ~${formatMoney((forecast - limit).toFixed(2), data.currency)}`
              : ' · w limicie'}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

export default function BudgetsScreen() {
  const current = monthKey();
  const [month, setMonth] = useState(current);
  const budgets = useBudgets(month);
  const suggestions = useBudgetSuggestions();
  const data = budgets.data;
  const canAdd = (suggestions.data ?? []).some((s) => !s.has_budget);

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={styles.container}
        contentInsetAdjustmentBehavior="automatic"
        refreshControl={
          <RefreshControl
            refreshing={budgets.isRefetching && !budgets.isPlaceholderData}
            onRefresh={() => {
              void budgets.refetch();
              void suggestions.refetch();
            }}
          />
        }
      >
        <View style={styles.monthBar}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Poprzedni miesiąc"
            hitSlop={10}
            onPress={() => setMonth(shiftMonth(month, -1))}
          >
            <Ionicons name="chevron-back" size={22} color={colors.primary} />
          </Pressable>
          <Text style={styles.month}>{monthTitle(month)}</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Następny miesiąc"
            hitSlop={10}
            disabled={month >= current}
            onPress={() => setMonth(shiftMonth(month, 1))}
          >
            <Ionicons
              name="chevron-forward"
              size={22}
              color={month >= current ? colors.border : colors.primary}
            />
          </Pressable>
        </View>

        {budgets.isPending ? (
          <Centered>
            <ActivityIndicator />
          </Centered>
        ) : budgets.isError || !data ? (
          <Centered>
            <ErrorText>{budgets.error?.message ?? 'Nie udało się wczytać budżetów'}</ErrorText>
          </Centered>
        ) : data.items.length === 0 ? (
          <View style={styles.empty}>
            <BudgetRing id="empty" used={0} expected={null} color={colors.primary} size={110} />
            <Text style={styles.emptyTitle}>Ustaw pierwszy limit</Text>
            <Text style={styles.emptyText}>
              Limit pilnuje, ile wydajesz w kategorii w miesiącu. Możesz go też ustawić na
              czacie, np. „ustaw budżet na jedzenie 1200 zł”.
            </Text>
            <Button title="Dodaj budżet" onPress={() => router.push('/budget/new')} />
          </View>
        ) : (
          <View style={[styles.sections, budgets.isPlaceholderData && { opacity: 0.5 }]}>
            <Summary data={data} />
            {data.items.map((item) => (
              <BudgetCard key={item.category_id} item={item} data={data} />
            ))}
            {data.is_current ? (
              <View style={styles.legend}>
                <View style={styles.legendDot} />
                <Text style={styles.legendText}>
                  kropka = równe tempo na dziś ({data.days_elapsed}. dzień z{' '}
                  {data.days_in_month})
                </Text>
              </View>
            ) : null}
          </View>
        )}
      </ScrollView>

      {canAdd && data && data.items.length > 0 ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Dodaj budżet"
          style={styles.fab}
          onPress={() => router.push('/budget/new')}
        >
          <Ionicons name="add" size={30} color={colors.primaryText} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, paddingBottom: 104, gap: spacing.md },
  monthBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xs,
  },
  month: { fontSize: 18, fontWeight: '700', color: colors.text },
  sections: { gap: spacing.md },
  summary: {
    backgroundColor: '#EFEDFF',
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: 6,
    overflow: 'hidden',
  },
  summaryLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: INK_SOFT,
    textTransform: 'uppercase',
    letterSpacing: 1.2,
  },
  summaryValue: {
    fontSize: 36,
    fontWeight: '300',
    color: INK,
    fontVariant: ['tabular-nums'],
    letterSpacing: -1,
    marginTop: spacing.xs,
  },
  summaryOf: { fontSize: 14, color: INK_SOFT, fontVariant: ['tabular-nums'] },
  bigTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(79,70,229,0.12)',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
  },
  within: { height: 6, borderRadius: 3, backgroundColor: colors.primary },
  over: { height: 6, borderRadius: 3, backgroundColor: status.exceeded, marginLeft: 2 },
  backdrop: { position: 'absolute', top: 0, left: 0 },
  limitMark: {
    position: 'absolute',
    width: 3,
    height: 18,
    marginLeft: -1.5,
    borderRadius: 1.5,
    backgroundColor: INK,
  },
  paceMark: {
    position: 'absolute',
    width: 2,
    height: 18,
    marginLeft: -1,
    borderRadius: 1,
    backgroundColor: INK_SOFT,
    opacity: 0.8,
  },
  markLegend: { flexDirection: 'row', flexWrap: 'wrap', columnGap: spacing.md, rowGap: 4 },
  markItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  markText: { fontSize: 12, color: INK_SOFT },
  swatchBar: { width: 14, height: 6, borderRadius: 3 },
  swatchLimit: { width: 3, height: 12, borderRadius: 1.5, backgroundColor: INK },
  swatchPace: { width: 2, height: 12, borderRadius: 1, backgroundColor: INK_SOFT },
  summaryDetail: { fontSize: 14, color: INK, fontVariant: ['tabular-nums'] },
  counts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md, marginTop: 2 },
  count: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  countText: { fontSize: 13, color: INK_SOFT },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  ringWrap: { width: RING, height: RING },
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
    fontSize: 18,
    fontWeight: '300',
    color: colors.text,
    fontVariant: ['tabular-nums'],
    letterSpacing: -0.5,
  },
  pctSign: { fontSize: 11, color: colors.muted },
  cardBody: { flex: 1, gap: 4 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  cardTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.text },
  cardAmount: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  cardOf: { fontSize: 13, fontWeight: '400', color: colors.muted },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
    backgroundColor: 'rgba(255,255,255,0.75)',
  },
  pillText: { fontSize: 11, fontWeight: '600', color: colors.text },
  cardDetail: { fontSize: 12, color: colors.text, fontVariant: ['tabular-nums'] },
  cardForecast: { fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  legend: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: colors.muted,
    backgroundColor: colors.card,
  },
  legendText: { fontSize: 12, color: colors.muted },
  empty: { alignItems: 'center', gap: spacing.md, paddingVertical: spacing.lg },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: colors.text },
  emptyText: { fontSize: 14, color: colors.muted, textAlign: 'center', lineHeight: 20 },
  fab: {
    position: 'absolute',
    right: spacing.md,
    bottom: spacing.md,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 3 },
  },
});
