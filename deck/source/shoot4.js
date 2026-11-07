const { chromium } = require('playwright');
const S = __dirname + '/s2', U = 'http://localhost:8031';
const j = (u, b) => fetch(U + u, { method: b ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }).then(r => r.json());
async function apiOrder(sid, phone) {
  const post = (b) => j('/api/advisor/message', { session_id: sid, ...b });
  let r = await post({ text: 'Pharmacy in Jaipur, 4 people, GSTIN 08EAHXC5550F1ZF' });
  r = await post({ slot: r.chips[0].slot, value: r.chips[0].value });
  for (let i = 0; i < 6 && !r.recommendation; i++) r = r.needs ? await post({ needs: r.needs.filter(n => n.selected).map(n => n.key) }) : await post({ slot: r.chips[0].slot, value: r.chips[0].value });
  await j(`/api/kyc/digilocker/${sid}`, {}); await j('/api/kyc/ekyc', { session_id: sid, name: 'Owner Name', otp: '123456' }); await j(`/api/kyc/verify/${sid}`, {});
  const q = r.recommendation.quote;
  return j('/api/orders', { session_id: sid, selection: q.lines.map(l => ({ id: l.id, qty: l.qty })), contract_months: 12, contact_name: 'Owner Name', phone, whatsapp_updates: true, esign_otp: '123456' });
}
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'en-IN' });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.dismiss());
  const shot = async (name) => { await p.waitForTimeout(500); await p.screenshot({ path: `${S}/${name}.png` }); };
  const n = async () => p.$$eval('.wa-msg', e => e.length);
  const wait = async (k) => { await p.waitForFunction(k => document.querySelectorAll('.wa-msg').length > k + 1 && !document.querySelector('.wa-typing'), k, { timeout: 15000 }).catch(() => {}); await p.waitForTimeout(900) };
  const say = async (t) => { const k = await n(); await p.fill('.wa-input input', t); await p.press('.wa-input input', 'Enter'); await wait(k) };
  const tap = async (t) => { const k = await n(); await p.click(`.wa-btn:has-text("${t}") >> nth=-1`); await wait(k) };
  const top = async (sel, off = 70, i = 0) => { await p.evaluate(([s, o, i]) => { const all = document.querySelectorAll(s); const el = all[i < 0 ? all.length + i : i]; window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o) }, [sel, off, i]); await p.waitForTimeout(400) };
  // A. WhatsApp to bundle
  await p.goto(U + '/#/whatsapp'); await p.waitForTimeout(1500);
  await say('नमस्ते, जयपुर में मेरी दवाइयों की दुकान है, 4 लोग। GSTIN 08EAHXC5550F1ZF');
  await shot('20_wa_start');
  await tap('हाँ, यह मेरा है'); await say('1'); await say('फोन हॉटस्पॉट'); await tap('आगे बढ़ें');
  await shot('21_wa_bundle');
  const link = await p.$eval('a.wa-btn', a => a.getAttribute('href'));
  // continue in the app and buy
  await p.goto(U + '/' + link); await p.waitForSelector('.bubble.bot'); await p.waitForTimeout(1500);
  await shot('22_app_continue');
  await p.click('.card .btn:has-text("कीमत")'); await p.waitForSelector('.line', { timeout: 8000 }); await p.waitForTimeout(600);
  await p.click('.bottombar .btn'); await p.waitForSelector('.consent', { timeout: 8000 });
  await p.click('.purpose >> nth=0'); await p.click('.bottombar .btn'); await p.waitForTimeout(1500);
  await p.click('.btn.dark'); await p.waitForTimeout(1500);
  await p.fill('#signatory input >> nth=0', 'Priya Chauhan'); await p.fill('#signatory input >> nth=1', '482913');
  await p.click('#signatory .btn'); await p.waitForTimeout(1200);
  await p.click('.bottombar .btn'); await p.waitForSelector('.decision', { timeout: 30000 }); await p.waitForTimeout(600);
  await top('.decision', 300); await shot('23_kyc_verified');
  await p.click('.bottombar .btn'); await p.waitForSelector('input[autocomplete=tel]', { timeout: 10000 }); await p.waitForTimeout(800);
  const inputs = await p.$$('main input:not([type=checkbox]):visible');
  await inputs[0].fill('Priya Chauhan'); await inputs[1].fill('9876501234'); await inputs[2].fill('482913');
  for (const c of await p.$$('main input[type=checkbox]')) { if (!(await c.isChecked())) await c.check() }
  await p.click('.bottombar .btn'); await p.waitForSelector('.timeline', { timeout: 10000 }); await p.waitForTimeout(1000);
  const nx = async () => { await p.click('.demo .btn'); await p.waitForTimeout(900) };
  await nx(); await nx();
  const track = await p.evaluate(() => location.hash);
  // back to WhatsApp: status and reschedule
  await p.goto(U + '/#/whatsapp'); await p.waitForTimeout(1500);
  await say('मेरा ऑर्डर कहाँ तक पहुँचा?'); await shot('24_wa_status');
  const btns = await p.$$eval('.wa-btn', bs => bs.map(b => b.textContent).slice(-4)); console.log('wa btns', btns);
  await say('RESCHEDULE'); await shot('25_wa_resched');
  // B. tracker to live
  await p.goto(U + '/' + track); await p.waitForSelector('.timeline'); await p.waitForTimeout(1000);
  for (let i = 0; i < 8; i++) { const dis = await p.$eval('.demo .btn', b => b.disabled); if (dis) break; await nx() }
  await p.evaluate(() => window.scrollTo(0, 0)); await shot('11_tracker_live');
  await top('.onebill', 90); await shot('12_onebill');
  // C. partner data + console
  const a = await j('/api/assist/start', { partner_id: 'PT03', lang: 'hi' });
  const c = await j('/api/assist/owner-code', { session_id: a.session_id, phone: '9876502222' });
  await j('/api/kyc/consent', { session_id: a.session_id, accepted: true, owner_code: c.demo_code });
  await apiOrder(a.session_id, '9876502222');
  const s2 = await j('/api/advisor/start', { lang: 'en' }); await apiOrder(s2.session_id, '9876502222'); // protected
  const s3 = await j('/api/advisor/start', { lang: 'en', ref: 'PT01' }); await j('/api/kyc/consent', { session_id: s3.session_id, accepted: true }); await apiOrder(s3.session_id, '9876503333');
  const d = await b.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2 }); const q = await d.newPage();
  await q.goto(U + '/#/console'); await q.waitForTimeout(2500);
  await q.selectOption('.card select >> nth=0', 'PT03'); await q.selectOption('.card select >> nth=1', 'hi');
  await q.click('text=Start assisted chat'); await q.waitForTimeout(1500);
  await q.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => x.textContent === 'Assisted mode'); window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 30) }); await q.waitForTimeout(500);
  await q.screenshot({ path: S + '/30_console_partner.png' });
  await q.evaluate(() => window.scrollTo(0, 0)); await q.waitForTimeout(300); await q.screenshot({ path: S + '/31_console_top.png' });
  console.log('errors', errs); await b.close();
})();
