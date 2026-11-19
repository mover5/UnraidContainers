// Renders public/favicon.svg to the PNG icons (PWA + Unraid template) using
// Playwright's Chromium:  node scripts/make-icons.cjs
const path = require('node:path');
const { execSync } = require('node:child_process');
const { chromium } = require(path.join(execSync('npm root -g').toString().trim(), 'playwright'));

const root = path.join(__dirname, '..');
const svg = require('node:fs').readFileSync(path.join(root, 'public/favicon.svg'), 'utf8');

(async () => {
  const browser = await chromium.launch();
  for (const [size, out] of [[192, 'public/icon-192.png'], [512, 'public/icon-512.png'], [512, 'icon.png']]) {
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    await page.setContent(`<style>html,body{margin:0;background:#1c1618}svg{width:${size}px;height:${size}px;display:block}</style>${svg}`);
    await page.screenshot({ path: path.join(root, out), omitBackground: false });
    await page.close();
  }
  await browser.close();
})();
