import { Stack } from 'expo-router';

import { colors } from '@/components/theme';

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerTintColor: colors.primary,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Logowanie' }} />
      <Stack.Screen name="register" options={{ title: 'Rejestracja' }} />
    </Stack>
  );
}
