import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';

import { mix, shade } from '@/lib/colors';

import { colors } from './theme';

export function BudgetRing({
  id,
  used,
  expected,
  color,
  size = 96,
  stroke = 7,
}: {
  id: string;
  used: number;
  expected: number | null;
  color: string;
  size?: number;
  stroke?: number;
}) {
  const r = (size - stroke) / 2 - 3;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  const filled = Math.min(used, 100) / 100;
  const overflow = Math.min(Math.max(used - 100, 0), 100) / 100;
  const tick = expected !== null ? (Math.min(expected, 100) / 100) * Math.PI * 2 : null;
  const gradient = `ring-${id}`;
  return (
    <Svg width={size} height={size}>
      <Defs>
        <LinearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={mix(color, 0.45)} />
          <Stop offset="1" stopColor={color} />
        </LinearGradient>
      </Defs>
      <Circle cx={c} cy={c} r={r} stroke={mix(color, 0.78)} strokeWidth={stroke} fill="none" />
      {filled > 0 ? (
        <Circle
          cx={c}
          cy={c}
          r={r}
          stroke={`url(#${gradient})`}
          strokeWidth={stroke}
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
          strokeWidth={stroke}
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
