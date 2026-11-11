import React, { useEffect, useRef, useState } from 'react'
import { api, inr } from './api.js'
import { SPEECH_LANG, tr } from './i18n.js'
import ItemDetails from './Item.jsx'
import Icon, { BusinessIcon, NeedIcon, ProductIcon } from './Icon.jsx'

// The laptop layout puts the bundle beside the chat; a phone keeps it inside the chat.
function useWide() {
  const q = '(min-width: 1000px)'
  const [wide, setWide] = useState(() => typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(q).matches)
  useEffect(() => {
    if (!window.matchMedia) return undefined
    const m = window.matchMedia(q)
    const on = () => setWide(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return wide
}

const Recognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

export default function Advisor({ lang, session, setSession, onDone, onTrack, config, onLang, onPartner }) {
  const [msgs, setMsgs] = useState([])
  const [chips, setChips] = useState([])
  const [needs, setNeeds] = useState(null)
  const [profile, setProfile] = useState(null)
  const [result, setResult] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [speak, setSpeak] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef(null)
  const recRef = useRef(null)
  const startedLang = useRef(null)
  const wide = useWide()

  const show = (r) => {
    setChips(r.chips || [])
    setProfile(r.profile || null)
    setNeeds(r.needs || null)
    setResult(r.recommendation || null)
  }

  const resume = async (sid) => {
    setBusy(true); setError('')
    try {
      const r = await api.resume(sid)
      onPartner?.(r.partner || null)
      startedLang.current = r.lang
      if (r.lang && r.lang !== lang && onLang) onLang(r.lang)
      setMsgs(r.history.map((m) => ({ who: m.role === 'user' ? 'me' : 'bot', text: m.text, sources: m.sources })))
      show(r)
    } catch { setSession(null); await begin(lang) } finally { setBusy(false) }
  }

  const begin = async (l) => {
    setBusy(true); setError('')
    try {
      const r = await api.start(l)
      onPartner?.(r.partner || null)
      startedLang.current = l
      setSession(r.session_id)
      setMsgs(r.messages.map((m) => ({ who: 'bot', text: m })))
      setChips(r.chips || []); setNeeds(null); setResult(null); setProfile(null)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  // Coming back from the quote, or reloading the page, redraws the saved conversation instead of a blank chat.
  useEffect(() => { if (session) resume(session); else begin(lang) }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // Switching language before the owner has said anything restarts the chat in that language.
    if (session && startedLang.current && startedLang.current !== lang && msgs.filter((m) => m.who === 'me').length === 0) begin(lang)
  }, [lang])  // eslint-disable-line react-hooks/exhaustive-deps
  // Follow the conversation as it grows, but leave the opening screen at the top so the first thing seen is the offer.
  useEffect(() => { if (msgs.length > 1) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [msgs, busy, needs, result])

  const say = (lines) => {
    if (!speak || !window.speechSynthesis) return
    const u = new SpeechSynthesisUtterance(lines.join(' '))
    u.lang = SPEECH_LANG[lang]
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
  }

  // The speaker on each reply reads that reply aloud in the chat's language, whether or not auto-read is on.
  const sayOne = (text) => {
    if (!window.speechSynthesis) return
    const u = new SpeechSynthesisUtterance(text)
    u.lang = SPEECH_LANG[lang]
    const v = window.speechSynthesis.getVoices().find((x) => x.lang === u.lang) || window.speechSynthesis.getVoices().find((x) => x.lang.startsWith(u.lang.slice(0, 2)))
    if (v) u.voice = v
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
  }

  const send = async (payload, shown) => {
    if (!session || busy) return
    if (shown) setMsgs((m) => [...m, { who: 'me', text: shown }])
    setBusy(true); setChips([]); setError('')
    try {
      const r = await api.message({ session_id: session, display: shown, ...payload })
      const bot = r.messages.map((t, i) => ({ who: 'bot', text: t, sources: i === 0 ? r.sources : null }))
      setMsgs((m) => (r.reset ? bot : [...m, ...bot]))
      say(r.messages)
      show(r)
      if (r.lang && r.lang !== lang && onLang) { startedLang.current = r.lang; onLang(r.lang) }  // owner switched language
      if (r.go === 'quote' && r.recommendation) setTimeout(() => onDone(r.recommendation), 700)
      if (r.go === 'tracker') setTimeout(onTrack, 700)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const submit = (e) => {
    e.preventDefault()
    const t = text.trim()
    if (!t) return
    setText('')
    send({ text: t }, t)
  }

  const mic = () => {
    if (!Recognition) { setError(tr(lang, 'voiceUnsupported')); return }
    if (listening) { recRef.current?.stop(); return }
    const r = new Recognition()
    r.lang = SPEECH_LANG[lang]; r.interimResults = false; r.maxAlternatives = 1
    r.onresult = (ev) => { const t = ev.results[0][0].transcript; send({ text: t }, t) }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    recRef.current = r; setListening(true); r.start()
  }

  const toggleNeed = (k) => setNeeds((ns) => ns.map((n) => (n.key === k ? { ...n, selected: !n.selected } : n)))
  const fresh = msgs.length <= 1
  const typeTiles = chips.length > 0 && chips.every((c) => c.slot === 'business_type')
  const canSpeak = typeof window !== 'undefined' && !!window.speechSynthesis

  const intro = (
    <div className="hero">
      <h1>{tr(lang, 'heroTitle')}</h1>
      <p>{tr(lang, 'heroSub')}</p>
      <div className="stats">
        <div><b>5 min</b><span>{tr(lang, 'statQuote')}</span></div><div><b>0</b><span>{tr(lang, 'statPaper')}</span></div><div><b>1</b><span>{tr(lang, 'statBill')}</span></div>
      </div>
      <a className="wa-link" href="#/whatsapp"><Icon name="chat" size={16} /> {tr(lang, 'preferWa')}</a>
    </div>
  )

  const facts = profile && (profile.business_type || profile.city) && (
    <div className="profilebar">
      {profile.business_name && <span className="tag"><Icon name="building" size={13} /> {profile.business_name}</span>}
      {profile.business_type && <span className="tag">{profile.business_type}</span>}
      {profile.city && <span className="tag"><Icon name="pin" size={13} /> {profile.city}{profile.city_tier ? ` · Tier ${profile.city_tier}` : ''}</span>}
      {profile.employees != null && <span className="tag"><Icon name="people" size={13} /> {profile.employees} people</span>}
      {profile.sites != null && <span className="tag">{profile.sites} site{profile.sites > 1 ? 's' : ''}</span>}
      {profile.has_gstin === true && <span className={'tag ' + (profile.gstin_verified === false ? 'bad' : 'ok')}><Icon name="verified" size={13} /> GSTIN {profile.gstin_masked}</span>}
      {profile.has_gstin === false && <span className="tag warn">No GSTIN</span>}
    </div>
  )

  const bundle = result && !busy && (
    <div className="card bundlecard">
      <div className="row between"><h3>{tr(lang, 'bundle')}</h3><span className="badge">{result.segment_name}</span></div>
      <div className="headline">
        <b>{inr(result.quote.monthly)}</b><span>{tr(lang, 'perMonth')} + GST</span>
      </div>
      <div className="summary-grid">
        <div><Icon name="bill" size={15} /><b>{inr(result.quote.setup)}</b><span>{tr(lang, 'setup')}</span></div>
        <div><Icon name="timer" size={15} /><b>{result.quote.activation_days} {tr(lang, 'days')}</b><span>{tr(lang, 'liveIn')}</span></div>
        <div><Icon name="check" size={15} /><b>{result.quote.lines.length}</b><span>{tr(lang, 'services')}</span></div>
      </div>
      {result.options?.length > 1 && (
        <div className="levels" role="radiogroup" aria-label={tr(lang, 'chooseLevel')}>
          {result.options.map((o) => (
            <button key={o.key} role="radio" aria-checked={o.current} className={'level ' + (o.current ? 'on' : '')}
              onClick={() => !o.current && send({ slot: 'refine', value: `option:${o.key}` }, o.label)}>
              <span>{o.label}</span><b>{inr(o.monthly)}</b><small>{tr(lang, 'nServices', { n: o.count })}</small>
            </button>
          ))}
        </div>
      )}
      {result.why?.length > 0 && (
        <details className="why">
          <summary><Icon name="idea" size={16} /> {tr(lang, 'whyBundle')} <Icon name="chevron" size={15} className="caret" /></summary>
          <ol>{result.why.map((w) => <li key={w.title}><b>{w.title.replace(/^\d+\.\s*/, '')}</b><span>{w.text}</span></li>)}</ol>
        </details>
      )}
      <div className="items">
        {result.quote.lines.map((l) => (
          <details key={l.id} className="item">
            <summary>
              <span className="ic"><ProductIcon id={l.id} size={17} /></span>
              <span className="nm">{l.plain || l.name}{l.qty > 1 ? `\u00a0×\u00a0${l.qty}` : ''}{l.asked && <span className="badge">{tr(lang, 'youAsked')}</span>}</span>
              <span className="pr">{inr(l.monthly)}</span>
            </summary>
            <ItemDetails lang={lang} line={l} />
          </details>
        ))}
      </div>
      <p className="small muted hint">{tr(lang, 'tapItem')}</p>
      <button className="btn" onClick={() => onDone(result)}>{tr(lang, 'seeBundle')} <Icon name="next" size={17} /></button>
    </div>
  )

  return (
    <div className={'advisor' + (wide ? ' wide' : '')}>
      <section className="conv">
        <main className="page">
          {!wide && fresh && intro}
          {!wide && facts}
          <div className="chat" aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={'bubble ' + m.who}>{m.text}
                {m.who === 'bot' && canSpeak && (
                  <button type="button" className="speak" title={tr(lang, 'readAloud')} aria-label={tr(lang, 'readAloud')} onClick={() => sayOne(m.text)}><Icon name="speak" size={14} /></button>
                )}
                {m.sources?.length > 0 && <div className="src" title="Where this answer comes from"><Icon name="doc" size={12} /> {m.sources.map((x) => x.title.replace(/^Product sheet: /, '')).join(' · ')}</div>}
              </div>
            ))}
            {busy && <div className="bubble bot typing"><span /><span /><span /></div>}
          </div>
          {needs && !busy && (
            <div className="card needcard">
              <div className="needs">
                {needs.map((n) => (
                  <label key={n.key} className={'need ' + (n.selected ? 'on' : '')}>
                    <input type="checkbox" checked={n.selected} onChange={() => toggleNeed(n.key)} />
                    <span className="ic"><NeedIcon id={n.key} size={17} /></span><span className="nm">{n.label}</span>
                    <i className="tick" aria-hidden><Icon name="check" size={12} strokeWidth={3} /></i>
                  </label>
                ))}
              </div>
              <button className="btn" onClick={() => send({ needs: needs.filter((n) => n.selected).map((n) => n.key) }, needs.filter((n) => n.selected).map((n) => n.label).join(', ') || '—')}>
                {tr(lang, 'continue')} <Icon name="next" size={17} />
              </button>
            </div>
          )}
          {!wide && bundle}
          {chips.length > 0 && !busy && (
            <div className={'chips' + (typeTiles ? ' tiles' : '')}>
              {chips.filter((c) => !(result?.options?.length > 1 && String(c.value).startsWith('option:'))).map((c) => (
                <button key={c.label} className={'chip' + (typeTiles ? ' tile' : '')} onClick={() => send({ slot: c.slot, value: c.value }, c.label)}>
                  {typeTiles && <span className="ic"><BusinessIcon id={c.value} size={18} /></span>}{c.label}
                </button>
              ))}
            </div>
          )}
          {error && <div className="notice">{error}</div>}
          <div ref={endRef} />
          {fresh && (
            <p className="small muted foot">
              {tr(lang, 'alreadyOrdered')} <button className="link" onClick={onTrack}>{tr(lang, 'track')}</button>
              {config && <span className={'aimode' + (config.llm ? ' on' : '')}>{config.llm ? tr(lang, 'aiOn') : tr(lang, 'aiOff')}</span>}
            </p>
          )}
        </main>
        <div className="bottombar">
          <form className="composer" onSubmit={submit}>
            <button type="button" className="iconbtn ghost" title={tr(lang, 'readAloud')} aria-label={tr(lang, 'readAloud')} aria-pressed={speak} onClick={() => setSpeak(!speak)}><Icon name={speak ? 'speak' : 'mute'} /></button>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? tr(lang, 'listening') : tr(lang, 'type')} aria-label={tr(lang, 'type')} />
            <button type="button" className={'iconbtn ' + (listening ? 'rec' : 'ghost')} onClick={mic} title="Speak" aria-label="Speak"><Icon name="mic" /></button>
            <button className="iconbtn" disabled={busy || !text.trim()} aria-label="Send"><Icon name="send" size={20} strokeWidth={2.4} /></button>
          </form>
        </div>
      </section>
      {wide && (
        <aside className="side">
          {facts && <div className="card factcard">{facts}</div>}
          {bundle || intro}
        </aside>
      )}
    </div>
  )
}
