import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AskAssistant } from '@/components/dashboard/AskAssistant';
import { BalanceCard } from '@/components/dashboard/BalanceCard';
import { BudgetMeters } from '@/components/dashboard/BudgetMeters';
import { Card } from '@/components/dashboard/Card';
import { CategoryDonut } from '@/components/dashboard/CategoryDonut';
import { SpendingPaceChart } from '@/components/dashboard/SpendingPaceChart';
import { UpcomingPayments } from '@/components/dashboard/UpcomingPayments';
import { colors, spacing } from '@/components/theme';
import { TransactionRow } from '@/components/TransactionRow';
import { Button, Centered, ErrorText } from '@/components/ui';
import { useCategories, useDashboard, useTransactions } from '@/hooks/queries';
import { monthKey, monthRange, monthTitle, shiftMonth } from '@/lib/format';

const NO_FILTERS = {};

export default function DashboardScreen() {
  const current = monthKey();
  const [month, setMonth] = useState(current);
  const dashboard = useDashboard(month);
  const recent = useTransactions(NO_FILTERS);
  const categories = useCategories();
  const byId = useMemo(
    () => new Map((categories.data ?? []).map((c) => [c.id, c])),
    [categories.data],
  );
  const range = useMemo(() => {
    const [y, m] = month.split('-').map(Number) as [number, number];
    const now = new Date();
    return monthRange((y - now.getFullYear()) * 12 + (m - 1 - now.getMonth()));
  }, [month]);
  const recentItems = (recent.data?.pages[0]?.items ?? []).filter(
    (t) => t.occurred_on >= range.from && t.occurred_on <= range.to,
  );

  const refresh = () => {
    void dashboard.refetch();
    void recent.refetch();
  };

  const data = dashboard.data;

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={styles.container}
        contentInsetAdjustmentBehavior="automatic"
        refreshControl={
          <RefreshControl
            refreshing={dashboard.isRefetching && !dashboard.isPlaceholderData}
            onRefresh={refresh}
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

        {dashboard.isPending ? (
          <Centered>
            <ActivityIndicator />
          </Centered>
        ) : dashboard.isError || !data ? (
          <Centered>
            <ErrorText>{dashboard.error?.message ?? 'Nie udało się wczytać pulpitu'}</ErrorText>
            <Button title="Spróbuj ponownie" variant="secondary" onPress={refresh} />
          </Centered>
        ) : (
          <View style={[styles.sections, dashboard.isPlaceholderData && { opacity: 0.5 }]}>
            <BalanceCard data={data} />

            {data.transaction_count === 0 ? (
              <Card>
                <Text style={styles.emptyTitle}>Pusto w tym miesiącu</Text>
                <Text style={styles.emptyText}>
                  Dodaj pierwszy wydatek przyciskiem + albo napisz na czacie, np. „kawa 14 zł”.
                </Text>
              </Card>
            ) : (
              <>
                <Card title="Tempo wydatków">
                  <SpendingPaceChart data={data} />
                </Card>
                <Card title="Na co wydajesz">
                  <CategoryDonut
                    key={data.month}
                    categories={data.categories}
                    total={data.expense}
                    currency={data.currency}
                  />
                </Card>
              </>
            )}

            <Card
              title="Budżety"
              action={data.budgets.length > 0 ? 'Szczegóły' : undefined}
              onAction={() => router.push('/budgets')}
            >
              <BudgetMeters budgets={data.budgets} currency={data.currency} />
            </Card>

            {data.upcoming.length > 0 ? (
              <Card
                title="Nadchodzące płatności"
                action="Wszystkie"
                onAction={() => router.push('/recurring')}
              >
                <UpcomingPayments payments={data.upcoming} />
              </Card>
            ) : null}

            {recentItems.length > 0 ? (
              <Card
                title="Ostatnie transakcje"
                action="Wszystkie"
                onAction={() => router.push('/transactions')}
              >
                <View style={styles.recent}>
                  {recentItems.slice(0, 5).map((tx) => (
                    <TransactionRow key={tx.id} tx={tx} byId={byId} />
                  ))}
                </View>
              </Card>
            ) : null}

            {data.is_current ? <AskAssistant /> : null}
          </View>
        )}
      </ScrollView>

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
  recent: { marginHorizontal: -spacing.md, marginBottom: -spacing.md, overflow: 'hidden' },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  emptyText: { fontSize: 14, color: colors.muted, lineHeight: 20, marginTop: -spacing.sm },
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
