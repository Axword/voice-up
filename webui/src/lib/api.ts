import type { AudioDevice, Engine, ModuleInfo, ProfilesDocument, Settings, Status, TestResult } from './types';
import { t } from './i18n';
interface Session { token: string; apiBase: string }
declare global { interface Window { __LOLVOICE__?: Partial<Session> } }
const session: Session = { token: '', apiBase: '/api/v1' };
export function bootToken(): void {
  const boot = window.__LOLVOICE__;
  if (typeof boot?.token === 'string') session.token = boot.token;
  if (typeof boot?.apiBase === 'string') session.apiBase = boot.apiBase;
}
export function wsUrl(): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/status?token=${encodeURIComponent(session.token)}`;
}
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${session.apiBase}${path}`, {
      method, headers: { 'X-Auth-Token': session.token, ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("Brak połączenia z lokalną aplikacją Voice Control.");
  }
  if (!response.ok) {
    let detail = '';
    try {
      const error = await response.json();
      detail = typeof error.detail === 'string' ? error.detail : Array.isArray(error.detail)
        ? error.detail.map((item: { msg: string; loc?: unknown[] }) => `${item.loc?.join('.') ?? ''}: ${item.msg}`).join('; ') : '';
    } catch { /* Fall back to HTTP status. */ }
    throw new Error(detail || t('Błąd połączenia ({status}).',{status:response.status}));
  }
  return response.json() as Promise<T>;
}
const icons = new Map<string, Promise<string | null>>();
export const api = {
  // Fetched with the token header and shown from a blob URL, so the token never appears in a URL.
  iconBlobUrl: async (profileId: string): Promise<string | null> => {
    const cached = icons.get(profileId);
    if (cached) return cached;
    const pending = (async () => {
      try {
        const response = await fetch(`${session.apiBase}/profiles/${encodeURIComponent(profileId)}/icon`, { headers: { 'X-Auth-Token': session.token } });
        return response.ok ? URL.createObjectURL(await response.blob()) : null;
      } catch { return null; }
    })();
    icons.set(profileId, pending);
    return pending;
  },
  installedProfiles: () => request<{ ids: string[] }>('/profiles/installed'),
  modules: () => request<{ modules: ModuleInfo[] }>('/modules'),
  status: () => request<Status>('/status'),
  profiles: () => request<ProfilesDocument>('/profiles'),
  saveProfiles: (document: ProfilesDocument) => request<ProfilesDocument>('/profiles', 'PUT', document),
  settings: () => request<Settings>('/settings'),
  saveSettings: (patch: Partial<Settings>) => request<Settings>('/settings', 'PUT', patch),
  start: () => request<{ listening: boolean; error?: string }>('/listening/start', 'POST'),
  stop: () => request<{ listening: boolean; error?: string }>('/listening/stop', 'POST'),
  release: () => request<{ released: boolean }>('/keys/release', 'POST'),
  test: (text: string) => request<TestResult>('/commands/test', 'POST', { text }),
  engines: () => request<{ engines: Engine[] }>('/engines'),
  downloadEngine: (id: string) => request<{ started: boolean }>(`/engines/${encodeURIComponent(id)}/download`, 'POST'),
  cancelEngine: (id: string) => request<unknown>(`/engines/${encodeURIComponent(id)}/cancel`, 'POST'),
  activateEngine: (id: string) => request<{ engine_id: string }>(`/engines/${encodeURIComponent(id)}/activate`, 'POST'),
  devices: () => request<{ devices: AudioDevice[]; error?: string }>('/audio/devices'),
  testAudio: () => request<{ level: number; transcript: string; error?: string }>('/audio/test', 'POST', { seconds: 3 }),
};
