// Read-only: relaunch from saved profile, confirm login persisted, screenshot
// Master Tasks, and locate the database view tabs. No mutations.
import playwright from 'playwright';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { launchPersistent, isLoggedIn, MASTER_TASKS_URL } from './config.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const EVID = join(__dirname, '..', '..', '.context', 'applied', 'notion-ui-ops', `inspect-${stamp}`);
mkdirSync(EVID, { recursive: true });

const KNOWN_VIEWS = [
  'All tasks', 'By status', 'Due soon', 'Inbox (no workspace)', 'Inbox',
  'Top-level tasks', 'Operations', 'Sales', 'Product', 'Product',
  'Morning Report',
];

const ctx = await launchPersistent(playwright);
const page = ctx.pages()[0] || (await ctx.newPage());
await page.goto(MASTER_TASKS_URL, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForTimeout(4000);

const loggedIn = await isLoggedIn(page);
console.log('PERSISTED_LOGIN', loggedIn);
if (!loggedIn) {
  await page.screenshot({ path: join(EVID, 'NOT-logged-in.png') });
  console.log('EVID', EVID);
  await ctx.close();
  process.exit(2);
}

await page.screenshot({ path: join(EVID, '01-master-tasks.png'), fullPage: false });

// Locate the view-tab bar. Notion renders view tabs as elements in the
// collection toolbar. Report which known views are present + visible.
const found = [];
for (const name of KNOWN_VIEWS) {
  const loc = page.getByText(name, { exact: true });
  const n = await loc.count().catch(() => 0);
  let visible = false;
  if (n > 0) { visible = await loc.first().isVisible().catch(() => false); }
  if (n > 0) found.push({ name, count: n, visible });
}
console.log('VIEWS_FOUND', JSON.stringify(found));

// Dump the toolbar text for ground truth
const barText = await page
  .locator('.notion-collection-view-tabs-content, [class*="collection-view-tabs"]')
  .first()
  .innerText()
  .catch(() => '');
console.log('VIEW_BAR_TEXT', JSON.stringify(barText));

console.log('EVID', EVID);
await ctx.close();
process.exit(0);
