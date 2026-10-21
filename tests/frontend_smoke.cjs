// Run against a disposable local instance; never submits a venue booking.
const { chromium } = require('playwright');

(async () => {
  const browser = process.env.CDP_URL
    ? await chromium.connectOverCDP(process.env.CDP_URL)
    : await chromium.launch({ headless: true, channel: 'msedge' });
  const page = process.env.CDP_URL
    ? browser.contexts()[0].pages()[0]
    : await browser.newPage({ viewport: { width: 1240, height: 860 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const base = process.env.SMOKE_URL || 'http://127.0.0.1:18767';
  await page.goto(base);
  await page.getByText('下一场精彩，从这里开始').waitFor();
  await page.screenshot({ path: 'runtime/dashboard-desktop.png', fullPage: true, animations: 'disabled' });
  for (const route of ['/venues', '/tasks', '/bookings', '/settings']) {
    await page.goto(base + route);
    await page.locator('.page-title').waitFor();
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) {
      throw new Error(`Horizontal overflow on ${route}`);
    }
  }
  await page.getByRole('button', { name: '一键登录（打开登录窗口）' }).waitFor();
  await page.screenshot({ path: 'runtime/settings-desktop.png', fullPage: true, animations: 'disabled' });
  await page.setViewportSize({ width: 440, height: 800 });
  await page.goto(base);
  await page.getByText('下一场精彩，从这里开始').waitFor();
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) {
    throw new Error('Horizontal overflow on mobile');
  }
  await page.screenshot({ path: 'runtime/dashboard-mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: '退出服务', exact: true }).click();
  await page.getByText('退出程序与后台服务', { exact: true }).waitFor();
  await page.getByRole('button', { name: '继续使用' }).click();
  if (errors.length) throw new Error(errors.join('\n'));
  await page.getByRole('button', { name: '退出服务', exact: true }).click();
  await page.getByRole('button', { name: '退出程序与后台服务' }).click();
  console.log('PASS: five routes, desktop/mobile layout, login action, cancel/confirm exit; no JS errors.');
  await browser.close().catch(() => {});
})().catch(error => { console.error(error); process.exit(1); });
