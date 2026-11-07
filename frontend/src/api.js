async function call(method, url, body, isForm = false) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    if (isForm) opts.body = body
    else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  let res = await fetch(url, opts)
  for (let i = 0; i < 3 && (res.status === 502 || res.status === 503); i++) {
    // the server is restarting for an update (nginx answers, the app doesn't yet): the request never reached it
    await new Promise((r) => setTimeout(r, 2000))
    res = await fetch(url, opts)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(', ') : data.detail
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return data
}

export const api = {
  config: () => call('GET', '/api/config'),
  start: (lang) => call('POST', '/api/advisor/start', { lang, source: 'web', ref: referral() }),
  assistStart: (partner_id, lang) => call('POST', '/api/assist/start', { partner_id, lang }),
  ownerCode: (session_id, phone) => call('POST', '/api/assist/owner-code', { session_id, phone }),
  partners: () => call('GET', '/api/partners'),
  consolePartners: () => call('GET', '/api/console/partners'),
  message: (body) => call('POST', '/api/advisor/message', body),
  resume: (sid) => call('GET', `/api/advisor/${encodeURIComponent(sid)}`),
  setLang: (sid, lang) => call('POST', `/api/advisor/${sid}/language/${lang}`),
  quote: (session_id, selection, contract_months) => call('POST', '/api/quote', { session_id, selection, contract_months }),
  consent: (body) => call('POST', '/api/kyc/consent', body),
  upload: (session_id, doc_type, file) => {
    const f = new FormData()
    f.append('session_id', session_id)
    f.append('doc_type', doc_type)
    f.append('file', file)
    return call('POST', '/api/kyc/upload', f, true)
  },
  samples: () => call('GET', '/api/kyc/samples'),
  useSample: (session_id, applicant) => call('POST', '/api/kyc/sample', { session_id, applicant }),
  digilocker: (sid) => call('POST', `/api/kyc/digilocker/${sid}`),
  ekyc: (session_id, name, otp) => call('POST', '/api/kyc/ekyc', { session_id, name, otp }),
  accelKyc: (session_id, name, mobile, otp) => call('POST', '/api/kyc/accel', { session_id, name, mobile, otp }),
  verify: (sid) => call('POST', `/api/kyc/verify/${sid}`),
  removeDoc: (session_id, doc_type) => call('POST', '/api/kyc/remove', { session_id, doc_type }),
  kyc: (sid) => call('GET', `/api/kyc/${sid}`),
  order: (body) => call('POST', '/api/orders', body),
  getOrder: (id) => call('GET', `/api/orders/${encodeURIComponent(id)}`),
  advance: (id) => call('POST', `/api/orders/${id}/advance`),
  slot: (id, slot) => call('POST', `/api/orders/${id}/slot`, { slot }),
  ticket: (id, text) => call('POST', `/api/orders/${id}/ticket`, { text }),
  erase: (sid) => call('POST', `/api/privacy/erase/${sid}`),
  consoleLeads: () => call('GET', '/api/console/leads'),
  consoleModel: () => call('GET', '/api/console/model'),
  consoleOverview: () => call('GET', '/api/console/overview'),
  consoleAudit: () => call('GET', '/api/console/audit'),
}

// A partner's shop QR opens the app with ?ref=PT01. The code is kept for 30 days on this phone, so a chat started
// later still credits that partner.
const REF_DAYS = 30
export function rememberReferral() {
  const m = window.location.search.match(/[?&]ref=(PT\d{2})\b/i)
  if (!m) return
  try { localStorage.setItem('ref', JSON.stringify({ id: m[1].toUpperCase(), at: Date.now() })) } catch { /* private mode */ }
  window.history.replaceState(null, '', window.location.pathname + window.location.hash)
}
function referral() {
  try {
    const r = JSON.parse(localStorage.getItem('ref') || 'null')
    return r && Date.now() - r.at < REF_DAYS * 864e5 ? r.id : undefined
  } catch { return undefined }
}

export const inr = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN')
