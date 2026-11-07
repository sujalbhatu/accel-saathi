const { chromium } = require('playwright');
const S = __dirname + '/s2', U = 'http://localhost:8031';
const j = (u, b) => fetch(U + u, { method: b ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }).then(r => r.json());
(async () => {
  const o = await j('/api/orders/ABA3BCD2E8'); console.log(o.stage, o.slots?.[0])
  if (o.slots?.length) await j('/api/orders/ABA3BCD2E8/slot', { slot: o.slots[0] })
  for (let i = 0; i < 4; i++) { const r = await j('/api/orders/ABA3BCD2E8/advance', {}); console.log(r.stage || r.detail) }
  const b = await chromium.launch(); const d = await b.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2 }); const q = await d.newPage();
  await q.goto(U + '/#/console'); await q.waitForTimeout(2500);
  await q.selectOption('.card select >> nth=0', 'PT03'); await q.selectOption('.card select >> nth=1', 'hi');
  await q.click('text=Start assisted chat'); await q.waitForTimeout(1500);
  await q.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => x.textContent === 'Assisted mode'); window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 24) }); await q.waitForTimeout(500);
  await q.screenshot({ path: S + '/30_console_partner.png' });
  await b.close();
})();
