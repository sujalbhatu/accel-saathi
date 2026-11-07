import React, { useEffect, useRef, useState } from 'react'
import { api, inr } from './api.js'
import { SPEECH_LANG, tr } from './i18n.js'
import ItemDetails from './Item.jsx'

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
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [msgs, busy, needs, result])

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

  return (
    <>
      <main className="page" style={{ paddingBottom: 90 }}>
        {msgs.length <= 1 && (
          <div className="hero">
            <h1>{tr(lang, 'heroTitle')}</h1>
            <p>{tr(lang, 'heroSub')}</p>
            <a className="wa-link" href="#/whatsapp">💬 {tr(lang, 'preferWa')}</a>
            <div className="stats">
              <div><b>5 min</b>{tr(lang, 'statQuote')}</div><div><b>0</b>{tr(lang, 'statPaper')}</div><div><b>1</b>{tr(lang, 'statBill')}</div>
            </div>
          </div>
        )}
        {profile && (profile.business_type || profile.city) && (
          <div className="profilebar">
            {profile.business_name && <span className="tag">{profile.business_name}</span>}
            {profile.business_type && <span className="tag">{profile.business_type}</span>}
            {profile.city && <span className="tag">{profile.city}{profile.city_tier ? ` · Tier ${profile.city_tier}` : ''}</span>}
            {profile.employees != null && <span className="tag">{profile.employees} people</span>}
            {profile.sites != null && <span className="tag">{profile.sites} site{profile.sites > 1 ? 's' : ''}</span>}
            {profile.has_gstin === true && <span className={'tag ' + (profile.gstin_verified === false ? 'bad' : 'ok')}>GSTIN {profile.gstin_masked}</span>}
            {profile.has_gstin === false && <span className="tag warn">No GSTIN</span>}
          </div>
        )}
        <div className="chat" aria-live="polite">
          {msgs.map((m, i) => (
            <div key={i} className={'bubble ' + m.who}>{m.text}
              {m.who === 'bot' && typeof window !== 'undefined' && window.speechSynthesis && (
                <button type="button" className="speak" title={tr(lang, 'readAloud')} aria-label={tr(lang, 'readAloud')} onClick={() => sayOne(m.text)}>🔈</button>
              )}
              {m.sources?.length > 0 && <div className="src" title="Where this answer comes from">📄 {m.sources.map((x) => x.title.replace(/^Product sheet: /, '')).join(' · ')}</div>}
            </div>
          ))}
          {busy && <div className="bubble bot typing"><span /><span /><span /></div>}
        </div>
        {needs && !busy && (
          <div className="card">
            <div className="needs">
              {needs.map((n) => (
                <label key={n.key} className={'need ' + (n.selected ? 'on' : '')}>
                  <input type="checkbox" checked={n.selected} onChange={() => toggleNeed(n.key)} /> {n.label}
                </label>
              ))}
            </div>
            <button className="btn" style={{ marginTop: 10 }} onClick={() => send({ needs: needs.filter((n) => n.selected).map((n) => n.key) }, needs.filter((n) => n.selected).map((n) => n.label).join(', ') || '—')}>
              {tr(lang, 'continue')}
            </button>
          </div>
        )}
        {result && !busy && (
          <div className="card">
            <div className="row between"><h3>{tr(lang, 'bundle')}</h3><span className="badge">{result.segment_name}</span></div>
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
                <summary>💡 {tr(lang, 'whyBundle')}</summary>
                <ol>{result.why.map((w) => <li key={w.title}><b>{w.title.replace(/^\d+\.\s*/, '')}</b><span>{w.text}</span></li>)}</ol>
              </details>
            )}
            {result.quote.lines.map((l) => (
              <details key={l.id} className="item">
                <summary>
                  <span>{l.plain || l.name}{l.qty > 1 ? ` × ${l.qty}` : ''}{l.asked && <span className="badge">{tr(lang, 'youAsked')}</span>}</span>
                  <span className="muted">{inr(l.monthly)}</span>
                </summary>
                <ItemDetails lang={lang} line={l} />
              </details>
            ))}
            <p className="small muted" style={{ margin: '6px 0 0' }}>{tr(lang, 'tapItem')}</p>
            <div className="summary-grid">
              <div><b>{inr(result.quote.monthly)}</b><span>{tr(lang, 'perMonth')} + GST</span></div>
              <div><b>{inr(result.quote.setup)}</b><span>{tr(lang, 'setup')}</span></div>
              <div><b>{result.quote.activation_days} {tr(lang, 'days')}</b><span>{tr(lang, 'liveIn')}</span></div>
            </div>
            <button className="btn" style={{ marginTop: 12 }} onClick={() => onDone(result)}>{tr(lang, 'seeBundle')}</button>
          </div>
        )}
        {chips.length > 0 && !busy && (
          <div className="chips">
            {chips.filter((c) => !(result?.options?.length > 1 && String(c.value).startsWith('option:'))).map((c) => (
              <button key={c.label} className="chip" onClick={() => send({ slot: c.slot, value: c.value }, c.label)}>{c.label}</button>
            ))}
          </div>
        )}
        {error && <div className="notice">{error}</div>}
        <div ref={endRef} />
        {msgs.length <= 1 && (
          <p className="small muted" style={{ textAlign: 'center' }}>
            {tr(lang, 'alreadyOrdered')} <button className="link" onClick={onTrack}>{tr(lang, 'track')}</button>
            {config && <><br />{config.llm ? tr(lang, 'aiOn') : tr(lang, 'aiOff')}</>}
          </p>
        )}
      </main>
      <div className="bottombar">
        <form className="composer" onSubmit={submit}>
          <button type="button" className={'iconbtn ghost'} title="Read replies aloud" aria-pressed={speak} onClick={() => setSpeak(!speak)}>{speak ? '🔊' : '🔈'}</button>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? tr(lang, 'listening') : tr(lang, 'type')} aria-label={tr(lang, 'type')} />
          <button type="button" className={'iconbtn ' + (listening ? 'rec' : 'ghost')} onClick={mic} title="Speak">🎤</button>
          <button className="iconbtn" disabled={busy || !text.trim()} aria-label="Send">➤</button>
        </form>
      </div>
    </>
  )
}
