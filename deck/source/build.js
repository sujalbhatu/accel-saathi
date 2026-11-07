// Round-1 deck: TouristGuide_NIT_Jamshedpur. Intro + 7 scored slides + appendix, on the Airtel Sync template backgrounds.
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
pres.title = 'Accel Saathi · Project Udyam Digital · Team TouristGuide_NIT_Jamshedpur'
pres.author = 'Sujal Bhatu, Prince Mehta (Team TouristGuide_NIT_Jamshedpur)'
pres.company = 'NIT Jamshedpur'
pres.subject = 'Airtel Sync 2026, Digital Track, Round 1'
const C = pres.SchemeColor

pres.defineSlideMaster({ title: 'COVER', background: { path: IMG('bg_cover.jpg') }, objects: [] })
const contentMaster = (title, footer, extra = []) => pres.defineSlideMaster({
  title,
  background: { path: IMG('bg_content.jpg') },
  margin: [0.7, 0.45, 0.5, 0.45],
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.45, y: 0.62, w: 9.1, h: 0.46, fontSize: 21, bold: true, color: C.text1, align: 'left', valign: 'middle', margin: 0 }, text: '' } },
    { placeholder: { options: { name: 'sub', type: 'body', x: 0.45, y: 1.08, w: 9.1, h: 0.32, fontSize: 11, color: C.text2, align: 'left', valign: 'top', margin: 0 }, text: '' } },
    { text: { text: footer, options: { x: 0.75, y: 5.22, w: 5.2, h: 0.22, fontSize: 8, color: C.accent6, margin: 0 } } },
    ...extra,
  ],
  slideNumber: { x: 0.45, y: 5.22, w: 0.28, h: 0.22, fontSize: 8, bold: true, color: C.accent1, margin: 0 },
})
contentMaster('CONTENT', 'Team TouristGuide_NIT_Jamshedpur · Accel Saathi (Project Udyam Digital)')
contentMaster('ANNEX', 'APPENDIX · not scored · Team TouristGuide_NIT_Jamshedpur', [
  // a red tag at the top of every appendix page, so nobody mistakes it for a scored slide
  { rect: { x: 1.3, y: 0.16, w: 2.3, h: 0.34, fill: { color: THEME.colors.accent1 }, rectRadius: 0.06 } },
  { text: { text: 'APPENDIX · NOT SCORED', options: { x: 1.3, y: 0.16, w: 2.3, h: 0.34, fontSize: 12, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', charSpacing: 1.5, margin: 0 } } },
])

// ---------- helpers ----------
const box = (s, x, y, w, h, fill, extra = {}) =>
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: fill, width: 0 }, ...extra })
const txt = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, valign: 'top', fontSize: 10, color: C.text1, ...o })
const label = (s, text, x, y, w) => txt(s, text, { x, y, w, h: 0.2, fontSize: 9, bold: true, color: C.accent1, charSpacing: 1 })
const run = (text, o = {}) => ({ text, options: o })
// subtitle with the case question the slide answers, so a judge can tick it off
const sub = (s, tag, text) => s.addText([run(tag + '   ', { bold: true, color: HEX.accent1, charSpacing: 1 }), run(text)], { placeholder: 'sub' })
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
  txt(s, 'A GenAI advisor in 10 Indian languages, in the app and on WhatsApp, that sells like your best salesperson: the right bundle with reasons, one monthly price, KYC in minutes and a tracker that ends status calls.',
    { x: 0.62, y: 3.7, w: 4.3, h: 0.62, fontSize: 9.5, color: 'D7D9DE' })
  const kpis = [['7.4% → 15%', 'lead to activation'], ['17.6 → 7 days', 'lead to live'], ['₹15k → ₹7.7k', 'running cost per activation']]
  kpis.forEach(([a, b], i) => {
    const x = 0.62 + i * 1.42
    // a solid card, so the binary pattern behind never shows through the numbers
    s.addShape(pres.ShapeType.roundRect, { x, y: 4.36, w: 1.34, h: 0.54, rectRadius: 0.06, fill: { color: '1A0B0E' }, line: { color: 'FF5A5A', transparency: 40, width: 0.75 } })
    txt(s, lines([run(a, { fontSize: 12, bold: true, color: 'FFFFFF' }), run(b, { fontSize: b.length > 20 ? 7.5 : 8.5, color: 'D7D9DE' })]), { x: x + 0.12, y: 4.38, w: 1.16, h: 0.5, valign: 'middle' })
  })
  txt(s, [run('Team TouristGuide_NIT_Jamshedpur', { bold: true }), run('  ·  Sujal Bhatu, Prince Mehta  ·  Airtel Sync 2026')], { x: 0.62, y: 5.0, w: 4.8, h: 0.2, fontSize: 9, color: 'FFFFFF' })

  // try-it card
  s.addShape(pres.ShapeType.roundRect, { x: 7.72, y: 3.36, w: 1.86, h: 1.7, rectRadius: 0.08, fill: { color: 'FFFFFF' }, line: { color: 'FFFFFF', width: 0 } })
  s.addImage({ path: IMG('qr_app.png'), x: 8.13, y: 3.44, w: 1.04, h: 1.04, altText: 'QR code to the live Accel Saathi app', hyperlink: { url: LIVE } })
  txt(s, [run('Try it live', { bold: true, color: HEX.accent1, breakLine: true, hyperlink: { url: LIVE } }), run('udyam.openforge.online', { color: HEX.dk1, hyperlink: { url: LIVE }, breakLine: true }), run('Deployed · 10 languages', { color: HEX.dk2, fontSize: 7.5 })],
    { x: 7.76, y: 4.55, w: 1.78, h: 0.46, fontSize: 8.5, align: 'center' })
  if (!VIDEO) console.warn('VIDEO_URL is not set: the cover has no video link yet (nothing is printed in its place)')
  const VIDEO_SHORT = VIDEO.replace(/^https?:\/\//, '')
  if (VIDEO) txt(s, [run('► DEMO VIDEO (2½ min): ', { bold: true, color: 'FFFFFF', hyperlink: { url: VIDEO } }), run(VIDEO, { color: 'FF8A8A', underline: true, hyperlink: { url: VIDEO } })],
    { x: 0.62, y: 5.22, w: 4.8, h: 0.2, fontSize: 9, color: 'FF8A8A' })
  if (VIDEO && !require('fs').existsSync(IMG('qr_video.png'))) throw new Error('run make_qr.js with the video link first')
  if (VIDEO) {  // the demo video card, beside the live app's: a QR plus the link written out, so it reads as a video
    s.addShape(pres.ShapeType.roundRect, { x: 5.0, y: 3.9, w: 2.6, h: 1.16, rectRadius: 0.08, fill: { color: 'FFFFFF' }, line: { color: 'FFFFFF', width: 0 } })
    s.addImage({ path: IMG('qr_video.png'), x: 5.08, y: 3.98, w: 1.0, h: 1.0, altText: 'QR code to the demo video on YouTube', hyperlink: { url: VIDEO } })
    txt(s, [
      run('► DEMO VIDEO', { bold: true, color: HEX.accent1, fontSize: 11, breakLine: true, hyperlink: { url: VIDEO } }),
      run('2½ minutes · YouTube', { color: HEX.dk1, fontSize: 8, breakLine: true }),
      run(VIDEO_SHORT, { color: HEX.accent1, fontSize: 8.5, underline: true, breakLine: true, hyperlink: { url: VIDEO } }),
      run('Click or scan to watch', { color: HEX.dk2, fontSize: 7.5 }),
    ], { x: 6.16, y: 4.04, w: 1.4, h: 0.9, valign: 'middle' })
  }
  s.addNotes('Accel Saathi answers Project Udyam Digital. One line: a pharmacy owner sends one message in her own language and leaves with a priced, verified, booked order, then never has to call to chase it. The three numbers are the modelled results on slide 8, each built from Accel\'s own leads data: half of the journey losses removed at each step, with every other loss kept; cost per activation includes our running costs (cloud, model, e-KYC, WhatsApp); with a 5-person product team (about 30 lakh a quarter, our estimate) it is about 11,700 at this lead volume, falling as leads grow. The QR opens the live build; the partner console is at /#/console.')
}

// ======================================================================
// 1. Problem and signals
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Accel loses small businesses to the journey, not to demand', { placeholder: 'title' })
  sub(s, 'THE PROBLEM', 'Apr–Jun 2026: 5,000 leads, 368 activated (7.4%). ₹35.6 lakh of ₹55.4 lakh spent went on leads never won.')

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
    ['9.6% vs 2.0%', 'activation with vs without a GSTIN (4.7×)', 'GSTIN first: one number fills and verifies the profile'],
    ['5.9% → 27.9%', '6-month churn after 1 vs 5 status chases (small samples: 34 and 43)', 'WhatsApp update at every stage; STATUS by message'],
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
  s.addNotes('All numbers from smb_leads.csv (5,000 leads, Apr to Jun 2026). Acquisition spend 55.4 lakh in total, 35.6 lakh of it on leads that dropped. 1,583 of the 4,632 lost leads (34%) left for reasons the journey causes: no time for a visit 531, visit not scheduled 296, documents and paperwork 273 (missing GST/Udyam 94, paperwork too long 79, signatory unavailable 53, details mismatch 47), quote too complex 206, quote too slow 179, install over 21 days 98. Days are the average gaps between stage dates for the 368 activated customers. Churn by status chases: 2 of 34 customers with one chase churned, 12 of 43 with five; a link, not proof of cause, so the pilot A/B tests it.')
}

// ======================================================================
// 2. Segments, bundles and channels (Q1)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Win offices first, shops on self-serve, chains with the field force', { placeholder: 'title' })
  sub(s, 'Q1 · SEGMENTS AND BUNDLES', 'Ranked on the leads data; each bundle is our advisor\'s real output (12-month price, before GST).')

  const head = ['Segment, in order', 'Share of leads', 'Activation', 'Cost per activation', 'Payback on revenue', '6-month churn', 'Contract', 'How they buy', 'Example bundle from our advisor']
    .map((t) => ({ text: t, options: H }))
  const seg = (name, wave) => [run(name, { bold: true, breakLine: true }), run(wave, { color: HEX.accent1, fontSize: 8.5, bold: true })]
  const ex = (who, what, price) => [run(who, { bold: true }), run(what), run(price, { bold: true, color: HEX.accent1 })]
  const rows = [
    [seg('Professional offices', '1st · the pilot starts here'), '25%', '11.1%', '₹10,695', '1.6 mo', '13.8%', '12 months', 'Self-serve; a call back when asked',
      ex('Dental clinic, Pune, 8 staff: ', 'fibre 300, 2 mobile lines, email and security for 5, cloud backup · ', '₹4,936/mo')],
    [seg('Micro retail & services', '2nd · self-serve alongside'), '54%', '4.1%', '₹20,007', '8.1 mo', '22.7%', '12 months', 'Self-serve on WhatsApp or the app; no visit',
      ex('Pharmacy, Jaipur, 4 staff, UPI fails, a theft: ', 'fibre 100, 2 mobile lines, billing tablet, 2 CCTV, backup internet · ', '₹3,593/mo')],
    [seg('Small multi-site', '3rd · at scale, assisted'), '15%', '11.0%', '₹15,614', '0.6 mo', '10.8%', '12 months', 'Advisor quotes; field confirms each site',
      ex('Restaurant chain, 5 outlets: ', 'fibre 300 × 5, SD-WAN, failover, POS, CCTV, guest Wi-Fi · ', '₹33,819/mo')],
    [seg('Small manufacturers', '4th · field-led'), '6%', '12.8%', '₹15,324', '1.0 mo', '8.1%', '24 months', 'Field-led; advisor prices it on the visit',
      ex('Auto-parts plant, 80 staff: ', '20 Mbps leased line, firewall, 8 machine IoT, CCTV, email · ', '₹19,811/mo')],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci === 4 ? { bold: true, color: i === 1 ? HEX.accent1 : HEX.accent3, align: 'center' } : ci === 6 ? { bold: true, align: 'center' } : ci >= 1 && ci <= 5 ? { align: 'center' } : {})))
  table(s, [head, ...rows], { x: 0.45, y: 1.5, w: 9.1, colW: [1.38, 0.55, 0.65, 0.74, 0.72, 0.6, 0.66, 1.18, 2.62], rowH: [0.36, 0.52, 0.52, 0.52, 0.52] })

  const cards = [
    ['Shops only pay back digitally', '₹20,007 to win a ₹2,470 bundle is 8 months of revenue. At our ₹5,000 target, self-serve pays back in 2. Basic starts at ₹1,448 (fibre and a SIM).'],
    ['Field force moves up-market', 'Chains and plants pay back in a month and bring 73% of revenue. Field visits go there; shops and offices close on their own.'],
    ['Contract by segment', '12 months for shops, offices and chains; 24 for plants (same churn, and 62% already choose it). No 6-month deals: 2 of 3 churned. 24 months is offered only as a lower monthly price.'],
  ]
  cards.forEach(([h, b], i) => {
    const x = 0.45 + i * 3.075
    box(s, x, 4.02, 2.95, 1.08, C.background2)
    txt(s, h, { x: x + 0.13, y: 4.08, w: 2.7, h: 0.24, fontSize: 10.5, bold: true, color: C.accent1 })
    txt(s, b, { x: x + 0.13, y: 4.34, w: 2.72, h: 0.72, fontSize: 9, color: C.text1 })
  })
  s.addNotes('Segment metrics from smb_leads.csv. Cost per activation = all acquisition spend in the segment / activations in it. Payback = cost per activation / median monthly bundle of activated customers, in months of revenue (not margin). Revenue share of activated bundles: multi-site 57%, professional 21%, manufacturers 16%, micro 6%. Example bundles are the advisor\'s own output on product_catalogue.csv at 12-month prices, before GST, as the app shows them first (3 Nov build, Recommended level); on 24 months they are 4,316 / 3,093 / 30,869 / 16,822. Micro owners spend a median 925 a month on telecom today, so we never claim a saving; the advisor offers a lighter bundle in one tap and sells on what the bundle fixes (UPI drops, theft). The demo persona is a shop because it is the hardest case: the smallest budget and the most price sensitive. The pharmacy owner told the advisor that UPI fails at rush hour and she had a theft, so billing, backup internet and CCTV are in; without those problems the advisor pre-ticks billing only (what 9 pharmacies on Accel mostly kept): fibre 100, 2 lines and billing for 2,546 a month. Order of segments: offices first (11.1% activation, 1.6-month payback, already self-serve), shops self-serve alongside in the same cities, chains at scale with field site checks, plants stay field-led. Contracts: in the data only chains and plants ever signed 24 months; within chains, 24-month customers churned more (15.8% of 38 vs 6.7% of 45) and plants churn the same either way (8.7% vs 7.1%), so the overall 13.1% vs 15.1% is a mix effect, not proof that 24 months keeps customers. So 12 months is the default for shops, offices and chains, 24 for plants, and 24 months is shown only as a lower monthly price. No 6-month deals: 2 of 3 churned.')
}

// ======================================================================
// 3. Priya's journey (Q2 and the build)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Priya goes from one message to a booked installation in 15 minutes', { placeholder: 'title' })
  sub(s, 'Q2 + Q3 · THE JOURNEY, BUILT', 'Coral Medicals, Jaipur: our hardest, lowest-paying segment. Live-app screens; 15 min is our timed run.')
  // five screens, cropped to the card that matters so a judge can read them
  const cards = [
    ['c_gstin.png', 'One line, profile filled', 'Her GSTIN fills the profile; it asks "is this you?" first.'],
    ['c_why.png', 'Built on her problems', '"UPI fails" and "theft" add backup and 2 cameras: ₹2,546 → ₹3,593.'],
    ['c_kyc.png', 'KYC in 2 minutes', 'DigiLocker and Aadhaar OTP, checked line by line. No paper.'],
    ['c_tracker.png', 'A tracker, not calls', 'Her install slot, a date per service, WhatsApp at each step.'],
    ['c_onebill.png', 'One bill, one number', '5 services, ₹4,240 a month with GST, one support number.'],
  ]
  const gap = 0.12, cw = (9.1 - 4 * gap) / 5, chh = cw * 900 / 780, top = 1.5
  cards.forEach(([img, name, cap], i) => {
    const x = 0.45 + i * (cw + gap)
    s.addImage({ path: IMG(img), x, y: top, w: cw, h: chh, altText: `${name}: screen from the Accel Saathi build` })
    // the number sits beside the caption, not on the screen, so no text on the screen is hidden
    const cy = top + chh + 0.08
    badge(s, i + 1, x, cy)
    txt(s, name, { x: x + 0.36, y: cy, w: cw - 0.36, h: 0.3, fontSize: 9.5, bold: true, color: C.accent1, valign: 'middle', margin: 0 })
    txt(s, cap, { x, y: cy + 0.33, w: cw, h: 0.44, fontSize: 8.5, color: C.text1, margin: 0 })
  })
  // before and after, in one strip
  const sh = 0.62, sy = 5.1 - sh
  box(s, 0.45, sy, 3.2, sh, C.background2)
  txt(s, lines([run('TODAY', { bold: true, color: HEX.dk2, fontSize: 8, charSpacing: 1 }),
    run('17.6 days · 3 calls to chase · a 4-day quote · a bill per product', { fontSize: 9, color: HEX.dk1 })]), { x: 0.57, y: sy + 0.04, w: 3.0, h: sh - 0.08, valign: 'middle' })
  box(s, 3.75, sy, 3.6, sh, C.accent1)
  txt(s, lines([run('ACCEL SAATHI', { bold: true, color: 'FFFFFF', fontSize: 8, charSpacing: 1 }),
    run('15 min to a booked install · live in ~5 days · 0 calls · 1 bill', { fontSize: 9, bold: true, color: 'FFFFFF' })]), { x: 3.87, y: sy + 0.04, w: 3.4, h: sh - 0.08, valign: 'middle' })
  box(s, 7.45, sy, 2.1, sh, C.background2)
  s.addImage({ path: IMG('qr_app.png'), x: 7.5, y: sy + (sh - 0.36) / 2, w: 0.36, h: 0.36, hyperlink: { url: LIVE }, altText: 'QR code to the live app' })
  txt(s, lines([run('Same journey in 10 languages', { bold: true, fontSize: 8.5, color: HEX.accent1 }), run('Try it live', { fontSize: 8.5, bold: true, color: HEX.dk1, hyperlink: { url: LIVE } })]),
    { x: 7.92, y: sy + 0.04, w: 1.6, h: sh - 0.08, valign: 'middle' })
  s.addNotes('Screens are from our app as deployed at https://udyam.openforge.online (a 390 x 844 phone, English). Priya Chauhan, Coral Medicals, GSTIN 08EAHXC5550F1ZF is in mock_gstin_registry.csv and has no Udyam registration, so the app does not ask for one. The same journey runs in 10 languages (English, Hindi, Marathi, Kannada, Gujarati, Telugu, Tamil, Bengali, Punjabi, Malayalam) with voice input and read-aloud, and on the real WhatsApp Cloud API number. 1: GSTIN lookup with a confirm step. 2: at the needs step she taps two of the problems the advisor asks about (UPI fails at rush hour, theft); it ticks billing and backup internet for the first and CCTV for the second, and the why-this-bundle panel quotes her words. 5 services for 3,593 a month on 12 months (3,093 on 24); without the two problems the same pharmacy gets fibre 100, 2 lines and billing for 2,546, close to the 2,470 median micro bundle, so she pays 1,047 more only for what she asked to fix; Basic 3,244 and Complete 4,842 are one tap away; every line opens to why, what it does and what happens without it. 3: DigiLocker + Aadhaar OTP, verified with the checks listed. 4: tracker with stage times and slot booking, shown up to the booked slot; every stage also goes to WhatsApp. In the demo the partner console advances the stages, so their times are the same minute; in production they come from Accel\'s order system. Why a shop: it is our lowest-paying segment (slide 3), so if the journey works for her, offices, where the pilot starts, are easier. 5: the one-bill card after go-live. 15 minutes: about 3 for the chat, 2 for KYC, 1 to e-sign and pick a slot, with room to spare.')
}

// ======================================================================
// 4. The advisor: how it decides, how it sells, proof (Q2, Q3, technical depth)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('The advisor sells like a good salesperson and never invents a price', { placeholder: 'title' })
  sub(s, 'Q2 · THE ADVISOR', 'The AI understands her; rules, real customers and the catalogue decide. Try these lines live.')

  // how it decides
  label(s, 'HOW IT DECIDES', 0.45, 1.5, 2.6)
  const steps = [
    ['Understand', 'Her words, in any of 10 languages, become facts and problems.'],
    ['Check', 'Rules on all 25 services. Every ₹ is the catalogue\'s.'],
    ['Rank', 'Learned from 368 customers; her problems go first.'],
    ['Level', 'Basic, Recommended, Complete, with a "why" in her words.'],
  ]
  steps.forEach(([h, b], i) => {
    const y = 1.72 + i * 0.68
    box(s, 0.45, y, 2.55, 0.62, i === 2 ? C.accent4 : C.background2)
    badge(s, i + 1, 0.52, y + 0.07)
    txt(s, lines([run(h, { bold: true, fontSize: 9.5, color: C.text1 }), run(b, { fontSize: 8, color: C.text2 })]), { x: 0.9, y: y + 0.05, w: 2.04, h: 0.55 })
  })

  // it sells
  label(s, 'IT SELLS, NOT JUST ANSWERS', 3.17, 1.5, 3.6)
  const chats = [
    ['This is too expensive for me', 'I understand, every rupee counts. ₹3,593/month is about ₹120 a day for 5 services on one bill. Your choice: trim the extras ₹3,244 · the same bundle on 24 months ₹3,093 · or tell me a budget.',
      ['Trim extras: ₹3,244/mo', '24 months: ₹3,093/mo', 'Keep it, go ahead']],
    ['My nephew set up Jio for 399, why should I pay you?', 'Fair question. I can\'t see that plan, but your ₹3,593 gets 100 Mbps fibre steady enough for UPI and billing, 5 services on one bill, live in about 5 days. Want only the essentials? Basic is ₹3,244.',
      ['Basic: ₹3,244/mo', 'Make it cheaper', '✓ Go ahead']],
  ]
  const cx = 3.17, cw = 3.6
  chats.forEach(([me, bot, chips], i) => {
    const y = 1.72 + i * 1.3
    const mw = Math.min(cw - 0.5, 0.2 + me.length * 0.058)
    s.addShape(pres.ShapeType.roundRect, { x: cx + cw - mw, y, w: mw, h: 0.22, rectRadius: 0.08, fill: { color: HEX.dk1 }, line: { color: HEX.dk1, width: 0 } })
    txt(s, me, { x: cx + cw - mw + 0.08, y, w: mw - 0.12, h: 0.22, fontSize: 8, color: C.background1, valign: 'middle' })
    box(s, cx, y + 0.28, cw - 0.25, 0.86, C.background2)
    txt(s, lines([run(bot, { fontSize: 8.5, color: C.text1 }),
      run(chips.map((c) => `[ ${c} ]`).join('  '), { fontSize: 8, bold: true, color: HEX.accent1 })]), { x: cx + 0.08, y: y + 0.33, w: cw - 0.4, h: 0.78 })
  })
  txt(s, 'Never changes her bundle without asking; every reply ends with a next step.', { x: cx, y: 4.3, w: cw, h: 0.18, fontSize: 8, italic: true, color: C.text2 })

  // personal, not one-size: the same shop with and without her problems (the back-test tie is on A5)
  label(s, 'PERSONAL, NOT ONE-SIZE', 6.95, 1.5, 2.6)
  const ba = [
    ['Same pharmacy, no problems', 'Fibre 100, 2 lines, billing', '₹2,546/mo', C.background2],
    ['She says "UPI fails" and "theft"', '+ backup internet, + 2 cameras', '₹3,593/mo', C.accent4],
  ]
  ba.forEach(([h, b, p], i) => {
    const y = 1.72 + i * 0.55
    box(s, 6.95, y, 2.6, 0.5, p === '₹3,593/mo' ? C.accent4 : C.background2)
    txt(s, lines([run(h, { bold: true, fontSize: 8.5, color: C.text1 }), run(b, { fontSize: 8, color: C.text2 })]), { x: 7.03, y: y + 0.05, w: 1.75, h: 0.42 })
    txt(s, p, { x: 8.7, y: y + 0.05, w: 0.8, h: 0.42, fontSize: 10.5, bold: true, color: i ? C.accent1 : C.text1, align: 'right', valign: 'middle' })
  })
  txt(s, 'Her own problems add what no best-seller list can: backup and 2 cameras. The learned ranking ties segment best-sellers (A5).',
    { x: 6.95, y: 2.78, w: 2.6, h: 0.24, fontSize: 7, color: C.text2 })

  label(s, 'PROOF IT WORKS', 6.95, 3.02, 2.6)
  const proof = [['92/92', 'advisor checks, AI on and off, 28 sales moments'], ['100/100', 'the journey in all 10 languages, AI off'],
    ['12/12', 'KYC specimens judged right'], ['106/106', 'WhatsApp, privacy, partner, KYC, ranking']]
  proof.forEach(([n, t], i) => {
    const x = 6.95 + (i % 2) * 1.32, y = 3.22 + Math.floor(i / 2) * 0.62
    box(s, x, y, 1.26, 0.57, C.accent4)
    txt(s, lines([run(n, { fontSize: n.length > 5 ? 12 : 13, bold: true, color: C.accent1 }), run(t, { fontSize: 7, color: C.text1 })]), { x: x + 0.07, y: y + 0.03, w: 1.14, h: 0.53 })
  })

  label(s, 'SMART KYC AND PRIVACY BY DESIGN · DPDP ACT 2023', 0.45, 4.5, 6)
  const chips = ['GSTIN and Udyam registry, DigiLocker, Aadhaar OTP', 'OCR re-read with checksums; 20+ checks', 'Encrypted before storage (AES-256-GCM)',
    'Tokens, not data, sent to any AI', 'One consent switch per purpose', 'Erase my data, any time']
  const cw6 = (9.1 - 5 * 0.08) / 6
  chips.forEach((c, i) => {
    const x = 0.45 + i * (cw6 + 0.08)
    box(s, x, 4.7, cw6, 0.4, C.background2)
    txt(s, c, { x: x + 0.05, y: 4.7, w: cw6 - 0.1, h: 0.4, fontSize: 8, bold: true, color: C.text1, align: 'center', valign: 'middle' })
  })
  s.addNotes('The LLM only turns free text into structured facts, an action and a language; it never picks a product or a price. Prototype routing: Groq (gpt-oss-120b) first for English and Hindi, Gemini Flash-Lite first for the other 8 languages, each falling back to the other on 429/5xx, then to rules; production runs the same open-weights model in Accel\'s private cloud. ' +
    'Selling: a price complaint gets ways down with prices (Basic, a lighter bundle, 24 months, a budget) and nothing changes until she picks; a competitor price gets what her bundle includes and the cheapest honest alternative; "let me think" saves the bundle (link or WhatsApp) and asks what holds her back; "ask my partner" gives a summary to share; "which do you recommend" gives reasons from her problems and from what similar customers kept. These replies are rules-based, so they are instant and identical with the AI off. The two replies are Priya\'s, from the build (4-person Jaipur pharmacy, phone hotspot), shortened to fit the slide; the buttons are exactly as shown; try the same lines on the live site. No invented prices: any ₹ amount in an AI reply that is not in her quote is removed before she sees it. ' +
    'Ranking (ranker.py, backtest.py): each service\'s share among similar activated customers, business type pulled toward its segment with a prior of 30 customers, churned customers weighted 0.5. Leave-one-out back-test on all 368 activated customers, same bundle size for every method: precision 63.2% learned vs 60.0% hand-written rules vs 37.2% one popular bundle; recall 67.1 / 65.2 / 43.1; F1 0.651 / 0.625 / 0.399. Best-sellers per segment score 63.1% (F1 0.650), a tie: Accel\'s purchases differ mainly by segment, so learning cannot beat that on this data; what it adds is business type where there is data, retention (churned customers count half) and the owner\'s own problems, which no average can know. Appendix A5 has the method. ' +
    'Tests in backend/tests, run by GitHub Actions on every push: tests/eval/run_rag_eval.py (83 labelled owner questions in 10 languages: right section first 76.6%, in the top 4 sent to the AI 93.5%, MRR 0.85, vs 54.5% / 64.9% / 0.60 for plain BM25; Tamil is weakest at 67% top 4; with the live AI: 0% answers with a number not in the sources, 96.2% in the owner\'s language, 93.8% cite a correct source, 5 of 6 off-topic questions declined, about 1.8 s typical and 4 s slow; a typical AI call is about 3,000 tokens in and 130 out, and the rules handle most turns, so at public paid prices an advisor conversation costs about ₹0.11, ₹0 on free plans), run_retrieval_eval (66 questions after the keyword fixes, plus 16 written later and never tuned on: 12 of 16 found; privacy questions in Malayalam, Telugu and Tamil still miss), run_advisor_scenarios 92 (also run with the live AI; turns the free AI could not serve fell back to rules as designed), run_language_checks 100 (10 languages x 10 checks, AI off), run_kyc_pack 12, run_whatsapp_orders 59, run_privacy_checks 17, run_partner_flows 17, run_kyc_flows 10, run_ranking_eval 3; 59 + 17 + 17 + 10 + 3 = 106. Security: store.py seals every record with AES-256-GCM before it is written, phone-number keys become HMAC tokens; llm.py swaps phone, GSTIN, PAN, Aadhaar, e-mail and names for tokens before any AI call.')
}

// ======================================================================
// 5. Field force and partners (Q4)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('The field force and partners sell more, not less', { placeholder: 'title' })
  sub(s, 'Q4 · FIELD FORCE AND PARTNERS', 'The advisor does the paperwork; partners keep the sale and are paid for customers who stay.')

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
  s.addShape(pres.ShapeType.rect, { x: 3.72, y: y2, w: cw5, h: cw5 * 320 / 914, fill: { color: 'FFFFFF' }, line: { color: HEX.accent5, width: 0.75 } })
  s.addImage({ path: IMG('con_sales_crop.png'), x: 3.72, y: y2, w: cw5, h: cw5 * 320 / 914, altText: 'Partner sales and commission table: Ganga Connect has 2 sales, 1 protected' })
  const y3 = y2 + cw5 * 320 / 914 + 0.06
  txt(s, 'Ganga Connect starts a chat for an owner; the QR hands it to her phone. Its sales, protected sales and commission update live.',
    { x: 3.72, y: y3, w: cw5, h: 0.4, fontSize: 8.5, color: C.text2 })
  box(s, 3.72, 4.34, cw5, 0.78, C.accent4)
  txt(s, lines([run('Field time goes where it pays', { bold: true, color: C.accent1, fontSize: 10 }),
    run('Field sales costs ₹24,335 per activation; a shop takes 8 months to pay that back. Freed visits go to chains and plants (73% of revenue). In the pilot, every self-serve sale in a rep\'s area counts toward their target.', { fontSize: 8 })]),
  { x: 3.82, y: 4.39, w: 3.02, h: 0.7 })

  label(s, 'WHY PARTNERS WILL PUSH IT', 7.12, 1.5, 2.5)
  const why = [
    ['Commission protection', 'The owner confirms her number by a code on her own phone. That number stays the partner\'s for 30 days, even if she orders alone later. A typed-in number earns nothing.'],
    ['Pay tied to retention', 'One month\'s rental per sale, half when live, half after 6 months: ₹2,470 for a typical shop, ₹6,900 at the median. The advisor does the paperwork, so a partner serves more owners a day.'],
    ['Counter QR', 'Each partner\'s QR opens the app tagged to them, so walk-ins they send are credited too.'],
  ]
  why.forEach(([h, b], i) => {
    const y = 1.72 + i * 1.13
    box(s, 7.12, y, 2.43, 1.05, C.background2)
    txt(s, lines([run(h, { bold: true, fontSize: 10, color: C.text1 }), run(b, { fontSize: 8.5, color: C.text2 })]), { x: 7.22, y: y + 0.07, w: 2.26, h: 0.95 })
  })
  s.addNotes('Channel costs: acquisition spend per activation by lead_source in smb_leads.csv (field sales 24,335; channel partner 20,851; website 6,352; inbound 5,113; referral 4,099; WhatsApp campaign 4,026). Assisted mode, owner-code consent, 30-day protection and the commission ledger are built and tested (backend/tests/run_partner_flows.py, 17 checks: wrong code refused, 5 wrong tries lock the code, unverified numbers earn nothing, referral QR credited, protection across a new session). The commission rate is a proposal for the pilot. Today ₹16.9 lakh a quarter goes to partner-sourced leads for 81 activations; at one month\'s rental (₹6,900 median) the 167 partner sales in our model (22% of 760, today\'s share) cost ₹11.5 lakh, inside that budget, which is why the impact model keeps spend flat. What partners earn per sale today is not in the data, so we do not claim a rise per sale; the gain for a partner is volume, because an assisted chat takes about 15 minutes instead of a visit and the sale stays theirs.')
}

// ======================================================================
// 6. Competitive analysis
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Rivals sell plans or single products; we sell the whole setup, self-serve', { placeholder: 'title' })
  sub(s, 'COMPETITIVE ANALYSIS', 'What a small-business owner can buy today, and how; from official pages and press, checked 3–4 Nov 2026.')

  // a 2x2 map instead of a self-scored table: where each rival sits for a small-business owner
  label(s, 'WHERE EACH RIVAL SITS FOR AN OWNER', 0.45, 1.5, 3.6)
  const mx = 0.45, my = 1.74, mw = 3.55, mh = 2.32
  box(s, mx, my, mw, mh, C.background2)
  s.addShape(pres.ShapeType.roundRect, { x: mx + mw / 2, y: my, w: mw / 2, h: mh / 2, rectRadius: 0.06, fill: { color: HEX.accent4 }, line: { color: HEX.accent4, width: 0 } })
  s.addShape(pres.ShapeType.line, { x: mx + mw / 2, y: my + 0.05, w: 0, h: mh - 0.1, line: { color: HEX.accent6, width: 0.75, dashType: 'dash' } })
  s.addShape(pres.ShapeType.line, { x: mx + 0.05, y: my + mh / 2, w: mw - 0.1, h: 0, line: { color: HEX.accent6, width: 0.75, dashType: 'dash' } })
  txt(s, '▲ Self-serve, in minutes', { x: mx + 0.06, y: my + 0.04, w: 1.7, h: 0.16, fontSize: 7, bold: true, color: C.text2 })
  txt(s, '▼ A visit, a store or a call', { x: mx + 0.06, y: my + mh - 0.2, w: 1.7, h: 0.16, fontSize: 7, bold: true, color: C.text2 })
  txt(s, '←  One product', { x: mx, y: my + mh + 0.03, w: mw / 2 - 0.05, h: 0.16, fontSize: 7, bold: true, color: C.text2, align: 'right' })
  txt(s, 'The whole setup  →', { x: mx + mw / 2 + 0.05, y: my + mh + 0.03, w: mw / 2, h: 0.16, fontSize: 7, bold: true, color: C.text2 })
  // [name, what they sell, x 0..1 (one product .. whole setup), y 0..1 (visit .. self-serve), label on the left?]
  const dots = [
    ['PhonePe, Paytm', 'UPI or a sound-box, on the phone', 0.08, 0.8, false],
    ['Local ISP or cable', 'a line from someone next door', 0.08, 0.3, false],
    ['Tata Tele Business', 'cloud telephony and SaaS, sales-led', 0.36, 0.14, false],
    ['Vi Business', 'plans and an assessment', 0.42, 0.45, false],
    ['Jio Business', 'broadband + 3 apps, cheapest entry', 0.5, 0.62, false],
    ['Accel today', 'the whole setup, by visits: 17.6 days', 0.95, 0.24, true],
  ]
  const at = (fx, fy) => [mx + 0.12 + fx * (mw - 0.24), my + 0.12 + (1 - fy) * (mh - 0.24)]
  dots.forEach(([n, w, fx, fy, left]) => {
    const [x, y] = at(fx, fy)
    s.addShape(pres.ShapeType.ellipse, { x: x - 0.06, y: y - 0.06, w: 0.12, h: 0.12, fill: { color: HEX.dk1 }, line: { color: 'FFFFFF', width: 1 } })
    txt(s, lines([run(n, { bold: true, fontSize: 7.5, color: C.text1 }), run(w, { fontSize: 6.5, color: C.text2 })]),
      { x: left ? x - 1.58 : x + 0.1, y: y - 0.1, w: 1.5, h: 0.3, align: left ? 'right' : 'left' })
  })
  {
    const [x1, y1] = at(0.95, 0.24), [x2, y2] = at(0.95, 0.86)
    s.addShape(pres.ShapeType.line, { x: x1, y: y2 + 0.12, w: 0, h: (y1 - 0.1) - (y2 + 0.12), line: { color: HEX.accent1, width: 1.5, dashType: 'dash', beginArrowType: 'triangle' } })
    s.addShape(pres.ShapeType.ellipse, { x: x2 - 0.09, y: y2 - 0.09, w: 0.18, h: 0.18, fill: { color: HEX.accent1 }, line: { color: 'FFFFFF', width: 1.5 } })
    txt(s, lines([run('Accel Saathi', { bold: true, fontSize: 8.5, color: C.accent1 }), run('the whole setup, self-serve: the gap we fill', { fontSize: 6.5, color: C.text1 })]),
      { x: x2 - 1.86, y: y2 - 0.12, w: 1.74, h: 0.32, align: 'right' })
  }

  // what the prototype really has, so the map is not read as a finished product
  label(s, 'OUR SIDE, HONESTLY', 4.18, 1.5, 2.4)
  box(s, 4.18, 1.74, 2.42, 1.16, C.background2)
  txt(s, lines([run('Built and live', { bold: true, fontSize: 8.5, color: C.accent3 }),
    run('Advisor in 10 languages, catalogue prices, KYC checks, tracker, real WhatsApp (test number), partner console', { fontSize: 7.5, color: C.text1 })]),
  { x: 4.26, y: 1.79, w: 2.28, h: 1.08 })
  box(s, 4.18, 2.96, 2.42, 1.1, C.background2)
  txt(s, lines([run('Needs Accel to switch on', { bold: true, fontSize: 8.5, color: 'B26A00' }),
    run('Live GST and Udyam registries (we use the case\'s mock ones), an e-KYC licence (KUA) for Aadhaar, one-bill billing, a verified WhatsApp sender', { fontSize: 7.5, color: C.text1 })]),
  { x: 4.26, y: 3.01, w: 2.28, h: 1.02 })

  // the price row, kept: each rival's cheapest public way in
  box(s, 0.45, 4.3, 6.15, 0.36, C.background2)
  txt(s, [run('Cheapest way in, public price a month:  ', { bold: true, color: C.text1 }), run('Jio Max 801, 100 Mbps + 3 apps · Vi ₹349 business SIM · PhonePe ₹125 sound-box · ', { color: C.text1 }),
    run('Saathi Basic ₹1,448, fibre + a SIM', { bold: true, color: C.accent1 })], { x: 0.53, y: 4.3, w: 6.0, h: 0.36, fontSize: 7.5, valign: 'middle' })
  txt(s, 'Placement is our reading of official pages and press, checked 3–4 Nov 2026: jio.com/business, Business Broadband Max with JioMeet, JioGate, JioAttendance (Max 801 at 100 Mbps: TelecomTalk, 13 Mar 2026); myvi.in/business, ReadyForNext assessment, business postpaid from ₹349 (TelecomTalk, 13 Apr 2025); TTBS sells Smartflo cloud telephony, no mobile network since 2019; phonepe.com merchant help, SmartSpeaker ₹125 a month. Accel is the case\'s fictional operator.',
    { x: 0.45, y: 4.72, w: 6.15, h: 0.4, fontSize: 6.5, color: C.text2 })

  label(s, 'WHAT THEY DO BETTER, AND OUR ANSWER', 6.8, 1.5, 2.8)
  const wins = [
    ['Jio Business: price and brand', 'We win on fit, not price: a right-sized bundle, the 24-month saving shown, cheaper in one tap.'],
    ['Local ISPs: cheapest, next door', '325 lost leads were "locked in", 207 went "cheaper". Local partners sell through us and keep the sale.'],
    ['Vi and TTBS: advice, cloud tools', 'Vi assesses, TTBS sells telephony. We go from advice to KYC and order in one flow.'],
    ['Payment apps: live in minutes', 'Owners sign up for UPI in minutes, for one product. We match that speed for the whole setup.'],
  ]
  wins.forEach(([h, b], i) => {
    const y = 1.72 + i * 0.68
    box(s, 6.8, y, 2.75, 0.62, C.background2)
    txt(s, lines([run(h, { bold: true, fontSize: 9, color: C.text1 }), run(b, { fontSize: 8, color: C.text2 })]), { x: 6.9, y: y + 0.05, w: 2.58, h: 0.56 })
  })
  box(s, 6.8, 4.45, 2.75, 0.65, C.accent1)
  txt(s, lines([run('Our moat', { bold: true, fontSize: 9, color: 'FFFFFF' }), run('38% of leads already use Accel and convert at 9.2% vs 6.2% on other providers. Their ID KYC is reused: no new ID documents.', { fontSize: 8, color: 'FFFFFF' })]),
    { x: 6.9, y: 4.49, w: 2.58, h: 0.6 })
  s.addNotes('The map places each rival by what an owner can see or do on public pages, not by internal capability: across, how much of the setup one purchase covers (a UPI sound-box or a single line, up to mobile, fibre and business apps together); up, how far an owner gets without a visit, a store or a call. Accel today sells the whole setup through field visits (17.6 days on average in the data); Saathi moves it to self-serve. Our side is a prototype: the box says what is built and live and what needs Accel to switch on. Jio Business sells broadband plans with its own apps (JioAttendance, JioMeet, JioGate). Vi Business offers the Ready For Next assessment with Dun & Bradstreet. Tata Tele Business Services sells Smartflo cloud telephony and SMB SaaS but has had no mobile network of its own since 2019. In our data, 325 lost leads were locked in with their provider and 207 left for a cheaper competitor. Accel mobile users: "Accel" and "Accel (mobile only)" current_provider, 1,890 of the 5,000 leads (38%: 1,505 mobile-only, 385 broadband), 9.1 to 9.2% activation vs 6.2% for leads on other providers (Competitor A 6.5%, Competitor B 7.4%, local ISP 5.4%). Their ID KYC is reused (the app asks "I already use an Accel mobile number"); business details such as the GSTIN are still checked. Payment apps (PhonePe for Business, Paytm for Business) sign a merchant up on the phone with e-KYC, for one product (UPI, a soundbox or a card machine) and with their own field agents: they set the speed owners now expect, which the case calls digital-first players offering instant sign-up for single products. The price row is each rival\'s cheapest public way in, not a like-for-like bundle: Jio\'s plan name Max 801 and its 100 Mbps and apps are from TelecomTalk (13 Mar 2026); Vi business postpaid starts at ₹349 (TelecomTalk, 13 Apr 2025); PhonePe SmartSpeaker monthly plan ₹125 plus ₹318 setup (phonepe.com merchant help). Our ₹1,448 is the advisor\'s Basic for a 3-person kirana (fibre 100 + one business SIM, 12 months, before GST). Claims re-checked on 4 Nov 2026.')
}

// ======================================================================
// 7. Impact, metrics, rollout, risks (Q5)
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'CONTENT' })
  s.addText('Twice the customers from the same leads, at half the running cost each', { placeholder: 'title' })
  sub(s, 'Q5 · IMPACT AND METRICS', 'Modelled on one quarter of Accel\'s leads; each target is a go/no-go gate for the pilot.')

  label(s, 'MODELLED: EVERY QUARTER, SAME LEADS', 0.45, 1.5, 3.2)
  const big = [['368 → 760', 'activations a quarter, same spend: +392 ≈ ₹3.2 crore a year'],
    ['₹15,053 → ₹7,746', 'per activation: (₹55.4 lakh same spend + ₹3.5 lakh to run) / 760'],
    ['≈ ₹11,700 all-in', 'with a 5-person team (₹30 lakh a quarter); falls as leads grow']]
  big.forEach(([n, t], i) => {
    const y = 1.72 + i * 0.52
    box(s, 0.45, y, 3.1, 0.48, i ? C.background2 : C.accent4)
    txt(s, n, { x: 0.57, y: y + 0.03, w: 2.9, h: 0.25, fontSize: 14, bold: true, color: C.accent1 })
    txt(s, t, { x: 0.57, y: y + 0.27, w: 2.92, h: 0.22, fontSize: 8, color: C.text1 })
  })
  txt(s, [run('Assumption: ', { bold: true, color: HEX.dk1 }), run('half the journey losses at each step go; those kept still face every later loss. Half, as the visit (827 of 1,583) is gone, not shortened.', { color: HEX.dk2, breakLine: true }),
    run('Range: ', { bold: true, color: HEX.dk1 }), run('a quarter → 538 (₹10,947); three quarters → 1,045 (₹5,638).', { color: HEX.dk2 })],
    { x: 0.45, y: 3.3, w: 3.1, h: 0.56, fontSize: 7.5 })

  label(s, 'HOW WE MEASURE SUCCESS: TARGET = PILOT GATE', 3.75, 1.5, 4)
  const kpi = [
    ['Lead to activation', '7.4%', '15%', 'Half the visit, quote and paperwork losses removed at each step'],
    ['Lead to live', '17.6 days', '≤ 7 days', '12.8 days of contact, needs, quote and KYC become one sitting'],
    ['Status chases per customer', '3.0', '< 0.5', 'WhatsApp update at every stage; STATUS by message'],
    ['Cost per activation', '₹15,053', '< ₹8,000', '2× activations, running cost incl.; the team cost per customer falls as leads grow'],
    ['6-month churn', '15.2%', '≤ today, by segment', 'Won-back leads are 57% shops (22.7% today); the pilot tracks chases per customer as the early sign'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, { color: ci === 2 ? HEX.accent3 : HEX.dk1, bold: ci === 2 || ci === 0, align: ci === 1 || ci === 2 ? 'center' : 'left' })))
  table(s, [['Metric', 'Today', 'Target', 'Why it is reachable'].map((t, i) => ({ text: t, options: { ...H, align: i === 1 || i === 2 ? 'center' : 'left' } })), ...kpi],
    { x: 3.75, y: 1.72, w: 5.8, colW: [1.38, 0.72, 0.7, 3.0], rowH: [0.28, 0.335, 0.335, 0.335, 0.335, 0.335], margin: [0.02, 0.06, 0.02, 0.06] })

  label(s, 'ROLLOUT, WITH A GATE AT EACH STEP', 0.45, 3.9, 4)
  const phases = [['Pilot · 8 weeks', 'Jaipur and Pune: offices first, shops self-serve alongside; 3 languages; A/B vs the field journey. About ₹30 lakh.', 'Go if 1.5× the field arm\'s conversion, ≤ 7 days, < 1 chase'],
    ['Scale · 2 quarters', 'All 10 languages, tier 1–2 cities, every partner on assisted mode; chains with field site checks.', 'Go if cost per activation < ₹8,000'],
    ['Grow · year 1', 'Bundles for Accel\'s mobile-only business base, GST and Udyam registration help, IoT for plants.', 'Churn ≤ today in every segment']]
  phases.forEach(([h, b, g], i) => {
    const x = 0.45 + i * 1.96
    s.addShape(pres.ShapeType.homePlate, { x, y: 4.1, w: 1.9, h: 0.25, fill: { color: i ? HEX.dk1 : HEX.accent1 }, line: { color: i ? HEX.dk1 : HEX.accent1, width: 0 } })
    txt(s, h, { x: x + 0.08, y: 4.1, w: 1.7, h: 0.25, fontSize: 9, bold: true, color: C.background1, valign: 'middle' })
    txt(s, lines([run(b, { fontSize: 8, color: HEX.dk1 }), run(g, { fontSize: 8, bold: true, color: HEX.accent3 })]), { x, y: 4.4, w: 1.86, h: 0.72 })
  })
  label(s, 'TOP RISKS AND OUR CONTROL', 6.4, 3.9, 3)
  const risks = [['AI says something wrong', 'rules set every price; a person on every screen'],
    ['Partners resist', 'commission protection, the scored call list'],
    ['e-KYC licence', 'Aadhaar OTP needs Accel as a KUA; else DigiLocker'],
    ['2× installs', 'slots capped at crew capacity; install days are a gate'],
    ['Business SIMs', 'each SIM user\'s own Aadhaar OTP, as DoT requires']]
  const rr = []
  risks.forEach(([r, c], i) => { rr.push(run(r + ': ', { bold: true, color: HEX.dk1 })); rr.push(run(c, { color: HEX.dk2, breakLine: i < risks.length - 1 })) })
  txt(s, rr, { x: 6.4, y: 4.08, w: 3.15, h: 0.72, fontSize: 7.5, paraSpaceAfter: 1 })
  txt(s, [run('Our cost estimates: ', { bold: true, color: HEX.dk1 }), run('running Saathi ₹3.5 lakh a quarter = cloud and model ₹3.0 + e-KYC ₹0.2 + WhatsApp and AI ₹0.3; a 5-person team ₹30 lakh a quarter. Pilot ₹30 lakh for 8 weeks.', { color: HEX.dk2 })],
    { x: 6.4, y: 4.82, w: 3.15, h: 0.32, fontSize: 6.5 })
  s.addNotes(`Impact model, re-run on smb_leads.csv: at each funnel step we split today's losses into journey losses (no time for a visit, visit not scheduled, quote too complex or too slow, missing documents, paperwork, signatory, details mismatch, install over 21 days: 1,583 leads) and every other loss (unreachable, not interested, price, locked in, competitor, site not feasible and so on). Saathi removes half of the journey losses at each step; the leads it keeps still face every other loss at today's rates further down. Result: 760 activations a quarter instead of 368, 15.2% conversion. Why half: the biggest journey loss, the visit (531 + 296 = 827 of the 1,583), is removed outright, not shortened, and the quote and KYC become one sitting. Sensitivity: a quarter of the journey losses removed gives 538 (10.8%) at 10,947 each; three quarters gives 1,045 (20.9%) at 5,638; all of them gives 1,401. Acquisition spend stays at 55.4 lakh a quarter and we add 3.5 lakh a quarter to run the service (our estimate: private cloud and open model 3.0 lakh at 1 lakh a month; Aadhaar e-KYC at 20 rupees each under UIDAI's 2019 pricing regulation, about 900 a quarter, 0.2 lakh; WhatsApp utility messages at 0.115 rupees each in India and the AI calls, about 0.15 lakh, rounded up to 0.3). Cost per activation = 58.9 lakh / 760 = 7,746 in running cost. People are not in that figure: a 5-person product team at the pilot's rate (about 30 lakh a quarter, our estimate) makes it 88.9 lakh / 760 = about 11,700 at this data's 5,000 leads, still 22% below today's 15,053 (which includes the field force). The team cost is fixed, so it falls per customer as leads grow, and the model keeps all of today's 55.4 lakh spend even though shops no longer need visits. Installs: 760 activations need about twice today's installs, so the pilot offers only the slots crews can cover and gates on install days. Business SIMs: DoT's business-connection rules need KYC of each SIM user, so each staff member verifies with an Aadhaar OTP on their own phone (production phase). Pilot gate: conversion at least 1.5 times the field arm in the same segment and city, because offices already convert at 11.1%. Revenue: 392 extra customers x 6,900 median bundle x 12 = about 3.2 crore a year; the median, not the mean (12,350), to stay conservative; revenue ignores churn (15.2% in 6 months), while the won-back mix implies about 7,700 a month: the two roughly cancel. Partner commission (one month's rental, 6,900 median, on 22% of sales = 11.5 lakh) fits inside the 16.9 lakh already spent on partner-sourced leads. Shifting the mix to WhatsApp, inbound and referral (4,000 to 5,100 per activation today) is the path to 5,000 in year 1. Pilot budget about 30 lakh for 8 weeks (a 5-person team, cloud, partner onboarding in two cities; our estimate). Churn: the won-back leads are 57% micro shops, whose churn is 22.7% today, so blended churn would rise to about 16.8% at today's segment rates; the target is therefore churn at or below today in each segment, not a blended number. The link between status chases and churn (1 chase 5.9% of 34, 5 chases 27.9% of 43, but 2 chases 14.3% and 3 chases 11.7%) is a hypothesis; an 8-week pilot cannot see 6-month churn, so it tracks chases per customer and first-month complaints. For Priya: 3,593 a month on 12 months (3,093 on 24), live in about 5 days, with no calls.`)
}

// ======================================================================
// Appendix divider: the scored deck ends above; what follows is supporting detail
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'COVER' })
  txt(s, 'PROJECT UDYAM DIGITAL · ACCEL SAATHI', { x: 0.62, y: 2.54, w: 5.6, h: 0.2, fontSize: 9.5, bold: true, color: 'FF8A8A', charSpacing: 2 })
  txt(s, 'APPENDIX', { x: 0.62, y: 2.7, w: 5.8, h: 0.86, fontSize: 60, bold: true, color: 'FFFFFF', charSpacing: 2 })
  txt(s, 'Supporting detail for the jury. Not part of the 7 scored slides.', { x: 0.62, y: 3.72, w: 5.6, h: 0.24, fontSize: 12, bold: true, color: 'FF8A8A' })
  const items = [['A1', 'Architecture'], ['A2', 'Privacy note (DPDP Act 2023)'], ['A3', 'Every signal in the data, and the decision it drove'],
    ['A4', 'Test results and the KYC answer key'], ['A5', 'How the advisor ranks a bundle, and the back-test']]
  items.forEach(([k, v], i) => txt(s, [run(k + '   ', { bold: true, color: 'FF8A8A' }), run(v, { color: 'FFFFFF' })],
    { x: 0.62, y: 4.03 + i * 0.205, w: 5.6, h: 0.2, fontSize: 10 }))
  txt(s, [run('Team TouristGuide_NIT_Jamshedpur', { bold: true }), run('  ·  Sujal Bhatu, Prince Mehta  ·  Airtel Sync 2026')], { x: 0.62, y: 5.1, w: 4.8, h: 0.2, fontSize: 9, color: 'FFFFFF' })
  s.addNotes('Appendix: supporting detail, not scored. A1 architecture, A2 privacy note, A3 data signals and decisions, A4 test results and the KYC answer key, A5 the ranking method and back-test.')
}

// ======================================================================
// Appendix A1: architecture
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A1 · Architecture: the AI understands, rules decide, privacy is built in', { placeholder: 'title' })
  s.addText('One FastAPI service behind HTTPS serves the app, the WhatsApp webhook and the partner console. Live at udyam.openforge.online. Code: github.com/sujalbhatu/udyam-digital (private; shared with the jury on request).', { placeholder: 'sub' })
  s.addImage({ path: IMG('arch.png'), x: 0.6, y: 1.48, w: 8.8, h: 8.8 * 900 / 2400, altText: 'Architecture diagram of Accel Saathi' })
  txt(s, ([
    run('Prototype: ', { bold: true }), run('React + Vite PWA · FastAPI · SQLite, every record encrypted · RapidOCR (ONNX, CPU) · scikit-learn · WhatsApp Cloud API · Groq and Gemini. Runs on a 1 GB VM; the AI is optional.'),
  ]), { x: 0.45, y: 4.7, w: 9.1, h: 0.2, fontSize: 8.5, color: C.text2 })
  txt(s, ([
    run('Production path: ', { bold: true }), run('the same service in Accel\'s private cloud, a managed encrypted database, an open model hosted there, and Accel\'s own e-KYC licence (KUA) for Aadhaar.'),
  ]), { x: 0.45, y: 4.9, w: 9.1, h: 0.2, fontSize: 8.5, color: C.text2 })
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
    ['Security', 'Encrypted before storage: every record sealed with AES-256-GCM, phone-number keys replaced by tokens. HTTPS everywhere; webhooks verified by Meta\'s signature; IDs masked in screens and logs.'],
    ['AI and breaches', 'Personal data becomes tokens before any AI call; images never leave. Production model runs in Accel\'s private cloud. Breaches reported as the DPDP Rules require.'],
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
    ['GSTIN holders activate at 9.6% vs 2.0% without (4.7×)', 'Ask for the GSTIN first; registry fills and verifies the profile'],
    ['Churn 5.9% after 1 status chase vs 27.9% after 5 (2 of 34 vs 12 of 43), not steady between; NPS 7.5 to 6.0', 'WhatsApp update at every stage, STATUS / RESCHEDULE / PROBLEM by message'],
    ['Regional-language leads convert at 6.2% vs 8.0% for Hindi or English', 'Advisor, buttons and WhatsApp in 10 languages, voice in, read-aloud out'],
    ['Referral ₹4,099 and WhatsApp ₹4,026 per activation vs field ₹24,335', 'WhatsApp entry, partner counter QR, assisted mode'],
    ['Accel users (38% of leads) convert at 9.2% vs 6.2% on other providers', 'Reuse Accel KYC; lead with the bundle for this base'],
    ['Only chains and plants took 24 months; in chains they churned more (15.8% vs 6.7%); 2 of 3 six-month deals churned', '12 months for shops, offices and chains, 24 for plants; 24 shown only as a lower price; no 6-month deals'],
    ['Micro shops: ₹20,007 to acquire, ₹2,470 bundle, 22.7% churn', 'Shops are self-serve only; field time goes to chains and plants'],
    ['1,583 drop-offs from visits, slow or complex quotes, paperwork, installs over 21 days', 'One sitting: instant quote in plain words, KYC in minutes, ETA per service'],
    ['325 "locked in", 207 "went cheaper"', 'Win on fit and one bill, not price; local partners sell through us'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, ci ? {} : { bold: false })))
  table(s, [['Signal in the data', 'Decision in the product and plan'].map((t) => ({ text: t, options: H })), ...rows], { x: 0.45, y: 1.5, w: 9.1, colW: [4.8, 4.3], rowH: [0.28, ...Array(9).fill(0.3)] })
  txt(s, 'Impact model (slide 8): at each funnel step, half of the journey losses are removed and every other loss stays at today\'s rate, so 368 → 760 (a quarter removed: 538; three quarters: 1,045). Cost per activation = (₹55.4 lakh, same spend, + ₹3.5 lakh a quarter to run Saathi) / 760 = ₹7,746; with a 5-person team (₹30 lakh a quarter), ≈ ₹11,700. Revenue = 392 × ₹6,900 median bundle × 12 ≈ ₹3.2 crore a year (the median, not the ₹12,350 mean).',
    { x: 0.45, y: 4.74, w: 9.1, h: 0.36, fontSize: 8.5, color: C.text2 })
}

// ======================================================================
// A4: test results
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A4 · Test results: what we checked, and the KYC answer key', { placeholder: 'title' })
  s.addText('All suites are in backend/tests and run on GitHub on every push; the advisor suite also runs with the live AI (--llm).', { placeholder: 'sub' })
  const suites = [
    ['Advisor scenarios', '92/92', '35 owners, 5 languages, 7 chat changes, 22 questions, 28 sales moments; 498+ catalogue checks; AI on and off'],
    ['Search test', '93.5%', '83 questions, 10 languages: right section in the 4 the AI gets (keywords alone 65%)'],
    ['AI answers', '0%', 'invented numbers (live AI, 83 questions); 96% owner\'s language, 94% right source; ≈ ₹0.11 a chat'],
    ['Ranking back-test', '3/3', 'Leave-one-out, 368 customers: beats hand rules and one bundle for all; ties segment best-sellers (A5)'],
    ['10 languages', '100/100', 'The whole journey in each language, AI off: every string, prices, script, the selling taps'],
    ['Specimen KYC pack', '12/12', 'Every applicant judged as the planted problem requires (right table)'],
    ['WhatsApp orders', '59/59', 'Signed webhooks, every stage update, STATUS, RESCHEDULE, PROBLEM; one reminder only'],
    ['Privacy and ranking', '17/17', 'No readable data in the DB file, tampering refused, AI sees only tokens, ranking learned per business type'],
    ['Partner flows', '17/17', 'Owner code, lockout after 5 tries, protection across sessions, referral QR, console totals'],
    ['KYC flows', '10/10', 'No-GSTIN owners, remove and replace, Udyam only when registered'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, { fontSize: 8, ...(ci === 1 ? { bold: true, color: HEX.accent3, align: 'center' } : ci === 0 ? { bold: true } : {}) })))
  table(s, [['Suite', 'Pass', 'What it covers'].map((t) => ({ text: t, options: H })), ...suites], { x: 0.45, y: 1.5, w: 4.9, colW: [1.2, 0.7, 3.0], rowH: [0.24, 0.34, 0.32, 0.32, 0.32, 0.3, 0.28, 0.32, 0.32, 0.3, 0.28] })
  const key = [
    ['K01', 'Rejected', 'GSTIN cancelled in the registry'], ['K02', 'Approved', 'Clean'], ['K03', 'Approved', 'Clean'],
    ['K04', 'Rejected', 'GST certificate too blurred to read'], ['K05', 'Rejected', 'Udyam certificate missing'],
    ['K06', 'Rejected', 'Altered GSTIN: checksum fails; registry shows the real one'], ['K07', 'Rejected', 'Legal name differs from the registry'],
    ['K08', 'Approved', 'Clean'], ['K09', 'Approved', 'Clean'], ['K10', 'Review', 'LLP: authorisation letter needed (template given)'],
    ['K11', 'Rejected', 'Bill 257 days old (limit 90)'], ['K12', 'Approved', 'Clean'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, { fontSize: 8.5, ...(ci === 1 ? { bold: true, color: c === 'Approved' ? HEX.accent3 : c === 'Review' ? 'B26A00' : HEX.accent1 } : {}) })))
  table(s, [['Applicant', 'Decision', 'Reason found'].map((t) => ({ text: t, options: { ...H, fontSize: 8.5 } })), ...key], { x: 5.55, y: 1.5, w: 4.0, colW: [0.7, 0.75, 2.55], rowH: [0.26, ...Array(12).fill(0.27)] })
}

// ======================================================================
// A5: how the advisor ranks, and the back-test
// ======================================================================
{
  const s = pres.addSlide({ masterName: 'ANNEX' })
  s.addText('A5 · How the advisor ranks a bundle, and how we tested it', { placeholder: 'title' })
  s.addText('Beyond fixed weights: metadata on both sides of the catalogue, learned from customers, re-ranked by what she tells us.', { placeholder: 'sub' })
  const parts = [
    ['Catalogue metadata', 'Each of the 25 services is tagged with the need it meets, who may buy it (city tier, size, GSTIN), what it depends on and how many to add per person, site or counter.'],
    ['Owner problems', '8 everyday problems (UPI fails at rush hour, theft, missed calls, records on one PC, internet drops, guests want Wi-Fi, repeat customers, branches out of sight) mapped to services. Asked as taps; read from free text in 10 languages by rules and the AI.'],
    ['Learned from customers', 'Share of similar activated customers who kept each service: her business type, pulled toward its segment with a 30-customer prior; churned customers count half. What owners asked for nudges the order (a quarter weight).'],
    ['Levels and reasons', 'Basic: essentials plus her problems. Recommended: the learned pre-ticks. Complete: plus what businesses like hers usually add. "Why this bundle" shows the four steps in her words.'],
  ]
  parts.forEach(([h, b], i) => {
    const y = 1.5 + i * 0.86
    box(s, 0.45, y, 4.5, 0.8, C.background2)
    badge(s, i + 1, 0.52, y + 0.08)
    txt(s, lines([run(h, { bold: true, fontSize: 10, color: C.text1 }), run(b, { fontSize: 8.5, color: C.text2 })]), { x: 0.92, y: y + 0.06, w: 3.95, h: 0.72 })
  })
  label(s, 'BACK-TEST: 368 ACTIVATED CUSTOMERS, LEAVE-ONE-OUT', 5.15, 1.5, 4.4)
  const bt = [
    ['One bundle for everyone', '37.2%', '43.1%', '0.399'],
    ['Hand-written rules (our first version)', '60.0%', '65.2%', '0.625'],
    ['Best-sellers in her segment', '63.1%', '66.9%', '0.650'],
    ['Accel Saathi, learned', '63.2%', '67.1%', '0.651'],
  ].map((r, i) => r.map((c, ci) => cell(c, i, { bold: i === 3, color: i === 3 ? HEX.accent1 : HEX.dk1, align: ci ? 'center' : 'left' })))
  table(s, [['Method', 'Precision', 'Recall', 'F1'].map((t, i) => ({ text: t, options: { ...H, align: i ? 'center' : 'left' } })), ...bt],
    { x: 5.15, y: 1.72, w: 4.4, colW: [2.2, 0.75, 0.75, 0.7], rowH: [0.28, 0.3, 0.3, 0.3, 0.3] })
  txt(s, [
    run('How: ', { bold: true }), run('each customer is taken out of the counts, then predicted from what we would know at the first chat (type, size, sites, city, GST, internet today). Every method builds a valid bundle of the same size.', { breakLine: true }),
    run('What it shows: ', { bold: true }), run('learning beats hand-written rules and a one-size bundle. Accel\'s purchases differ mostly by segment, so it matches segment best-sellers; business type, retention and her own problems add what no average can know.', { breakLine: true }),
    run('What we did not use: ', { bold: true }), run('products of interest at lead time matched purchases only 29% of the time, so they never decide a pre-tick.'),
  ], { x: 5.15, y: 3.32, w: 4.4, h: 1.78, fontSize: 8.5, color: C.text1, paraSpaceAfter: 4 })
}

;(async () => {
  await pres.writeFile({ fileName: OUT })
  await applyTheme(OUT, THEME)
  console.log('wrote', OUT)
})()
