import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { tr } from './i18n.js'
import Icon, { DocIcon } from './Icon.jsx'

const SOURCE = { digilocker: 'DigiLocker', gst_registry: 'GST registry', aadhaar_ekyc: 'Aadhaar e-KYC', accel_kyc: 'Accel KYC', upload: 'Photo' }

// One fix for every problem: what the owner taps next, by the check that failed.
function fixFor(c, required) {
  const code = c.code
  if (code === 'gst_not_needed') return { kind: 'remove', label: 'Remove it' }
  if (code.startsWith('udyam_') && !required.includes('udyam_certificate')) return { kind: 'remove', label: 'Remove it (Udyam is optional)' }
  if (code.startsWith('gstin_') || code.startsWith('gst_')) return { kind: 'digilocker', label: 'Fetch it from DigiLocker instead' }
  if (code.startsWith('signatory_') || (code === 'missing_document' && c.doc === 'signatory_id')) return { kind: 'signatory', label: 'Verify by Aadhaar OTP instead' }
  if (code === 'authorisation_letter') return { kind: 'template', label: 'Get a ready letter template' }
  if (code === 'address_proof_old') return { kind: 'upload', label: 'Upload a bill from the last 90 days' }
  if (['unreadable', 'wrong_document', 'missing_document', 'address_name_mismatch', 'address_mismatch', 'address_proof_future'].includes(code) || code.startsWith('udyam_'))
    return { kind: 'upload', label: code === 'missing_document' ? 'Upload it' : 'Upload a new photo' }
  return null
}

export default function Kyc({ lang, session, partner, onPartner, onBack, onNext, toast }) {
  const [k, setK] = useState(null)
  const [agree, setAgree] = useState(false)
  const [wa, setWa] = useState(true)
  const [mkt, setMkt] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [otp, setOtp] = useState('')
  const [accel, setAccel] = useState(false)
  const [accelNo, setAccelNo] = useState('')
  const [samples, setSamples] = useState({})
  const [ownerPhone, setOwnerPhone] = useState('')
  const [sent, setSent] = useState(null)
  const [ownerCode, setOwnerCode] = useState('')
  const needsOwner = partner?.mode === 'assisted' && !partner.owner_verified

  useEffect(() => { api.kyc(session).then(setK).catch((e) => setError(e.message)); api.samples().then(setSamples).catch(() => {}) }, [session])

  const run = async (label, fn) => {
    setBusy(label); setError('')
    try { setK(await fn()) } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  if (!k) return <main className="page"><div className="spinner dark" /></main>

  if (!k.consent?.accepted) {
    return (
      <>
        <main className="page consent narrow">
          <h2>{tr(lang, 'consentTitle')}</h2>
          <div className="card">
            <p className="small" style={{ marginTop: 0 }}>{tr(lang, 'consentIntro')}</p>
            <ul>
              <li><b>GST and Udyam details</b>: to confirm your business is registered and active.</li>
              <li><b>Signatory name and ID</b>: to confirm who signs the agreement.</li>
              <li><b>Business address</b>: where we install the connection.</li>
            </ul>
            <p className="small"><b>What we don't do:</b> we don't keep your photos. We read the fields we need, keep a fingerprint of the file, and discard the image. We never use KYC data for marketing.</p>
            <p className="small"><b>How long:</b> verified details are kept while your connection is active and for the period telecom licence rules require, then deleted. You can withdraw consent or ask us to erase your data any time before an order is placed.</p>
            <p className="small muted" style={{ marginBottom: 0 }}>Grievance officer: privacy@accelbusiness.example · Consent version {k.consent?.version || '2026-10-v1'}</p>
          </div>
          <div className="card">
            <h3>One switch for each use</h3>
            <Purpose on={agree} set={setAgree} title={<>{tr(lang, 'agree')} <b>(required)</b></>} what="GST, Udyam, signatory ID, address · kept while connected, then deleted" />
            <Purpose on={wa} set={setWa} title={tr(lang, 'waUpdates')} what="Your mobile number, masked · used only for this order" />
            <Purpose on={mkt} set={setMkt} title={tr(lang, 'marketing')} what="Off unless you switch it on · withdraw any time" />
          </div>
          {needsOwner && (
            <div className="card owner">
              <h3>{tr(lang, 'ownerTitle')}</h3>
              <p className="small muted" style={{ marginTop: 0 }}>{tr(lang, 'ownerIntro', { name: partner.name })}</p>
              <div className="row" style={{ gap: 8 }}>
                <input className="grow" value={ownerPhone} onChange={(e) => setOwnerPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                  inputMode="tel" placeholder={tr(lang, 'mobile')} aria-label={tr(lang, 'mobile')} />
                <button className="btn small ghost" disabled={!/^[6-9]\d{9}$/.test(ownerPhone) || busy === 'code'}
                  onClick={async () => { setBusy('code'); setError(''); try { setSent(await api.ownerCode(session, ownerPhone)) } catch (e) { setError(e.message) } finally { setBusy('') } }}>
                  {busy === 'code' ? <span className="spinner dark" /> : tr(lang, sent ? 'resendCode' : 'sendCode')}
                </button>
              </div>
              {sent && (
                <>
                  <p className="small" style={{ marginBottom: 6 }}>{tr(lang, sent.delivery === 'sent' ? 'codeSent' : 'codeDemo', { phone: sent.phone_masked, code: sent.demo_code })}</p>
                  <input value={ownerCode} onChange={(e) => setOwnerCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric"
                    placeholder={tr(lang, 'ownerCode')} aria-label={tr(lang, 'ownerCode')} style={{ width: '100%' }} />
                </>
              )}
            </div>
          )}
          {error && <div className="notice">{error}</div>}
          <button className="btn ghost back" onClick={onBack}><Icon name="back" size={17} /> Back</button>
        </main>
        <div className="bottombar">
          <button className="btn" disabled={!agree || !!busy || (needsOwner && ownerCode.length !== 6)} onClick={() => run('consent', async () => {
            const r = await api.consent({ session_id: session, accepted: true, whatsapp_updates: wa, marketing: mkt, owner_code: needsOwner ? ownerCode : undefined })
            if (needsOwner) onPartner?.({ ...partner, owner_verified: true })
            return r
          })}>
            {busy ? <span className="spinner" /> : tr(lang, 'giveConsent')}
          </button>
        </div>
      </>
    )
  }

  const res = k.result
  const docsByType = k.docs || {}
  const Fix = ({ c }) => {
    const f = fixFor(c, k.required)
    if (!f) return null
    if (f.kind === 'upload') {
      return (
        <label className="fix">{f.label} →
          <input type="file" accept="image/*" capture="environment" hidden onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) run('up-' + c.doc, () => api.upload(session, c.doc, file))
            e.target.value = ''
          }} />
        </label>
      )
    }
    if (f.kind === 'template') return <a className="fix" href="/authorisation-letter.html" target="_blank" rel="noreferrer">{f.label} →</a>
    const act = {
      remove: () => run('rm-' + c.doc, () => api.removeDoc(session, c.doc)),
      digilocker: () => run('dl', () => api.digilocker(session)),
      signatory: () => document.getElementById('signatory')?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
    }[f.kind]
    return <button className="fix" disabled={!!busy} onClick={act}>{f.label} →</button>
  }
  const checksFor = (dt) => (res?.checks || []).filter((c) => c.doc === dt)

  return (
    <>
      <main className="page narrow">
        <h2>{tr(lang, 'kycTitle')}</h2>

        <div className="card">
          <div className="row between"><h3><Icon name="zap" size={16} /> {tr(lang, 'fastest')}</h3></div>
          <p className="small muted" style={{ marginTop: 0 }}>{tr(lang, 'fastestSub')}</p>
          <button className="btn dark" disabled={!!busy} onClick={() => run('dl', () => api.digilocker(session))}>{busy === 'dl' ? <span className="spinner" /> : 'Fetch from DigiLocker'}</button>
        </div>

        <div className="card" id="signatory">
          <h3>{tr(lang, 'signatory')}</h3>
          <div className="row" style={{ alignItems: 'flex-end' }}>
            <label className="field" style={{ flex: 2, marginBottom: 0 }}><span>{tr(lang, 'signName')}</span><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
            <label className="field" style={{ flex: 1, marginBottom: 0 }}><span>{tr(lang, 'otp')}</span><input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" placeholder="6 digits" /></label>
          </div>
          <label className="check" style={{ marginTop: 8 }}><input type="checkbox" checked={accel} onChange={(e) => setAccel(e.target.checked)} /> <span>I already use an Accel mobile number (no new ID needed)</span></label>
          {accel && (
            <label className="field" style={{ marginBottom: 0 }}><span>Accel mobile number</span>
              <input value={accelNo} onChange={(e) => setAccelNo(e.target.value.replace(/\D/g, '').slice(0, 10))} inputMode="tel" placeholder="10-digit Accel number" /></label>
          )}
          <button className="btn ghost" style={{ marginTop: 10 }} disabled={!!busy || name.trim().length < 2 || otp.length !== 6 || (accel && !/^[6-9]\d{9}$/.test(accelNo))}
            onClick={() => run('ekyc', () => (accel ? api.accelKyc(session, name, accelNo, otp) : api.ekyc(session, name, otp)))}>
            {busy === 'ekyc' ? <span className="spinner dark" /> : accel ? 'Reuse my Accel KYC' : tr(lang, 'sendOtp')}
          </button>
          <p className="small muted" style={{ marginBottom: 0 }}>Demo: any 6-digit OTP works.</p>
        </div>

        <div className="card">
          <h3>{tr(lang, 'orUpload')}</h3>
          {(k.all || k.required).filter((dt) => k.required.includes(dt) || docsByType[dt] || dt === 'udyam_certificate').map((dt) => {
            const d = docsByType[dt]
            const needed = k.required.includes(dt)
            const issues = checksFor(dt).filter((c) => c.status !== 'pass')
            return (
              <div key={dt} className="doc">
                <div className="ico"><DocIcon id={dt} size={19} /></div>
                <div className="meta">
                  <div><b className="small">{k.labels[dt]}</b>{' '}
                    {!needed && <span className="tag">{tr(lang, dt === 'gst_certificate' ? 'notNeeded' : 'optional')}</span>}{' '}
                    {d && <span className={'tag ' + (issues.some((c) => c.status === 'fail') ? 'bad' : res ? 'ok' : '')}>{SOURCE[d.source] || d.source}</span>}
                  </div>
                  <div className="fields">{d ? Object.values(d.fields || {}).filter(Boolean).slice(0, 3).join(' · ') || 'Could not read' : 'Not added yet'}</div>
                </div>
                <div className="acts">
                  {d && <button className="link small" disabled={!!busy} onClick={() => run('rm-' + dt, () => api.removeDoc(session, dt))}>{tr(lang, 'remove')}</button>}
                  <label className="btn sm ghost" style={{ margin: 0 }}>
                    {d ? tr(lang, 'retake') : tr(lang, 'upload')}
                    <input type="file" accept="image/*" capture="environment" hidden onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) run('up-' + dt, () => api.upload(session, dt, f))
                      e.target.value = ''
                    }} />
                  </label>
                </div>
              </div>
            )
          })}
          {busy.startsWith('up-') && <p className="small muted"><span className="spinner dark" /> Reading your document…</p>}
          {Object.keys(samples).length > 0 && (
            <details style={{ marginTop: 10 }}>
              <summary>Demo: load a specimen applicant (K01–K12)</summary>
              <p className="small muted">Runs the hackathon's specimen photos through the same OCR and checks.</p>
              <div className="samples">
                {Object.keys(samples).map((a) => <button key={a} disabled={!!busy} onClick={() => run('sample', () => api.useSample(session, a))}>{a}</button>)}
              </div>
              {busy === 'sample' && <p className="small muted"><span className="spinner dark" /> Reading 4 documents…</p>}
            </details>
          )}
        </div>

        {res && (
          <>
            <div className={'decision ' + res.decision}>
              <Icon name={res.decision === 'approved' ? 'verified' : res.decision === 'review' ? 'warn' : 'fail'} size={20} />
              {res.decision === 'approved' ? 'Verified' : res.decision === 'review' ? 'Verified, one item to note' : res.fail_count + (res.fail_count === 1 ? ' item needs fixing' : ' items need fixing')}
            </div>
            <div className="card">
              {res.checks.map((c, i) => (
                <div key={i} className={'result ' + c.status}>
                  <span className="dot"><Icon name={c.status === 'pass' ? 'ok' : c.status === 'warn' ? 'warn' : 'fail'} size={17} /></span>
                  <span>{c.message}{c.status !== 'pass' && <Fix c={c} />}</span>
                </div>
              ))}
              {res.decision === 'rejected' && <p className="small muted" style={{ marginBottom: 0 }}>{tr(lang, 'fixIssues')}</p>}
            </div>
          </>
        )}
        {error && <div className="notice">{error}</div>}
        <button className="btn ghost back" onClick={onBack}><Icon name="back" size={17} /> Back to bundle</button>
        <p className="small muted" style={{ textAlign: 'center' }}>
          <button className="link small" onClick={async () => { if (window.confirm('Delete everything you have shared so far?')) { await api.erase(session).catch(() => {}); toast('Your data has been deleted.'); window.location.reload() } }}>{tr(lang, 'erase')}</button>
        </p>
      </main>
      <div className="bottombar">
        {res && res.decision !== 'rejected'
          ? <button className="btn" onClick={onNext}>{tr(lang, 'toCheckout')}</button>
          : <button className="btn" disabled={!!busy || !Object.keys(docsByType).length} onClick={() => run('verify', () => api.verify(session))}>{busy === 'verify' ? <><span className="spinner" /> {tr(lang, 'verifying')}</> : tr(lang, 'verify')}</button>}
      </div>
    </>
  )
}

function Purpose({ on, set, title, what }) {
  return (
    <label className="purpose">
      <span><span className="t">{title}</span><span className="w">{what}</span></span>
      <input type="checkbox" role="switch" checked={on} onChange={(e) => set(e.target.checked)} />
      <i className="sw" aria-hidden />
    </label>
  )
}
