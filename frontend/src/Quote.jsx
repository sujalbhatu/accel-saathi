import React, { useEffect, useState } from 'react'
import { api, inr } from './api.js'
import { tr } from './i18n.js'
import ItemDetails from './Item.jsx'

const WHY = { tier: 'Only in tier-1 cities', employees: 'Needs a bigger team', sites: 'For 3+ locations', gstin: 'Needs an active GSTIN', dependency: 'Needs a broadband line' }

export default function Quote({ lang, session, rec, cart, setCart, onBack, onNext }) {
  const [q, setQ] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    let live = true
    setBusy(true)
    api.quote(session, cart.selection, cart.term)
      .then((r) => { if (live) { setQ(r); setError('') } })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setBusy(false))
    return () => { live = false }
  }, [session, cart])

  const setQty = (id, d) => setCart((c) => ({ ...c, selection: c.selection.map((s) => (s.id === id ? { ...s, qty: Math.max(1, s.qty + d) } : s)) }))
  const remove = (id) => setCart((c) => ({ ...c, selection: c.selection.filter((s) => s.id !== id) }))
  const add = (id, qty = 1) => setCart((c) => ({ ...c, selection: [...c.selection, { id, qty, reason: 'addon' }] }))
  const setTerm = (term) => setCart((c) => ({ ...c, term }))

  if (!q) return <main className="page">{error ? <div className="notice">{error}</div> : <div className="spinner dark" />}</main>
  const quote = q.quote
  const suggested = (rec.suggested || []).filter((s) => !quote.lines.some((l) => l.id === s.id))
  const addons = q.addons.filter((a) => !suggested.some((s) => s.id === a.id))
  const visibleAddons = showAll ? addons : addons.filter((a) => a.eligible && a.fit).slice(0, 5)
  const saving = cart.term === 12 && q.term_compare.term === 24 ? quote.monthly - q.term_compare.monthly : 0

  return (
    <>
      <main className="page">
        <h2>{tr(lang, 'bundle')}</h2>
        {q.notes?.some((n) => n.startsWith('added:')) && <div className="notice info">We added an internet line because some services need one.</div>}
        {q.blocked?.length > 0 && q.blocked.map((b) => (
          <div key={b.id} className="notice">{b.name}: {WHY[b.why] || b.why}{b.alternative ? '. We suggested an alternative.' : '.'}</div>
        ))}
        <div className="card">
          {quote.lines.map((l) => (
            <div key={l.id} className="line">
              <div>
                <div className="name">{l.plain || l.name}{l.asked && <span className="badge">{tr(lang, 'youAsked')}</span>}</div>
                <div className="small muted">{l.name} · {inr(l.unit_price)} {l.unit} · {l.contract_months} {tr(lang, 'months')}{l.setup ? ` · ${tr(lang, 'setup')} ${inr(l.setup)}` : ''}</div>
              </div>
              <div className="price">{inr(l.monthly)}</div>
              <div className="why">{l.why || l.reason_text}</div>
              {l.skip && (
                <details className="item why">
                  <summary><span className="link small">{tr(lang, 'moreInfo')}</span></summary>
                  <ItemDetails lang={lang} line={l} showWhy={false} />
                </details>
              )}
              <div className="row" style={{ gridColumn: '1 / -1', marginTop: 4 }}>
                {l.unit !== 'per account' && l.unit !== 'per number' && l.unit !== 'per pack' && (
                  <div className="qty" aria-label="Quantity">
                    <button onClick={() => setQty(l.id, -1)} aria-label="Less">−</button><span>{l.qty}</span><button onClick={() => setQty(l.id, 1)} aria-label="More">+</button>
                  </div>
                )}
                <div className="spacer" />
                <button className="link small" onClick={() => remove(l.id)}>{tr(lang, 'remove')}</button>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>{tr(lang, 'term')}</h3>
          <div className="seg">
            {[12, 24].map((t) => <button key={t} className={cart.term === t ? 'on' : ''} onClick={() => setTerm(t)}>{t} {tr(lang, 'months')}</button>)}
          </div>
          {saving > 0 && <p className="small" style={{ color: 'var(--ok)', marginBottom: 0 }}>{tr(lang, 'save24', { amt: inr(saving) })}</p>}
        </div>

        {suggested.length > 0 && (
          <div className="card">
            <h3>Recommended add-ons</h3>
            {suggested.map((s) => (
              <div key={s.id} className="addon">
                <div className="meta"><b>{s.plain || s.name}</b>{s.qty > 1 ? ` × ${s.qty}` : ''}<div className="small muted">{s.does || s.reason_text}</div></div>
                <div style={{ textAlign: 'right' }}><div className="price small">{inr(s.monthly)}</div><button className="btn sm" onClick={() => add(s.id, s.qty)}>{tr(lang, 'add')}</button></div>
              </div>
            ))}
          </div>
        )}

        <div className="card">
          <div className="row between"><h3>{tr(lang, 'addons')}</h3><button className="link small" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show fewer' : `All ${addons.length}`}</button></div>
          {visibleAddons.map((a) => (
            <div key={a.id} className={'addon ' + (a.eligible ? '' : 'off')}>
              <div className="meta"><b>{a.plain || a.name}</b><div className="small muted">{a.does || a.description}</div>
                {!a.eligible && <div className="small" style={{ color: 'var(--bad)' }}>{tr(lang, 'notEligible')}: {WHY[a.why]}</div>}
              </div>
              <div style={{ textAlign: 'right' }}><div className="price small">{inr(a.unit_price)}</div>
                <button className="btn sm ghost" disabled={!a.eligible} onClick={() => add(a.id)}>{tr(lang, 'add')}</button></div>
            </div>
          ))}
        </div>
        <p className="small muted">{tr(lang, 'gstNote')} Prices are within Accel's published range; longer contracts get the lower end.</p>
        <button className="btn ghost" onClick={onBack}>← {tr(lang, 'backAdvisor')}</button>
      </main>
      <div className="bottombar">
        <div className="total">
          <div><b>{inr(quote.monthly)}</b><span className="muted">{tr(lang, 'perMonth')}</span><div className="small muted">{tr(lang, 'plusGst')} = {inr(quote.monthly_with_gst)} · {tr(lang, 'setup')} {inr(quote.setup)}</div>
            {quote.setup > 0 && quote.first_bill && <div className="small muted">{tr(lang, 'firstBill', { amt: inr(quote.first_bill) })}</div>}</div>
          <div className="small muted" style={{ textAlign: 'right' }}>{quote.lines.length} {tr(lang, 'services')}<br />{tr(lang, 'liveIn')} ~{quote.activation_days} {tr(lang, 'days')}</div>
        </div>
        <button className="btn" disabled={busy || !quote.lines.length} onClick={onNext}>{busy ? <span className="spinner" /> : tr(lang, 'toKyc')}</button>
      </div>
    </>
  )
}
