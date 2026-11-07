const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })).newPage();
  await p.goto('http://localhost:8031/#/track/AB56F802CA'); await p.waitForSelector('.onebill'); await p.waitForTimeout(1200);
  await p.addStyleTag({ content: '.dlv.demo{display:none!important}' });
  await p.evaluate(() => { const el = document.querySelector('.onebill'); window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 90) }); await p.waitForTimeout(500);
  await p.screenshot({ path: 's3/12_onebill.png' });
  await b.close();
})();
