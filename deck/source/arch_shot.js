const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 600 }, deviceScaleFactor: 1.5 });
  await p.goto('file://' + __dirname + '/arch.html'); await p.waitForTimeout(500);
  const h = await p.evaluate(() => document.querySelector('.wrap').scrollHeight); console.log('height', h);
  await p.screenshot({ path: __dirname + '/img/arch.png', clip: { x: 0, y: 0, width: 1600, height: 600 } }); await b.close(); })();
