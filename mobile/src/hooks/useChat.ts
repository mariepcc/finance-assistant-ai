import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '@/lib/api';
import { streamChat } from '@/lib/chat';
import type { ChatEvent, ChatTurn, Proposal } from '@/lib/types';

export const HISTORY_LIMIT = 6;

export type ProposalState = 'pending' | 'saved' | 'rejected' | 'expired' | 'handled';

export interface UserItem {
  id: string;
  role: 'user';
  text: string;
}

export interface AssistantItem {
  id: string;
  role: 'assistant';
  text: string;
  status: string | null;
  proposals: { proposal: Proposal; state: ProposalState }[];
  error: string | null;
  pending: boolean;
}

export type ChatItem = UserItem | AssistantItem;

let counter = 0;
const nextId = () => `${Date.now()}-${++counter}`;

export function historyFrom(items: ChatItem[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (const item of items) {
    if (item.role === 'user') turns.push({ role: 'user', content: item.text });
    else if (!item.pending && !item.error && item.text) {
      turns.push({ role: 'assistant', content: item.text });
    }
  }
  return turns.slice(-HISTORY_LIMIT);
}

function applyEvent(item: AssistantItem, event: ChatEvent): AssistantItem {
  switch (event.type) {
    case 'status':
      return { ...item, status: event.data.text };
    case 'proposal':
      return {
        ...item,
        proposals: [...item.proposals, { proposal: event.data, state: 'pending' }],
      };
    case 'token':
      return { ...item, text: item.text + event.data.text, status: null };
    case 'done':
      return { ...item, pending: false, status: null };
    case 'error':
      return { ...item, pending: false, status: null, error: event.data.message };
  }
}

export function useChat() {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [sending, setSending] = useState(false);
  const categories = useRef<string[]>([]);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const update = useCallback((id: string, fn: (item: AssistantItem) => AssistantItem) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id && item.role === 'assistant' ? fn(item) : item)),
    );
  }, []);

  const send = useCallback(
    async (raw: string) => {
      const message = raw.trim();
      if (!message || sending) return;
      const history = historyFrom(items);
      const assistantId = nextId();
      setItems((prev) => [
        ...prev,
        { id: nextId(), role: 'user', text: message },
        {
          id: assistantId,
          role: 'assistant',
          text: '',
          status: 'Łączę się z asystentem…',
          proposals: [],
          error: null,
          pending: true,
        },
      ]);
      setSending(true);
      const controller = new AbortController();
      abort.current = controller;
      try {
        await streamChat(
          { message, history, previous_categories: categories.current },
          (event) => {
            if (event.type === 'done') categories.current = event.data.categories;
            update(assistantId, (item) => applyEvent(item, event));
          },
          controller.signal,
        );
        update(assistantId, (item) =>
          item.pending
            ? {
                ...item,
                pending: false,
                status: null,
                error: item.text ? null : 'Przerwano odpowiedź.',
              }
            : item,
        );
      } catch (err) {
        if (controller.signal.aborted) return;
        const text =
          err instanceof ApiError ? err.message : 'Brak połączenia z serwerem. Spróbuj ponownie.';
        update(assistantId, (item) => ({ ...item, pending: false, status: null, error: text }));
      } finally {
        setSending(false);
      }
    },
    [items, sending, update],
  );

  const setProposalState = useCallback((proposalId: string, state: ProposalState) => {
    setItems((prev) =>
      prev.map((item) =>
        item.role === 'assistant' &&
        item.proposals.some((p) => p.proposal.proposal_id === proposalId)
          ? {
              ...item,
              proposals: item.proposals.map((p) =>
                p.proposal.proposal_id === proposalId ? { ...p, state } : p,
              ),
            }
          : item,
      ),
    );
  }, []);

  const reset = useCallback(() => {
    abort.current?.abort();
    categories.current = [];
    setItems([]);
    setSending(false);
  }, []);

  return { items, sending, send, setProposalState, reset };
}
