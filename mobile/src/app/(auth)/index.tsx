import { Link } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text } from 'react-native';

import { colors, spacing } from '@/components/theme';
import { Button, ErrorText, Field } from '@/components/ui';
import { supabase } from '@/lib/supabase';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function signIn() {
    setError(null);
    setLoading(true);
    const { error: authError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setLoading(false);
    if (authError) setError('Nieprawidłowy e-mail lub hasło');
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.container}
    >
      <Text style={styles.title}>Asystent finansowy</Text>
      <Field
        label="E-mail"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      <Field
        label="Hasło"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="current-password"
        textContentType="password"
      />
      <ErrorText>{error}</ErrorText>
      <Button title="Zaloguj się" onPress={signIn} loading={loading} disabled={!email || !password} />
      <Link href="/register" style={styles.link}>
        Nie masz konta? Zarejestruj się
      </Link>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: spacing.lg, gap: spacing.md, justifyContent: 'center' },
  title: { fontSize: 28, fontWeight: '700', color: colors.text, marginBottom: spacing.md },
  link: { color: colors.primary, textAlign: 'center', marginTop: spacing.sm, fontSize: 15 },
});
