import * as SecureStore from 'expo-secure-store';

const CHUNK = 1800;

const safeKey = (key: string) => key.replace(/[^A-Za-z0-9._-]/g, '_');
const countKey = (key: string) => `${safeKey(key)}.n`;
const chunkKey = (key: string, i: number) => `${safeKey(key)}.${i}`;

async function removeItem(key: string): Promise<void> {
  const n = Number((await SecureStore.getItemAsync(countKey(key))) ?? '0');
  await Promise.all(
    Array.from({ length: n }, (_, i) => SecureStore.deleteItemAsync(chunkKey(key, i))),
  );
  await SecureStore.deleteItemAsync(countKey(key));
}

async function getItem(key: string): Promise<string | null> {
  const raw = await SecureStore.getItemAsync(countKey(key));
  if (raw === null) return null;
  const parts = await Promise.all(
    Array.from({ length: Number(raw) }, (_, i) => SecureStore.getItemAsync(chunkKey(key, i))),
  );
  return parts.some((p) => p === null) ? null : parts.join('');
}

async function setItem(key: string, value: string): Promise<void> {
  await removeItem(key);
  const chunks = value.match(new RegExp(`[\\s\\S]{1,${CHUNK}}`, 'g')) ?? [''];
  await Promise.all(chunks.map((c, i) => SecureStore.setItemAsync(chunkKey(key, i), c)));
  await SecureStore.setItemAsync(countKey(key), String(chunks.length));
}

export const secureStorage = { getItem, setItem, removeItem };
