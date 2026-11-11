import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { LANGS, tr } from './i18n.js'
import Advisor from './Advisor.jsx'
import Quote from './Quote.jsx'
import Kyc from './Kyc.jsx'
import Checkout from './Checkout.jsx'
import Tracker from './Tracker.jsx'
import Icon from './Icon.jsx'

const STEP_INDEX = { advisor: 0, quote: 1, kyc: 2, checkout: 3, tracker: 4 }

export default function App({ hash }) {
  const [lang, setLang] = useState(() => localStorageGet('lang') || 'en')
  const [step, setStep] = useState('advisor')
  // Screen readers and the browser's text shaping both need to know which language is on screen
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  // A link from WhatsApp or a partner's QR (#/continue/<id>) picks up that conversation; it must win before the chat
  // screen mounts, or a fresh chat would start and replace it.
  const [session, setSessionState] = useState(() => {
    const c = window.location.hash.match(/^#\/continue\/(\w+)/)
    if (c) storageSet('advisor_session', c[1])
    return c ? c[1] : storageGet('advisor_session')
  })
  const setSession = (sid) => { setSessionState(sid); storageSet('advisor_session', sid) }
  const [rec, setRec] = useState(null)
  const [cart, setCart] = useState({ selection: [], term: 12 })
  const [order, setOrder] = useState(null)
  const [toast, setToast] = useState('')
  const [config, setConfig] = useState(null)
  const [partner, setPartner] = useState(null)

  useEffect(() => { api.config().then(setConfig).catch(() => {}) }, [])
  useEffect(() => {
    const m = hash.match(/^#\/track\/?(\w*)/)
    if (m) { setStep('tracker'); if (m[1]) setOrder({ id: m[1] }) }
    const c = hash.match(/^#\/continue\/(\w+)/)  // opened from WhatsApp: pick up the same conversation
    if (c) { setSession(c[1]); setStep('advisor'); window.location.hash = '' }
  }, [hash])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(''), 3500); return () => clearTimeout(t) } }, [toast])

  const changeLang = (l) => {
    setLang(l)
    localStorageSet('lang', l)
    if (session) api.setLang(session, l).catch(() => {})
  }
  const restart = () => {
    setSession(null); setPartner(null); setRec(null); setOrder(null); setCart({ selection: [], term: 12 }); setStep('advisor')
    window.location.hash = ''
  }

  return (
    <div className={'shell step-' + step}>
      <header className="topbar">
        <div className="inner">
          <div className="logo" aria-hidden>
            <svg viewBox="0 0 32 32" width="32" height="32"><rect width="32" height="32" rx="9" fill="currentColor" /><path d="M9.5 22.5 16 9.5l6.5 13" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <div className="brand">Accel Saathi<small>{tr(lang, 'tagline')}</small></div>
          {step !== 'tracker' && (
            <button type="button" className="toplink" onClick={() => { setStep('tracker'); window.location.hash = '#/track' }}>
              <Icon name="clock" size={16} /> {tr(lang, 'track')}
            </button>
          )}
          <label className="langpick">
            <Icon name="languages" size={16} />
            <select value={lang} onChange={(e) => changeLang(e.target.value)} aria-label="Language">
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
            </select>
          </label>
        </div>
      </header>
      <nav className="steps" aria-label={tr(lang, 'steps')[STEP_INDEX[step]]}>
        <ol>
          {tr(lang, 'steps').map((s, i) => (
            <li key={s} className={i < STEP_INDEX[step] ? 'done' : i === STEP_INDEX[step] ? 'on' : ''} aria-current={i === STEP_INDEX[step] ? 'step' : undefined}>
              <i>{i < STEP_INDEX[step] ? <Icon name="check" size={13} strokeWidth={3} /> : i + 1}</i><span>{s}</span>
            </li>
          ))}
        </ol>
      </nav>
      {partner && step !== 'tracker' && (
        <div className="assisted"><Icon name="handshake" size={16} /> {tr(lang, partner.mode === 'assisted' ? 'assistedBy' : 'referredBy', { name: partner.name })}</div>
      )}

      <div className="stage">
      {step === 'advisor' && (
        <Advisor key={session || 'new'} lang={lang} session={session} setSession={setSession} config={config}
          onLang={(l) => { setLang(l); localStorageSet('lang', l) }}
          onDone={(r) => { setRec(r); setCart({ selection: r.quote.lines.map((l) => ({ id: l.id, qty: l.qty, reason: l.reason })), term: r.quote.term_months }); setStep('quote') }}
          onTrack={() => { setStep('tracker'); window.location.hash = '#/track' }} onPartner={setPartner} />
      )}
      {step === 'quote' && rec && (
        <Quote lang={lang} session={session} rec={rec} cart={cart} setCart={setCart}
          onBack={() => setStep('advisor')} onNext={() => setStep('kyc')} />
      )}
      {step === 'kyc' && (
        <Kyc lang={lang} session={session} partner={partner} onPartner={setPartner} onBack={() => setStep('quote')} onNext={() => setStep('checkout')} toast={setToast} />
      )}
      {step === 'checkout' && (
        <Checkout lang={lang} session={session} cart={cart} onBack={() => setStep('kyc')} toast={setToast}
          onPlaced={(o) => { setOrder(o); setStep('tracker'); window.location.hash = `#/track/${o.id}` }} />
      )}
      {step === 'tracker' && (
        <Tracker lang={lang} initial={order} onNew={restart} toast={setToast} />
      )}
      </div>
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  )
}

function localStorageGet(k) { try { return localStorage.getItem(k) } catch { return null } }
function localStorageSet(k, v) { try { localStorage.setItem(k, v) } catch { /* private mode */ } }
// The conversation id lives for the browser tab, so a reload resumes the chat but a new tab starts fresh.
function storageGet(k) { try { return sessionStorage.getItem(k) } catch { return null } }
function storageSet(k, v) { try { if (v) sessionStorage.setItem(k, v); else sessionStorage.removeItem(k) } catch { /* private mode */ } }
