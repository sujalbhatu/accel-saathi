// Screens for slides 3 and 4 (3 Nov build): Priya taps her problems, the "why" panel quotes them, then KYC, tracker, one bill.
// A second chat shows the price objection. Run against a local server: node shoot_en3.js <out dir> [base url]
const { chromium } = require('playwright')
const S = process.argv[2] || __dirname + '/s4'
const U = process.argv[3] || 'http://localhost:8031'

;(async () => {
  const b = await chromium.launch()
  const mk = async () => {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'en-IN' })
    const p = await ctx.newPage()
    p.on('pageerror', (e) => console.log('pageerror', e.message))
    p.on('dialog', (d) => d.dismiss())
    return p
  }
  const kit = (p) => {
    const bubbles = async () => p.$$eval('.bubble', (els) => els.map((e) => e.textContent))
    const settle = async (n) => {
      await p.waitForFunction((n) => document.querySelectorAll('.bubble').length > n + 1 && !document.querySelector('.typing'), n, { timeout: 15000 }).catch(() => {})
      await p.waitForTimeout(900)
    }
    return {
      type: async (t) => { const n = (await bubbles()).length; await p.fill('.composer input', t); await p.press('.composer input', 'Enter'); await settle(n) },
      chip: async (label) => { const n = (await bubbles()).length; await p.click(`.chip:has-text("${label}")`, { timeout: 4000 }); await settle(n) },
      shot: async (name) => { await p.waitForTimeout(500); await p.screenshot({ path: `${S}/${name}.png` }) },
      top: async (sel, off = 70, i = 0) => {
        await p.evaluate(([s, o, i]) => {
          const all = document.querySelectorAll(s)
          const el = all[i < 0 ? all.length + i : i]
          window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o)
        }, [sel, off, i])
        await p.waitForTimeout(400)
      },
    }
  }

  // Priya's journey
  const p = await mk()
  const k = kit(p)
  await p.goto(U + '/')
  await p.waitForSelector('.bubble.bot')
  await p.waitForTimeout(1500)
  await k.type('I run a pharmacy in Jaipur, we are 4 people. GSTIN 08EAHXC5550F1ZF')
  await k.shot('02_gstin')
  await k.chip("Yes, that's mine")
  await k.chip('1')
  await k.chip('hotspot')
  await k.chip('UPI fails')
  await k.chip('Theft')
  await k.top('.bubble.bot', 60, -3)
  await k.shot('03_pains')
  await p.click('.needs + .btn')
  await p.waitForTimeout(2500)
  await p.click('details.why > summary')
  await p.waitForTimeout(500)
  await k.top('.card .levels', 70)
  await k.shot('04_why')
  await p.click('.card .btn:has-text("rice")')
  await p.waitForSelector('.line', { timeout: 8000 })
  await p.waitForTimeout(800)
  await k.shot('05_quote')
  await p.click('.bottombar .btn')
  await p.waitForSelector('.consent', { timeout: 8000 })
  await p.click('.purpose >> nth=0')
  await p.click('.bottombar .btn')
  await p.waitForTimeout(1500)
  await p.click('.btn.dark')
  await p.waitForTimeout(1500)
  await p.fill('#signatory input >> nth=0', 'Priya Chauhan')
  await p.fill('#signatory input >> nth=1', '482913')
  await p.click('#signatory .btn')
  await p.waitForTimeout(1200)
  await p.click('.bottombar .btn')
  await p.waitForSelector('.decision', { timeout: 30000 })
  await p.waitForTimeout(600)
  await k.top('.decision', 330)
  await k.shot('07_kyc')
  await p.click('.bottombar .btn')
  await p.waitForSelector('input[autocomplete=tel]', { timeout: 10000 })
  await p.waitForTimeout(800)
  const inputs = await p.$$('main input:not([type=checkbox]):visible')
  await inputs[0].fill('Priya Chauhan')
  await inputs[1].fill('9876501234')
  await inputs[2].fill('482913')
  for (const c of await p.$$('main input[type=checkbox]')) { if (!(await c.isChecked())) await c.check() }
  await p.click('.bottombar .btn')
  await p.waitForSelector('.timeline', { timeout: 10000 })
  await p.waitForTimeout(1000)
  const nx = async () => { await p.click('.demo .btn'); await p.waitForTimeout(900) }
  await nx()
  await nx()
  await k.top('.slots', 120)
  await p.click('.slots button >> nth=1')
  await p.click('.slots ~ .btn')
  await p.waitForTimeout(1000)
  await nx()
  await nx()
  await nx()
  await nx()
  await p.evaluate(() => window.scrollTo(0, 0))
  await k.shot('11_tracker_live')
  await p.addStyleTag({ content: '.dlv.demo{display:none!important}' })
  await k.top('.onebill', 90)
  await k.shot('12_onebill')
  console.log('order', await p.evaluate(() => location.hash))

  // A price objection, a competitor and a "let me think" on a kirana bundle
  const q = await mk()
  const k2 = kit(q)
  await q.goto(U + '/')
  await q.waitForSelector('.bubble.bot')
  await q.waitForTimeout(1200)
  await k2.type('I run a kirana store in Jaipur with 3 staff, one shop')
  await k2.chip('No GSTIN')
  await k2.chip('hotspot')
  await q.click('.needs + .btn')
  await q.waitForTimeout(2500)
  await k2.type('this is too expensive for me')
  await k2.top('.bubble.me', 20, -1)
  await k2.shot('20_price')
  await k2.type('my nephew set up Jio for 399, why should I pay you?')
  await k2.top('.bubble.me', 20, -1)
  await k2.shot('21_competitor')
  await k2.type("let me think about it, I'll come back later")
  await k2.top('.bubble.me', 20, -1)
  await k2.shot('22_think')
  await b.close()
})()
