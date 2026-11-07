// Records the demo journey on a phone-sized browser with scene marks: node record.js <out dir> [base url]
// Scenes: gstin, pains, why, objection, kyc, tracker, hindi. Marks go to <out>/marks.json (seconds from video start).
const { chromium } = require('playwright')
const fs = require('fs')
const OUT = process.argv[2]
const U = process.argv[3] || 'http://localhost:8031'

;(async () => {
  const b = await chromium.launch()
  const marks = {}
  const record = async (name, fn, opts = {}) => {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'en-IN',
      recordVideo: { dir: OUT + '/raw_' + name, size: { width: 390, height: 844 } }, ...opts })
    const p = await ctx.newPage()
    p.on('dialog', (d) => d.dismiss())
    const t0 = Date.now()
    const mark = (k) => { marks[name + ':' + k] = (Date.now() - t0) / 1000 }
    const css = () => p.addStyleTag({ content: '.dlv.demo{display:none!important} main > p.small.muted:last-of-type{visibility:hidden} *{scroll-behavior:smooth}' }).catch(() => {})
    p.on('load', css)
    const bubbles = async () => p.$$eval('.bubble', (els) => els.length)
    const settle = async (n) => {
      await p.waitForFunction((n) => document.querySelectorAll('.bubble').length > n + 1 && !document.querySelector('.typing'), n, { timeout: 15000 }).catch(() => {})
      await p.waitForTimeout(400)
    }
    const k = {
      p, mark,
      wait: (ms) => p.waitForTimeout(ms),
      type: async (t, hold = 1800) => {
        const n = await bubbles()
        await p.click('.composer input')
        await p.type('.composer input', t, { delay: 38 })
        await p.waitForTimeout(350)
        await p.press('.composer input', 'Enter')
        await settle(n)
        await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
        await p.waitForTimeout(hold)
      },
      chip: async (label, hold = 1500) => {
        const n = await bubbles()
        await p.hover(`.chip:has-text("${label}")`).catch(() => {})
        await p.waitForTimeout(450)
        await p.click(`.chip:has-text("${label}")`, { timeout: 4000 })
        await settle(n)
        await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
        await p.waitForTimeout(hold)
      },
      scrollTo: async (sel, off = 70, i = 0) => {
        await p.evaluate(([s, o, i]) => {
          const all = document.querySelectorAll(s)
          const el = all[i < 0 ? all.length + i : i]
          if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o)
        }, [sel, off, i])
        await p.waitForTimeout(900)
      },
    }
    await p.goto(U + '/')
    await css()
    await p.waitForSelector('.bubble.bot')
    await fn(k)
    await ctx.close()
  }

  // Priya, start to finish
  await record('priya', async (k) => {
    const { p } = k
    await k.wait(1500)
    k.mark('gstin')
    await k.type('I run a pharmacy in Jaipur, we are 4 people. GSTIN 08EAHXC5550F1ZF', 2600)
    await k.chip("Yes, that's mine", 1200)
    await k.chip('1', 900)
    await k.chip('hotspot', 1800)
    k.mark('pains')
    await k.chip('UPI fails', 2000)
    await k.chip('Theft', 2200)
    await k.scrollTo('.needs', 120)
    await k.wait(1500)
    k.mark('why')
    await p.click('.needs + .btn')
    await p.waitForTimeout(1500)
    await k.scrollTo('.card .levels', 90)
    await k.wait(1200)
    await p.click('details.why > summary')
    await k.wait(4000)
    await k.scrollTo('.card .levels', 90)
    await p.mouse.wheel(0, 350)
    await k.wait(3000)
    k.mark('objection')
    await k.type('this is too expensive for me', 600)
    await k.scrollTo('.bubble.me', 20, -1)
    await k.wait(5500)
    k.mark('kyc')
    await k.chip('Keep it, go ahead', 1200).catch(async () => { await p.click('.card .btn:has-text("rice")') })
    if (!(await p.$('.line'))) {
      await p.click('.card .btn:has-text("rice")').catch(() => {})
    }
    await p.waitForSelector('.line', { timeout: 8000 })
    await k.wait(2500)
    await p.mouse.wheel(0, 500)
    await k.wait(1500)
    await p.click('.bottombar .btn')
    await p.waitForSelector('.consent', { timeout: 8000 })
    await k.scrollTo('.purpose', 160, 0)
    await k.wait(2000)
    await p.click('.purpose >> nth=0')
    await k.wait(600)
    await p.click('.bottombar .btn')
    await k.wait(1500)
    await p.click('.btn.dark')
    await k.wait(1800)
    await p.fill('#signatory input >> nth=0', 'Priya Chauhan')
    await p.type('#signatory input >> nth=1', '482913', { delay: 90 })
    await p.click('#signatory .btn')
    await k.wait(1500)
    await p.click('.bottombar .btn')
    await p.waitForSelector('.decision', { timeout: 30000 })
    await k.wait(500)
    await k.scrollTo('.decision', 330)
    await k.wait(3500)
    k.mark('tracker')
    await p.click('.bottombar .btn')
    await p.waitForSelector('input[autocomplete=tel]', { timeout: 10000 })
    const inputs = await p.$$('main input:not([type=checkbox]):visible')
    await inputs[0].fill('Priya Chauhan')
    await inputs[1].fill('9876501234')
    await inputs[2].fill('482913')
    for (const c of await p.$$('main input[type=checkbox]')) { if (!(await c.isChecked())) await c.check() }
    await k.wait(800)
    await p.click('.bottombar .btn')
    await p.waitForSelector('.timeline', { timeout: 10000 })
    await k.wait(1200)
    const nx = async () => { await p.evaluate(() => document.querySelector('.demo .btn')?.click()); await p.waitForTimeout(900) }
    await nx(); await nx()
    await k.scrollTo('.slots', 160)
    await k.wait(1200)
    await p.click('.slots button >> nth=1')
    await k.wait(700)
    await p.click('.slots ~ .btn')
    await k.wait(1200)
    await nx(); await nx(); await nx(); await nx()
    await p.evaluate(() => window.scrollTo(0, 0))
    await k.wait(2500)
    await k.scrollTo('.onebill', 90)
    await k.wait(3000)
    await p.mouse.wheel(0, 500)
    await k.wait(2500)
    k.mark('end')
  })

  // the same advisor in Hindi
  await record('hindi', async (k) => {
    const { p } = k
    await k.wait(800)
    await p.selectOption('header select', 'hi').catch(async () => { await p.selectOption('select[aria-label=Language]', 'hi') })
    await k.wait(1500)
    k.mark('start')
    await k.type('जयपुर में मेरी किराना दुकान है, 3 लोग, एक दुकान', 1500)
    await k.chip('GSTIN', 1200)
    await k.chip('हॉटस्पॉट', 2500)
    k.mark('end')
  })

  fs.writeFileSync(OUT + '/marks.json', JSON.stringify(marks, null, 1))
  console.log(marks)
  await b.close()
})()
