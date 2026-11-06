import { computed, effect, signal } from '@preact/signals';
import { api, wsUrl } from './api';
import type { HeardItem, ProfilesDocument, Settings, Status } from './types';
import { uiLanguage, languages, locale } from './i18n';
export const view = signal<'commands' | 'settings' | 'activity'>('commands');
export const profiles = signal<ProfilesDocument | null>(null);
export const settings = signal<Settings | null>(null);
export const status = signal<Status | null>(null);
export const connection = signal<'connecting' | 'online' | 'offline'>('connecting');
export const error = signal('');
export const busy = signal(false);
export const heard = signal<HeardItem[]>([]);
export const downloads = signal<Record<string, { percent?: number; error?: string; done?: boolean; cancelled?: boolean }>>({});
export const activeProfile = computed(() => profiles.value?.profiles.find(p => p.id === profiles.value?.active_profile_id) ?? null);
const systemDark = matchMedia('(prefers-color-scheme: dark)');
const dark = signal(systemDark.matches);
systemDark.addEventListener('change', e => { dark.value = e.matches; });
effect(() => {
  const choice = settings.value?.theme ?? 'light';
  document.documentElement.dataset.theme = choice === 'system' ? dark.value ? 'dark' : 'light' : choice;
});
effect(() => {
  const choice = settings.value?.ui_language;
  uiLanguage.value = languages.some(item=>item.id===choice) ? choice! : 'pl_PL';
});
effect(() => { document.documentElement.lang = locale().split('-')[0]; });
export async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
  if (busy.value) return;
  busy.value = true; error.value = '';
  try { return await action(); }
  catch (cause) { error.value = cause instanceof Error ? cause.message : "Nie udało się wykonać działania."; }
  finally { busy.value = false; }
}
export async function saveProfiles(next: ProfilesDocument): Promise<boolean> {
  const saved = await run(() => api.saveProfiles(next));
  if (!saved) return false;
  profiles.value = saved;
  const [nextStatus,nextSettings] = await Promise.all([api.status().catch(()=>status.value),api.settings().catch(()=>settings.value)]);
  status.value = nextStatus; settings.value = nextSettings;
  return true;
}
export async function patchSettings(patch: Partial<Settings>): Promise<void> {
  const saved = await run(() => api.saveSettings(patch));
  if (saved) {
    settings.value = saved;
    if (patch.language) {
      const [nextProfiles,nextStatus] = await Promise.all([api.profiles().catch(()=>profiles.value),api.status().catch(()=>status.value)]);
      profiles.value = nextProfiles; status.value = nextStatus;
    }
  }
}
export async function refreshAll(): Promise<void> {
  try {
    const [nextStatus, nextProfiles, nextSettings] = await Promise.all([api.status(), api.profiles(), api.settings()]);
    status.value = nextStatus; profiles.value = nextProfiles; settings.value = nextSettings;
    connection.value = 'online'; error.value = nextStatus.error ?? '';
  } catch (cause) {
    connection.value = 'offline';
    error.value = cause instanceof Error ? cause.message : "Nie udało się połączyć z aplikacją.";
  }
}
let socket: WebSocket | null = null;
let retry: ReturnType<typeof setTimeout> | undefined;
let backoff = 1000;
export function connect(): void {
  clearTimeout(retry);
  if (socket && socket.readyState < WebSocket.CLOSING) return;
  const ws = new WebSocket(wsUrl()); socket = ws;
  ws.onopen = () => { backoff = 1000; connection.value = 'online'; void refreshAll(); };
  ws.onmessage = e => {
    try {
      const frame = JSON.parse(String(e.data));
      if (frame.type === 'status') {
        if (typeof frame.error === 'string' && frame.error && frame.error !== status.value?.error) error.value = frame.error;
        status.value = frame as Status;
      }
      if (frame.type === 'heard') {
        const matched = frame.matched;
        const keys = Array.isArray(frame.keys) ? frame.keys : Array.isArray(matched) ? matched
          : typeof matched === 'string' ? [matched] : matched?.keys ?? [];
        const profileId = typeof frame.profile_id === 'string' ? frame.profile_id : status.value?.active_profile_id;
        const profile = profiles.value?.profiles.find(item => item.id === profileId);
        const normalize = (text: string) => text.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l').replace(/[^\p{L}\p{N}\s_]/gu, ' ').trim().replace(/\s+/g, ' ');
        const command = profile?.commands.find(item => typeof frame.command_id === 'string'
          ? item.id === frame.command_id : normalize(item.phrase) === normalize(String(frame.text ?? '')));
        const mode = frame.mode === 'click' || frame.mode === 'timed' || frame.mode === 'toggle' ? frame.mode : command?.mode;
        const at = typeof frame.time === 'number' && Number.isFinite(frame.time) && frame.time > 0 ? frame.time * 1000 : Date.now();
        heard.value = [{ at, phrase: String(frame.text ?? ''), keys: keys.filter((key:unknown):key is string => typeof key === 'string'),
          matched: Boolean(matched), executed: typeof frame.executed === 'boolean' ? frame.executed : undefined,
          command_id: typeof frame.command_id === 'string' ? frame.command_id : command?.id,
          profile_id: profileId, profile_name: typeof frame.profile_name === 'string' ? frame.profile_name : profile?.name,
          mode, duration_ms: typeof frame.duration_ms === 'number' ? frame.duration_ms : command?.duration_ms,
          held: typeof frame.held === 'boolean' ? frame.held : undefined,
          error: typeof frame.error === 'string' && frame.error ? frame.error
            : matched && frame.executed === false ? "Nie udało się wykonać komendy." : undefined }, ...heard.value].slice(0, 100);
      }
      if (frame.type === 'download' && frame.engine_id)
        downloads.value = { ...downloads.value, [frame.engine_id]: {
          percent: frame.percent, error: frame.error, done: frame.done, cancelled: frame.cancelled } };
    } catch { /* Ignore incomplete frames. */ }
  };
  ws.onclose = () => {
    if (socket !== ws) return;
    socket = null; connection.value = 'offline';
    retry = setTimeout(() => { backoff = Math.min(backoff * 2, 15000); connect(); }, backoff);
  };
  ws.onerror = () => ws.close();
}
export function retryNow(): void {
  clearTimeout(retry); const old = socket; socket = null; old?.close();
  connection.value = 'connecting'; backoff = 1000; connect(); void refreshAll();
}
