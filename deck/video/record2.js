// Records the demo for video v2 as sharp 2x frames (780 x 1688 for the phone), with beat marks:
//   node record2.js <out dir> [base url]
// Each recording goes to <out>/<name>/NNNNN.jpg + index.json ([[epoch seconds, file], ...]). Beat marks and taps
// (epoch seconds) go to <out>/marks.json. Recordings: priya (the whole story), k06 (a tampered certificate caught),
// hi and ta (the same advisor in Hindi and Tamil), chain (5 restaurants, each outlet set up for its size),
// console (the partner console, desktop).
const { chromium } = require('playwright')
const fs = require('fs')
const OUT = process.argv[2]
const U = process.argv[3] || 'http://localhost:8031'
const marks = {}
const taps = []
const rects = {}
// finds the last element matching a selector whose text includes a phrase
const BYTEXT = (a) => [...document.querySelectorAll(a[0])].reverse().find((e) => e.textContent.includes(a[1]))
const now = () => Date.now() / 1000

const HIDE = '.demo,.dlv.demo{display:none!important} main > p.small.muted:last-of-type{visibility:hidden} *{scroll-behavior:smooth}'
function ripple() {  // a tap shows as a soft red ring, so viewers see what was touched
  addEventListener('pointerdown', (e) => {
    const d = document.createElement('div')
    d.style.cssText = `position:fixed;left:${e.clientX - 24}px;top:${e.clientY - 24}px;width:48px;height:48px;border-radius:50%;` +
      'background:rgba(226,62,87,.28);border:2px solid rgba(226,62,87,.85);pointer-events:none;z-index:99999;' +
      'transform:scale(.35);opacity:1;transition:transform .5s ease-out,opacity .5s ease-out'
    document.documentElement.appendChild(d)
    requestAnimationFrame(() => requestAnimationFrame(() => { d.style.transform = 'scale(1.5)'; d.style.opacity = '0' }))
    setTimeout(() => d.remove(), 700)
  }, true)
}

async function capture(ctx, page, name, max) {
  const dir = `${OUT}/${name}`
  fs.mkdirSync(dir, { recursive: true })
  const cdp = await ctx.newCDPSession(page)
  const idx = []
  let n = 0
  cdp.on('Page.screencastFrame', (f) => {
    const file = String(n++).padStart(5, '0') + '.jpg'
    fs.writeFileSync(`${dir}/${file}`, Buffer.from(f.data, 'base64'))
    idx.push([f.metadata.timestamp, file])
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {})
  })
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: max[0], maxHeight: max[1], everyNthFrame: 1 })
  return async () => {
    await page.waitForTimeout(300)
    await cdp.send('Page.stopScreencast').catch(() => {})
    fs.writeFileSync(`${dir}/index.json`, JSON.stringify(idx))
  }
}

function kit(p, name) {
  const mark = (k) => { marks[`${name}:${k}`] = now() }
  const bubbles = () => p.$$eval('.bubble', (els) => els.length)
  const settle = async (n) => {
    await p.waitForFunction((n) => document.querySelectorAll('.bubble').length > n + 1 && !document.querySelector('.typing'), n, { timeout: 15000 }).catch(() => {})
    await p.waitForTimeout(300)
  }
  const bottom = () => p.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  const tap = async (sel, opts = {}) => {
    await p.hover(sel, { timeout: 6000 }).catch(() => {})
    await p.waitForTimeout(opts.aim ?? 350)
    // where the finger lands (CSS pixels in the viewport), so the editor can punch in on it
    const bb = await p.locator(sel).first().boundingBox().catch(() => null)
    taps.push([name, now(), bb ? bb.x + bb.width / 2 : null, bb ? bb.y + bb.height / 2 : null, 'tap'])
    await p.click(sel, { timeout: 8000 })
  }
  // where something is on screen right now (CSS pixels), so the editor can show it magnified next to the phone
  const rect = async (key, fn, arg = null) => {
    const r = await p.evaluate(([src, arg]) => {
      let els = (new Function('return ' + src))()(arg)
      els = (Array.isArray(els) ? els : [els]).filter(Boolean)
      if (!els.length) return null
      const rs = els.map((e) => e.getBoundingClientRect())
      const x = Math.min(...rs.map((r) => r.left)), y = Math.min(...rs.map((r) => r.top))
      return { x, y, w: Math.max(...rs.map((r) => r.right)) - x, h: Math.max(...rs.map((r) => r.bottom)) - y, sy: window.scrollY }
    }, [fn.toString(), arg])
    if (r) rects[`${name}:${key}`] = { t: now(), ...r }
    else console.log('no rect', name, key)
  }
  return {
    p, mark, tap, bottom, rect,
    wait: (ms) => p.waitForTimeout(ms),
    type: async (t, hold = 1500, delay = 40) => {
      const n = await bubbles()
      await p.click('.composer input')
      await p.type('.composer input', t, { delay })
      await p.waitForTimeout(250)
      taps.push([name, now(), null, null, 'type'])
      await p.press('.composer input', 'Enter')
      await settle(n)
      await bottom()
      await p.waitForTimeout(hold)
    },
    chip: async (label, hold = 1200) => {
      const n = await bubbles()
      await tap(`.chip:has-text("${label}")`)
      await settle(n)
      await bottom()
      await p.waitForTimeout(hold)
    },
    scrollTo: async (sel, off = 70, i = 0, ms = 900) => {
      await p.evaluate(([s, o, i]) => {
        const all = document.querySelectorAll(s)
        const el = all[i < 0 ? all.length + i : i]
        if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o)
      }, [sel, off, i])
      await p.waitForTimeout(ms)
    },
  }
}

;(async () => {
  const phone = await chromium.launch({ args: ['--force-device-scale-factor=2'] })
  const only = (process.env.ONLY || '').split(',').filter(Boolean)
  const record = async (name, fn, { lang } = {}) => {
    if (only.length && !only.includes(name)) return
    const ctx = await phone.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'en-IN', hasTouch: false })
    await ctx.addInitScript(ripple)
    await ctx.addInitScript((css) => document.addEventListener('DOMContentLoaded', () => {
      const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s)
    }), HIDE)
    const p = await ctx.newPage()
    p.on('dialog', (d) => d.dismiss())
    await p.goto(U + '/')
    await p.waitForSelector('.bubble.bot')
    if (lang) {
      await p.selectOption('header select', lang)
      await p.waitForTimeout(1200)
    }
    const stop = await capture(ctx, p, name, [780, 1688])
    await p.waitForTimeout(600)
    await fn(kit(p, name))
    await stop()
    await ctx.close()
  }

  // ---------- Priya, start to finish ----------
  await record('priya', async (k) => {
    const { p } = k
    k.mark('home')
    await k.wait(1500)
    k.mark('problem')
    await k.type('I run a pharmacy in Jaipur, we are 4 people. UPI fails at rush hour and we had a theft last month.', 2200)
    await k.rect('noted', BYTEXT, ['.bubble.bot', 'Noted:'])
    k.mark('gstin')
    await k.type('GSTIN 08EAHXC5550F1ZF', 1800)
    await k.rect('registry', BYTEXT, ['.bubble.bot', 'GST registry'])
    await k.chip("Yes, that's mine", 900)
    await k.chip('1', 700)
    await k.chip('hotspot', 900)
    k.mark('needs')
    await k.scrollTo('.needs', 150, 0, 1200)
    await k.rect('ticks', () => [...document.querySelectorAll('.need.on')])
    await k.wait(2600)
    k.mark('why')
    await k.tap('.needs + .btn')
    await k.wait(1400)
    await k.scrollTo('.card .levels', 90, 0, 1200)
    await k.tap('details.why > summary')
    await k.wait(1200)
    await k.scrollTo('details.why', 60, 0, 1200)
    await k.rect('why', () => document.querySelector('details.why'))
    await k.wait(3500)
    k.mark('objection')
    await k.type('this is too expensive', 500)
    await k.scrollTo('.bubble.me', 20, -1, 900)
    await k.rect('choices', () => [...document.querySelectorAll('.bubble.bot')].filter((e) => /every rupee counts|Take out the extras/.test(e.textContent)).slice(-2))
    await k.wait(4200)
    k.mark('recommend')
    await k.type('which one do you recommend and why?', 500)
    await k.scrollTo('.bubble.me', 20, -1, 900)
    await k.rect('reasons', BYTEXT, ['.bubble.bot', 'fixes what you told me'])
    await k.wait(4200)
    await k.bottom()
    await k.wait(800)
    k.mark('goahead')
    await k.chip('Go ahead', 600).catch(async () => { await k.tap('.chip:has-text("Go ahead")') })
    await p.waitForSelector('.line', { timeout: 10000 })
    k.mark('quote')
    await k.wait(1800)
    await p.mouse.wheel(0, 520)
    await k.wait(1800)
    k.mark('kyc')
    await k.tap('.bottombar .btn')
    await p.waitForSelector('.consent', { timeout: 8000 })
    await k.scrollTo('.purpose', 160, 0, 900)
    await k.wait(1200)
    await k.tap('.purpose >> nth=0')
    await k.wait(500)
    await k.tap('.bottombar .btn')
    await k.wait(1200)
    k.mark('digilocker')
    await k.tap('.btn.dark')
    await k.wait(1500)
    await p.fill('#signatory input >> nth=0', 'Priya Chauhan')
    await p.type('#signatory input >> nth=1', '482913', { delay: 80 })
    await k.tap('#signatory .btn')
    await k.wait(1200)
    await k.tap('.bottombar .btn')
    await p.waitForSelector('.decision', { timeout: 30000 })
    await k.wait(300)
    await k.scrollTo('.decision', 330, 0, 900)
    k.mark('verified')
    await k.rect('verified', () => [document.querySelector('.decision'), document.querySelector('.decision + .card')])
    await k.wait(3000)
    k.mark('checkout')
    await k.tap('.bottombar .btn')
    await p.waitForSelector('input[autocomplete=tel]', { timeout: 10000 })
    const inputs = await p.$$('main input:not([type=checkbox]):visible')
    await inputs[0].fill('Priya Chauhan')
    await inputs[1].fill('9876501234')
    await inputs[2].fill('482913')
    for (const c of await p.$$('main input[type=checkbox]')) { if (!(await c.isChecked())) await c.check() }
    await k.wait(600)
    await k.tap('.bottombar .btn')
    await p.waitForSelector('.timeline', { timeout: 10000 })
    const nx = async (ms = 700) => { await p.evaluate(() => document.querySelector('.demo .btn')?.click()); await p.waitForTimeout(ms) }
    await nx(300); await nx(300)
    k.mark('tracker')
    await k.wait(1200)
    await k.scrollTo('.slots', 170, 0, 1000)
    await k.rect('slots', () => document.querySelector('.slots').closest('.card'))
    await k.wait(900)
    await k.tap('.slots button >> nth=1')
    await k.wait(600)
    await k.tap('.slots ~ .btn')
    await k.wait(1400)
    await p.evaluate(() => window.scrollTo(0, 0))
    await k.wait(1600)
    await p.mouse.wheel(0, 420)
    await k.wait(1600)
    k.mark('updates')
    await nx(500); await nx(500)
    await k.scrollTo('.wa', 140, 0, 1000)
    await k.rect('update', () => [...document.querySelectorAll('.wa')].slice(0, 2))
    await k.wait(3500)
    k.mark('live')
    await nx(250); await nx(250); await nx(250); await nx(600)
    await p.evaluate(() => window.scrollTo(0, 0))
    await k.wait(1500)
    await k.rect('livecard', () => document.querySelector('main .card'))
    k.mark('livetop')
    await k.wait(1000)
    await k.scrollTo('.wa', 140, 0, 1000)
    await k.rect('liveupdate', () => document.querySelector('.wa'))
    k.mark('liveupdates')
    await k.wait(2500)
    k.mark('end')
  })

  // ---------- a tampered certificate is caught ----------
  await record('k06', async (k) => {
    const { p } = k
    await k.type('I run a unisex salon in Jaipur, 5 people, one shop, phone hotspot. GSTIN 08YKZXS5189L1ZO', 300, 0)
    await k.chip("Yes, that's mine", 300).catch(() => {})
    for (let i = 0; i < 4 && !(await p.$('.needs + .btn')); i++) {
      const c = await p.$('.chip')
      if (!c) break
      await c.click(); await p.waitForTimeout(500)
    }
    await p.click('.needs + .btn').catch(() => {})
    await p.waitForTimeout(900)
    await p.click('.chip:has-text("Go ahead")').catch(() => {})
    await p.waitForSelector('.line', { timeout: 10000 })
    await p.click('.bottombar .btn')
    await p.waitForSelector('.consent', { timeout: 8000 })
    await p.click('.purpose >> nth=0')
    await p.waitForTimeout(300)
    await p.click('.bottombar .btn')
    await p.waitForTimeout(1200)
    await k.scrollTo('details', 200, -1, 600)
    k.mark('start')
    await k.tap('details > summary >> nth=-1')
    await k.wait(700)
    await k.tap('.samples button:has-text("K06")')
    await p.waitForFunction(() => !document.querySelector('.samples button[disabled]'), null, { timeout: 240000 })
    k.mark('loaded')
    await k.wait(400)
    await k.tap('.bottombar .btn')
    await p.waitForSelector('.decision', { timeout: 120000 })
    k.mark('decision')
    await k.scrollTo('.decision', 220, 0, 900)
    await k.rect('fail', () => [document.querySelector('.decision'), document.querySelector('.result.fail')])
    await k.wait(3500)
    k.mark('end')
  })

  // ---------- the same advisor in Hindi and Tamil ----------
  await record('hi', async (k) => {
    await k.rect('mic', () => document.querySelector('.composer button[title="Speak"]'))
    k.mark('start')
    await k.type('जयपुर में मेरी दवा की दुकान है, हम 4 लोग हैं', 1300)
    await k.chip('1', 1800)
    k.mark('end')
  }, { lang: 'hi' })
  await record('ta', async (k) => {
    k.mark('start')
    await k.type('சென்னையில் எனக்கு ஒரு மளிகைக் கடை இருக்கிறது, 3 பேர்', 1300)
    await k.chip('1', 1800)
    k.mark('end')
  }, { lang: 'ta' })

  // ---------- a restaurant chain: each outlet set up for its size, on one bill ----------
  await record('chain', async (k) => {
    const { p } = k
    await k.type('We run 5 restaurants in Jaipur, about 60 staff, GST registered, on local broadband today.', 300, 0)
    await k.chip('Skip for now', 300).catch(() => {})
    await p.waitForSelector('.needs + .btn', { timeout: 8000 })
    await p.click('.needs + .btn')
    await p.waitForTimeout(1500)
    await k.bottom()
    await k.scrollTo('.bubble.bot', 20, -4, 900)
    k.mark('start')
    await k.wait(1400)
    await k.type('Can each outlet have its own setup? Two are small.', 2800)
    await k.chip('Lighter for 2', 700)
    await k.scrollTo('.bubble.me', 20, -1, 700)
    await k.rect('outlets', () => [...document.querySelectorAll('.bubble.bot')].filter((e) => /Done: a lighter|Main outlets/.test(e.textContent)).slice(-2))
    await k.wait(2800)
    k.mark('end')
  })
  await phone.close()

  // ---------- the partner console: one sharp full-page shot; the editor pans across it ----------
  if (!only.length || only.includes('console')) {
    const desk = await chromium.launch({ args: ['--force-device-scale-factor=2'] })
    const ctx = await desk.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
    const p = await ctx.newPage()
    await p.goto(U + '/#/console')
    await p.waitForSelector('table tbody tr', { timeout: 15000 })
    await p.waitForTimeout(2500)
    await p.screenshot({ path: `${OUT}/console.png`, fullPage: true })
    const k = kit(p, 'console')
    await k.rect('kpis', () => document.querySelector('.kpis'))
    await k.rect('leads', () => document.querySelector('table').closest('.card'))
    await k.rect('rows', () => [...document.querySelectorAll('table tbody tr')])
    await k.rect('assist', () => [...document.querySelectorAll('h3')].find((h) => h.textContent.includes('Assisted mode')).closest('.card'))
    await k.rect('sales', () => [...document.querySelectorAll('h3')].find((h) => h.textContent.includes('Partner sales')).closest('.card'))
    await desk.close()
  }

  let old = { marks: {}, taps: [] }  // a partial run (ONLY=k06,hi) keeps the other recordings' marks
  try { old = JSON.parse(fs.readFileSync(`${OUT}/marks.json`)) } catch {}
  const names = new Set([...Object.keys(marks), ...Object.keys(rects)].map((m) => m.split(':')[0]))
  const keep = Object.fromEntries(Object.entries(old.marks).filter(([m]) => !names.has(m.split(':')[0])))
  const keepR = Object.fromEntries(Object.entries(old.rects || {}).filter(([m]) => !names.has(m.split(':')[0])))
  fs.writeFileSync(`${OUT}/marks.json`, JSON.stringify({ marks: { ...keep, ...marks }, rects: { ...keepR, ...rects },
    taps: [...old.taps.filter(([n]) => !names.has(n)), ...taps] }, null, 1))
  console.log(Object.fromEntries(Object.entries(marks).map(([a, b]) => [a, Math.round(b * 10) / 10])))
})()
