import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs, router } from 'expo-router';
import type { ComponentProps } from 'react';
import { Alert, type ColorValue, Pressable } from 'react-native';

import { colors } from '@/components/theme';
import { supabase } from '@/lib/supabase';

type IconName = ComponentProps<typeof Ionicons>['name'];

const icon =
  (name: IconName) =>
  ({ color, size }: { color: ColorValue; size: number }) => (
    <Ionicons name={name} color={typeof color === "number" ? undefined : (color ?? undefined)} size={size} />
  );

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        sceneStyle: { backgroundColor: colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Pulpit',
          tabBarIcon: icon('home'),
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Wyloguj"
              hitSlop={8}
              style={{ paddingHorizontal: 16 }}
              onPress={() =>
                Alert.alert('Wylogować się?', undefined, [
                  { text: 'Anuluj', style: 'cancel' },
                  {
                    text: 'Wyloguj',
                    style: 'destructive',
                    onPress: () => void supabase.auth.signOut(),
                  },
                ])
              }
            >
              <Ionicons name="log-out-outline" size={24} color={colors.primary} />
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen name="chat" options={{ title: 'Czat', tabBarIcon: icon('chatbubbles') }} />
      <Tabs.Screen
        name="transactions"
        options={{
          title: 'Transakcje',
          tabBarIcon: icon('list'),
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Stałe płatności"
              hitSlop={8}
              style={{ paddingHorizontal: 16 }}
              onPress={() => router.push('/recurring')}
            >
              <Ionicons name="repeat" size={24} color={colors.primary} />
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen name="budgets" options={{ title: 'Budżety', tabBarIcon: icon('pie-chart') }} />
    </Tabs>
  );
}
