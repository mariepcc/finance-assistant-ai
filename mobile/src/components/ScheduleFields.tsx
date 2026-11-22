import { StyleSheet, Text, View } from 'react-native';

import { MONTHS_SHORT } from '@/lib/format';
import type { Frequency } from '@/lib/types';

import { colors, spacing } from './theme';
import { Chip, ErrorText, Field } from './ui';

export interface Schedule {
  frequency: Frequency;
  day: string;
  month: number | null;
}

export function ScheduleFields({
  value,
  onChange,
  dayError,
  monthError,
}: {
  value: Schedule;
  onChange: (next: Schedule) => void;
  dayError?: string;
  monthError?: string;
}) {
  const set = (patch: Partial<Schedule>) => onChange({ ...value, ...patch });
  return (
    <View style={styles.container}>
      <Text style={styles.label}>Jak często</Text>
      <View style={styles.wrap}>
        <Chip
          label="Co miesiąc"
          selected={value.frequency === 'monthly'}
          onPress={() => set({ frequency: 'monthly', month: null })}
        />
        <Chip
          label="Co rok"
          selected={value.frequency === 'yearly'}
          onPress={() =>
            set({ frequency: 'yearly', month: value.month ?? new Date().getMonth() + 1 })
          }
        />
      </View>
      <Field
        label="Dzień miesiąca (1–31)"
        value={value.day}
        onChangeText={(day) => set({ day })}
        keyboardType="number-pad"
        maxLength={2}
        error={dayError}
      />
      {value.frequency === 'yearly' ? (
        <>
          <Text style={styles.label}>Miesiąc</Text>
          <View style={styles.wrap}>
            {MONTHS_SHORT.map((name, i) => (
              <Chip
                key={name}
                label={name}
                selected={value.month === i + 1}
                onPress={() => set({ month: i + 1 })}
              />
            ))}
          </View>
          <ErrorText>{monthError}</ErrorText>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.sm },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  label: { fontSize: 14, color: colors.muted, fontWeight: '500' },
});
