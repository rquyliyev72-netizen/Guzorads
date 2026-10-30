// Renders every asset in kit.html to PNG, then screenshots the profile preview.
// Usage: node instagram/build.js
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const dir = __dirname;
const out = path.join(dir, 'export');

(async () => {
  for (const sub of ['', 'highlights', 'posts', 'stories']) fs.mkdirSync(path.join(out, sub), { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1800, height: 1200 } });
  await page.goto('file://' + path.join(dir, 'kit.html'), { waitUntil: 'networkidle' });
  await page.evaluate(async () => { await document.fonts.load('800 40px Manrope'); await document.fonts.ready; });

  const ids = await page.$$eval('.asset[id]', els => els.map(e => e.id));
  for (const id of ids) {
    const file = id.startsWith('hl-') ? `highlights/${id.slice(3)}.png`
      : id.startsWith('post-') ? `posts/${id}.png`
      : id.startsWith('story-') ? `stories/${id.slice(6)}.png`
      : `${id}.png`;
    const transparent = id === 'logo-mark' || id === 'story-ramka';
    await page.evaluate(t => { document.body.style.background = t ? 'transparent' : ''; }, transparent);
    await page.locator('#' + id).screenshot({ path: path.join(out, file), omitBackground: transparent });
    console.log('✓', file);
  }

  const preview = await browser.newPage({ viewport: { width: 430, height: 900 }, deviceScaleFactor: 2 });
  await preview.goto('file://' + path.join(dir, 'preview.html'));
  await preview.evaluate(() => document.fonts.ready);
  await preview.waitForLoadState('networkidle');
  await preview.screenshot({ path: path.join(out, 'profile-preview.png'), fullPage: true });
  console.log('✓ profile-preview.png');

  await browser.close();
})();
