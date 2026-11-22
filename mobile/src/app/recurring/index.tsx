import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useMemo } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';

import { colors, radius, spacing } from '@/components/theme';
import { Centered, ErrorText } from '@/components/ui';
import { useCategories, useRecurringList, useUpdateRecurring } from '@/hooks/queries';
import { categoryLabel } from '@/lib/categories';
import { formatDate, formatMoney, formatSchedule } from '@/lib/format';
import type { Category, RecurringRule } from '@/lib/types';

export default function RecurringScreen() {
  const list = useRecurringList();
  const categories = useCategories();
  const byId = useMemo(
    () => new Map((categories.data ?? []).map((c) => [c.id, c])),
    [categories.data],
  );

  if (list.isPending) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }
  if (list.isError) {
    return (
      <Centered>
        <ErrorText>{list.error.message}</ErrorText>
      </Centered>
    );
  }

  const currency = list.data.items[0]?.currency ?? 'PLN';

  return (
    <View style={{ flex: 1 }}>
      <FlatList
        data={list.data.items}
        keyExtractor={(rule) => rule.id}
        renderItem={({ item }) => <RecurringRow rule={item} byId={byId} />}
        ListHeaderComponent={
          list.data.items.length > 0 ? (
            <View style={styles.summary}>
              <Text style={styles.summaryLabel}>Miesięcznie</Text>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryText}>Wydatki</Text>
                <Text style={[styles.summaryAmount, { color: colors.expense }]}>
                  {formatMoney(list.data.monthly_expense, currency, 'expense')}
                </Text>
              </View>
              {Number(list.data.monthly_income) > 0 ? (
                <View style={styles.summaryRow}>
                  <Text style={styles.summaryText}>Przychody</Text>
                  <Text style={[styles.summaryAmount, { color: colors.income }]}>
                    {formatMoney(list.data.monthly_income, currency, 'income')}
                  </Text>
                </View>
              ) : null}
            </View>
          ) : undefined
        }
        ListEmptyComponent={
          <Text style={styles.empty}>
            Nie masz jeszcze stałych płatności. Dodaj je przyciskiem + albo napisz na czacie, np.
            „Spotify 23,99 zł co miesiąc”.
          </Text>
        }
        refreshControl={
          <RefreshControl refreshing={list.isRefetching} onRefresh={() => void list.refetch()} />
        }
        contentContainerStyle={{ paddingBottom: 96 }}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Dodaj stałą płatność"
        style={styles.fab}
        onPress={() => router.push('/recurring/new')}
      >
        <Ionicons name="add" size={30} color={colors.primaryText} />
      </Pressable>
    </View>
  );
}

function RecurringRow({ rule, byId }: { rule: RecurringRule; byId: Map<string, Category> }) {
  const update = useUpdateRecurring();
  const category = byId.get(rule.category_id);
  const parent = category?.parent_id ? byId.get(category.parent_id) : undefined;
  return (
    <Pressable
      style={({ pressed }) => [styles.item, pressed && { opacity: 0.7 }]}
      onPress={() => router.push({ pathname: '/recurring/[id]', params: { id: rule.id } })}
    >
      <View
        style={[styles.dot, { backgroundColor: parent?.color ?? category?.color ?? colors.muted }]}
      />
      <View style={{ flex: 1, opacity: rule.active ? 1 : 0.5 }}>
        <Text style={styles.itemTitle}>{rule.name}</Text>
        <Text style={styles.itemNote} numberOfLines={1}>
          {categoryLabel(category, byId)} ·{' '}
          {formatSchedule(rule.frequency, rule.day_of_month, rule.month)}
        </Text>
        <Text style={styles.itemNote}>
          {rule.active ? `Następna: ${formatDate(rule.next_due_on)}` : 'Wstrzymana'}
        </Text>
      </View>
      <View style={styles.right}>
        <Text
          style={[
            styles.amount,
            { color: rule.type === 'expense' ? colors.expense : colors.income },
            !rule.active && { opacity: 0.5 },
          ]}
        >
          {formatMoney(rule.amount, rule.currency, rule.type)}
        </Text>
        <Switch
          value={rule.active}
          disabled={update.isPending}
          onValueChange={(active) => update.mutate({ id: rule.id, input: { active } })}
          accessibilityLabel={rule.active ? 'Wstrzymaj płatność' : 'Wznów płatność'}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  summary: {
    margin: spacing.md,
    padding: spacing.md,
    gap: spacing.xs,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
  },
  summaryLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.muted,
    textTransform: 'uppercase',
  },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between' },
  summaryText: { fontSize: 16, color: colors.text },
  summaryAmount: { fontSize: 16, fontWeight: '600', fontVariant: ['tabular-nums'] },
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
  itemTitle: { fontSize: 16, color: colors.text },
  itemNote: { fontSize: 13, color: colors.muted },
  right: { alignItems: 'flex-end', gap: spacing.xs },
  amount: { fontSize: 16, fontWeight: '600', fontVariant: ['tabular-nums'] },
  empty: { textAlign: 'center', color: colors.muted, margin: spacing.lg },
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
