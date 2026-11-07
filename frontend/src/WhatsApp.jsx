import React, { useEffect, useRef, useState } from 'react'

// A WhatsApp chat that talks to the same handler as the real number, in the WhatsApp Cloud API format, so this
// screen shows exactly what an owner gets on WhatsApp. It posts to /api/whatsapp/demo, which never sends to Meta.

const Recognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

// Demo chats use "910" numbers, which no real Indian mobile has, so this screen can never speak for a real customer.
function waId() {
  const fresh = () => '910' + String(Math.floor(Math.random() * 1e9)).padStart(9, '0')
  try {
    let id = localStorage.getItem('wa_demo_id')
    if (!/^910\d{9}$/.test(id || '')) { id = fresh(); localStorage.setItem('wa_demo_id', id) }
    return id
  } catch { return fresh() }
}

const now = () => new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })

export default function WhatsApp() {
  const [items, setItems] = useState([{ who: 'bot', type: 'text', text: 'Namaste! 👋 This is Accel Saathi, Accel Business on WhatsApp. Tell me about your business in a line, in any language, and I\'ll suggest the right internet, phone and billing bundle.', at: now() }])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [sheet, setSheet] = useState(null)
  const [listening, setListening] = useState(false)
  const id = useRef(waId())
  const endRef = useRef(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [items, busy])

  const post = async (message, shown) => {
    setItems((x) => [...x, { who: 'me', type: 'text', text: shown, at: now() }])
    setBusy(true)
    try {
      const res = await fetch('/api/whatsapp/demo', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ object: 'whatsapp_business_account', entry: [{ changes: [{ value: { messages: [{ from: id.current, id: 'wamid.' + Date.now(), ...message }] } }] }] }),
      })
      const j = await res.json()
      setItems((x) => [...x, ...j.sent.map((b) => ({ who: 'bot', at: now(), ...b }))])
    } catch {
      setItems((x) => [...x, { who: 'bot', type: 'text', text: 'Network problem, please try again.', at: now() }])
    } finally { setBusy(false) }
  }

  const sendText = (e) => {
    e?.preventDefault()
    const t = text.trim()
    if (!t || busy) return
    setText('')
    post({ type: 'text', text: { body: t } }, t)
  }
  const tap = (reply, kind = 'button_reply') => { setSheet(null); post({ type: 'interactive', interactive: { type: kind, [kind]: reply } }, reply.title) }

  const mic = () => {
    if (!Recognition || listening) return
    const r = new Recognition()
    r.lang = 'hi-IN'; r.interimResults = false
    r.onresult = (ev) => { const t = ev.results[0][0].transcript; post({ type: 'text', text: { body: t } }, '🎤 ' + t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    setListening(true); r.start()
  }

  return (
    <div className="wa-shell">
      <header className="wa-top">
        <a href="#/" className="wa-back" aria-label="Back to the app">←</a>
        <div className="wa-avatar">A</div>
        <div className="wa-title"><b>Accel Saathi <span className="wa-tick" title="Verified business">✓</span></b><small>{busy ? 'typing…' : 'Official business account'}</small></div>
      </header>
      <main className="wa-chat" aria-live="polite">
        <div className="wa-note">🔒 Messages are handled by Accel's advisor. Same conversation continues in the app.</div>
        {items.map((m, i) => <Bubble key={i} m={m} onTap={tap} onList={setSheet} />)}
        {busy && <div className="wa-msg in"><span className="wa-typing"><i /><i /><i /></span></div>}
        <div ref={endRef} />
      </main>
      <form className="wa-input" onSubmit={sendText}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Message" aria-label="Message" />
        {text.trim()
          ? <button className="wa-send" aria-label="Send">➤</button>
          : <button type="button" className={'wa-send' + (listening ? ' rec' : '')} onClick={mic} aria-label="Voice message">🎤</button>}
      </form>
      {sheet && (
        <div className="wa-sheet" onClick={() => setSheet(null)}>
          <div className="wa-sheet-box" onClick={(e) => e.stopPropagation()}>
            <b>{sheet.button}</b>
            {sheet.sections.flatMap((s) => s.rows).map((r) => <button key={r.id} onClick={() => tap(r, 'list_reply')}>{r.title}</button>)}
          </div>
        </div>
      )}
    </div>
  )
}

function Bubble({ m, onTap, onList }) {
  const cls = 'wa-msg ' + (m.who === 'me' ? 'out' : 'in')
  if (m.type === 'text') return <div className={cls}>{m.text?.body ?? m.text}<time>{m.at}{m.who === 'me' ? ' ✓✓' : ''}</time></div>
  const it = m.interactive
  if (it.type === 'cta_url') {
    const url = it.action.parameters.url
    const local = url.includes('#') ? '#' + url.split('#')[1] : url
    return (
      <div className={cls + ' card'}><pre>{it.body.text}</pre><time>{m.at}</time>
        <a className="wa-btn" href={local}>↗ {it.action.parameters.display_text}</a></div>
    )
  }
  if (it.type === 'button') {
    return (
      <div className={cls + ' card'}>{it.body.text !== '👇' && <pre>{it.body.text}</pre>}
        {it.action.buttons.map((b) => <button key={b.reply.id} className="wa-btn" onClick={() => onTap(b.reply)}>{b.reply.title}</button>)}
      </div>
    )
  }
  if (it.type === 'list') {
    return (
      <div className={cls + ' card'}>
        <button className="wa-btn" onClick={() => onList(it.action)}>☰ {it.action.button}</button>
      </div>
    )
  }
  return null
}
