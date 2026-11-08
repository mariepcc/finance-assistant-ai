import { router } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { colors } from '@/components/theme';
import { Button, Centered } from '@/components/ui';
import { supabase } from '@/lib/supabase';

export default function DashboardScreen() {
  return (
    <Centered>
      <Text style={styles.title}>Pulpit</Text>
      <Text style={styles.muted}>Podsumowanie miesiąca pojawi się w tygodniu 4.</Text>
      <Button title="Dodaj transakcję" onPress={() => router.push('/transaction/new')} />
      <Button title="Wyloguj" variant="secondary" onPress={() => void supabase.auth.signOut()} />
    </Centered>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 22, fontWeight: '700', color: colors.text },
  muted: { color: colors.muted, textAlign: 'center' },
});
