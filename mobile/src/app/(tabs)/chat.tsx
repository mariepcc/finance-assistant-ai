import Ionicons from '@expo/vector-icons/Ionicons';
import { type ComponentRef, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ProposalCard } from '@/components/ProposalCard';
import { colors, radius, spacing } from '@/components/theme';
import { Chip } from '@/components/ui';
import { type AssistantItem, type ChatItem, useChat } from '@/hooks/useChat';

const EXAMPLES = [
  'Kawa 14 zł i bilet 4,40',
  'Ile wydałam w tym miesiącu na jedzenie?',
  'Jak stoją moje budżety?',
  'Porównaj wydatki z poprzednim miesiącem',
];
const HEADER_OFFSET = 100;

function AssistantBubble({
  item,
  onProposalState,
  onCorrect,
}: {
  item: AssistantItem;
  onProposalState: ReturnType<typeof useChat>['setProposalState'];
  onCorrect: () => void;
}) {
  return (
    <View style={styles.assistantRow}>
      {item.text ? (
        <View style={[styles.bubble, styles.assistantBubble]}>
          <Text style={styles.assistantText}>{item.text}</Text>
        </View>
      ) : null}
      {item.status ? (
        <View style={styles.status}>
          <ActivityIndicator size="small" color={colors.muted} />
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      ) : null}
      {item.proposals.map(({ proposal, state }) => (
        <ProposalCard
          key={proposal.proposal_id}
          proposal={proposal}
          state={state}
          onStateChange={(next) => onProposalState(proposal.proposal_id, next)}
          onCorrect={onCorrect}
        />
      ))}
      {item.error ? <Text style={styles.error}>{item.error}</Text> : null}
    </View>
  );
}

export default function ChatScreen() {
  const { items, sending, send, setProposalState, reset } = useChat();
  const [draft, setDraft] = useState('');
  const list = useRef<FlatList<ChatItem>>(null);
  const input = useRef<ComponentRef<typeof TextInput>>(null);

  const submit = (text: string) => {
    if (!text.trim() || sending) return;
    setDraft('');
    void send(text);
  };

  const renderItem = ({ item }: { item: ChatItem }) =>
    item.role === 'user' ? (
      <View style={[styles.bubble, styles.userBubble]}>
        <Text style={styles.userText}>{item.text}</Text>
      </View>
    ) : (
      <AssistantBubble
        item={item}
        onProposalState={setProposalState}
        onCorrect={() => input.current?.focus()}
      />
    );

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? HEADER_OFFSET : 0}
    >
      <FlatList
        ref={list}
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>Zapytaj o swoje finanse</Text>
            <Text style={styles.emptyText}>
              Napisz wydatek zwykłym zdaniem albo zadaj pytanie. Zapis następuje dopiero po
              potwierdzeniu.
            </Text>
            <View style={styles.examples}>
              {EXAMPLES.map((example) => (
                <Chip
                  key={example}
                  label={example}
                  selected={false}
                  onPress={() => submit(example)}
                />
              ))}
            </View>
          </View>
        }
      />
      <View style={styles.inputRow}>
        {items.length > 0 ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Nowa rozmowa"
            onPress={reset}
            style={styles.iconButton}
          >
            <Ionicons name="refresh" size={22} color={colors.muted} />
          </Pressable>
        ) : null}
        <TextInput
          ref={input}
          value={draft}
          onChangeText={setDraft}
          placeholder="Napisz wiadomość…"
          placeholderTextColor={colors.muted}
          multiline
          maxLength={2000}
          style={styles.input}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Wyślij"
          onPress={() => submit(draft)}
          disabled={sending || !draft.trim()}
          style={({ pressed }) => [
            styles.send,
            (sending || !draft.trim() || pressed) && { opacity: 0.5 },
          ]}
        >
          {sending ? (
            <ActivityIndicator color={colors.primaryText} />
          ) : (
            <Ionicons name="arrow-up" size={20} color={colors.primaryText} />
          )}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.md, gap: spacing.sm, flexGrow: 1 },
  bubble: { borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 10, maxWidth: '85%' },
  userBubble: { alignSelf: 'flex-end', backgroundColor: colors.primary },
  userText: { color: colors.primaryText, fontSize: 16 },
  assistantRow: { alignSelf: 'stretch' },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  assistantText: { color: colors.text, fontSize: 16, lineHeight: 22 },
  status: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: 6 },
  statusText: { color: colors.muted, fontSize: 14 },
  error: { color: colors.danger, fontSize: 14, marginTop: spacing.xs },
  empty: { flex: 1, justifyContent: 'center', gap: spacing.md, paddingVertical: spacing.lg },
  emptyTitle: { fontSize: 20, fontWeight: '600', color: colors.text },
  emptyText: { fontSize: 15, color: colors.muted, lineHeight: 21 },
  examples: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    padding: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.card,
  },
  iconButton: { padding: 9 },
  input: {
    flex: 1,
    maxHeight: 120,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingTop: 10,
    paddingBottom: 10,
    fontSize: 16,
    color: colors.text,
  },
  send: {
    backgroundColor: colors.primary,
    borderRadius: radius.pill,
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
