import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text } from 'react-native';

import { colors, spacing } from '@/components/theme';
import { Button, ErrorText, Field } from '@/components/ui';
import { supabase } from '@/lib/supabase';

const MIN_PASSWORD = 8;

export default function RegisterScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function signUp() {
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(`Hasło musi mieć co najmniej ${MIN_PASSWORD} znaków`);
      return;
    }
    if (password !== repeat) {
      setError('Hasła nie są takie same');
      return;
    }
    setLoading(true);
    const { data, error: authError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
    });
    setLoading(false);
    if (authError) {
      setError(authError.message);
    } else if (!data.session) {
      setInfo('Sprawdź skrzynkę i potwierdź adres e-mail, a potem się zaloguj.');
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.container}
    >
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
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <Field label="Powtórz hasło" value={repeat} onChangeText={setRepeat} secureTextEntry />
      <ErrorText>{error}</ErrorText>
      {info ? <Text style={styles.info}>{info}</Text> : null}
      <Button
        title="Utwórz konto"
        onPress={signUp}
        loading={loading}
        disabled={!email || !password}
      />
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: spacing.lg, gap: spacing.md, justifyContent: 'center' },
  info: { color: colors.income, fontSize: 14 },
});
