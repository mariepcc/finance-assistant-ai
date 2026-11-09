import { fetch } from 'expo/fetch';

import { ApiError, detailMessage } from './api';
import { env } from './env';
import { supabase } from './supabase';
import type { ChatEvent, ChatRequest } from './types';

const EVENT_TYPES = new Set<ChatEvent['type']>(['status', 'proposal', 'token', 'done', 'error']);

export function parseFrame(frame: string): ChatEvent | null {
  let type = '';
  const data: string[] = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) type = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
  }
  if (!EVENT_TYPES.has(type as ChatEvent['type']) || data.length === 0) return null;
  try {
    return { type, data: JSON.parse(data.join('\n')) } as ChatEvent;
  } catch {
    return null;
  }
}

export async function streamChat(
  body: ChatRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const res = await fetch(`${env.apiUrl}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const payload: unknown = await res.json().catch(() => null);
    throw new ApiError(res.status, detailMessage(payload, res.status));
  }
  if (!res.body) throw new ApiError(res.status, 'Serwer nie zwrócił strumienia odpowiedzi');

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer = (buffer + value).replace(/\r\n/g, '\n');
    let end = buffer.indexOf('\n\n');
    while (end >= 0) {
      const event = parseFrame(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      if (event) onEvent(event);
      end = buffer.indexOf('\n\n');
    }
  }
  const tail = parseFrame(buffer);
  if (tail) onEvent(tail);
}
