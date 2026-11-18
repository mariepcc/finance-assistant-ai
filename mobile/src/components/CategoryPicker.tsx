import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { useCategories } from '@/hooks/queries';
import type { Category, TransactionType } from '@/lib/types';

import { colors, spacing } from './theme';
import { Chip, ErrorText } from './ui';

export interface PickedCategory {
  id: string;
  category: string;
  subcategory: string | null;
}

export function CategoryPicker({
  kind,
  value,
  onChange,
  error,
}: {
  kind: TransactionType;
  value: string | null;
  onChange: (picked: PickedCategory) => void;
  error?: string;
}) {
  const categories = useCategories(kind);
  if (categories.isPending) return <ActivityIndicator />;

  const all = categories.data ?? [];
  const selected = all.find((c) => c.id === value);
  const parentId = selected?.parent_id ?? selected?.id ?? null;
  const parents = all.filter((c) => c.parent_id === null);
  const parent = parents.find((c) => c.id === parentId);
  const children = all.filter((c) => c.parent_id !== null && c.parent_id === parentId);

  const pick = (c: Category, main: Category) =>
    onChange({ id: c.id, category: main.name, subcategory: c.id === main.id ? null : c.name });

  return (
    <View style={styles.container}>
      <View style={styles.wrap}>
        {parents.map((c) => (
          <Chip
            key={c.id}
            label={c.name}
            color={c.color ?? undefined}
            selected={parentId === c.id}
            onPress={() => pick(c, c)}
          />
        ))}
      </View>
      {parent && children.length > 0 ? (
        <>
          <Text style={styles.label}>Podkategoria</Text>
          <View style={styles.wrap}>
            {children.map((c) => (
              <Chip
                key={c.id}
                label={c.name}
                color={parent.color ?? undefined}
                selected={value === c.id}
                onPress={() => pick(value === c.id ? parent : c, parent)}
              />
            ))}
          </View>
        </>
      ) : null}
      <ErrorText>{error ?? categories.error?.message}</ErrorText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.sm },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  label: { fontSize: 13, color: colors.muted, fontWeight: '500' },
});
