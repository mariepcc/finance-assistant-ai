import { useState } from 'react';
import { type LayoutChangeEvent, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Path, Text as SvgText } from 'react-native-svg';

import { compactMoney, formatMoney, MONTHS_SHORT } from '@/lib/format';
import type { Dashboard } from '@/lib/types';

import { colors, spacing } from '../theme';

const HEIGHT = 190;
const PAD = { left: 44, right: 16, top: 14, bottom: 24 };
const REFERENCE = '#B8BEC9';
const GRID = '#EEF0F4';

function niceMax(value: number): number {
  if (value <= 0) return 100;
  const raw = value / 3;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  return step * 3;
}

function linePath(values: number[], x: (i: number) => number, y: (v: number) => number) {
  return values
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join('');
}

function monthIndex(key: string): number {
  return (key.split('-').map(Number)[1] ?? 1) - 1;
}

export function SpendingPaceChart({ data }: { data: Dashboard }) {
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState<number | null>(null);

  const money = (value: number | string) => formatMoney(String(value), data.currency);
  const current = data.daily.map(Number);
  const previous = data.previous_daily.map(Number).slice(0, data.days_in_month);
  const forecast = data.forecast
    ? {
        low: Number(data.forecast.low),
        typical: Number(data.forecast.typical),
        high: Number(data.forecast.high),
      }
    : null;
  const lastValue = current.at(-1) ?? 0;

  const top = niceMax(Math.max(...current, ...previous, forecast?.high ?? 0, 1));
  const plotW = Math.max(width - PAD.left - PAD.right, 1);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const last = data.days_in_month - 1;
  const x = (i: number) => PAD.left + (last > 0 ? (i / last) * plotW : 0);
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;
  const ticks = [0, top / 3, (2 * top) / 3, top];

  const cm = monthIndex(data.month);
  const pm = monthIndex(data.previous_month);
  const day = active ?? current.length - 1;
  const readCurrent = current[day];
  const readPrevious = previous[day];

  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);
  const pick = (locationX: number) => {
    const i = Math.round(((locationX - PAD.left) / plotW) * last);
    setActive(Math.min(Math.max(i, 0), last));
  };

  const summary =
    `Wydatki narastająco: ${money(lastValue)} do dnia ${current.length}` +
    (forecast ? `, prognoza na koniec miesiąca ${money(forecast.typical)}` : '');

  return (
    <View style={{ gap: spacing.sm }}>
      <View style={styles.readout}>
        <Text style={styles.readoutDay}>
          {day + 1} {MONTHS_SHORT[cm]}
        </Text>
        <Text style={styles.readoutValue}>
          {readCurrent !== undefined ? money(readCurrent) : '—'}
        </Text>
        {readPrevious !== undefined ? (
          <Text style={styles.readoutRef}>
            {MONTHS_SHORT[pm]}: {money(readPrevious)}
          </Text>
        ) : null}
      </View>

      <View
        onLayout={onLayout}
        style={{ height: HEIGHT }}
        accessible
        accessibilityLabel={summary}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderGrant={(e) => pick(e.nativeEvent.locationX)}
        onResponderMove={(e) => pick(e.nativeEvent.locationX)}
        onResponderRelease={() => setActive(null)}
        onResponderTerminate={() => setActive(null)}
      >
        {width > 0 ? (
          <Svg width={width} height={HEIGHT}>
            {ticks.map((t) => (
              <Line
                key={`g${t}`}
                x1={PAD.left}
                x2={width - PAD.right}
                y1={y(t)}
                y2={y(t)}
                stroke={GRID}
                strokeWidth={1}
              />
            ))}
            {ticks.map((t) => (
              <SvgText
                key={`t${t}`}
                x={PAD.left - 6}
                y={y(t) + 4}
                fontSize={11}
                fill={colors.muted}
                textAnchor="end"
              >
                {compactMoney(t)}
              </SvgText>
            ))}
            {[0, 9, 19, last].map((i) => (
              <SvgText
                key={`d${i}`}
                x={x(i)}
                y={HEIGHT - 6}
                fontSize={11}
                fill={colors.muted}
                textAnchor="middle"
              >
                {i + 1}
              </SvgText>
            ))}

            {previous.length > 1 ? (
              <Path
                d={linePath(previous, x, y)}
                stroke={REFERENCE}
                strokeWidth={2}
                fill="none"
                strokeLinejoin="round"
              />
            ) : null}

            {forecast && current.length > 0 ? (
              <>
                <Line
                  x1={x(current.length - 1)}
                  y1={y(lastValue)}
                  x2={x(last)}
                  y2={y(forecast.typical)}
                  stroke={colors.primary}
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  opacity={0.6}
                />
                <Line
                  x1={x(last)}
                  x2={x(last)}
                  y1={y(forecast.low)}
                  y2={y(forecast.high)}
                  stroke={colors.primary}
                  strokeWidth={8}
                  strokeLinecap="round"
                  opacity={0.2}
                />
                <Circle
                  cx={x(last)}
                  cy={y(forecast.typical)}
                  r={5}
                  fill={colors.primary}
                  stroke={colors.card}
                  strokeWidth={2}
                />
              </>
            ) : null}

            {current.length > 1 ? (
              <Path
                d={linePath(current, x, y)}
                stroke={colors.primary}
                strokeWidth={2.5}
                fill="none"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ) : null}
            {current.length > 0 ? (
              <Circle
                cx={x(current.length - 1)}
                cy={y(lastValue)}
                r={4.5}
                fill={colors.primary}
                stroke={colors.card}
                strokeWidth={2}
              />
            ) : null}

            {active !== null ? (
              <>
                <Line
                  x1={x(active)}
                  x2={x(active)}
                  y1={PAD.top}
                  y2={PAD.top + plotH}
                  stroke={colors.muted}
                  strokeWidth={1}
                />
                {readCurrent !== undefined ? (
                  <Circle
                    cx={x(active)}
                    cy={y(readCurrent)}
                    r={5}
                    fill={colors.primary}
                    stroke={colors.card}
                    strokeWidth={2}
                  />
                ) : null}
                {readPrevious !== undefined ? (
                  <Circle
                    cx={x(active)}
                    cy={y(readPrevious)}
                    r={4}
                    fill={REFERENCE}
                    stroke={colors.card}
                    strokeWidth={2}
                  />
                ) : null}
              </>
            ) : null}
          </Svg>
        ) : null}
      </View>

      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: colors.primary }]} />
          <Text style={styles.legendText}>{MONTHS_SHORT[cm]}</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: REFERENCE }]} />
          <Text style={styles.legendText}>{MONTHS_SHORT[pm]}</Text>
        </View>
        {forecast ? (
          <View style={styles.legendItem}>
            <View style={styles.forecastSwatch} />
            <Text style={styles.legendText}>Prognoza ~{money(forecast.typical)}</Text>
          </View>
        ) : null}
      </View>
      {forecast ? (
        <Text style={styles.note}>
          Zakres prognozy na koniec miesiąca: {money(forecast.low)} – {money(forecast.high)}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  readout: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm, flexWrap: 'wrap' },
  readoutDay: { fontSize: 13, color: colors.muted, fontWeight: '600' },
  readoutValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  readoutRef: { fontSize: 13, color: colors.muted, fontVariant: ['tabular-nums'] },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 14, height: 3, borderRadius: 2 },
  forecastSwatch: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.primary,
    borderWidth: 2,
    borderColor: '#C7D2FE',
  },
  legendText: { fontSize: 12, color: colors.muted },
  note: { fontSize: 12, color: colors.muted },
});
