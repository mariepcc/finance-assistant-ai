import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '../theme';

const QUESTIONS = [
  'Ile wydam do końca miesiąca?',
  'Czy w tym miesiącu było coś nietypowego?',
  'Na co wydaję najwięcej?',
];

export function AskAssistant() {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Ionicons name="sparkles" size={18} color={colors.primary} />
        <Text style={styles.title}>Zapytaj asystenta</Text>
      </View>
      <View style={{ gap: spacing.sm }}>
        {QUESTIONS.map((q) => (
          <Pressable
            key={q}
            accessibilityRole="button"
            style={({ pressed }) => [styles.question, pressed && { opacity: 0.7 }]}
            onPress={() => router.push({ pathname: '/chat', params: { q } })}
          >
            <Text style={styles.questionText}>{q}</Text>
            <Ionicons name="arrow-forward" size={16} color={colors.primary} />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#EEF2FF',
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md,
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  title: { fontSize: 17, fontWeight: '700', color: colors.text },
  question: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
  },
  questionText: { flex: 1, fontSize: 14, color: colors.text },
});
