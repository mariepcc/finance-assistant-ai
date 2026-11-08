import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';
import type { ComponentProps } from 'react';
import type { ColorValue } from 'react-native';

import { colors } from '@/components/theme';

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
      <Tabs.Screen name="index" options={{ title: 'Pulpit', tabBarIcon: icon('home') }} />
      <Tabs.Screen name="chat" options={{ title: 'Czat', tabBarIcon: icon('chatbubbles') }} />
      <Tabs.Screen
        name="transactions"
        options={{ title: 'Transakcje', tabBarIcon: icon('list') }}
      />
      <Tabs.Screen name="budgets" options={{ title: 'Budżety', tabBarIcon: icon('pie-chart') }} />
    </Tabs>
  );
}
