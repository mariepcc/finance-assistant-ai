import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '@/components/theme';
import { Button, Chip, ErrorText } from '@/components/ui';
import { useAcceptConsent, useMe } from '@/hooks/queries';
import { supabase } from '@/lib/supabase';

const CURRENCIES = ['PLN', 'EUR', 'USD'] as const;

export default function OnboardingScreen() {
  const me = useMe();
  const consent = useAcceptConsent();
  const [accepted, setAccepted] = useState(false);
  const [currency, setCurrency] = useState<string>('PLN');

  if (me.isError) {
    return (
      <View style={styles.container}>
        <ErrorText>Nie udało się połączyć z serwerem: {me.error.message}</ErrorText>
        <Button title="Spróbuj ponownie" onPress={() => void me.refetch()} />
        <Button title="Wyloguj" variant="secondary" onPress={() => void supabase.auth.signOut()} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Zanim zaczniemy</Text>
      <Text style={styles.body}>
        Aplikacja przechowuje Twoje transakcje, kategorie i budżety, aby pokazywać podsumowania.
        Asystent AI otrzymuje tylko dane potrzebne do odpowiedzi na Twoje pytanie.
      </Text>
      <Chip
        label={accepted ? '✓ Wyrażam zgodę na przetwarzanie danych' : 'Wyrażam zgodę na przetwarzanie danych'}
        selected={accepted}
        onPress={() => setAccepted((v) => !v)}
      />

      <Text style={styles.section}>Waluta domyślna</Text>
      <View style={styles.row}>
        {CURRENCIES.map((c) => (
          <Chip key={c} label={c} selected={currency === c} onPress={() => setCurrency(c)} />
        ))}
      </View>

      <ErrorText>{consent.error?.message}</ErrorText>
      <Button
        title="Zaczynamy"
        disabled={!accepted}
        loading={consent.isPending}
        onPress={() => consent.mutate(currency)}
      />
      <Button title="Wyloguj" variant="secondary" onPress={() => void supabase.auth.signOut()} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.lg, gap: spacing.md },
  title: { fontSize: 24, fontWeight: '700', color: colors.text },
  body: { fontSize: 15, lineHeight: 22, color: colors.text },
  section: { fontSize: 16, fontWeight: '600', color: colors.text, marginTop: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.sm },
});
