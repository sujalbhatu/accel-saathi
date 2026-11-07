import React, { useEffect, useState } from 'react'
import { api, inr } from './api.js'
import { tr } from './i18n.js'

// What WhatsApp said happened to each update we sent (Meta reports sent, delivered and read)
const DELIVERY = { sent: 'waSent', template: 'waSent', delivered: 'waDelivered', read: 'waRead', demo: 'waDemo',
  test_only: 'waTestOnly', failed: 'waFailed' }

export default function Tracker({ lang, initial, onNew, toast }) {
  const [id, setId] = useState(initial?.id || '')
  const [o, setO] = useState(initial?.steps ? initial : null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [slot, setSlot] = useState('')
  const [ticket, setTicket] = useState('')

  const load = async (oid) => {
    if (!oid) return
    setBusy(true); setError('')
    try { setO(await api.getOrder(oid.trim().toUpperCase())) } catch (e) { setError(e.message); setO(null) } finally { setBusy(false) }
  }
  useEffect(() => { if (initial?.id && !initial.steps) load(initial.id) }, [initial])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!o) return
    const t = setInterval(() => api.getOrder(o.id).then(setO).catch(() => {}), 15000)
    return () => clearInterval(t)
  }, [o?.id])  // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (fn, msg) => {
    setBusy(true)
    try { setO(await fn()); if (msg) toast(msg) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (!o) {
    return (
      <main className="page">
        <h2>{tr(lang, 'trackTitle')}</h2>
        <div className="card">
          <label className="field"><span>{tr(lang, 'orderNo')}</span><input value={id} onChange={(e) => setId(e.target.value)} placeholder="e.g. AB1234ABCD" /></label>
          <button className="btn" disabled={!id || busy} onClick={() => load(id)}>{busy ? <span className="spinner" /> : tr(lang, 'trackBtn')}</button>
        </div>
        {error && <div className="notice">{error}</div>}
        <button className="btn ghost" onClick={onNew}>{tr(lang, 'newBundle')}</button>
      </main>
    )
  }

  const canBook = ['esigned', 'feasibility', 'scheduled'].includes(o.stage)
  return (
    <main className="page" style={{ paddingBottom: 24 }}>
      <div className="card">
        <div className="row between"><div><div className="small muted">{tr(lang, 'orderNo')}</div><b style={{ fontSize: 18, letterSpacing: 0.5 }}>{o.id}</b></div>
          <div style={{ textAlign: 'right' }}><div className="small muted">{tr(lang, 'expected')}</div><b>{new Date(o.expected_activation).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</b></div></div>
        <div className="progress"><div style={{ width: `${o.progress}%` }} /></div>
        <div className="small muted">{o.business} · {o.city} · {inr(o.quote.monthly)}{tr(lang, 'perMonth')}</div>
        {o.partner && <div className="small muted" style={{ marginTop: 4 }}>🤝 {tr(lang, 'helpedBy', { name: o.partner.name })}</div>}
      </div>

      <div className="card">
        <ul className="timeline">
          {o.steps.map((s) => (
            <li key={s.key} className={(s.done ? 'done ' : '') + (s.current ? 'current' : '')}>
              <span className="pt">{s.done && !s.current ? '✓' : ''}</span>
              <div className="lbl">{s.label}</div>
              {s.at && <div className="ts">{new Date(s.at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</div>}
              {s.key === 'scheduled' && o.slot && <div className="ts">{tr(lang, 'slotIs', { slot: o.slot })}</div>}
            </li>
          ))}
        </ul>
      </div>

      {canBook && (
        <div className="card">
          <h3>{tr(lang, 'pickSlot')}</h3>
          <div className="slots">{(o.slots || []).map((s) => <button key={s} className={(slot || o.slot) === s ? 'on' : ''} onClick={() => setSlot(s)}>{s}</button>)}</div>
          <button className="btn" style={{ marginTop: 10 }} disabled={!slot || busy} onClick={() => act(() => api.slot(o.id, slot), tr(lang, 'slotBooked'))}>{tr(lang, 'bookSlot')}</button>
        </div>
      )}

      <div className="card">
        <h3>{tr(lang, 'yourServices')}</h3>
        {o.items.map((it) => (
          <div key={it.id} className="svc"><span>{it.plain || it.name}{it.qty > 1 ? ` × ${it.qty}` : ''}<br /><span className="small muted">{tr(lang, 'byDate', { date: new Date(it.eta).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) })}</span></span>
            <span className={'status ' + it.status}>{tr(lang, 'item_' + it.status)}</span></div>
        ))}
      </div>

      <div className={'card onebill' + (o.stage === 'activated' ? ' live' : '')}>
        <h3>{tr(lang, 'oneBill')}</h3>
        <p className="small muted" style={{ marginTop: 0 }}>{tr(lang, 'oneBillSub')}</p>
        {o.quote.lines.map((l) => (
          <div key={l.id} className="row between small" style={{ padding: '3px 0' }}><span>{l.name}{l.qty > 1 ? ` × ${l.qty}` : ''}</span><span>{inr(l.monthly)}</span></div>
        ))}
        <div className="row between small muted" style={{ padding: '3px 0' }}><span>GST 18%</span><span>{inr(o.quote.gst)}</span></div>
        <div className="row between" style={{ borderTop: '1px solid var(--line)', paddingTop: 6, marginTop: 4 }}><b>{tr(lang, 'everyMonth')}</b><b>{inr(o.quote.monthly + o.quote.gst)}</b></div>
        <div className="nums">
          <div><b>1</b><span>{tr(lang, 'oneBillN')}</span></div>
          <div><b>121</b><span>{tr(lang, 'oneNumber')}</span></div>
          <div><b>1</b><span>{tr(lang, 'oneChat')}</span></div>
        </div>
      </div>

      <div className="card">
        <h3>{tr(lang, 'updates')}</h3>
        {o.notifications.slice(0, 6).map((n, i) => (
          <div key={i} className="wa"><small>{n.channel} · {new Date(n.at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</small>{n.text}
            {DELIVERY[n.delivery] && <small className={'dlv ' + n.delivery}>{tr(lang, DELIVERY[n.delivery])}</small>}</div>
        ))}
      </div>

      <div className="card">
        <h3>{tr(lang, 'help')}</h3>
        {o.tickets.map((t) => <div key={t.id} className="small" style={{ marginBottom: 6 }}><b>{t.id}</b> · {t.text} <span className="tag">{t.status}</span></div>)}
        <div className="row"><input className="field" style={{ flex: 1, marginBottom: 0, border: '1px solid var(--line)', borderRadius: 10, padding: 10 }} value={ticket} onChange={(e) => setTicket(e.target.value)} placeholder={tr(lang, 'helpPh')} />
          <button className="btn sm" disabled={ticket.trim().length < 3 || busy} onClick={() => act(() => api.ticket(o.id, ticket), 'Ticket raised').then(() => setTicket(''))}>{tr(lang, 'raise')}</button></div>
      </div>

      <div className="demo">
        <b>{tr(lang, 'demo')}</b> · stands in for field-engineer and back-office updates.
        <button className="btn sm dark" style={{ marginLeft: 8 }} disabled={busy || o.stage === 'activated'} onClick={() => act(() => api.advance(o.id))}>{tr(lang, 'nextUpdate')}</button>
      </div>
      {error && <div className="notice" style={{ marginTop: 10 }}>{error}</div>}
      <button className="btn ghost" style={{ marginTop: 12 }} onClick={onNew}>{tr(lang, 'newBundle')}</button>
    </main>
  )
}
