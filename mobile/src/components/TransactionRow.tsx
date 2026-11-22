import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { categoryLabel } from '@/lib/categories';
import { formatMoney } from '@/lib/format';
import type { Category, Transaction } from '@/lib/types';

import { colors, spacing } from './theme';

export function TransactionRow({ tx, byId }: { tx: Transaction; byId: Map<string, Category> }) {
  const category = byId.get(tx.category_id);
  const parent = category?.parent_id ? byId.get(category.parent_id) : undefined;
  return (
    <Pressable
      style={({ pressed }) => [styles.item, pressed && { opacity: 0.7 }]}
      onPress={() => router.push({ pathname: '/transaction/[id]', params: { id: tx.id } })}
    >
      <View
        style={[styles.dot, { backgroundColor: parent?.color ?? category?.color ?? colors.muted }]}
      />
      <View style={{ flex: 1 }}>
        <View style={styles.titleRow}>
          <Text style={styles.itemTitle}>{categoryLabel(category, byId)}</Text>
          {tx.recurring_id ? (
            <Ionicons
              name="repeat"
              size={14}
              color={colors.muted}
              accessibilityLabel="Stała płatność"
            />
          ) : null}
        </View>
        {tx.note ? (
          <Text style={styles.itemNote} numberOfLines={1}>
            {tx.note}
          </Text>
        ) : null}
      </View>
      <Text
        style={[styles.amount, { color: tx.type === 'expense' ? colors.expense : colors.income }]}
      >
        {formatMoney(tx.amount, tx.currency, tx.type)}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.card,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  itemTitle: { fontSize: 16, color: colors.text },
  itemNote: { fontSize: 13, color: colors.muted },
  amount: { fontSize: 16, fontWeight: '600', fontVariant: ['tabular-nums'] },
});
