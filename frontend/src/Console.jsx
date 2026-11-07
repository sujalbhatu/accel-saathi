import React, { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { api, inr } from './api.js'
import { LANGS } from './i18n.js'

const STAGE_LABEL = { advisor_started: 'Started advisor', needs_assessed: 'Needs assessed', quote_viewed: 'Saw quote', kyc_started: 'Started KYC', kyc_complete: 'KYC complete', order_placed: 'Order placed' }

export default function Console() {
  const [ov, setOv] = useState(null)
  const [leads, setLeads] = useState(null)
  const [model, setModel] = useState(null)
  const [audit, setAudit] = useState([])
  const [tab, setTab] = useState('live')

  const refresh = () => {
    api.consoleOverview().then(setOv).catch(() => {})
    api.consoleLeads().then(setLeads).catch(() => {})
    api.consoleAudit().then(setAudit).catch(() => {})
  }
  useEffect(() => { refresh(); api.consoleModel().then(setModel).catch(() => {}); const t = setInterval(refresh, 20000); return () => clearInterval(t) }, [])

  const rows = leads ? (tab === 'live' ? leads.live : leads.pipeline) : []
  const max = ov ? Math.max(1, ...Object.values(ov.live_funnel)) : 1
  return (
    <>
      <div className="console-top"><div className="inner">
        <div className="logo">A</div><div className="brand">Accel Saathi<small>Partner &amp; sales console</small></div>
        <div className="spacer" /><a href="#" style={{ color: '#fff', fontSize: 14 }}>Open customer app →</a>
      </div></div>
      <div className="console-wrap">
        {ov && (
          <div className="kpis">
            <div className="kpi"><span>Baseline lead → activation</span><b>{(ov.baseline.conversion * 100).toFixed(1)}%</b><span>{ov.baseline.activated} of {ov.baseline.leads.toLocaleString('en-IN')} leads, Apr–Jun</span></div>
            <div className="kpi"><span>Baseline days to activate</span><b>{ov.baseline.days_to_activate}</b><em>Target: under 7</em></div>
            <div className="kpi"><span>Baseline status chases / customer</span><b>{ov.baseline.follow_up_calls}</b><em>Tracker target: under 0.5</em></div>
            <div className="kpi"><span>Baseline acquisition cost</span><b>{inr(ov.baseline.cac)}</b><em>Target: under ₹5,000</em></div>
            {model && <div className="kpi"><span>Lead score model (AUC)</span><b>{model.auc}</b><em>Top 10% convert {model.lift}x the average</em></div>}
          </div>
        )}
        <div className="grid2">
          <div className="card">
            <div className="row between"><h3>Leads to call</h3>
              <div className="tabs">
                <button className={tab === 'live' ? 'on' : ''} onClick={() => setTab('live')}>Advisor could not close ({leads?.live.length ?? 0})</button>
                <button className={tab === 'pipe' ? 'on' : ''} onClick={() => setTab('pipe')}>Recoverable Q1 leads</button>
              </div></div>
            <div className="scroll">
              <table>
                <thead><tr><th>Business</th><th>City · language</th><th>Stuck at</th><th>Chance</th><th>Why</th><th>Next best action</th><th>Owner</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.lead_id}>
                      <td><b>{r.business || '—'}</b><div className="small muted">{r.type}</div></td>
                      <td>{r.city || '—'}<div className="small muted">{r.language}</div></td>
                      <td>{r.stage}<div className="small muted">{r.drop_reason}</div></td>
                      <td><span className="score">{r.score}%<i style={{ width: Math.max(4, r.score) }} /></span></td>
                      <td className="small">{r.drivers.map((d) => (d.effect === 'up' ? '▲ ' : '▼ ') + d.factor).join(' · ')}</td>
                      <td className="small">{r.action}</td>
                      <td className="small">{r.partner}</td>
                    </tr>
                  ))}
                  {!rows.length && <tr><td colSpan={7} className="muted">No open leads yet. Start a chat in the customer app and leave before ordering.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
          <div>
            {ov && (
              <div className="card">
                <h3>Live digital funnel</h3>
                <div className="funnel">
                  {Object.entries(ov.live_funnel).map(([k, v]) => (
                    <div key={k} className="bar"><span className="small">{STAGE_LABEL[k]}</span><div style={{ width: `${(100 * v) / max}%` }} /><b className="small">{v}</b></div>
                  ))}
                </div>
              </div>
            )}
            {ov && (
              <div className="card">
                <h3>Recent orders</h3>
                {ov.orders.slice(0, 6).map((o) => (
                  <div key={o.id} className="row between small" style={{ padding: '5px 0', borderBottom: '1px solid var(--line)' }}>
                    <span><a href={`#/track/${o.id}`}>{o.id}</a> · {o.business}</span><span>{o.stage} · {inr(o.monthly)}</span>
                  </div>
                ))}
                {!ov.orders.length && <p className="small muted">No orders yet.</p>}
              </div>
            )}
            {model && (
              <div className="card">
                <h3>What drives activation</h3>
                <p className="small muted" style={{ marginTop: 0 }}>Logistic regression on {model.training_rows.toLocaleString('en-IN')} leads, 5-fold cross-validated.</p>
                {model.top_factors.map((f) => <div key={f.factor} className="row between small" style={{ padding: '3px 0' }}><span>{f.factor}</span><b style={{ color: f.weight > 0 ? 'var(--ok)' : 'var(--bad)' }}>{f.weight > 0 ? '+' : ''}{f.weight}</b></div>)}
              </div>
            )}
          </div>
        </div>
        <AssistCard />
        <PartnerSales />
        <div className="card">
          <h3>Audit log <span className="small muted">(identifiers masked, no document images stored)</span></h3>
          <div className="scroll"><table><thead><tr><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Reference</th><th>Detail</th></tr></thead>
            <tbody>{audit.slice(0, 25).map((a, i) => <tr key={i}><td className="small">{a.ts.replace('T', ' ').slice(0, 19)}</td><td>{a.actor}</td><td>{a.action}</td><td className="small">{a.ref}</td><td className="small">{a.detail}</td></tr>)}</tbody></table></div>
        </div>
      </div>
    </>
  )
}

function Qr({ url }) {
  const [src, setSrc] = useState('')
  useEffect(() => { QRCode.toDataURL(url, { margin: 1, width: 300 }).then(setSrc).catch(() => setSrc('')) }, [url])
  return src ? <img src={src} alt={`QR code for ${url}`} /> : null
}

// The partner sits with the owner: start the chat on the partner's tablet; the owner can scan to carry on on her phone.
function AssistCard() {
  const [partners, setPartners] = useState([])
  const [pid, setPid] = useState('PT01')
  const [lang, setLang] = useState('en')
  const [started, setStarted] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.partners().then(setPartners).catch(() => {}) }, [])
  const p = partners.find((x) => x.id === pid)
  const refUrl = `${window.location.origin}/?ref=${pid}`
  const start = async () => {
    setError('')
    try { setStarted(await api.assistStart(pid, lang)) } catch (e) { setError(e.message) }
  }
  const openHere = () => {
    try { sessionStorage.setItem('advisor_session', started.session_id); localStorage.setItem('lang', lang) } catch { /* private mode */ }
    window.location.hash = `#/continue/${started.session_id}`
  }
  return (
    <div className="card">
      <h3>Assisted mode</h3>
      <p className="small muted" style={{ marginTop: 0 }}>A partner sits with the owner and fills the chat for her. She gives KYC consent herself, by a code on her own phone, and her verified number stays credited to the partner for 30 days, even if she orders on her own later.</p>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <select value={pid} onChange={(e) => { setPid(e.target.value); setStarted(null) }} aria-label="Partner">
          {partners.map((x) => <option key={x.id} value={x.id}>{x.id} · {x.name}</option>)}
        </select>
        <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Owner's language">
          {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
        <button className="btn small" onClick={start}>Start assisted chat</button>
      </div>
      {p && <div className="small muted" style={{ marginTop: 6 }}>Covers {p.cities.join(', ')} · speaks {p.languages.join(', ')}</div>}
      {error && <div className="notice" style={{ marginTop: 8 }}>{error}</div>}
      <div className="qrs">
        {started && (
          <div className="qr">
            <Qr url={started.join_url} />
            <div>
              <b>Chat ready for the owner</b>
              <p className="small" style={{ margin: '4px 0 8px' }}>She scans this to carry on on her own phone, or the partner continues here.</p>
              <button className="btn small" onClick={openHere}>Continue on this device →</button>
              <div className="link muted" style={{ marginTop: 6 }}>{started.join_url}</div>
            </div>
          </div>
        )}
        <div className="qr">
          <Qr url={refUrl} />
          <div>
            <b>Counter QR for {p?.name || pid}</b>
            <p className="small" style={{ margin: '4px 0 0' }}>Print it at the shop. An owner who scans it and orders alone, within 30 days, is still this partner's sale.</p>
            <div className="link muted" style={{ marginTop: 6 }}>{refUrl}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

const VIA = { assisted: 'assisted', referral: 'counter QR', protected: 'protected (30 days)' }

function PartnerSales() {
  const [rows, setRows] = useState([])
  useEffect(() => { const load = () => api.consolePartners().then(setRows).catch(() => {}); load(); const t = setInterval(load, 20000); return () => clearInterval(t) }, [])
  return (
    <div className="card">
      <h3>Partner sales and commission</h3>
      <p className="small muted" style={{ marginTop: 0 }}>One month's rental per sale: half when every service is live, half after 6 months retained.</p>
      <div className="scroll"><table>
        <thead><tr><th>Partner</th><th>Chats started</th><th>Sales</th><th>Earned</th><th>Pending</th><th>Latest sales</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.id}>
            <td><b>{r.name}</b><div className="small muted">{r.id} · {r.cities.slice(0, 3).join(', ')}</div></td>
            <td>{r.assisted + r.referral}<div className="small muted">{r.assisted} assisted · {r.referral} counter QR</div></td>
            <td>{r.orders}{r.protected_orders ? <div className="small muted">{r.protected_orders} protected</div> : null}</td>
            <td>{inr(r.earned)}</td>
            <td>{inr(r.pending)}</td>
            <td className="small">{r.recent.map((o) => <div key={o.id}><a href={`#/track/${o.id}`}>{o.id}</a> · {VIA[o.via] || o.via} · {inr(o.commission)}</div>)}</td>
          </tr>
        ))}</tbody>
      </table></div>
    </div>
  )
}
