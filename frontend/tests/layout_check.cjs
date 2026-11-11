// Layout check: walk the whole buying journey in each of the 10 languages on a small phone, a tablet and a laptop,
// and report any text that spills out of its box, any screen that scrolls sideways, and any script error.
//   node layout_check.cjs <base url> [dir for screenshots]
// Needs Playwright (npm i -D playwright) and the app running with no AI key, so replies are the same every run.
const { chromium } = require('playwright')
const U = process.argv[2] || 'http://127.0.0.1:8000', S = process.argv[3]
const LANGS = ['en', 'hi', 'mr', 'kn', 'gu', 'te', 'ta', 'bn', 'pa', 'ml']
const SIZES = [['phone', { width: 360, height: 780 }], ['tablet', { width: 820, height: 1100 }], ['laptop', { width: 1440, height: 900 }]]

const findSpills = () => {
  const out = []
  const vw = document.documentElement.clientWidth
  if (document.documentElement.scrollWidth > vw + 1) out.push('page scrolls sideways by ' + (document.documentElement.scrollWidth - vw) + 'px')
  const clips = (el) => /hidden|auto|scroll|clip/.test(getComputedStyle(el).overflowX)
  for (const el of document.querySelectorAll('.shell *')) {
    if (!el.offsetParent || el.closest('svg') || el.matches('.need, .needs')) continue  // the tick badge sits on the tile's corner on purpose
    const r = el.getBoundingClientRect()
    if (!r.width || !r.height) continue
    const label = el.tagName.toLowerCase() + '.' + String(typeof el.className === 'string' ? el.className : '').trim().replace(/\s+/g, '.') + ' "' + (el.textContent || '').trim().slice(0, 30) + '"'
    if (!clips(el) && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).display !== 'inline') out.push('spills ' + (el.scrollWidth - el.clientWidth) + 'px: ' + label)
    else if (r.right > vw + 1 && !el.closest('.conv, .side')) out.push('off screen: ' + label)
  }
  return [...new Set(out)].slice(0, 6)
}

;(async () => {
  const b = await chromium.launch()
  let bad = 0, screens = 0
  const journey = async (size, vp, lang) => {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: 1, locale: 'en-IN' })
    const p = await ctx.newPage()
    const say = (m) => { bad++; console.log(`${size} [${lang}] ${m}`) }
    p.on('pageerror', (e) => say('script error: ' + e.message))
    p.on('dialog', (d) => d.dismiss())
    await p.addInitScript((l) => { try { localStorage.setItem('lang', l) } catch (e) {} }, lang)
    const bubbles = async () => p.$$eval('.bubble', (els) => els.length)
    const settle = async (n) => { await p.waitForFunction((n) => document.querySelectorAll('.bubble').length > n + 1 && !document.querySelector('.typing'), n, { timeout: 15000 }).catch(() => {}); await p.waitForTimeout(500) }
    const type = async (t) => { const n = await bubbles(); await p.fill('.composer input', t); await p.press('.composer input', 'Enter'); await settle(n) }
    const chipN = async (i) => { const n = await bubbles(); await p.click(`.chip >> nth=${i}`, { timeout: 4000 }); await settle(n) }
    const check = async (screen) => {
      await p.waitForTimeout(350)
      screens++
      const now = await p.evaluate(() => document.documentElement.lang)
      if (now !== lang) say(`${screen}: screen is in "${now}"`)
      for (const f of await p.evaluate(findSpills)) say(`${screen}: ${f}`)
      if (S && size !== 'tablet' && ['ta', 'ml', 'kn', 'bn'].includes(lang)) await p.screenshot({ path: `${S}/${size}_${lang}_${screen}.jpg`, type: 'jpeg', quality: 70 })
    }
    try {
      await p.goto(U + '/'); await p.waitForSelector('.bubble.bot'); await p.waitForTimeout(900)
      await check('01-start')
      await type('Pharmacy, Jaipur, 4 staff. GSTIN 08EAHXC5550F1ZF')
      await chipN(0); await chipN(0); await chipN(0); await chipN(0); await chipN(1)
      await p.waitForSelector('.needs', { timeout: 5000 })
      await check('02-needs')
      await p.click('.needs + .btn'); await p.waitForSelector('.levels', { timeout: 8000 }); await p.waitForTimeout(1200)
      await check('03-bundle')
      await p.click('.bundlecard > .btn'); await p.waitForSelector('.line', { timeout: 8000 }); await p.waitForTimeout(500)
      await check('04-quote')
      await p.click('.bottombar .btn'); await p.waitForSelector('.consent', { timeout: 8000 })
      await check('05-consent')
      await p.click('.purpose >> nth=0'); await p.click('.bottombar .btn'); await p.waitForTimeout(1200)
      await check('06-kyc')
      await p.click('.btn.dark'); await p.waitForTimeout(1300)
      await p.fill('#signatory input >> nth=0', 'Priya Chauhan'); await p.fill('#signatory input >> nth=1', '482913'); await p.click('#signatory .btn'); await p.waitForTimeout(1000)
      await p.click('.bottombar .btn'); await p.waitForSelector('.decision', { timeout: 30000 }); await p.waitForTimeout(400)
      await check('07-kyc-verified')
      await p.click('.bottombar .btn'); await p.waitForSelector('input[autocomplete=tel]', { timeout: 10000 }); await p.waitForTimeout(500)
      await check('08-checkout')
      const inputs = await p.$$('main input:not([type=checkbox]):visible')
      await inputs[0].fill('Priya Chauhan'); await inputs[1].fill('9876501234'); await inputs[2].fill('482913')
      for (const c of await p.$$('main input[type=checkbox]')) { if (!(await c.isChecked())) await c.check() }
      await p.click('.bottombar .btn'); await p.waitForSelector('.timeline', { timeout: 10000 }); await p.waitForTimeout(700)
      const nx = async () => { await p.click('.demo .btn'); await p.waitForTimeout(700) }
      await nx(); await nx()
      await check('09-tracker-slot')
      await p.click('.slots button >> nth=1'); await p.click('.slots ~ .btn'); await p.waitForTimeout(800)
      await nx(); await nx(); await nx(); await nx()
      await check('10-tracker-live')
    } catch (e) { say('journey stopped: ' + e.message.split('\n')[0]) }
    await ctx.close()
  }
  await Promise.all(SIZES.map(async ([size, vp]) => { for (const l of LANGS) await journey(size, vp, l) }))
  await b.close()
  console.log(bad ? `FAIL: ${bad} problems on ${screens} screens` : `OK: ${screens} screens (10 languages x 3 screen sizes x 10 steps), no text spills, no sideways scroll, no script errors`)
  process.exit(bad ? 1 : 0)
})()
