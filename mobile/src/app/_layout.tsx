import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SplashScreen, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { colors } from '@/components/theme';
import { useMe } from '@/hooks/queries';
import { ApiError } from '@/lib/api';
import { AuthProvider, useAuth } from '@/providers/AuthProvider';

void SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
});

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <StatusBar style="dark" />
        <RootNavigator />
      </AuthProvider>
    </QueryClientProvider>
  );
}

function RootNavigator() {
  const { session, loading } = useAuth();
  const me = useMe();
  const signedIn = !!session;
  const consented = !!me.data?.gdpr_consent_at;
  const ready = !loading && (!signedIn || !me.isPending);

  useEffect(() => {
    if (ready) SplashScreen.hide();
  }, [ready]);

  return (
    <Stack
      screenOptions={{
        headerTintColor: colors.primary,
        contentStyle: { backgroundColor: colors.bg },
        headerBackButtonDisplayMode: 'minimal',
      }}
    >
      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={signedIn && !consented}>
        <Stack.Screen name="onboarding" options={{ title: 'Witaj' }} />
      </Stack.Protected>
      <Stack.Protected guard={signedIn && consented}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="transaction/new"
          options={{ title: 'Nowa transakcja', presentation: 'modal' }}
        />
        <Stack.Screen name="transaction/[id]" options={{ title: 'Transakcja' }} />
      </Stack.Protected>
    </Stack>
  );
}
