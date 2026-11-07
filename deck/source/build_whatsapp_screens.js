// Round-1 deck: TouristGuide_NIT_Jamshedpur. Intro + 7 scored slides + annexure, on the Airtel Sync template backgrounds.
// Run: NODE_PATH=<pptxgenjs install> node build.js out.pptx
const path = require('path')
const pptxgen = require('pptxgenjs')
const { applyTheme } = require('/root/.claude/skills/synced/998f07f9-b9bf-423c-911b-aef9d4e724b8_1831365a-23c6-40aa-a2ef-06a9169d9abb/pptx/scripts/apply_theme.js')

const IMG = (f) => path.join(__dirname, 'img', f)
const OUT = process.argv[2] || path.join(__dirname, 'TouristGuide_NIT_Jamshedpur.pptx')
const LIVE = 'https://udyam.openforge.online'
const VIDEO = process.env.VIDEO_URL || ''

const THEME = {
  name: 'Accel Saathi',
  headFontFace: 'Calibri',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '1F1F24', lt1: 'FFFFFF', dk2: '5F6368', lt2: 'F3F4F6',
    accent1: 'D40000', accent2: '8E0000', accent3: '1E7E34', accent4: 'FDECEC', accent5: 'E5E7EB', accent6: '9CA3AF',
    hlink: 'D40000', folHlink: '8E0000',
  },
}
const HEX = THEME.colors

const pres = new pptxgen()
pres.layout = 'LAYOUT_16x9'
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace }
pres.title = 'Accel Saathi · Project Udyam Digital · Team TouristGuide, NIT Jamshedpur'
pres.author = 'Team TouristGuide, NIT Jamshedpur'
pres.company = 'NIT Jamshedpur'
pres.subject = 'Airtel Sync 2026, Digital Track, Round 1'
const C = pres.SchemeColor

pres.defineSlideMaster({ title: 'COVER', background: { path: IMG('bg_cover.jpg') }, objects: [] })
const contentMaster = (title, footer) => pres.defineSlideMaster({
  title,
  background: { path: IMG('bg_content.jpg') },
  margin: [0.7, 0.45, 0.5, 0.45],
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.45, y: 0.62, w: 9.1, h: 0.46, fontSize: 21, bold: true, color: C.text1, align: 'left', valign: 'middle', margin: 0 }, text: '' } },
    { placeholder: { options: { name: 'sub', type: 'body', x: 0.45, y: 1.08, w: 9.1, h: 0.32, fontSize: 11, color: C.text2, align: 'left', valign: 'top', margin: 0 }, text: '' } },
    { text: { text: footer, options: { x: 0.75, y: 5.22, w: 5.2, h: 0.22, fontSize: 8, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 0.45, y: 5.22, w: 0.28, h: 0.22, fontSize: 8, bold: true, color: C.accent1, margin: 0 },
})
contentMaster('CONTENT', 'Team TouristGuide · NIT Jamshedpur · Accel Saathi (Project Udyam Digital)')
contentMaster('ANNEX', 'Annexure · not scored · Team TouristGuide · NIT Jamshedpur')

// ---------- helpers ----------
const box = (s, x, y, w, h, fill, extra = {}) =>
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: fill, width: 0 }, ...extra })
const txt = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, valign: 'top', fontSize: 10, color: C.text1, ...o })
const label = (s, text, x, y, w) => txt(s, text, { x, y, w, h: 0.2, fontSize: 9, bold: true, color: C.accent1, charSpacing: 1 })
const run = (text, o = {}) => ({ text, options: o })
const lines = (arr) => arr.map((r, i) => ({ text: r.text, options: { ...r.options, breakLine: i < arr.length - 1 } }))
const arrow = (s, x1, y1, x2, y2) =>
  s.addShape(pres.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color: HEX.accent6, width: 1.25, endArrowType: 'triangle' } })
const badge = (s, n, x, y) => {
  s.addShape(pres.ShapeType.ellipse, { x, y, w: 0.3, h: 0.3, fill: { color: HEX.accent1 }, line: { color: 'FFFFFF', width: 1.5 } })
  txt(s, String(n), { x, y, w: 0.3, h: 0.3, fontSize: 11, bold: true, color: C.background1, align: 'center', valign: 'middle' })
}
const H = { bold: true, color: 'FFFFFF', fill: { color: HEX.dk1 }, fontSize: 9, valign: 'middle' }
const cell = (t, i, extra = {}) => ({ text: t, options: { fontSize: 9, color: HEX.dk1, valign: 'middle', fill: { color: i % 2 ? 'FFFFFF' : HEX.lt2 }, ...extra } })
const table = (s, rows, o) => s.addTable(rows, { border: { type: 'solid', pt: 0.5, color: HEX.accent5 }, margin: [0.03, 0.06, 0.03, 0.06], fontFace: THEME.bodyFontFace, ...o })

const chartBase = {
  barDir: 'bar', catAxisOrientation: 'maxMin', valAxisHidden: true, valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
  catAxisLabelColor: '3C4043', catAxisLabelFontSize: 9, catAxisLabelFontFace: '+mn-lt', catAxisLineShow: false,
  showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 9, dataLabelColor: HEX.dk1, dataLabelFontFace: '+mn-lt',
  barGapWidthPct: 45, showLegend: false, showTitle: false, layout: { x: 0.02, y: 0.02, w: 0.96, h: 0.96 },
}
const PH = 1376 / 816 // phone frame aspect (h / w)

// ======================================================================
// Intro
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'COVER' })
  txt(s, 'PROJECT UDYAM DIGITAL · DIGITAL TRACK', { x: 0.62, y: 2.66, w: 4.4, h: 0.22, fontSize: 10, bold: true, color: 'FF5A5A', charSpacing: 2 })
  txt(s, [run('Accel Saathi', { color: 'FFFFFF' }), run(': a small business gets online in one conversation', { color: 'FFFFFF' })],
    { x: 0.62, y: 2.9, w: 4.6, h: 0.78, fontSize: 22, bold: true, fontFace: THEME.headFontFace })
  txt(s, 'A GenAI advisor in 10 Indian languages, in the app and on WhatsApp: the right bundle with reasons, one monthly price, KYC in minutes and a tracker that ends status calls.',
    { x: 0.62, y: 3.72, w: 4.4, h: 0.56, fontSize: 10, color: 'D7D9DE' })
  const kpis = [['7.4% → 15%', 'lead to activation'], ['17.6 → 7 days', 'lead to live'], ['₹15k → ₹5k', 'cost per activation']]
  kpis.forEach(([a, b], i) => {
    const x = 0.62 + i * 1.42
    s.addShape(pres.ShapeType.roundRect, { x, y: 4.36, w: 1.34, h: 0.54, rectRadius: 0.06, fill: { color: 'FFFFFF', transparency: 86 }, line: { color: 'FFFFFF', transparency: 60, width: 0.75 } })
    txt(s, lines([run(a, { fontSize: 12, bold: true, color: 'FFFFFF' }), run(b, { fontSize: 8.5, color: 'D7D9DE' })]), { x: x + 0.12, y: 4.38, w: 1.16, h: 0.5, valign: 'middle' })
  })
  txt(s, 'Team TouristGuide · NIT Jamshedpur · Airtel Sync 2026', { x: 0.62, y: 5.0, w: 4.6, h: 0.2, fontSize: 9, color: 'FFFFFF' })

  // try-it card
  s.addShape(pres.ShapeType.roundRect, { x: 7.72, y: 3.42, w: 1.86, h: 1.62, rectRadius: 0.08, fill: { color: 'FFFFFF' }, line: { color: 'FFFFFF', width: 0 } })
  s.addImage({ path: IMG('qr_app.png'), x: 8.13, y: 3.5, w: 1.04, h: 1.04, altText: 'QR code to the live Accel Saathi app', hyperlink: { url: LIVE } })
  txt(s, [run('Try it live', { bold: true, color: HEX.accent1, breakLine: true, hyperlink: { url: LIVE } }), run('udyam.openforge.online', { color: HEX.dk1, hyperlink: { url: LIVE } })],
    { x: 7.76, y: 4.56, w: 1.78, h: 0.34, fontSize: 8.5, align: 'center' })
  txt(s, VIDEO ? [run('▶ Watch the 3-minute demo', { bold: true, color: 'FFFFFF', hyperlink: { url: VIDEO } })] : '▶ 3-minute demo video: link added on submission',
    { x: 0.62, y: 5.22, w: 4.6, h: 0.2, fontSize: 9, color: 'FF8A8A' })
  s.addNotes('Accel Saathi answers Project Udyam Digital. One line: a pharmacy owner sends one message in Hindi and leaves with a priced, verified, booked order, then never has to call to chase it. The three targets are the success metrics on slide 7, each built from Accel\'s own leads data. The QR opens the live build; the partner console is at /#/console.')
}

// ======================================================================
// 1. Problem and signals
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Accel loses small businesses to the journey, not to demand', { placeholder: 'title' })
  s.addText('Apr–Jun 2026: 5,000 leads, 368 activated (7.4%). ₹35.6 lakh of the ₹55.4 lakh spent went on leads that were never won.', { placeholder: 'sub' })

  label(s, 'LEAD FUNNEL, APR–JUN 2026', 0.45, 1.5, 2.9)
  s.addChart(pres.ChartType.bar, [{ name: 'Leads', labels: ['Leads', 'Contacted', 'Needs assessed', 'Quote accepted', 'KYC complete', 'Activated'], values: [5000, 3406, 1974, 861, 588, 368] }],
    { ...chartBase, x: 0.38, y: 1.72, w: 3.0, h: 1.9, dataLabelFormatCode: '#,##0', chartColors: [HEX.accent6, HEX.accent6, HEX.accent6, HEX.accent6, HEX.accent6, HEX.accent1] })

  label(s, '1,583 LEADS LOST TO THE JOURNEY ITSELF', 3.55, 1.5, 3.0)
  s.addChart(pres.ChartType.bar, [{ name: 'Lost', labels: ['No time for a sales visit', 'Visit never scheduled', 'Documents & paperwork', 'Quote too complex', 'Quote took too long', 'Install over 21 days'], values: [531, 296, 273, 206, 179, 98] }],
    { ...chartBase, x: 3.48, y: 1.72, w: 3.05, h: 1.9, dataLabelFormatCode: '#,##0', chartColors: [HEX.accent1] })

  label(s, 'WHERE THE 17.6 DAYS GO', 6.7, 1.5, 2.85)
  s.addChart(pres.ChartType.bar, [{ name: 'Days', labels: ['Contact', 'Needs visit', 'Quote', 'KYC', 'Install'], values: [1.95, 2.96, 4.11, 3.8, 4.8] }],
    { ...chartBase, x: 6.63, y: 1.72, w: 2.95, h: 1.32, dataLabelFormatCode: '0.0" d"', chartColors: [HEX.accent1, HEX.accent1, HEX.accent1, HEX.accent1, HEX.accent6] })
  txt(s, [run('12.8 days', { bold: true, color: C.accent1 }), run(' are spent waiting for people and paper. We do all of it in one sitting; only the install (4.8 days) stays.')],
    { x: 6.7, y: 3.07, w: 2.85, h: 0.55, fontSize: 9.5, color: C.text2 })

  label(s, 'SIGNALS IN THE DATA, AND WHAT WE BUILT FOR EACH', 0.45, 3.74, 6)
  const cards = [
    ['9.6% vs 2.0%', 'activation with vs without a GSTIN (4.8×)', 'GSTIN first: one number fills and verifies the profile'],
    ['5.9% → 27.9%', '6-month churn as status chases rise from 1 to 5', 'WhatsApp update at every stage; STATUS by message'],
    ['6.2% vs 8.0%', 'conversion of regional-language vs Hindi or English leads', 'The advisor in all 10 languages the leads speak'],
    ['₹4.1k vs ₹24.3k', 'cost per activation: referral vs field sales', 'WhatsApp entry, partner QR and assisted mode'],
  ]
  cards.forEach(([stat, what, built], i) => {
    const x = 0.45 + i * 2.31
    box(s, x, 3.96, 2.17, 1.14, C.background2)
    txt(s, stat, { x: x + 0.12, y: 4.02, w: 1.95, h: 0.3, fontSize: 17, bold: true, color: C.accent1 })
    txt(s, what, { x: x + 0.12, y: 4.33, w: 1.95, h: 0.34, fontSize: 9, color: C.text1 })
    txt(s, [run('Built: ', { bold: true, color: C.accent3 }), run(built)], { x: x + 0.12, y: 4.7, w: 1.98, h: 0.36, fontSize: 9, color: C.text2 })
  })
  s.addNotes('All numbers from smb_leads.csv (5,000 leads, Apr to Jun 2026). Acquisition spend 55.4 lakh in total, 35.6 lakh of it on leads that dropped. 1,583 of the 4,632 lost leads (34%) left for reasons the journey causes: no time for a visit 531, visit not scheduled 296, documents and paperwork 273 (missing GST/Udyam 94, paperwork too long 79, signatory unavailable 53, details mismatch 47), quote too complex 206, quote too slow 179, install over 21 days 98. Days are the average gaps between stage dates for the 368 activated customers.')
}

// ======================================================================
// 2. Segments, bundles and channels (Q1)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Win offices first, shops on self-serve, chains with the field force', { placeholder: 'title' })
  s.addText('Segments ranked on the leads data. Every example bundle was priced by our advisor on the real catalogue (24-month price, + GST).', { placeholder: 'sub' })

  const head = ['Segment', 'Share of leads', 'Activation', 'Cost per activation', 'Payback', '6-month churn', 'How they buy', 'Example bundle from our advisor']
    .map((t) => ({ text: t, options: H }))
  const seg = (name, wave) => [run(name, { bold: true, breakLine: true }), run(wave, { color: HEX.accent1, fontSize: 8.5, bold: true })]
  const ex = (who, what, price) => [run(who, { bold: true }), run(what), run(price, { bold: true, color: HEX.accent1 })]
  const rows = [
    [seg('Professional offices', 'Wave 1 · start here'), '25%', '11.1%', '₹10,695', '1.6 mo', '13.8%', 'Self-serve; a call back when asked',
      ex('Dental clinic, Pune, 8 staff: ', 'fibre 300, email and security for 5, cloud backup, 4G failover, WhatsApp API · ', '₹5,814/mo')],
    [seg('Micro retail & services', 'Wave 1 · volume, digital only'), '54%', '4.1%', '₹20,007', '8.1 mo', '22.7%', 'Self-serve on WhatsApp or the app; no visit',
      ex('Pharmacy, Jaipur, 4 staff: ', 'fibre 100, 2 mobile lines, billing tablet, verified WhatsApp, 2 CCTV · ', '₹3,593/mo')],
    [seg('Small multi-site', 'Wave 1 · assisted'), '15%', '11.0%', '₹15,614', '0.6 mo', '10.8%', 'Advisor quotes; field confirms each site',
      ex('Restaurant chain, 5 outlets: ', 'fibre 300 × 5, SD-WAN, failover, POS, CCTV, guest Wi-Fi · ', '₹30,869/mo')],
    [seg('Small manufacturers', 'Wave 2'), '6%', '12.8%', '₹15,324', '1.0 mo', '8.1%', 'Field-led; advisor prices it on the visit',
      ex('Auto-parts plant, 80 staff: ', '20 Mbps leased line, firewall, 8 machine IoT, CCTV, email · ', '₹16,822/mo')],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci === 4 ? { bold: true, color: i === 1 ? HEX.accent1 : HEX.accent3, align: 'center' } : ci >= 1 && ci <= 5 ? { align: 'center' } : {})))
  table(s, [head, ...rows], { x: 0.45, y: 1.5, w: 9.1, colW: [1.38, 0.55, 0.65, 0.78, 0.6, 0.62, 1.4, 3.12], rowH: [0.36, 0.52, 0.52, 0.52, 0.52] })

  const cards = [
    ['Shops only pay back digitally', '₹20,007 to win a ₹2,470 bundle is 8.1 months of revenue, and 22.7% churn within 6 months. At under ₹5,000 a self-serve sale pays back in 2 months.'],
    ['Field force moves up-market', 'Chains and plants pay back in a month and bring 73% of revenue. The advisor prices them on the visit; shops and offices close on their own.'],
    ['Price and contract rule', 'The 24-month price is shown first (13.1% churn vs 15.1% on 12 months). No 6-month deals (2 of 3 churned). "Make it cheaper" never drops what the owner chose.'],
  ]
  cards.forEach(([h, b], i) => {
    const x = 0.45 + i * 3.075
    box(s, x, 4.02, 2.95, 1.08, C.background2)
    txt(s, h, { x: x + 0.13, y: 4.08, w: 2.7, h: 0.24, fontSize: 10.5, bold: true, color: C.accent1 })
    txt(s, b, { x: x + 0.13, y: 4.34, w: 2.72, h: 0.72, fontSize: 9, color: C.text1 })
  })
  s.addNotes('Segment metrics from smb_leads.csv. Cost per activation = all acquisition spend in the segment / activations in it. Payback = cost per activation / median monthly bundle of activated customers (revenue months). Revenue share of activated bundles: multi-site 57%, professional 21%, manufacturers 16%, micro 6%. Example bundles are the advisor\'s own output on product_catalogue.csv, at 24-month prices; on 12 months they are 6,734 / 4,293 / 33,819 / 19,811.')
}

// ======================================================================
// 3. Priya's journey (Q2 and the build)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Priya goes from one Hindi message to a booked installation in 15 minutes', { placeholder: 'title' })
  s.addText('Coral Medicals: a 4-person pharmacy in Jaipur on a phone hotspot, taken from the case\'s GST registry. Real screens from the live build.', { placeholder: 'sub' })
  const phones = [
    ['f_wa.png', 'WhatsApp, 10 pm', 'One Hindi message with her GSTIN. The registry fills her profile; three taps later she sees a priced bundle.', 'No sales visit, no 3–5 day quote'],
    ['f_item.png', 'Every line explained', 'Why she needs it, what it does, what happens without it, and its cost per day.', 'No product codes, no target-driven pitch'],
    ['f_kyc.png', 'KYC in 2 minutes', 'DigiLocker pulls her GST record, Aadhaar OTP checks the signatory, no Udyam asked for as she has none.', 'No paper, no email'],
    ['f_wastatus.png', 'Status on WhatsApp', '"मेरा ऑर्डर कहाँ तक पहुँचा?" gets the stage, the engineer\'s slot and buttons to reschedule.', 'No chasing calls'],
    ['f_onebill.png', 'One bill, one number', 'All 5 services on one ₹5,066 bill with GST, one support number, one chat.', 'No five vendors'],
  ]
  const ph = 2.25, pw = ph / PH, gap = (7.58 - 5 * pw) / 4, cy = 1.48 + ph + 0.1
  phones.forEach(([img, name, cap, pain], i) => {
    const x = 0.45 + i * (pw + gap)
    s.addImage({ path: IMG(img), x, y: 1.48, w: pw, h: ph, altText: `${name}: screen from the Accel Saathi build` })
    badge(s, i + 1, x - 0.06, 1.42)
    txt(s, lines([run(name, { bold: true, color: C.accent1, fontSize: 10 }), run(cap, { fontSize: 8.5, color: C.text1 })]), { x: x - 0.02, y: cy, w: pw + 0.14, h: 0.95 })
    txt(s, [run('✕ ', { color: HEX.accent1, bold: true }), run(pain, { bold: true })], { x: x - 0.02, y: cy + 0.98, w: pw + 0.14, h: 0.34, fontSize: 8.5, color: C.text2 })
  })
  // before / after column
  const bx = 8.18
  box(s, bx, 1.48, 1.37, 1.55, C.background2)
  txt(s, lines([run('TODAY', { bold: true, color: HEX.dk2, fontSize: 8.5, charSpacing: 1 }), run('17.6 days', { bold: true, fontSize: 16, color: HEX.dk1 }),
    run('3 calls to chase', { fontSize: 9 }), run('a quote in 4 days', { fontSize: 9 }), run('one bill per product', { fontSize: 9 })]), { x: bx + 0.1, y: 1.55, w: 1.2, h: 1.45 })
  box(s, bx, 3.1, 1.37, 1.55, C.accent1)
  txt(s, lines([run('ACCEL SAATHI', { bold: true, color: 'FFFFFF', fontSize: 8.5, charSpacing: 1 }), run('15 min', { bold: true, fontSize: 16, color: 'FFFFFF' }),
    run('to a booked install', { fontSize: 9, color: 'FFFFFF' }), run('live in ~5 days', { fontSize: 9, color: 'FFFFFF' }), run('0 calls, 1 bill', { fontSize: 9, color: 'FFFFFF' })]), { x: bx + 0.1, y: 3.17, w: 1.2, h: 1.45 })
  s.addImage({ path: IMG('qr_app.png'), x: bx + 0.03, y: 4.72, w: 0.38, h: 0.38, hyperlink: { url: LIVE }, altText: 'QR code to the live app' })
  txt(s, [run('Try it live', { bold: true, color: HEX.accent1, hyperlink: { url: LIVE } })], { x: bx + 0.47, y: 4.72, w: 0.9, h: 0.38, fontSize: 9, valign: 'middle' })
  s.addNotes('Screens are from the running build at udyam.openforge.online, captured on a 390 x 844 phone. Priya Chauhan, Coral Medicals, GSTIN 08EAHXC5550F1ZF is in mock_gstin_registry.csv and has no Udyam registration, so the app does not ask for one. 1: the in-app WhatsApp view; the same advisor answers on the real WhatsApp Cloud API number (tested on a phone with updates, read receipts and STATUS / RESCHEDULE / PROBLEM). 2: an item opened: why, what it does, what happens without it, per-day cost. 3: DigiLocker + Aadhaar OTP, verified with the checks listed. 4: the owner asks for status in Hindi. 5: after go-live, the one-bill card. 15 minutes: about 3 for the chat, 2 for KYC, 1 to e-sign and pick a slot, with room to spare.')
}

// ======================================================================
// 4. How it works and proof (Q3, technical depth)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('An AI that cannot invent a price, and KYC that cannot be fooled', { placeholder: 'title' })
  s.addText('The model reads the owner; a rules engine on the catalogue picks and prices. Every KYC problem comes with a reason and a one-tap fix.', { placeholder: 'sub' })

  const flowBox = (x, y, w, h, head, body, fill = C.background2) => {
    box(s, x, y, w, h, fill)
    txt(s, lines([run(head, { bold: true, fontSize: 10, color: C.text1 }), run(body, { fontSize: 8.5, color: C.text2 })]), { x: x + 0.09, y: y + 0.07, w: w - 0.16, h: h - 0.1 })
  }
  label(s, 'ADVISE', 0.45, 1.5, 2)
  const r1 = [['Owner', 'App, WhatsApp or voice; 10 languages and Hinglish'],
    ['LLM understands', 'Facts, intent and language. Groq or Gemini on free tiers; one call per turn at most'],
    ['Rules decide', '25 products: eligibility, dependencies, quantities, prices; Basic, Recommended, Complete'],
    ['Grounded reply', '47 knowledge sections, source shown; any ₹ not in the quote is blocked']]
  const w1 = 1.43, g1 = 0.2
  r1.forEach(([h, b], i) => {
    const x = 0.45 + i * (w1 + g1)
    flowBox(x, 1.72, w1, 0.98, h, b, i === 2 ? C.accent4 : C.background2)
    if (i) arrow(s, x - g1 + 0.02, 2.21, x - 0.02, 2.21)
  })
  label(s, 'VERIFY AND GO LIVE', 0.45, 2.84, 3)
  const r2 = [['Smart KYC', 'GSTIN and Udyam registry, DigiLocker, Aadhaar OTP or Accel mobile KYC, OCR with checksum re-read; 20+ checks'],
    ['E-sign and tracker', 'WhatsApp update at every stage with read receipts; slot booking; STATUS by message'],
    ['Partner console', 'Assisted mode, counter QR, leads scored (AUC 0.71) with a next best action']]
  const w2 = (4 * w1 + 3 * g1 - 2 * g1) / 3
  r2.forEach(([h, b], i) => {
    const x = 0.45 + i * (w2 + g1)
    flowBox(x, 3.05, w2, 0.9, h, b)
    if (i) arrow(s, x - g1 + 0.02, 3.5, x - 0.02, 3.5)
  })
  txt(s, 'No AI key, a slow model or a used-up quota? The rules engine runs the same journey, so the price and the demo never depend on the model. The full test run with the AI on cost ₹0.11.',
    { x: 0.45, y: 4.02, w: 6.3, h: 0.34, fontSize: 9, italic: true, color: C.text2 })

  label(s, 'PROOF IT WORKS', 7.0, 1.5, 2.5)
  const proof = [['64/64', 'advisor tests pass with the AI on and off: 35 owners in 5 languages, 7 chat changes, 22 questions; 498 catalogue checks'],
    ['12/12', 'specimen applicants judged right: cancelled and altered GSTIN, name mismatch, blur, missing Udyam, 257-day-old bill'],
    ['0', 'prices invented: a reply quoting any ₹ amount not in the catalogue or the quote is dropped'],
    ['81/81', 'checks on WhatsApp orders (54), partner sales (17) and KYC flows (10)']]
  proof.forEach(([n, t], i) => {
    const y = 1.72 + i * 0.62
    box(s, 7.0, y, 2.55, 0.56, C.accent4)
    txt(s, n, { x: 7.06, y, w: 0.8, h: 0.56, fontSize: 17, bold: true, color: C.accent1, valign: 'middle', align: 'center' })
    txt(s, t, { x: 7.88, y: y + 0.03, w: 1.62, h: 0.52, fontSize: 7.5, color: C.text1, valign: 'middle' })
  })

  label(s, 'PRIVACY BY DESIGN · DPDP ACT 2023', 0.45, 4.42, 5)
  const chips = ['One consent switch per purpose', 'Photos read, then discarded', 'IDs and numbers masked', 'Owner consents on her own phone', 'Erase my data, any time', 'Audit log of every check']
  const cw = (9.1 - 5 * 0.08) / 6
  chips.forEach((c, i) => {
    const x = 0.45 + i * (cw + 0.08)
    box(s, x, 4.66, cw, 0.42, C.background2)
    txt(s, c, { x: x + 0.05, y: 4.66, w: cw - 0.1, h: 0.42, fontSize: 8.5, bold: true, color: C.text1, align: 'center', valign: 'middle' })
  })
  s.addNotes('The LLM only turns free text into structured facts, an action and a language; it never picks a product or a price. Routing: Groq (gpt-oss-120b) first for English and Hindi, Gemini Flash-Lite first for the other 8 languages, each falling back to the other on 429/5xx, then to rules. Known terms (static IP, Mbps, SLA...) are answered from fixed cards even with the AI on. Tests in backend/tests: run_advisor_scenarios (64, with --llm for the AI-on run: 64/64, 2 AI calls, Rs 0.11), run_kyc_pack (12 applicants), run_whatsapp_orders (54), run_partner_flows (17), run_kyc_flows (10); 54 + 17 + 10 = 81 (annexure A4). Every failed KYC check has a fix button: DigiLocker instead, upload a newer bill, Aadhaar OTP, remove a certificate that is not needed, or a ready authorisation-letter template.')
}

// ======================================================================
// 5. Field force and partners (Q4)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('The field force and partners sell more, not less', { placeholder: 'title' })
  s.addText('The advisor takes the paperwork, not the customer: every sale a partner starts stays theirs, and pay follows customers who stay.', { placeholder: 'sub' })

  label(s, 'COST PER ACTIVATION BY CHANNEL, APR–JUN', 0.45, 1.5, 3.2)
  s.addChart(pres.ChartType.bar, [{ name: 'Cost', labels: ['Field sales', 'Channel partner', 'Website form', 'Inbound call', 'Referral', 'WhatsApp campaign'], values: [24335, 20851, 6352, 5113, 4099, 4026] }],
    { ...chartBase, x: 0.38, y: 1.68, w: 3.12, h: 1.5, dataLabelFormatCode: '"₹"#,##0', chartColors: [HEX.accent1, HEX.accent1, HEX.accent6, HEX.accent6, HEX.accent6, HEX.accent6] })

  label(s, 'WHO SELLS WHAT', 0.45, 3.3, 3)
  const route = [
    ['Shops, offices', 'Self-serve: app or WhatsApp'],
    ['Wants a person', 'Partner assists, in person'],
    ['Chat didn\'t close', 'Scored call list, next step'],
    ['Chains, plants', 'Advisor prices, field checks sites'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci ? { fontSize: 8.5 } : { bold: true, fontSize: 8.5 })))
  table(s, [[{ text: 'Owner', options: H }, { text: 'Channel', options: H }], ...route], { x: 0.45, y: 3.52, w: 3.05, colW: [1.05, 2.0], rowH: [0.26, 0.28, 0.28, 0.28, 0.28] })

  label(s, 'PARTNER CONSOLE IN THE BUILD', 3.72, 1.5, 3)
  const cw5 = 3.2
  s.addShape(pres.ShapeType.rect, { x: 3.72, y: 1.72, w: cw5, h: cw5 * 381 / 1331, fill: { color: 'FFFFFF' }, line: { color: HEX.accent5, width: 0.75 } })
  s.addImage({ path: IMG('con_assist.png'), x: 3.72, y: 1.72, w: cw5, h: cw5 * 381 / 1331, altText: 'Partner console: an assisted chat started by Ganga Connect, with a QR for the owner' })
  const y2 = 1.72 + cw5 * 381 / 1331 + 0.1
  s.addShape(pres.ShapeType.rect, { x: 3.72, y: y2, w: cw5, h: cw5 * 486 / 1664, fill: { color: 'FFFFFF' }, line: { color: HEX.accent5, width: 0.75 } })
  s.addImage({ path: IMG('con_sales.png'), x: 3.72, y: y2, w: cw5, h: cw5 * 486 / 1664, altText: 'Partner sales and commission table: Ganga Connect has 2 sales, 1 protected' })
  const y3 = y2 + cw5 * 486 / 1664 + 0.06
  txt(s, 'Ganga Connect starts a chat for an owner; the QR hands it to her phone. Its sales, protected sales and commission update live.',
    { x: 3.72, y: y3, w: cw5, h: 0.4, fontSize: 8.5, color: C.text2 })
  box(s, 3.72, 4.34, cw5, 0.78, C.accent4)
  txt(s, lines([run('Field time goes where it pays', { bold: true, color: C.accent1, fontSize: 10 }),
    run('Field sales costs ₹24,335 per activation; a shop takes 8 months to pay that back. Freed visits go to chains and plants: 73% of revenue.', { fontSize: 8.5 })]),
  { x: 3.82, y: 4.39, w: 3.02, h: 0.7 })

  label(s, 'WHY PARTNERS WILL PUSH IT', 7.12, 1.5, 2.5)
  const why = [
    ['Commission protection', 'The owner confirms her number by a code on her own phone. That number stays the partner\'s for 30 days, even if she orders alone later. A typed-in number earns nothing.'],
    ['Pay tied to retention', 'One month\'s rental per sale: half when every service is live, half after 6 months. 15.2% churn in 6 months today, so we pay for customers who stay.'],
    ['Counter QR', 'Each partner\'s QR opens the app tagged to them, so walk-ins they send are credited too.'],
  ]
  why.forEach(([h, b], i) => {
    const y = 1.72 + i * 1.13
    box(s, 7.12, y, 2.43, 1.05, C.background2)
    txt(s, lines([run(h, { bold: true, fontSize: 10, color: C.text1 }), run(b, { fontSize: 8.5, color: C.text2 })]), { x: 7.22, y: y + 0.07, w: 2.26, h: 0.95 })
  })
  s.addNotes('Channel costs: acquisition spend per activation by lead_source in smb_leads.csv (field sales 24,335; channel partner 20,851; website 6,352; inbound 5,113; referral 4,099; WhatsApp campaign 4,026). Assisted mode, owner-code consent, 30-day protection and the commission ledger are built and tested (backend/tests/run_partner_flows.py, 17 checks: wrong code refused, 5 wrong tries lock the code, unverified numbers earn nothing, referral QR credited, protection across a new session). The commission rate is a proposal for the pilot.')
}

// ======================================================================
// 6. Competitive analysis
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Rivals sell plans or single products; we sell the whole setup, self-serve', { placeholder: 'title' })
  s.addText('What a small-business owner can do today, from public websites and press reviewed in October 2026.', { placeholder: 'sub' })

  const Y = 'Yes', P = 'Partly', N = '—'
  const head = ['What the owner needs', 'Accel Saathi', 'Jio Business', 'Vi Business', 'Tata Tele Business', 'Local ISP or cable']
    .map((t, i) => ({ text: t, options: { bold: true, fontSize: 9, color: 'FFFFFF', fill: { color: i === 1 ? HEX.accent1 : HEX.dk1 }, align: i ? 'center' : 'left', valign: 'middle' } }))
  const matrix = [
    ['Mobile and fixed internet on one bill', Y, Y, P, N, N],
    ['Business apps in the bundle (WhatsApp, email, security, CCTV, POS)', Y, P, P, Y, N],
    ['A bundle recommended for my business, with reasons', Y, N, P, N, P],
    ['Buy in Hindi or my own language, or on WhatsApp', Y, P, P, N, P],
    ['All-in monthly price before anyone visits', Y, Y, P, P, P],
    ['Instant KYC: GSTIN and Udyam lookup, DigiLocker, e-sign', Y, N, N, N, N],
    ['Order tracker and updates, so I never have to chase', Y, P, N, N, N],
    ['Lowest price and someone next door', P, Y, P, P, Y],
  ]
  const tone = { Yes: [HEX.accent3, true], Partly: ['B26A00', false], '—': [HEX.accent6, false] }
  const rows = matrix.map((r, ri) => r.map((c, ci) => {
    const fill = { color: ci === 1 ? HEX.accent4 : (ri % 2 ? 'FFFFFF' : HEX.lt2) }
    if (!ci) return { text: c, options: { fontSize: 9, color: HEX.dk1, fill, valign: 'middle' } }
    const [color, bold] = tone[c]
    return { text: c, options: { fontSize: 9.5, color, bold, align: 'center', valign: 'middle', fill } }
  }))
  table(s, [head, ...rows], { x: 0.45, y: 1.5, w: 6.15, colW: [2.35, 0.8, 0.75, 0.75, 0.75, 0.75], rowH: [0.36, ...Array(8).fill(0.3)], margin: [0.02, 0.06, 0.02, 0.06] })
  txt(s, '— not seen on public pages. Sources: Jio Business broadband plans with JioAttendance, JioMeet and JioGate (TheTechOutlook, Mar 2026); Vi Business "Ready For Next" assessment with Dun & Bradstreet (tele.net, Jun 2023); TTBS Smartflo; TTBS has had no mobile network of its own since 2019. Accel is the case\'s fictional operator.',
    { x: 0.45, y: 4.6, w: 6.15, h: 0.48, fontSize: 7.5, color: C.text2 })

  label(s, 'WHERE THEY WIN, AND OUR ANSWER', 6.8, 1.5, 2.8)
  const wins = [
    ['Jio Business: price and brand', 'We win on fit, not price: the advisor right-sizes the bundle, shows the 24-month price and cuts cost in one tap.'],
    ['Local ISPs: cheapest, next door', '325 lost leads were "locked in" and 207 went "cheaper". Local partners now sell through our advisor and keep the sale.'],
    ['Vi and TTBS: advice and cloud tools', 'Vi assesses and TTBS sells telephony. We go from advice to price, KYC and order in one flow, on our own mobile and fibre.'],
  ]
  wins.forEach(([h, b], i) => {
    const y = 1.72 + i * 0.86
    box(s, 6.8, y, 2.75, 0.78, C.background2)
    txt(s, lines([run(h, { bold: true, fontSize: 9.5, color: C.text1 }), run(b, { fontSize: 8.5, color: C.text2 })]), { x: 6.9, y: y + 0.06, w: 2.58, h: 0.7 })
  })
  box(s, 6.8, 4.35, 2.75, 0.75, C.accent1)
  txt(s, lines([run('Our moat', { bold: true, fontSize: 9.5, color: 'FFFFFF' }), run('30% of leads already use Accel mobile and convert at 9.2% vs 5.4% for local-ISP users. Their KYC is reused, so they buy with no new documents.', { fontSize: 8.5, color: 'FFFFFF' })]),
    { x: 6.9, y: 4.4, w: 2.58, h: 0.68 })
  s.addNotes('Ratings are what an owner can see or do on public pages, not internal capability; anything we could not find is marked as not seen rather than no. Jio Business sells broadband plans with its own apps (JioAttendance, JioMeet, JioGate). Vi Business offers the Ready For Next assessment with Dun & Bradstreet. Tata Tele Business Services sells Smartflo cloud telephony and SMB SaaS but has had no mobile network of its own since 2019. In our data, 325 lost leads were locked in with their provider and 207 left for a cheaper competitor. Accel mobile users: "Accel" and "Accel (mobile only)" current_provider, 9.1 to 9.2% activation vs 5.4% for local ISP.')
}

// ======================================================================
// 7. Impact, metrics, rollout, risks (Q5)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Twice the customers from the same leads, at half the cost of each', { placeholder: 'title' })
  s.addText('Modelled on one quarter of Accel\'s leads. The partner console already tracks the live funnel against these baselines.', { placeholder: 'sub' })

  label(s, 'EVERY QUARTER, SAME LEADS', 0.45, 1.5, 3)
  const big = [['368 → 764', 'activations: +396, a quarter of the 1,583 journey drop-offs won back'],
    ['₹15,053 → ₹7,251', 'cost per activation on the same spend; under ₹5,000 as WhatsApp and partner QR grow'],
    ['≈ ₹3.3 crore', 'new yearly revenue from each quarter\'s extra customers (396 × ₹6,900 median × 12)']]
  big.forEach(([n, t], i) => {
    const y = 1.72 + i * 0.7
    box(s, 0.45, y, 3.1, 0.63, C.background2)
    txt(s, n, { x: 0.57, y: y + 0.04, w: 2.9, h: 0.3, fontSize: 15, bold: true, color: C.accent1 })
    txt(s, t, { x: 0.57, y: y + 0.33, w: 2.92, h: 0.3, fontSize: 8.5, color: C.text1 })
  })

  label(s, 'HOW WE MEASURE SUCCESS', 3.75, 1.5, 3)
  const kpi = [
    ['Lead to activation', '7.4%', '15%', 'Win back 25% of visit, quote and paperwork drop-offs'],
    ['Lead to live', '17.6 days', '≤ 7 days', '12.8 days of contact, needs, quote and KYC become one sitting'],
    ['Status chases per customer', '3.0', '< 0.5', 'WhatsApp update at every stage; STATUS by message'],
    ['Cost per activation', '₹15,053', '< ₹5,000', '2× activations on the same spend, then the ₹4–5k channels'],
    ['6-month churn', '15.2%', '< 10%', 'One chase: 5.9% churn; five chases: 27.9%'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, { color: ci === 2 ? HEX.accent3 : HEX.dk1, bold: ci === 2 || ci === 0, align: ci === 1 || ci === 2 ? 'center' : 'left' })))
  table(s, [['Metric', 'Today', 'Target', 'Why it is reachable'].map((t, i) => ({ text: t, options: { ...H, align: i === 1 || i === 2 ? 'center' : 'left' } })), ...kpi],
    { x: 3.75, y: 1.72, w: 5.8, colW: [1.38, 0.72, 0.7, 3.0], rowH: [0.28, 0.335, 0.335, 0.335, 0.335, 0.335], margin: [0.02, 0.06, 0.02, 0.06] })

  label(s, 'ROLLOUT, WITH A GATE AT EACH STEP', 0.45, 3.9, 4)
  const phases = [['Pilot · 8 weeks', 'Jaipur and Pune, offices and shops, Hindi, Marathi, English, WhatsApp. A/B against the field journey.', 'Go if ≥ 12% conversion, ≤ 7 days, < 1 chase'],
    ['Scale · 2 quarters', 'All 10 languages, tier 1–2 cities, every partner on assisted mode; chains with field site checks.', 'Go if cost per activation < ₹7,000'],
    ['Grow · year 1', 'Bundles for Accel\'s mobile-only business base, GST and Udyam registration help, IoT for plants.', 'Track churn < 10%']]
  phases.forEach(([h, b, g], i) => {
    const x = 0.45 + i * 1.96
    s.addShape(pres.ShapeType.homePlate, { x, y: 4.1, w: 1.9, h: 0.25, fill: { color: i ? HEX.dk1 : HEX.accent1 }, line: { color: i ? HEX.dk1 : HEX.accent1, width: 0 } })
    txt(s, h, { x: x + 0.08, y: 4.1, w: 1.7, h: 0.25, fontSize: 9, bold: true, color: C.background1, valign: 'middle' })
    txt(s, lines([run(b, { fontSize: 8, color: HEX.dk1 }), run(g, { fontSize: 8, bold: true, color: HEX.accent3 })]), { x, y: 4.4, w: 1.86, h: 0.72 })
  })
  label(s, 'TOP RISKS AND OUR CONTROL', 6.4, 3.9, 3)
  const risks = [['AI says something wrong', 'rules set every price; answers cite a source; "talk to a person" on every screen'],
    ['Field force and partners resist', 'commission protection and the scored call list'],
    ['Forged documents', 'registry lookups, checksum, a review queue'],
    ['AI or WhatsApp limits', 'rules-only mode runs the full journey']]
  const rr = []
  risks.forEach(([r, c], i) => { rr.push(run(r + ': ', { bold: true, color: HEX.dk1 })); rr.push(run(c, { color: HEX.dk2, breakLine: i < risks.length - 1 })) })
  txt(s, rr, { x: 6.4, y: 4.1, w: 3.15, h: 1.02, fontSize: 8, paraSpaceAfter: 2 })
  s.addNotes('Impact model: 1,583 leads a quarter were lost to journey friction (visits, quotes, paperwork, install delay). Winning back 25% adds 396 activations: 764 in total, 15.3% conversion. Spend stays at 55.4 lakh a quarter, so cost per activation falls to 7,251; shifting the mix to WhatsApp, inbound and referral (4,000 to 5,100 per activation today) takes it under 5,000. Revenue uses the median activated bundle (6,900 a month), not the mean (12,350), to stay conservative. For Priya: 3,593 a month on 24 months, live in about 5 days, with no calls.')
}

// ======================================================================
// Annexure A1: architecture
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A1 · Architecture: the AI understands, rules decide, privacy is built in', { placeholder: 'title' })
  s.addText('One FastAPI service behind HTTPS serves the app, the WhatsApp webhook and the partner console. Live at udyam.openforge.online.', { placeholder: 'sub' })
  s.addImage({ path: IMG('arch.png'), x: 0.6, y: 1.48, w: 8.8, h: 8.8 * 900 / 2400, altText: 'Architecture diagram of Accel Saathi' })
  txt(s, 'Stack: React + Vite PWA · FastAPI · SQLite · RapidOCR (ONNX, CPU) · scikit-learn · WhatsApp Cloud API · Groq and Gemini. Runs on a 1 GB VM; the AI is optional.',
    { x: 0.45, y: 4.88, w: 9.1, h: 0.22, fontSize: 8.5, color: C.text2 })
}

// ======================================================================
// A2: privacy note
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A2 · Privacy note: collect what each step needs, for as long as it needs it', { placeholder: 'title' })
  s.addText('Designed to the DPDP Act 2023. The full notice is in the app at /privacy.html and shown before any document is read.', { placeholder: 'sub' })
  const rows = [
    ['Advice', 'Chat messages, business type, city, team size, sites', 'The session; erased on request before an order', 'Consent (owner starts the chat)'],
    ['KYC', 'GST, Udyam, signatory and address fields; a hash of each photo, never the image', 'While the connection is active, then as licence rules require', 'Consent switch (required for KYC)'],
    ['Order and installation', 'Contact name, masked mobile, install address, chosen bundle', 'Contract term', 'Contract'],
    ['Order updates', 'WhatsApp number, stored apart from the order, masked everywhere', 'Until go-live and support end', 'Consent switch (on by default, can be off)'],
    ['Marketing', 'Nothing unless switched on', 'Until withdrawn', 'Consent switch (off by default)'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci ? {} : { bold: true })))
  table(s, [['Purpose', 'Data', 'Kept for', 'Basis'].map((t) => ({ text: t, options: H })), ...rows], { x: 0.45, y: 1.5, w: 9.1, colW: [1.4, 3.6, 2.3, 1.8], rowH: [0.28, 0.36, 0.36, 0.36, 0.36, 0.3] })
  const cards = [
    ['Owner\'s rights', 'Consent in her language with one switch per purpose; withdraw as easily as given; erase my data in one tap before an order, or "DELETE MY DATA" on WhatsApp; a named grievance officer.'],
    ['Assisted sales', 'When a partner holds the device, consent comes only from a code sent to the owner\'s own phone, so a partner can never consent for her.'],
    ['Security', 'HTTPS everywhere; WhatsApp webhooks verified by Meta\'s signature; IDs masked in screens and logs; an audit log of every check; keys kept out of the code.'],
    ['AI and breaches', 'No document image or phone number goes to an AI model. A breach is reported to the Data Protection Board and to affected owners as the DPDP Rules require.'],
  ]
  cards.forEach(([h, b], i) => {
    const x = 0.45 + i * 2.31
    box(s, x, 3.75, 2.17, 1.35, C.background2)
    txt(s, lines([run(h, { bold: true, color: C.accent1, fontSize: 10 }), run(b, { fontSize: 8.5 })]), { x: x + 0.1, y: 3.82, w: 1.98, h: 1.25 })
  })
}

// ======================================================================
// A3: signals and decisions; impact model
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A3 · Every signal we found in the data, and the decision it drove', { placeholder: 'title' })
  s.addText('smb_leads.csv, 5,000 leads, Apr–Jun 2026. Nothing in the app is hard-coded to this copy of the data.', { placeholder: 'sub' })
  const rows = [
    ['GSTIN holders activate at 9.6% vs 2.0% without', 'Ask for the GSTIN first; registry fills and verifies the profile'],
    ['Churn rises from 5.9% (1 status chase) to 27.9% (5); NPS from 7.5 to 6.0', 'WhatsApp update at every stage, STATUS / RESCHEDULE / PROBLEM by message'],
    ['Regional-language leads convert at 6.2% vs 8.0% for Hindi or English', 'Advisor, buttons and WhatsApp in 10 languages, voice in, read-aloud out'],
    ['Referral ₹4,099 and WhatsApp ₹4,026 per activation vs field ₹24,335', 'WhatsApp entry, partner counter QR, assisted mode'],
    ['Accel mobile users convert at 9.2% vs 5.4% for local-ISP users', 'Reuse Accel KYC; lead with the bundle for this base'],
    ['24-month contracts churn 13.1% vs 15.1% on 12; 2 of 3 six-month deals churned', 'Show the 24-month price first; no 6-month deals'],
    ['Micro shops: ₹20,007 to acquire, ₹2,470 bundle, 22.7% churn', 'Shops are self-serve only; field time goes to chains and plants'],
    ['1,583 drop-offs from visits, slow or complex quotes, paperwork, installs over 21 days', 'One sitting: instant quote in plain words, KYC in minutes, ETA per service'],
    ['325 "locked in", 207 "went cheaper"', 'Win on fit and one bill, not price; local partners sell through us'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci ? {} : { bold: false })))
  table(s, [['Signal in the data', 'Decision in the product and plan'].map((t) => ({ text: t, options: H })), ...rows], { x: 0.45, y: 1.5, w: 9.1, colW: [4.8, 4.3], rowH: [0.28, ...Array(9).fill(0.3)] })
  txt(s, 'Impact model (slide 7): extra activations = 25% × 1,583 = 396; cost per activation = ₹55.4 lakh / 764 = ₹7,251; yearly revenue = 396 × ₹6,900 median bundle × 12 ≈ ₹3.28 crore. Mean bundle (₹12,350) would give ₹5.9 crore; we use the median.',
    { x: 0.45, y: 4.74, w: 9.1, h: 0.36, fontSize: 8.5, color: C.text2 })
}

// ======================================================================
// A4: test results
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A4 · Test results: what we checked, and the KYC answer key', { placeholder: 'title' })
  s.addText('All suites are in backend/tests and run in seconds; the advisor suite also runs with the live AI (--llm).', { placeholder: 'sub' })
  const suites = [
    ['Advisor scenarios', '64/64', '35 owners in 5 languages, 7 chat changes, 22 questions and buttons; 498+ catalogue checks; with the AI on and off'],
    ['Specimen KYC pack', '12/12', 'Every applicant judged as the planted problem requires (right table)'],
    ['WhatsApp orders', '54/54', 'Signed webhooks, updates at every stage, STATUS, RESCHEDULE, PROBLEM, typos, other people\'s orders refused'],
    ['Partner flows', '17/17', 'Owner code, lockout after 5 tries, protection across sessions, referral QR, console totals'],
    ['KYC flows', '10/10', 'No-GSTIN owners, remove and replace, Udyam only when registered'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci === 1 ? { bold: true, color: HEX.accent3, align: 'center' } : ci === 0 ? { bold: true } : {})))
  table(s, [['Suite', 'Pass', 'What it covers'].map((t) => ({ text: t, options: H })), ...suites], { x: 0.45, y: 1.5, w: 4.9, colW: [1.25, 0.55, 3.1], rowH: [0.28, 0.5, 0.42, 0.5, 0.42, 0.4] })
  const key = [
    ['K01', 'Rejected', 'GSTIN cancelled in the registry'], ['K02', 'Approved', 'Clean'], ['K03', 'Approved', 'Clean'],
    ['K04', 'Rejected', 'GST certificate too blurred to read'], ['K05', 'Rejected', 'Udyam certificate missing'],
    ['K06', 'Rejected', 'Altered GSTIN: checksum fails; registry shows the real one'], ['K07', 'Rejected', 'Legal name differs from the registry'],
    ['K08', 'Approved', 'Clean'], ['K09', 'Approved', 'Clean'], ['K10', 'Review', 'LLP: authorisation letter needed (template given)'],
    ['K11', 'Rejected', 'Bill 257 days old (limit 90)'], ['K12', 'Approved', 'Clean'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, { fontSize: 8.5, ...(ci === 1 ? { bold: true, color: c === 'Approved' ? HEX.accent3 : c === 'Review' ? 'B26A00' : HEX.accent1 } : {}) })))
  table(s, [['Applicant', 'Decision', 'Reason found'].map((t) => ({ text: t, options: { ...H, fontSize: 8.5 } })), ...key], { x: 5.55, y: 1.5, w: 4.0, colW: [0.7, 0.75, 2.55], rowH: [0.26, ...Array(12).fill(0.27)] })
}

;(async () => {
  await pres.writeFile({ fileName: OUT })
  await applyTheme(OUT, THEME)
  console.log('wrote', OUT)
})()
