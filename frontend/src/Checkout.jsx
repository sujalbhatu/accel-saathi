import React, { useEffect, useState } from 'react'
import { api, inr } from './api.js'
import { tr } from './i18n.js'

export default function Checkout({ lang, session, cart, onBack, onPlaced }) {
  const [q, setQ] = useState(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [wa, setWa] = useState(true)
  const [otp, setOtp] = useState('')
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.quote(session, cart.selection, cart.term).then(setQ).catch((e) => setError(e.message)) }, [session, cart])

  const valid = name.trim().length >= 2 && /^[6-9]\d{9}$/.test(phone) && otp.length === 6 && agree
  const place = async () => {
    setBusy(true); setError('')
    try {
      const o = await api.order({ session_id: session, selection: cart.selection, contract_months: cart.term, contact_name: name, phone, whatsapp_updates: wa, esign_otp: otp })
      onPlaced(o)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <>
      <main className="page">
        <h2>{tr(lang, 'checkout')}</h2>
        {q && (
          <div className="card">
            {q.quote.lines.map((l) => (
              <div key={l.id} className="row between small" style={{ padding: '5px 0' }}><span>{l.name}{l.qty > 1 ? ` × ${l.qty}` : ''}</span><span>{inr(l.monthly)}</span></div>
            ))}
            <hr style={{ border: 0, borderTop: '1px solid var(--line)' }} />
            <div className="row between"><b>Monthly ({cart.term} {tr(lang, 'months')})</b><b>{inr(q.quote.monthly)}</b></div>
            <div className="row between small muted"><span>GST 18%</span><span>{inr(q.quote.gst)}</span></div>
            <div className="row between small muted"><span>{tr(lang, 'setup')} (first bill)</span><span>{inr(q.quote.setup)}</span></div>
          </div>
        )}
        <div className="card">
          <label className="field"><span>{tr(lang, 'name')}</span><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
          <label className="field"><span>{tr(lang, 'mobile')}</span><input value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))} inputMode="tel" placeholder="10-digit mobile" autoComplete="tel" /></label>
          <label className="check"><input type="checkbox" checked={wa} onChange={(e) => setWa(e.target.checked)} /> <span>{tr(lang, 'waUpdates')}</span></label>
        </div>
        <div className="card">
          <h3>{tr(lang, 'esign')}</h3>
          <label className="check"><input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} /> <span>I accept the service agreement: {cart.term}-month term, prices fixed for the term, cancel any time after the term with 30 days' notice.</span></label>
          <label className="field" style={{ marginBottom: 0 }}><span>{tr(lang, 'otp')}</span><input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" placeholder="6 digits (demo: any)" /></label>
        </div>
        {error && <div className="notice">{error}</div>}
        <button className="btn ghost" onClick={onBack}>← Back</button>
      </main>
      <div className="bottombar">
        <button className="btn" disabled={!valid || busy} onClick={place}>{busy ? <><span className="spinner" /> {tr(lang, 'placing')}</> : tr(lang, 'place')}</button>
      </div>
    </>
  )
}
