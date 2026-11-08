import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  SectionList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { colors, radius, spacing } from '@/components/theme';
import { Centered, Chip, ErrorText } from '@/components/ui';
import { useCategories, useTransactions } from '@/hooks/queries';
import { formatDayHeader, formatMoney, monthRange } from '@/lib/format';
import type { Category, Transaction, TransactionFilters, TransactionType } from '@/lib/types';

type Period = 'this' | 'last' | 'all';

const PERIODS: { key: Period; label: string }[] = [
  { key: 'this', label: 'Ten miesiąc' },
  { key: 'last', label: 'Poprzedni' },
  { key: 'all', label: 'Wszystko' },
];

const TYPES: { key: TransactionType | undefined; label: string }[] = [
  { key: undefined, label: 'Wszystkie' },
  { key: 'expense', label: 'Wydatki' },
  { key: 'income', label: 'Przychody' },
];

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

function groupByDay(items: Transaction[]) {
  const sections: { title: string; data: Transaction[] }[] = [];
  for (const tx of items) {
    const last = sections[sections.length - 1];
    if (last?.title === tx.occurred_on) last.data.push(tx);
    else sections.push({ title: tx.occurred_on, data: [tx] });
  }
  return sections;
}

export default function TransactionsScreen() {
  const [period, setPeriod] = useState<Period>('this');
  const [type, setType] = useState<TransactionType | undefined>(undefined);
  const [categoryId, setCategoryId] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState('');
  const q = useDebounced(search.trim());

  const filters = useMemo<TransactionFilters>(() => {
    const range = period === 'all' ? {} : monthRange(period === 'this' ? 0 : -1);
    return { ...range, type, category_id: categoryId, q: q || undefined };
  }, [period, type, categoryId, q]);

  const categories = useCategories();
  const list = useTransactions(filters);
  const byId = useMemo(
    () => new Map((categories.data ?? []).map((c) => [c.id, c])),
    [categories.data],
  );
  const visibleCategories = (categories.data ?? []).filter((c) => !type || c.kind === type);
  const sections = useMemo(
    () => groupByDay(list.data?.pages.flatMap((p) => p.items) ?? []),
    [list.data],
  );

  function changeType(next: TransactionType | undefined) {
    setType(next);
    if (next && categoryId && byId.get(categoryId)?.kind !== next) setCategoryId(undefined);
  }

  return (
    <View style={{ flex: 1 }}>
      <View style={styles.filters}>
        <TextInput
          style={styles.search}
          value={search}
          onChangeText={setSearch}
          placeholder="Szukaj w notatkach"
          placeholderTextColor={colors.muted}
          clearButtonMode="while-editing"
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
          {PERIODS.map((p) => (
            <Chip key={p.key} label={p.label} selected={period === p.key} onPress={() => setPeriod(p.key)} />
          ))}
          <View style={styles.divider} />
          {TYPES.map((t) => (
            <Chip key={t.label} label={t.label} selected={type === t.key} onPress={() => changeType(t.key)} />
          ))}
        </ScrollView>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
          {visibleCategories.map((c) => (
            <Chip
              key={c.id}
              label={c.name}
              color={c.color ?? undefined}
              selected={categoryId === c.id}
              onPress={() => setCategoryId(categoryId === c.id ? undefined : c.id)}
            />
          ))}
        </ScrollView>
      </View>

      {list.isPending ? (
        <Centered>
          <ActivityIndicator />
        </Centered>
      ) : list.isError ? (
        <Centered>
          <ErrorText>{list.error.message}</ErrorText>
        </Centered>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(tx) => tx.id}
          renderSectionHeader={({ section }) => (
            <Text style={styles.dayHeader}>{formatDayHeader(section.title)}</Text>
          )}
          renderItem={({ item }) => <TransactionRow tx={item} category={byId.get(item.category_id)} />}
          stickySectionHeadersEnabled={false}
          onEndReached={() => {
            if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
          }}
          onEndReachedThreshold={0.5}
          refreshControl={
            <RefreshControl refreshing={list.isRefetching} onRefresh={() => void list.refetch()} />
          }
          ListEmptyComponent={<Text style={styles.empty}>Brak transakcji dla wybranych filtrów.</Text>}
          ListFooterComponent={list.isFetchingNextPage ? <ActivityIndicator /> : undefined}
          contentContainerStyle={{ paddingBottom: 96 }}
        />
      )}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Dodaj transakcję"
        style={styles.fab}
        onPress={() => router.push('/transaction/new')}
      >
        <Ionicons name="add" size={30} color={colors.primaryText} />
      </Pressable>
    </View>
  );
}

function TransactionRow({ tx, category }: { tx: Transaction; category?: Category }) {
  return (
    <Pressable
      style={({ pressed }) => [styles.item, pressed && { opacity: 0.7 }]}
      onPress={() => router.push({ pathname: '/transaction/[id]', params: { id: tx.id } })}
    >
      <View style={[styles.dot, { backgroundColor: category?.color ?? colors.muted }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.itemTitle}>{category?.name ?? 'Kategoria'}</Text>
        {tx.note ? (
          <Text style={styles.itemNote} numberOfLines={1}>
            {tx.note}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.amount, { color: tx.type === 'expense' ? colors.expense : colors.income }]}>
        {formatMoney(tx.amount, tx.currency, tx.type)}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  filters: { paddingTop: spacing.sm, gap: spacing.sm, backgroundColor: colors.bg },
  search: {
    marginHorizontal: spacing.md,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 16,
    color: colors.text,
  },
  row: { gap: spacing.sm, paddingHorizontal: spacing.md },
  divider: { width: 1, backgroundColor: colors.border, marginHorizontal: spacing.xs },
  dayHeader: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
    color: colors.muted,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
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
  amount: { fontSize: 16, fontWeight: '600', fontVariant: ['tabular-nums'] },
  empty: { textAlign: 'center', color: colors.muted, marginTop: spacing.lg },
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
