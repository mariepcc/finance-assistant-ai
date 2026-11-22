import Ionicons from '@expo/vector-icons/Ionicons';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { type ComponentProps, type ReactNode, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { colors, radius, spacing } from '@/components/theme';
import { Button, ErrorText } from '@/components/ui';
import { useMe, useUpdateMe } from '@/hooks/queries';
import { supabase } from '@/lib/supabase';
import { useAuth } from '@/providers/AuthProvider';

type IconName = ComponentProps<typeof Ionicons>['name'];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={{ gap: spacing.sm }}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={styles.group}>{children}</View>
    </View>
  );
}

function Row({
  icon,
  label,
  value,
  onPress,
  last,
}: {
  icon: IconName;
  label: string;
  value?: string;
  onPress?: () => void;
  last?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole={onPress ? 'button' : undefined}
      disabled={!onPress}
      onPress={onPress}
      style={({ pressed }) => [styles.row, !last && styles.rowBorder, pressed && { opacity: 0.6 }]}
    >
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={18} color={colors.primary} />
      </View>
      <Text style={styles.rowLabel}>{label}</Text>
      {value ? <Text style={styles.rowValue}>{value}</Text> : null}
      {onPress ? <Ionicons name="chevron-forward" size={16} color={colors.muted} /> : null}
    </Pressable>
  );
}

function initials(name: string | null | undefined, email: string | undefined): string {
  const source = name?.trim() || email || '?';
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? '?') + (name?.trim() ? (parts[1]?.[0] ?? '') : '')).toUpperCase();
}

export default function ProfileScreen() {
  const { session } = useAuth();
  const me = useMe();
  const update = useUpdateMe();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');

  const email = session?.user.email;
  const displayName = me.data?.display_name ?? null;
  const consent = me.data?.gdpr_consent_at
    ? new Date(me.data.gdpr_consent_at).toLocaleDateString('pl-PL')
    : undefined;

  const startEditing = () => {
    update.reset();
    setName(displayName ?? '');
    setEditing(true);
  };

  const save = () =>
    update.mutate({ display_name: name.trim() }, { onSuccess: () => setEditing(false) });

  const signOut = () =>
    Alert.alert('Wylogować się?', undefined, [
      { text: 'Anuluj', style: 'cancel' },
      { text: 'Wyloguj', style: 'destructive', onPress: () => void supabase.auth.signOut() },
    ]);

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.hero}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{initials(displayName, email)}</Text>
        </View>
        {editing ? (
          <View style={styles.editor}>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Jak mamy się do Ciebie zwracać?"
              placeholderTextColor={colors.muted}
              maxLength={60}
              autoFocus
              style={styles.input}
              returnKeyType="done"
              onSubmitEditing={save}
            />
            <View style={styles.editorActions}>
              <View style={{ flex: 1 }}>
                <Button title="Zapisz" onPress={save} loading={update.isPending} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title="Anuluj" variant="secondary" onPress={() => setEditing(false)} />
              </View>
            </View>
            <ErrorText>{update.error?.message}</ErrorText>
          </View>
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Zmień imię"
            onPress={startEditing}
            style={styles.nameRow}
          >
            <Text style={styles.name}>{displayName || 'Dodaj imię'}</Text>
            <Ionicons name="pencil" size={14} color={colors.muted} />
          </Pressable>
        )}
        {email ? <Text style={styles.email}>{email}</Text> : null}
      </View>

      <Section title="Ustawienia">
        <Row icon="cash-outline" label="Waluta domyślna" value={me.data?.default_currency} />
        <Row
          icon="shield-checkmark-outline"
          label="Zgoda na przetwarzanie danych"
          value={consent ? `od ${consent}` : undefined}
          last
        />
      </Section>

      <Section title="Finanse">
        <Row icon="repeat" label="Stałe płatności" onPress={() => router.push('/recurring')} />
        <Row icon="pie-chart-outline" label="Budżety" onPress={() => router.push('/budgets')} />
        <Row
          icon="chatbubbles-outline"
          label="Asystent"
          onPress={() => router.push('/chat')}
          last
        />
      </Section>

      <Section title="O aplikacji">
        <Row
          icon="information-circle-outline"
          label="Wersja"
          value={Constants.expoConfig?.version ?? '—'}
        />
        <Row icon="sparkles-outline" label="Model asystenta" value="Claude Haiku" last />
      </Section>

      <Button title="Wyloguj się" variant="danger" onPress={signOut} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.lg, paddingBottom: spacing.lg * 2 },
  hero: { alignItems: 'center', gap: spacing.xs, paddingVertical: spacing.md },
  avatar: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  avatarText: { fontSize: 30, fontWeight: '700', color: colors.primaryText },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  name: { fontSize: 22, fontWeight: '700', color: colors.text },
  email: { fontSize: 14, color: colors.muted },
  editor: { alignSelf: 'stretch', gap: spacing.sm },
  editorActions: { flexDirection: 'row', gap: spacing.sm },
  input: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.text,
    textAlign: 'center',
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.muted,
    textTransform: 'uppercase',
    marginLeft: spacing.xs,
  },
  group: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: spacing.md,
    paddingVertical: 13,
  },
  rowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowIcon: {
    width: 30,
    height: 30,
    borderRadius: 8,
    backgroundColor: '#EEF2FF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowLabel: { flex: 1, fontSize: 15, color: colors.text },
  rowValue: { fontSize: 15, color: colors.muted },
});
