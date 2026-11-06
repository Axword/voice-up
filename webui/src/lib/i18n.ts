import { signal } from '@preact/signals';
import en from './locales/en.json';
import de from './locales/de.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import uk from './locales/uk.json';

export const languages = [
  {id:'pl_PL', label:'Polski'}, {id:'en_US', label:'English'},
  {id:'de_DE', label:'Deutsch'}, {id:'es_ES', label:'Español'},
  {id:'fr_FR', label:'Français'}, {id:'uk_UA', label:'Українська'},
] as const;
export type Language = typeof languages[number]['id'];
export type TranslationKey = keyof typeof en;
export const uiLanguage = signal<Language>('pl_PL');
const dictionaries: Record<string, Record<TranslationKey, string>> = {en_US:en,de_DE:de,es_ES:es,fr_FR:fr,uk_UA:uk};

export function t(source: TranslationKey, values: Record<string,string|number> = {}): string {
  const translated = dictionaries[uiLanguage.value]?.[source] ?? source;
  return translated.replace(/\{(\w+)\}/g, (placeholder, key:string) => String(values[key] ?? placeholder));
}
export function translateMessage(message: string): string {
  return Object.prototype.hasOwnProperty.call(en, message) ? t(message as TranslationKey) : message;
}
export function locale(): string { return uiLanguage.value.replace('_','-'); }
export function languageName(language: string): string {
  return languages.find(item=>item.id===language)?.label ?? language;
}
export function keyLabel(key: string): string {
  const labels: Record<string,string> = {ctrl:'Ctrl',shift:'Shift',alt:'Alt',cmd:'Win',enter:'Enter',esc:'Esc',tab:'Tab',backspace:'Backspace',up:'↑',down:'↓',left:'←',right:'→',caps_lock:'Caps Lock',delete:'Del'};
  if(key==='space') return t('Spacja');
  if(key==='left_click') return t('LPM');
  if(key==='right_click') return t('PPM');
  if(key==='middle_click') return t('ŚPM');
  return labels[key] ?? key.toUpperCase();
}
