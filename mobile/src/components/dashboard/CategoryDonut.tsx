import Ionicons from '@expo/vector-icons/Ionicons';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { G, Path } from 'react-native-svg';

import { formatMoney, formatPct } from '@/lib/format';
import type { DashboardCategory } from '@/lib/types';

import { colors, spacing } from '../theme';

const ORDER = [
  'Transport',
  'Jedzenie',
  'Podróże',
  'Rachunki',
  'Rozrywka',
  'Zakupy',
  'Mieszkanie',
  'Zdrowie',
  'Inne',
];
const FALLBACK = '#94A3B8';
const SIZE = 232;
const STROKE = 30;
const POP = 7;
const GAP_PX = 2.5;
const SHADES = [0, 0.3, 0.5, 0.65, 0.75, 0.82];

interface Slice {
  key: string;
  name: string;
  amount: number;
  share: string;
  color: string;
  hasChildren: boolean;
}

function mix(hex: string, amount: number): string {
  const n = Number.parseInt(hex.slice(1), 16);
  const channel = (shift: number) => {
    const c = (n >> shift) & 255;
    return Math.round(c + (255 - c) * amount);
  };
  const out = (channel(16) << 16) | (channel(8) << 8) | channel(0);
  return `#${out.toString(16).padStart(6, '0')}`;
}

function arc(cx: number, cy: number, r: number, start: number, end: number): string {
  const point = (a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)] as const;
  const [x1, y1] = point(start);
  const [x2, y2] = point(end);
  const large = end - start > Math.PI ? 1 : 0;
  const from = `${x1.toFixed(2)},${y1.toFixed(2)}`;
  return `M${from}A${r},${r} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)}`;
}

function rank(name: string): number {
  const i = ORDER.indexOf(name);
  return i === -1 ? ORDER.length : i;
}

export function CategoryDonut({
  categories,
  total,
  currency,
}: {
  categories: DashboardCategory[];
  total: string;
  currency: string;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [drill, setDrill] = useState<string | null>(null);

  const parent = drill ? categories.find((c) => c.category_id === drill) : undefined;

  const slices = useMemo<Slice[]>(() => {
    if (parent) {
      const base = parent.color ?? FALLBACK;
      return parent.subcategories.map((s, i) => ({
        key: s.category_id ?? 'other',
        name: s.name,
        amount: Number(s.amount),
        share: s.share_pct,
        color: mix(base, SHADES[i % SHADES.length] ?? 0),
        hasChildren: false,
      }));
    }
    return [...categories]
      .sort((a, b) => rank(a.name) - rank(b.name) || Number(b.amount) - Number(a.amount))
      .map((c) => ({
        key: c.category_id,
        name: c.name,
        amount: Number(c.amount),
        share: c.share_pct,
        color: c.color ?? FALLBACK,
        hasChildren: c.subcategories.length > 0,
      }));
  }, [categories, parent]);

  if (slices.length === 0) {
    return <Text style={styles.empty}>Brak wydatków w tym miesiącu.</Text>;
  }

  const sum = slices.reduce((acc, s) => acc + s.amount, 0) || 1;
  const radius = (SIZE - STROKE) / 2 - POP - 3;
  const gap = slices.length > 1 ? GAP_PX / radius : 0;
  const active = slices.find((s) => s.key === selected);

  const choose = (slice: Slice) => {
    if (selected === slice.key && slice.hasChildren) {
      setDrill(slice.key);
      setSelected(null);
      return;
    }
    setSelected(selected === slice.key ? null : slice.key);
  };

  const back = () => {
    setSelected(drill);
    setDrill(null);
  };

  let angle = 0;
  const arcs = slices.map((s) => {
    const sweep = (s.amount / sum) * Math.PI * 2;
    const start = angle + gap / 2;
    const end = angle + sweep - gap / 2;
    angle += sweep;
    const bounded = Math.min(Math.max(end, start + 0.001), start + Math.PI * 2 - 0.0005);
    return { slice: s, start, end: bounded, mid: (start + bounded) / 2 };
  });

  const centerTitle = active?.name ?? parent?.name ?? 'Wydatki';
  const centerAmount = active
    ? formatMoney(String(active.amount), currency)
    : formatMoney(parent?.amount ?? total, currency);
  const centerHint = active
    ? active.hasChildren
      ? 'dotknij ponownie: podkategorie'
      : `${formatPct(active.share)} ${parent ? 'kategorii' : 'wydatków'}`
    : parent
      ? `${slices.length} podkategorie`
      : 'dotknij kategorii';

  return (
    <View style={{ gap: spacing.md }}>
      <View style={styles.chartWrap}>
        <Svg width={SIZE} height={SIZE}>
          <G>
            {arcs.map(({ slice, start, end, mid }) => {
              const isActive = slice.key === selected;
              const dim = selected !== null && !isActive;
              const dx = isActive ? Math.sin(mid) * POP : 0;
              const dy = isActive ? -Math.cos(mid) * POP : 0;
              return (
                <Path
                  key={slice.key}
                  d={arc(SIZE / 2 + dx, SIZE / 2 + dy, radius, start, end)}
                  stroke={slice.color}
                  strokeWidth={isActive ? STROKE + 6 : STROKE}
                  fill="none"
                  opacity={dim ? 0.3 : 1}
                  onPress={() => choose(slice)}
                />
              );
            })}
          </G>
        </Svg>
        <View style={styles.center} pointerEvents="box-none">
          {parent ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Wróć do wszystkich kategorii"
              hitSlop={10}
              onPress={back}
              style={styles.back}
            >
              <Ionicons name="chevron-back" size={14} color={colors.primary} />
              <Text style={styles.backText}>Wszystkie</Text>
            </Pressable>
          ) : null}
          <Text style={styles.centerTitle} numberOfLines={1}>
            {centerTitle}
          </Text>
          <Text style={styles.centerAmount} numberOfLines={1} adjustsFontSizeToFit>
            {centerAmount}
          </Text>
          <Text style={styles.centerHint}>{centerHint}</Text>
        </View>
      </View>

      <View style={styles.legend}>
        {slices.map((s) => {
          const isActive = s.key === selected;
          return (
            <Pressable
              key={s.key}
              accessibilityRole="button"
              accessibilityState={{ selected: isActive }}
              accessibilityLabel={`${s.name}: ${formatMoney(String(s.amount), currency)}, ${
                formatPct(s.share)
              }`}
              onPress={() => choose(s)}
              style={[styles.legendItem, isActive && styles.legendActive]}
            >
              <View style={[styles.dot, { backgroundColor: s.color }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.legendName} numberOfLines={1}>
                  {s.name}
                </Text>
                <Text style={styles.legendValue} numberOfLines={1}>
                  {formatMoney(String(s.amount), currency)} · {formatPct(s.share)}
                </Text>
              </View>
              {s.hasChildren && isActive ? (
                <Ionicons name="chevron-forward" size={14} color={colors.primary} />
              ) : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  chartWrap: { alignItems: 'center', justifyContent: 'center' },
  center: {
    position: 'absolute',
    width: SIZE - 2 * (STROKE + POP) - 16,
    alignItems: 'center',
  },
  back: { flexDirection: 'row', alignItems: 'center', gap: 2, marginBottom: 2 },
  backText: { fontSize: 12, fontWeight: '600', color: colors.primary },
  centerTitle: { fontSize: 14, fontWeight: '600', color: colors.muted },
  centerAmount: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  centerHint: { fontSize: 11, color: colors.muted, textAlign: 'center', marginTop: 2 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', rowGap: spacing.xs, columnGap: spacing.xs },
  legendItem: {
    width: '49%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: 10,
  },
  legendActive: { backgroundColor: '#EEF2FF' },
  dot: { width: 12, height: 12, borderRadius: 6 },
  legendName: { fontSize: 14, color: colors.text, fontWeight: '500' },
  legendValue: { fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  empty: { fontSize: 14, color: colors.muted },
});
