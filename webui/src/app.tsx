import { useEffect, useRef, useState } from 'preact/hooks';
import type { ComponentChildren, JSX } from 'preact';
import { Icon } from './components/Icon';
import { LiveActivity } from './components/LiveActivity';
import type { IconName } from './components/Icon';
import { api } from './lib/api';
import { activeProfile, busy, connection, downloads, error, patchSettings, profiles, retryNow, run, saveProfiles, settings, status, view } from './lib/state';
import type { AudioDevice, CommandMode, Engine, Profile, TestResult, VoiceCommand } from './lib/types';
import { keyLabel, languageName, languages, locale, t, translateMessage, uiLanguage } from './lib/i18n';
import type { Language, TranslationKey } from './lib/i18n';

const modes: {id: CommandMode; icon: IconName; label: TranslationKey; title: TranslationKey}[] = [
  {id:'click', icon:'click', label:'Kliknięcie', title:'Naciśnij i puść'},
  {id:'timed', icon:'timer', label:'Przytrzymaj 3 s', title:'Przytrzymaj przez 3 sekundy'},
  {id:'toggle', icon:'toggle', label:'Przełącz trzymanie', title:'Trzymaj do ponownego wypowiedzenia komendy'},
];
const durationLabel = (milliseconds: number) => `${(milliseconds / 1000).toLocaleString(locale(), {maximumFractionDigits:3})} s`;
const id = () => crypto.randomUUID();
const normalize = (value: string) => value.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/ł/g,'l').replace(/[^\p{L}\p{N}\s_]/gu,' ').trim().replace(/\s+/g,' ');
const emptyCommand = (): VoiceCommand => ({id:id(),phrase:'',keys:[],mode:'click',duration_ms:3000,enabled:true});
const profileName = (profile: Profile): string => profile.language==='en_US'?profile.name.replace(/ · EN$/,''):profile.name;
const profileOption = (profile: Profile): string => `${profileName(profile)} · ${profile.language.split('_')[0].toUpperCase()}`;
function savedProfileLanguage(): Language|'all'|null {
  try {
    const value = localStorage.getItem('voice-control-profile-language');
    return value==='all'||languages.some(language=>language.id===value)?value as Language|'all':null;
  } catch { return null; }
}

function Button({icon, children, primary, quiet, danger, ...props}: JSX.IntrinsicElements['button'] & {
  icon?: IconName; children?: ComponentChildren; primary?: boolean; quiet?: boolean; danger?: boolean;
}) {
  return <button type="button" class={`btn ${primary ? 'primary' : ''} ${quiet ? 'quiet' : ''} ${danger ? 'danger' : ''}`} {...props}>
    {icon && <Icon name={icon} size={16}/>} {children}
  </button>;
}
function IconButton({icon, label, ...props}: JSX.IntrinsicElements['button'] & {icon: IconName; label: string}) {
  return <button type="button" class="icon-button" title={label} aria-label={label} {...props}><Icon name={icon} size={17}/></button>;
}
function Keys({keys}: {keys: string[]}) {
  return <span class="key-combination">{keys.map((key, i) => <span class="key-part" key={key}>{i > 0 && <span class="key-plus">+</span>}<kbd>{keyLabel(key)}</kbd></span>)}</span>;
}
function Toggle({checked, label, onChange, disabled}: {checked:boolean; label:string; onChange:()=>void; disabled?:boolean}) {
  return <button type="button" role="switch" aria-checked={checked} aria-label={label} class={`switch ${checked ? 'on' : ''}`} onClick={onChange} disabled={disabled}><span/></button>;
}
function Modal({title, onClose, children, wide}: {title:string;onClose:()=>void;children:ComponentChildren;wide?:boolean}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = dialog.current!;
    el.showModal();
    const onCancel = (e: Event) => { e.preventDefault(); if (!busy.value) onClose(); };
    el.addEventListener('cancel', onCancel);
    return () => { el.removeEventListener('cancel', onCancel); el.close(); };
  }, []);
  return <dialog ref={dialog} aria-label={title} class={`modal ${wide ? 'wide' : ''}`} onClick={e => {
    if (e.target === dialog.current && !busy.value) {
      const r = dialog.current!.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) onClose();
    }
  }}>
    <header class="modal-head"><h2>{title}</h2><IconButton icon="close" label={t("Zamknij")} onClick={onClose} disabled={busy.value}/></header>
    {children}
  </dialog>;
}
function ProfileMark({profile, large}: {profile:Profile;large?:boolean}) {
  const label = profile.game.toLowerCase();
  if (label==='keyboard') return <span class={`profile-mark keyboard ${large?'large':''}`}><Icon name="keyboard" size={large?30:17}/></span>;
  const mark = label.includes('league') ? 'L' : label.includes('minecraft') ? 'M' : label.includes('counter') ? 'CS' : profile.name.slice(0,2).toUpperCase();
  return <span class={`profile-mark ${label.includes('minecraft') ? 'minecraft' : ''} ${large ? 'large' : ''}`}>{mark}</span>;
}

export function App() {
  const [profileEditor, setProfileEditor] = useState<Profile | 'new' | null>(null);
  const [commandEditor, setCommandEditor] = useState<VoiceCommand | null>(null);
  const [jsonOpen, setJsonOpen] = useState(false);
  const [profileLanguage, setProfileLanguage] = useState<Language|'all'>(savedProfileLanguage()??uiLanguage.value);
  const interfaceLanguage = settings.value?.ui_language;
  useEffect(()=>{if(interfaceLanguage&&!savedProfileLanguage())setProfileLanguage(interfaceLanguage);},[interfaceLanguage]);
  function filterProfileLanguage(language: Language|'all') {
    setProfileLanguage(language);
    try { localStorage.setItem('voice-control-profile-language',language); } catch { /* Filtering works without storage. */ }
  }
  const profile = activeProfile.value;
  const filteredProfiles = (profiles.value?.profiles??[]).filter(item=>profileLanguage==='all'||item.language===profileLanguage)
    .sort((a,b)=>Number(b.id.startsWith('basic-keyboard'))-Number(a.id.startsWith('basic-keyboard')));
  const online = connection.value === 'online';
  async function selectProfile(nextId: string) {
    if (!profiles.value || busy.value) return;
    if (nextId !== profiles.value.active_profile_id) await saveProfiles({...profiles.value,active_profile_id:nextId});
    view.value = 'commands';
  }
  async function listen() {
    await run(async () => {
      const response = status.value?.listening ? await api.stop() : await api.start();
      status.value = await api.status();
      if (response.error) throw new Error(response.error);
      if (!response.listening && status.value.error) throw new Error(status.value.error);
    });
  }
  return <div class="app-shell">
    <header class="topbar">
      <a class="brand" href="https://axword.pl/" target="_blank" rel="noopener noreferrer">Axword<span>/</span><span class="brand-product">Voice Control</span></a>
      <div class="topbar-actions">
        <select class="language-select" aria-label={t('Język interfejsu')} value={settings.value?.ui_language??'pl_PL'} disabled={!online||busy.value} onChange={e=>void patchSettings({ui_language:e.currentTarget.value as Language})}>{languages.map(language=><option key={language.id} value={language.id}>{language.label}</option>)}</select>
        <span class={`connection-label ${online ? 'connected' : ''}`}><i/>{online ? t("Połączono lokalnie") : connection.value === 'connecting' ? t("Łączenie…") : t("Brak połączenia")}</span>
        <span class="topbar-divider"/>
        <IconButton icon={settings.value?.theme === 'dark' ? 'sun' : 'moon'} label={settings.value?.theme === 'dark' ? t("Włącz jasny motyw") : t("Włącz ciemny motyw")} disabled={!online || busy.value}
          onClick={() => void patchSettings({theme:settings.value?.theme === 'dark' ? 'light' : 'dark'})}/>
      </div>
    </header>
    <aside class="sidebar">
      <nav aria-label={t("Panel")}>
        <button class={`nav-item ${view.value === 'commands' ? 'selected' : ''}`} onClick={()=>{view.value='commands';}}><Icon name="command"/>{t("Komendy głosowe")}</button>
        <button class={`nav-item ${view.value === 'activity' ? 'selected' : ''}`} onClick={()=>{view.value='activity';}}><Icon name="activity"/>{t("Aktywność")}</button>
        <button class={`nav-item ${view.value === 'settings' ? 'selected' : ''}`} onClick={()=>{view.value='settings';}}><Icon name="settings"/>{t("Ustawienia")}</button>
      </nav>
      <div class="sidebar-section">
        <div class="sidebar-label"><span>{t("PROFILE GIER")}</span><IconButton icon="plus" label={t("Dodaj profil")} disabled={!online || busy.value} onClick={()=>setProfileEditor('new')}/></div>
        <label class="profile-language-filter"><span>{t('Język profili')}</span><select aria-label={t('Język profili')} value={profileLanguage} onChange={e=>filterProfileLanguage(e.currentTarget.value as Language|'all')}><option value="all">{t('Wszystkie języki')}</option>{languages.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <nav class="profile-nav" aria-label={t("Profile gier")}>{filteredProfiles.map(p =>
          <button key={p.id} title={`${p.name} · ${languageName(p.language)}`} class={`profile-nav-item ${p.id===profile?.id ? 'active' : ''}`} onClick={()=>void selectProfile(p.id)} disabled={!online || busy.value}>
            <ProfileMark profile={p}/><span>{profileName(p)}</span><span class="profile-language" title={languageName(p.language)}>{p.language.split('_')[0].toUpperCase()}</span>{p.id===profile?.id && <span class="profile-dot"/>}
          </button>
        )}</nav>
        <button class="add-profile" onClick={()=>setProfileEditor('new')} disabled={!online || busy.value}><Icon name="plus" size={15}/>{t("Nowy profil")}</button>
      </div>
      <div class="sidebar-bottom">
        <button onClick={()=>setJsonOpen(true)} disabled={!online || !profiles.value}><Icon name="code" size={16}/>{t("Import / eksport JSON")}</button>
        <a href="https://axword.pl/" target="_blank" rel="noopener noreferrer">axword.pl<Icon name="external" size={13}/></a>
        <span class="version">{status.value?.version ? `v${status.value.version}` : 'Voice Control'} · Windows</span>
      </div>
    </aside>
    <main id="main" class={view.value==='commands' ? 'dashboard-main' : ''}>
      {!online && <div class="notice"><Icon name="refresh" size={17}/><span>{connection.value==='connecting' ? t("Łączenie z aplikacją…") : t("Brak połączenia z lokalną aplikacją Voice Control.")}</span><Button quiet onClick={retryNow}>{t("Połącz ponownie")}</Button></div>}
      {error.value && <div class="notice error" role="alert"><span>{translateMessage(error.value)}</span><IconButton icon="close" label={t("Zamknij komunikat")} onClick={()=>{error.value='';}}/></div>}
      {view.value!=='commands' && <div class="page-top"><span class="eyebrow">VOICE CONTROL <span>/</span> {view.value==='settings' ? t("USTAWIENIA") : t("AKTYWNOŚĆ")}</span>
        <Button icon={status.value?.listening ? 'pause' : 'mic'} primary={!status.value?.listening} disabled={!online || busy.value || !profile} onClick={()=>void listen()}>
          {busy.value ? t("Chwila…") : status.value?.listening ? t("Zatrzymaj nasłuch") : t("Włącz nasłuch")}
        </Button>
      </div>}
      {view.value==='commands' && profile && <>
        <div class="dashboard-heading"><h1>{t("Komendy głosowe")}</h1></div>
        <VoicePanel profile={profile} availableProfiles={filteredProfiles} onToggle={()=>void listen()} onSelectProfile={selectProfile} onProfileEdit={()=>setProfileEditor(profile)}/>
        <div class="dashboard-workspace">
          <div class="dashboard-commands"><Commands key={profile.id} profile={profile} onAdd={()=>setCommandEditor(emptyCommand())} onEdit={setCommandEditor} onJson={()=>setJsonOpen(true)}/></div>
          <LiveActivity compact/>
        </div>
      </>}
      {view.value==='commands' && !profile && <div class="page-empty"><Icon name="game" size={36}/><h1>{t("Profile gier")}</h1>
        <p>{online ? t("Dodaj profil i przypisz pierwszą komendę.") : t("Profile pojawią się po połączeniu z aplikacją.")}</p>
        {online && <Button primary icon="plus" onClick={()=>setProfileEditor('new')}>{t("Dodaj profil")}</Button>}</div>}
      {view.value==='settings' && <SettingsView/>}
      {view.value==='activity' && <LiveActivity/>}
      <footer class="page-footer"><span>Voice Control <span class="muted">by</span> <a href="https://axword.pl/" target="_blank" rel="noopener noreferrer">Axword</a></span><span><Icon name="mic" size={13}/>{t("Rozpoznawanie lokalne")}</span></footer>
    </main>
    {profileEditor && <ProfileEditor profile={profileEditor==='new' ? null : profileEditor} onClose={()=>setProfileEditor(null)}/>}
    {commandEditor && profile && <CommandEditor profile={profile} command={commandEditor} onClose={()=>setCommandEditor(null)}/>}
    {jsonOpen && <JsonEditor onClose={()=>setJsonOpen(false)}/>}
  </div>;
}

function VoicePanel({profile,availableProfiles,onToggle,onSelectProfile,onProfileEdit}: {profile:Profile;availableProfiles:Profile[];onToggle:()=>void;onSelectProfile:(id:string)=>Promise<void>;onProfileEdit:()=>void}) {
  const [engines,setEngines] = useState<Engine[]>([]);
  const [devices,setDevices] = useState<AudioDevice[]>([]);
  const online = connection.value==='online';
  const cfg = settings.value;
  const [threshold,setThreshold] = useState(Math.round((cfg?.matching_threshold??1)*100));
  useEffect(()=>{setThreshold(Math.round((cfg?.matching_threshold??1)*100));},[cfg?.matching_threshold]);
  async function saveThreshold(value: number) {
    await patchSettings({matching_threshold:value/100});
    setThreshold(Math.round((settings.value?.matching_threshold??1)*100));
  }
  const completed = Object.entries(downloads.value).filter(([,download])=>download.done).map(([key])=>key).join(',');
  useEffect(()=>{
    let mounted=true;
    void Promise.all([api.engines(),api.devices()]).then(([engineResponse,deviceResponse])=>{
      if(mounted){setEngines(engineResponse.engines);setDevices(deviceResponse.devices);}
    }).catch(cause=>{if(mounted)error.value=cause instanceof Error?cause.message:"Nie udało się pobrać urządzeń i modeli.";});
    return ()=>{mounted=false;};
  },[completed]);
  async function switchEngine(engineId:string) {
    await run(async()=>{
      await api.activateEngine(engineId);
      const [nextSettings,nextStatus]=await Promise.all([api.settings(),api.status()]);
      settings.value=nextSettings;status.value=nextStatus;
      if(nextStatus.error)throw new Error(nextStatus.error);
    });
  }
  const engineId=cfg?.engine_id??status.value?.engine_id??'';
  return <section class={`voice-panel ${status.value?.listening?'listening':''}`} aria-label={t("Sterowanie głosem")}>
    <div class="voice-panel-state">
      <div class="voice-state-label"><span class="listening-indicator"><Icon name="mic" size={21}/></span><strong>{status.value?.listening?t("Nasłuch włączony"):t("Nasłuch wyłączony")}</strong></div>
      <span class="voice-panel-language">{languageName(profile.language)}</span>
      <Button primary={!status.value?.listening} icon={status.value?.listening?'pause':'play'} disabled={!online||busy.value} onClick={onToggle}>{busy.value?t("Chwila…"):status.value?.listening?t("Zatrzymaj nasłuch"):t("Włącz nasłuch")}</Button>
    </div>
    <div class="voice-panel-selectors">
      <label><span>{t("Profil")}</span><div class="voice-select-control"><select aria-label={t("Aktywny profil")} value={profile.id} disabled={!online||busy.value} onChange={e=>void onSelectProfile(e.currentTarget.value)}>{!availableProfiles.some(p=>p.id===profile.id)&&<optgroup label={t('Aktywny profil')}><option value={profile.id}>{profileOption(profile)}</option></optgroup>}{availableProfiles.map(p=><option key={p.id} value={p.id}>{profileOption(p)}</option>)}</select><IconButton icon="edit" label={t("Edytuj profil")} disabled={!online||busy.value} onClick={onProfileEdit}/></div></label>
      <label><span>{t("Model")}</span><div class="voice-select-control"><select aria-label={t("Model rozpoznawania")} value={engineId} disabled={!online||busy.value||!engines.length} onChange={e=>void switchEngine(e.currentTarget.value)}>{!engines.length&&<option value={engineId}>{status.value?.engine_name??t("Ładowanie…")}</option>}{engines.map(engine=><option key={engine.id} value={engine.id} disabled={!engine.installed}>{engine.name}{engine.installed?'':` · ${t('niepobrany')}`}</option>)}</select><IconButton icon="settings" label={t("Zarządzaj modelami")} onClick={()=>{view.value='settings';}}/></div></label>
      <label><span>{t("Mikrofon")}</span><select aria-label={t("Mikrofon do nasłuchu")} value={cfg?.audio_device??''} disabled={!online||busy.value} onChange={e=>void patchSettings({audio_device:e.currentTarget.value||null})}><option value="">{t("Domyślny mikrofon systemowy")}</option>{devices.map(device=><option key={device.id} value={device.id}>{device.name}</option>)}{cfg?.audio_device&&!devices.some(device=>device.id===cfg.audio_device)&&<option value={cfg.audio_device}>{cfg.audio_device}</option>}</select></label>
    </div>
    <details class="voice-advanced"><summary>{t('Zaawansowane')}</summary><div class="voice-advanced-content"><label for="matching-threshold">{t('Podobieństwo komendy')}<output for="matching-threshold">{threshold}%</output></label><input id="matching-threshold" type="range" min="0" max="100" step="1" value={threshold} aria-label={t('Podobieństwo komendy')} aria-valuetext={t('Wymagane podobieństwo: {percent}%',{percent:threshold})} disabled={!online||busy.value} onInput={e=>setThreshold(Number(e.currentTarget.value))} onChange={e=>void saveThreshold(Number(e.currentTarget.value))}/>{threshold===100&&<span class="muted">{t('Tylko dokładne dopasowanie')}</span>}</div></details>
  </section>;
}

function Commands({profile,onAdd,onEdit,onJson}: {profile:Profile;onAdd:()=>void;onEdit:(command:VoiceCommand)=>void;onJson:()=>void}) {
  const [query,setQuery] = useState('');
  const [filter,setFilter] = useState<'all' | CommandMode>('all');
  const [text,setText] = useState('');
  const [result,setResult] = useState<TestResult | null>(null);
  const [testing,setTesting] = useState(false);
  useEffect(()=>setResult(null),[profile.commands]);
  const items = profile.commands.filter(c=>(filter==='all'||c.mode===filter) && normalize(c.phrase+' '+c.keys.join(' ')).includes(normalize(query)));
  const online = connection.value==='online';
  const held = status.value?.held_command_ids ?? [];
  async function update(command:VoiceCommand,patch:Partial<VoiceCommand>) {
    const document = profiles.value;
    if (document) await saveProfiles({...document,profiles:document.profiles.map(p=>p.id===profile.id
      ? {...p,commands:p.commands.map(c=>c.id===command.id ? {...c,...patch} : c)} : p)});
  }
  async function test(e:Event) {
    e.preventDefault();
    if (!text.trim() || testing) return;
    setTesting(true);
    const response = await run(()=>api.test(text.trim()));
    setResult(response ?? null); setTesting(false);
  }
  return <>
    <section class="commands-section">
      <div class="section-heading"><h2>{profile.name}</h2><div class="section-actions"><Button icon="code" onClick={onJson} disabled={!online}>JSON</Button><Button primary icon="plus" onClick={onAdd} disabled={busy.value || !online}>{t("Dodaj komendę")}</Button></div></div>
      <div class="command-toolbar">
        <div class="filters" role="group" aria-label={t("Filtr trybu")}>
          <button class={filter==='all' ? 'active' : ''} onClick={()=>setFilter('all')}>{t("Wszystkie")}</button>
          {modes.map(m=><button key={m.id} class={filter===m.id ? 'active' : ''} onClick={()=>setFilter(m.id)}><Icon name={m.icon} size={14}/>{m.id==='click' ? t("Kliknięcie") : m.id==='timed' ? t("3 sekundy") : t("Przełącznik")}</button>)}
        </div>
        <label class="search"><Icon name="search" size={16}/><input aria-label={t("Szukaj komendy")} placeholder={t("Szukaj komendy…")} value={query} onInput={e=>setQuery(e.currentTarget.value)}/></label>
      </div>
      <div class="command-table">
        <div class="table-labels"><span>{t("POWIEDZ")}</span><span/><span>{t("PRZYCISKI")}</span><span>{t("TRYB DZIAŁANIA")}</span><span>{t("AKTYWNA")}</span><span/></div>
        {items.map(c=><div key={c.id} class={`command-row ${!c.enabled ? 'disabled' : ''} ${held.includes(c.id) ? 'holding' : ''} ${result?.command?.id===c.id ? 'matched' : ''}`}>
          <button class="phrase" onClick={()=>onEdit(c)} disabled={!online || busy.value}><span class="quote">“</span>{c.phrase}<span class="quote">”</span>{held.includes(c.id) && <span class="holding-dot" title={t("Przycisk jest trzymany")}/>}</button>
          <span class="command-arrow"><Icon name="arrow" size={18}/></span>
          <Keys keys={c.keys}/>
          <div class="mode-group" role="group" aria-label={t('Tryb: {phrase}',{phrase:c.phrase})}>{modes.map(m=><button key={m.id} title={m.id==='timed'&&c.mode==='timed' ? t('Przytrzymaj przez {duration}',{duration:durationLabel(c.duration_ms)}) : t(m.title)} aria-label={m.id==='timed'&&c.mode==='timed' ? t('Przytrzymaj przez {duration}',{duration:durationLabel(c.duration_ms)}) : t(m.title)} aria-pressed={c.mode===m.id}
            class={c.mode===m.id ? 'selected' : ''} disabled={!online||busy.value} onClick={()=>void update(c,{mode:m.id,duration_ms:3000})}><Icon name={m.icon} size={17}/>{c.mode===m.id && <span>{m.id==='click' ? t("Klik") : m.id==='timed' ? durationLabel(c.duration_ms) : t("Hold")}</span>}</button>)}</div>
          <Toggle checked={c.enabled} label={t('Włącz komendę: {phrase}',{phrase:c.phrase})} onChange={()=>void update(c,{enabled:!c.enabled})} disabled={!online||busy.value}/>
          <IconButton icon="edit" label={t('Edytuj komendę: {phrase}',{phrase:c.phrase})} onClick={()=>onEdit(c)} disabled={!online||busy.value}/>
        </div>)}
        {!items.length && <div class="table-empty"><Icon name="command" size={25}/><p>{profile.commands.length ? t("Brak pasujących komend.") : t("Ten profil nie ma jeszcze komend.")}</p>{!profile.commands.length && <Button quiet icon="plus" onClick={onAdd}>{t("Dodaj pierwszą komendę")}</Button>}</div>}
      </div>
      <div class="mode-legend">{modes.map(m=><span key={m.id} title={t(m.title)}><Icon name={m.icon} size={15}/>{m.id==='click' ? t("Kliknięcie") : m.id==='timed' ? t("Przytrzymaj 3 s") : t("Trzymaj do powtórzenia")}</span>)}</div>
    </section>
    <section class="test-section">
      <div class="test-title"><Icon name="keyboard" size={20}/><h2>{t("Sprawdź komendę")}</h2></div>
      <form onSubmit={test}><input aria-label={t("Fraza do sprawdzenia")} value={text} onInput={e=>{setText(e.currentTarget.value);setResult(null);}} placeholder={t("Wpisz swoją komendę…")} maxLength={200}/><Button icon="arrow" type="submit" disabled={!online||busy.value||!text.trim()||testing}>{testing ? t("Sprawdzanie…") : t("Sprawdź")}</Button></form>
      <div class="test-result" aria-live="polite">{result ? result.matched && result.command
        ? <><Icon name="check" size={15}/><span>“{result.text}”</span><Icon name="arrow" size={14}/><Keys keys={result.command.keys}/><span class="muted">{result.command.mode==='timed' ? t('Przytrzymaj {duration}',{duration:durationLabel(result.command.duration_ms)}) : t(modes.find(m=>m.id===result.command?.mode)!.label)}</span></>
        : <span class="muted">{t("Brak pasującej aktywnej komendy.")}</span> : <span class="muted">{t("Test dopasowania bez naciskania przycisków.")}</span>}</div>
    </section>
  </>;
}

function CommandEditor({profile,command,onClose}: {profile:Profile;command:VoiceCommand;onClose:()=>void}) {
  const [draft,setDraft] = useState({...command,keys:[...command.keys]});
  const [keyText,setKeyText] = useState(command.keys.join(' + '));
  const [recording,setRecording] = useState(false);
  const [localError,setLocalError] = useState('');
  const [deleting,setDeleting] = useState(false);
  const isNew = !profile.commands.some(c=>c.id===command.id);
  const capture = useRef<HTMLButtonElement>(null);
  function keysFromText(value:string):string[] {
    const aliases:Record<string,string> = {control:'ctrl',win:'cmd',windows:'cmd',escape:'esc',spacja:'space',lpm:'left_click',ppm:'right_click',śpm:'middle_click',lmb:'left_click',rmb:'right_click',mmb:'middle_click'};
    return [...new Set(value.split(/[+,]/).map(k=>k.trim().toLowerCase()).filter(Boolean).map(k=>aliases[k]??k))];
  }
  function captureKeys(e: KeyboardEvent) {
    if (!recording) return;
    e.preventDefault(); e.stopPropagation();
    if (e.key==='Escape') {setRecording(false);return;}
    const aliases:Record<string,string> = {' ':'space',Control:'ctrl',Shift:'shift',Alt:'alt',Meta:'cmd',ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',CapsLock:'caps_lock'};
    const modifiers = [e.ctrlKey?'ctrl':'',e.shiftKey?'shift':'',e.altKey?'alt':'',e.metaKey?'cmd':''].filter(Boolean);
    const current = aliases[e.key] ?? e.key.toLowerCase();
    const keys = [...new Set([...modifiers,current])];
    setKeyText(keys.join(' + '));
    if (!['Control','Shift','Alt','Meta'].includes(e.key)) setRecording(false);
  }
  async function submit(e:Event) {
    e.preventDefault();
    const phrase = draft.phrase.trim().replace(/\s+/g,' ');
    const keys = keysFromText(keyText);
    if (!phrase) {setLocalError("Podaj komendę głosową.");return;}
    if (!keys.length || keys.length>4) {setLocalError("Wybierz od 1 do 4 przycisków.");return;}
    if (profile.commands.some(c=>c.id!==draft.id && normalize(c.phrase)===normalize(phrase))) {setLocalError("Ta fraza jest już przypisana w tym profilu.");return;}
    const document = profiles.value;
    if (!document) return;
    const saved:VoiceCommand = {...draft,phrase,keys};
    const nextCommands = isNew ? [...profile.commands,saved] : profile.commands.map(c=>c.id===draft.id?saved:c);
    if (await saveProfiles({...document,profiles:document.profiles.map(p=>p.id===profile.id?{...p,commands:nextCommands}:p)})) onClose();
  }
  async function remove() {
    const document = profiles.value;
    if (document && await saveProfiles({...document,profiles:document.profiles.map(p=>p.id===profile.id?{...p,commands:p.commands.filter(c=>c.id!==draft.id)}:p)})) onClose();
  }
  return <Modal title={isNew ? t("Nowa komenda") : t("Edytuj komendę")} onClose={onClose}>
    <form onSubmit={submit} class="editor-form">
      <label>{t("Powiedz")}<input autoFocus required maxLength={160} placeholder={t("np. biegnij")} value={draft.phrase} onInput={e=>{setDraft({...draft,phrase:e.currentTarget.value});setLocalError('');}}/></label>
      <label>{t("Przyciski")}<span class="key-input-row"><input aria-label={t("Przyciski")} placeholder={t("np. ctrl + w")} value={keyText} onInput={e=>{setKeyText(e.currentTarget.value);setLocalError('');}}/>
        <button type="button" ref={capture} class={`btn ${recording?'recording':''}`} onClick={()=>{setRecording(!recording);capture.current?.focus();}} onKeyDown={captureKeys}><Icon name="keyboard" size={17}/>{recording?t("Naciśnij klawisze…"):t("Nagraj skrót")}</button></span></label>
      <div class="key-preview"><Keys keys={keysFromText(keyText)}/></div>
      <div class="mouse-keys">{[['left_click',t("LPM")],['right_click',t("PPM")],['middle_click',t("ŚPM")]].map(([key,label])=><Button key={key} quiet icon="click" onClick={()=>{const keys=keysFromText(keyText);if(!keys.includes(key)&&keys.length<4)setKeyText([...keys,key].join(' + '));}}>{label}</Button>)}</div>
      <fieldset><legend>{t("Tryb działania")}</legend><div class="mode-options">{modes.map(m=><button type="button" key={m.id} class={draft.mode===m.id?'selected':''} aria-pressed={draft.mode===m.id} onClick={()=>setDraft({...draft,mode:m.id,duration_ms:3000})}><Icon name={m.icon} size={22}/><strong>{m.id==='timed'&&draft.mode==='timed' ? t('Przytrzymaj {duration}',{duration:durationLabel(draft.duration_ms)}) : t(m.label)}</strong></button>)}</div></fieldset>
      <div class="enabled-row"><span>{t("Komenda aktywna")}</span><Toggle checked={draft.enabled} label={t("Komenda aktywna")} onChange={()=>setDraft({...draft,enabled:!draft.enabled})}/></div>
      {(localError||error.value) && <p role="alert" class="form-error">{translateMessage(localError||error.value)}</p>}
      {deleting && <div class="delete-confirm"><span>{t("Usunąć tę komendę?")}</span><Button danger disabled={busy.value} onClick={()=>void remove()}>{t("Usuń")}</Button><Button quiet onClick={()=>setDeleting(false)}>{t("Anuluj")}</Button></div>}
      <footer class="modal-footer">{!isNew && <IconButton icon="trash" label={t("Usuń komendę")} disabled={busy.value} onClick={()=>setDeleting(true)}/>}<span class="spacer"/><Button onClick={onClose} disabled={busy.value}>{t("Anuluj")}</Button><Button primary type="submit" icon="check" disabled={busy.value||recording}>{busy.value?t("Zapisywanie…"):t("Zapisz komendę")}</Button></footer>
    </form>
  </Modal>;
}

function ProfileEditor({profile,onClose}: {profile:Profile|null;onClose:()=>void}) {
  const [name,setName] = useState(profile?.name??'');
  const [game,setGame] = useState(profile?.game??'');
  const [language,setLanguage] = useState<Language>(profile?.language??settings.value?.ui_language??'pl_PL');
  const [localError,setLocalError] = useState('');
  const [deleting,setDeleting] = useState(false);
  async function save(e:Event) {
    e.preventDefault(); const document=profiles.value;
    if (!document || !name.trim() || !game.trim()) return;
    const next:Profile = {id:profile?.id??id(),name:name.trim(),game:game.trim(),language,commands:profile?.commands??[]};
    if (await saveProfiles({...document,active_profile_id:next.id,profiles:profile ? document.profiles.map(p=>p.id===profile.id?next:p):[...document.profiles,next]})) onClose();
  }
  async function duplicate() {
    const document=profiles.value;
    if (!profile||!document) return;
    const next={...profile,id:id(),name:`${profile.name.slice(0,64)} (${t('kopia')})`,commands:profile.commands.map(c=>({...c,id:id()}))};
    if(await saveProfiles({...document,active_profile_id:next.id,profiles:[...document.profiles,next]})) onClose();
  }
  async function remove() {
    const document=profiles.value;
    if (!profile||!document) return;
    const remaining=document.profiles.filter(p=>p.id!==profile.id);
    if (!remaining.length) {setLocalError("Pozostaw co najmniej jeden profil.");return;}
    if (await saveProfiles({...document,profiles:remaining,active_profile_id:document.active_profile_id===profile.id?remaining[0].id:document.active_profile_id})) onClose();
  }
  return <Modal title={profile?t("Edytuj profil"):t("Nowy profil")} onClose={onClose}><form class="editor-form" onSubmit={save}>
    <label>{t("Nazwa profilu")}<input autoFocus required maxLength={80} value={name} placeholder={t("np. Mój profil")} onInput={e=>setName(e.currentTarget.value)}/></label>
    <label>{t("Gra / aplikacja")}<input required maxLength={100} value={game} placeholder={t("np. Counter-Strike 2")} onInput={e=>setGame(e.currentTarget.value)}/></label>
    <label>{t('Język komend')}<select value={language} onChange={e=>setLanguage(e.currentTarget.value as Language)}>{languages.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
    {profile && <div class="profile-actions"><Button icon="copy" onClick={()=>void duplicate()} disabled={busy.value}>{t("Duplikuj profil")}</Button><Button icon="trash" danger onClick={()=>setDeleting(true)} disabled={busy.value}>{t("Usuń profil")}</Button></div>}
    {deleting && <div class="delete-confirm"><span>{t("Usunąć profil i jego komendy?")}</span><Button danger onClick={()=>void remove()} disabled={busy.value}>{t("Usuń")}</Button><Button quiet onClick={()=>setDeleting(false)}>{t("Anuluj")}</Button></div>}
    {(localError||error.value)&&<p role="alert" class="form-error">{translateMessage(localError||error.value)}</p>}
    <footer class="modal-footer"><span class="spacer"/><Button onClick={onClose} disabled={busy.value}>{t("Anuluj")}</Button><Button primary icon="check" type="submit" disabled={busy.value}>{busy.value?t("Zapisywanie…"):t("Zapisz profil")}</Button></footer>
  </form></Modal>;
}

function JsonEditor({onClose}: {onClose:()=>void}) {
  const [text,setText]=useState(JSON.stringify(profiles.value,null,2));
  const [localError,setLocalError]=useState('');
  const [copied,setCopied]=useState(false);
  const input=useRef<HTMLInputElement>(null);
  async function save() {
    try {
      const parsed=JSON.parse(text);
      if (await saveProfiles(parsed)) onClose();
    } catch {setLocalError("Nieprawidłowy JSON. Sprawdź przecinki, nawiasy i cudzysłowy.");}
  }
  function exportJson() {
    try {
      const parsed=JSON.parse(text);
      const blob=new Blob([JSON.stringify(parsed,null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob);const a=document.createElement('a');
      a.href=url;a.download='voice-control-profiles.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      setLocalError('');
    } catch {setLocalError("Nieprawidłowy JSON. Popraw go przed eksportem.");}
  }
  async function importJson(e:JSX.TargetedEvent<HTMLInputElement>) {
    const file=e.currentTarget.files?.[0];
    if(!file)return;
    if(file.size>1024*1024){setLocalError("Plik może mieć maksymalnie 1 MB.");return;}
    try{setText(await file.text());setLocalError('');}catch{setLocalError("Nie udało się odczytać pliku.");}
  }
  return <Modal title={t("Profile · JSON")} onClose={onClose} wide>
    <div class="json-toolbar"><Button icon="upload" onClick={()=>input.current?.click()}>{t("Importuj plik")}</Button><Button icon="download" onClick={exportJson}>{t("Eksportuj")}</Button><span class="spacer"/><Button icon={copied?'check':'copy'} onClick={()=>{void navigator.clipboard.writeText(text).then(()=>setCopied(true)).catch(()=>setLocalError("Nie udało się skopiować. Zaznacz tekst i skopiuj ręcznie."));}}>{copied?t("Skopiowano"):t("Kopiuj")}</Button></div>
    <input class="visually-hidden" type="file" ref={input} accept=".json,application/json" onChange={importJson}/>
    <textarea class="json-editor" aria-label={t("Konfiguracja profili JSON")} value={text} spellcheck={false} onInput={e=>{setText(e.currentTarget.value);setCopied(false);setLocalError('');}}/>
    {(localError||error.value)&&<p role="alert" class="form-error json-error">{translateMessage(localError||error.value)}</p>}
    <footer class="modal-footer"><Button onClick={onClose} disabled={busy.value}>{t("Anuluj")}</Button><Button primary icon="check" onClick={()=>void save()} disabled={busy.value}>{busy.value?t("Zapisywanie…"):t("Zapisz konfigurację")}</Button></footer>
  </Modal>;
}

function SettingsView() {
  const [devices,setDevices]=useState<AudioDevice[]>([]);
  const [engines,setEngines]=useState<Engine[]>([]);
  const [audioResult,setAudioResult]=useState('');
  const [audioBusy,setAudioBusy]=useState(false);
  const cfg=settings.value;
  const online=connection.value==='online';
  useEffect(()=>{
    if(!online)return;
    let active=true;
    void Promise.all([api.devices(),api.engines()]).then(([d,e])=>{if(active){setDevices(d.devices);setEngines(e.engines);}}).catch(cause=>{error.value=String(cause);});
    return ()=>{active=false;};
  },[online]);
  const completed=Object.entries(downloads.value).filter(([,d])=>d.done||d.cancelled||d.error).map(([key])=>key).join(',');
  useEffect(()=>{
    if(!online||!completed)return;
    void api.engines().then(e=>setEngines(e.engines)).catch(()=>{});
  },[completed,online]);
  async function testAudio() {
    setAudioBusy(true);setAudioResult('');
    try{const result=await api.testAudio();setAudioResult(result.error||result.transcript||"Nie rozpoznano mowy.");}
    catch(cause){setAudioResult(String(cause));}
    finally{setAudioBusy(false);}
  }
  async function download(engine:Engine) {
    error.value='';
    downloads.value={...downloads.value,[engine.id]:{percent:0}};
    try{
      const response=await api.downloadEngine(engine.id);
      if(!response.started) throw new Error("Nie udało się rozpocząć pobierania.");
    }catch(cause){
      const message=cause instanceof Error?cause.message:String(cause);
      error.value=message;
      downloads.value={...downloads.value,[engine.id]:{error:message}};
    }
  }
  return <>
    <div class="plain-heading"><h1>{t("Ustawienia")}</h1></div>
    {!cfg ? <p class="muted">{t("Oczekiwanie na ustawienia aplikacji…")}</p> : <div class="settings-content">
      <section class="settings-section"><h2><Icon name="mic"/>{t("Mikrofon i rozpoznawanie")}</h2>
        <label class="setting-row"><span>{t("Mikrofon")}</span><select value={cfg.audio_device??''} disabled={!online||busy.value||audioBusy||status.value?.listening} onChange={e=>void patchSettings({audio_device:e.currentTarget.value||null})}><option value="">{t("Domyślny mikrofon systemowy")}</option>{devices.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}{cfg.audio_device&&!devices.some(d=>d.id===cfg.audio_device)&&<option value={cfg.audio_device}>{cfg.audio_device} ({t('niedostępny')})</option>}</select></label>
        <label class="setting-row"><span>{t("Język rozpoznawania")}</span><select value={cfg.language} disabled={!online||busy.value} onChange={e=>void patchSettings({language:e.currentTarget.value})}>{languages.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <div class="setting-row"><span>{t("Test mikrofonu")}</span><Button icon="volume" onClick={()=>void testAudio()} disabled={!online||audioBusy||busy.value||Boolean(status.value?.listening)}>{audioBusy?t("Nagrywanie · 3 s…"):t("Nagraj 3 sekundy")}</Button></div>
        {audioResult&&<p class="audio-result" aria-live="polite">{translateMessage(audioResult)}</p>}
      </section>
      <section class="settings-section"><h2><Icon name="command"/>{t("Silnik rozpoznawania")}</h2>
        <div class="engine-list">{engines.map(engine=>{
          const progress=downloads.value[engine.id];
          const downloading=Boolean(progress)&&!progress?.done&&!progress?.cancelled&&!progress?.error&&!engine.installed;
          return <div class="engine-row" key={engine.id}><div><strong>{engine.name}</strong><span class="muted">{engine.backend}{engine.requires_cuda?' · NVIDIA CUDA':''}{engine.size_bytes>0?` · ${Math.round(engine.size_bytes/1024/1024)} MB`:''}</span>{progress?.error&&<span class="form-error">{translateMessage(progress.error)}</span>}</div>
            {downloading?<div class="download-state"><span>{Math.round(progress?.percent??0)}%</span><progress max="100" value={progress?.percent??0}/><IconButton icon="close" label={t('Anuluj pobieranie {name}',{name:engine.name})} disabled={!online} onClick={()=>{void api.cancelEngine(engine.id).catch(cause=>{error.value=String(cause);});}}/></div>
              :cfg.engine_id===engine.id&&engine.installed?<span class="engine-active"><Icon name="check" size={15}/>{t("Aktywny")}</span>
              :<Button icon={engine.installed?'check':'download'} disabled={!online||busy.value} onClick={()=>engine.installed?void run(async()=>{await api.activateEngine(engine.id);settings.value=await api.settings();status.value=await api.status();}):void download(engine)}>{engine.installed?t("Wybierz"):t("Pobierz")}</Button>}
          </div>;
        })}</div>
      </section>
      <section class="settings-section"><h2><Icon name="settings"/>{t("Aplikacja")}</h2>
        <label class="setting-row"><span>{t('Język interfejsu')}</span><select value={cfg.ui_language} disabled={!online||busy.value} onChange={e=>void patchSettings({ui_language:e.currentTarget.value as Language})}>{languages.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label class="setting-row"><span>{t("Motyw")}</span><select value={cfg.theme} disabled={!online||busy.value} onChange={e=>void patchSettings({theme:e.currentTarget.value as 'light'|'dark'|'system'})}><option value="light">{t("Jasny")}</option><option value="dark">{t("Ciemny")}</option><option value="system">{t("Systemowy")}</option></select></label>
        <div class="setting-row"><span>{t("Uruchamiaj z systemem Windows")}</span><Toggle checked={cfg.start_with_windows} label={t("Uruchamiaj z systemem Windows")} disabled={!online||busy.value} onChange={()=>void patchSettings({start_with_windows:!cfg.start_with_windows})}/></div>
        <div class="setting-row"><span>{t("Włącz nasłuch po uruchomieniu")}</span><Toggle checked={cfg.start_listening_on_launch} label={t("Włącz nasłuch po uruchomieniu")} disabled={!online||busy.value} onChange={()=>void patchSettings({start_listening_on_launch:!cfg.start_listening_on_launch})}/></div>
      </section>
    </div>}
  </>;
}
