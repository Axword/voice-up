import { Icon } from './Icon';
import { api } from '../lib/api';
import { busy, connection, heard, run, status } from '../lib/state';
import type { HeardItem } from '../lib/types';
import { keyLabel, locale, t, translateMessage } from '../lib/i18n';
import '../styles/activity.css';

function Keys({keys}: {keys:string[]}) {
  return <span class="live-activity-keys">{keys.map((key,index)=><span key={`${key}-${index}`}>
    {index>0&&<span class="live-activity-plus">+</span>}<kbd>{keyLabel(key)}</kbd>
  </span>)}</span>;
}

function resultLabel(item:HeardItem):string {
  if (item.error || item.executed===false && item.matched) return t("Błąd wykonania");
  if (!item.matched) return t("Brak dopasowania");
  if (item.executed!==true) return t("Dopasowano");
  if (item.mode==='toggle') return item.held===true ? t("Włączono trzymanie") : item.held===false ? t("Zwolniono przyciski") : t("Przełączono trzymanie");
  if (item.mode==='timed') return t('Przytrzymanie {duration}',{duration:`${(Math.max(0,item.duration_ms??3000)/1000).toLocaleString(locale(),{maximumFractionDigits:3})} s`});
  if (item.mode==='click') return t("Kliknięcie");
  return t("Wykonano");
}

export function LiveActivity({compact=false}: {compact?:boolean}={}) {
  const items=heard.value;
  const held=status.value?.held_keys??[];
  async function release() {
    await run(async()=>{await api.release();status.value=await api.status();});
  }
  return <section class={`live-activity ${compact?'live-activity--compact':''}`}>
    <header class="live-activity-head"><h2>{compact?t("Aktywność"):t("Rozpoznane komendy")}</h2><button type="button" class="live-activity-clear" disabled={!items.length} onClick={()=>{heard.value=[];}}>{t("Wyczyść")}</button></header>
    {held.length>0&&<div class="live-activity-held"><Keys keys={held}/><button type="button" class="live-activity-release" disabled={busy.value||connection.value!=='online'} onClick={()=>void release()}><Icon name="release" size={14}/>{t("Zwolnij przyciski")}</button></div>}
    <div class="live-activity-feed" role="log" aria-live="polite" aria-label={t("Rozpoznane komendy")}>
      {items.length?items.map((item,index)=><div class={`live-activity-item ${item.error?'live-activity-item--error':''}`} key={`${item.at}-${index}`}>
        <div class="live-activity-phrase"><Icon name={item.error?'close':item.executed?'check':'mic'} size={15}/><strong>{item.phrase}</strong><time dateTime={new Date(item.at).toISOString()}>{new Date(item.at).toLocaleTimeString(locale(),{hour12:false})}</time></div>
        <div class="live-activity-result"><span>{resultLabel(item)}</span>{item.matched&&item.keys.length>0&&<Keys keys={item.keys}/>}</div>
        {item.error&&<p class="live-activity-error">{translateMessage(item.error)}</p>}
      </div>):status.value?.last_heard?<div class="live-activity-last"><span>{t("Ostatnio usłyszano")}</span><strong>{status.value.last_heard}</strong></div>:<p class="live-activity-empty">{t("Brak rozpoznanych komend")}</p>}
    </div>
  </section>;
}
