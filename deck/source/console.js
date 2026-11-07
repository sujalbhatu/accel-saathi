const { chromium } = require('playwright');
const S = __dirname + '/s2', U = 'http://localhost:8031';
const j = (u, b) => fetch(U + u, { method: b ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }).then(r => r.json());
async function apiOrder(sid, phone, consent = true) {
  if (consent) await j('/api/kyc/consent', { session_id: sid, accepted: true })
  const post = (b) => j('/api/advisor/message', { session_id: sid, ...b });
  let r = await post({ text: 'Pharmacy in Jaipur, 4 people, GSTIN 08EAHXC5550F1ZF' });
  r = await post({ slot: r.chips[0].slot, value: r.chips[0].value });
  for (let i = 0; i < 6 && !r.recommendation; i++) r = r.needs ? await post({ needs: r.needs.filter(n => n.selected).map(n => n.key) }) : await post({ slot: r.chips[0].slot, value: r.chips[0].value });
  await j(`/api/kyc/digilocker/${sid}`, {}); await j('/api/kyc/ekyc', { session_id: sid, name: 'Priya Chauhan', otp: '123456' }); await j(`/api/kyc/verify/${sid}`, {});
  const q = r.recommendation.quote;
  return j('/api/orders', { session_id: sid, selection: q.lines.map(l => ({ id: l.id, qty: l.qty })), contract_months: 12, contact_name: 'Priya Chauhan', phone, whatsapp_updates: true, esign_otp: '123456' });
}
(async () => {
  const a = await j('/api/assist/start', { partner_id: 'PT03', lang: 'hi' });
  const c = await j('/api/assist/owner-code', { session_id: a.session_id, phone: '9876504444' });
  await j('/api/kyc/consent', { session_id: a.session_id, accepted: true, owner_code: c.demo_code });
  const o1 = await apiOrder(a.session_id, '9876504444', false); console.log(o1.id, o1.partner)
  for (let i = 0; i < 6; i++) await j(`/api/orders/${o1.id}/advance`, {})
  const s2 = await j('/api/advisor/start', { lang: 'en' }); const o2 = await apiOrder(s2.session_id, '9876504444'); console.log(o2.id, o2.partner)
  const s3 = await j('/api/advisor/start', { lang: 'en', ref: 'PT01' }); const o3 = await apiOrder(s3.session_id, '9876505555'); console.log(o3.id, o3.partner)
  const b = await chromium.launch(); const d = await b.newContext({ viewport: { width: 1280, height: 760 }, deviceScaleFactor: 2 }); const q = await d.newPage();
  await q.goto(U + '/#/console'); await q.waitForTimeout(2500);
  await q.selectOption('.card select >> nth=0', 'PT03'); await q.selectOption('.card select >> nth=1', 'hi');
  await q.click('text=Start assisted chat'); await q.waitForTimeout(1500);
  await q.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => x.textContent === 'Assisted mode'); window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 24) }); await q.waitForTimeout(500);
  await q.screenshot({ path: S + '/30_console_partner.png' });
  await q.evaluate(() => window.scrollTo(0, 0)); await q.waitForTimeout(300); await q.screenshot({ path: S + '/31_console_top.png' });
  await b.close();
})();
