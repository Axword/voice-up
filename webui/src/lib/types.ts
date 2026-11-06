export type CommandMode = 'click' | 'timed' | 'toggle';
export interface VoiceCommand { id: string; phrase: string; keys: string[]; mode: CommandMode; duration_ms: number; enabled: boolean }
import type { Language } from './i18n';
export interface Profile { id: string; name: string; game: string; language: Language; commands: VoiceCommand[] }
export interface ProfilesDocument { version: 1; active_profile_id: string; profiles: Profile[] }
export interface Status {
  listening: boolean; active_profile_id: string; profile_name: string; mappings_count: number;
  held_keys: string[]; held_command_ids: string[]; engine_id: string; engine_name: string | null;
  version: string; last_command: string | null; last_heard: string | null; error?: string | null;
}
export interface Settings {
  language: string; ui_language: Language; engine_id: string; audio_device: string | null; start_with_windows: boolean;
  start_listening_on_launch: boolean; matching_threshold: number; theme: 'light' | 'dark' | 'system';
}
export interface AudioDevice { id: string; name: string; default: boolean }
export interface Engine { id: string; name: string; backend: string; speed: string; quality: string; size_bytes: number; installed: boolean; active: boolean; requires_cuda: boolean }
export interface HeardItem {
  at: number;
  phrase: string;
  keys: string[];
  matched: boolean;
  executed?: boolean;
  command_id?: string;
  profile_id?: string;
  profile_name?: string;
  mode?: CommandMode;
  duration_ms?: number;
  held?: boolean;
  error?: string;
}
export interface TestResult { text: string; matched: boolean; command: VoiceCommand | null; profile_id: string }
