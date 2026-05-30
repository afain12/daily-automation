// Deletes ONE Master Tasks view by name via the proven path:
// overflow -> filter -> ••• -> "Delete view". Screenshots pre/menu/post.
import playwright from 'playwright';
import { mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPersistent, isLoggedIn, MASTER_TASKS_URL } from './config.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const TARGET = process.argv[2];
if (!TARGET) { console.log('USAGE: node delete-view.mjs "<View Name>"'); process.exit(64); }
const EVID = join(__dirname, '..', '..', '.context', 'applied', 'notion-ui-ops', `del-${TARGET.replace(/\W+/g,'_')}-${stamp}`);
mkdirSync(EVID, { recursive: true });

const ctx = await launchPersistent(playwright);
const page = ctx.pages()[0] || (await ctx.newPage());
await page.goto(MASTER_TASKS_URL, { waitUntil: 'domcontentloaded', timeout: 60_000 });
await page.waitForTimeout(4000);
if (!(await isLoggedIn(page))) { console.log('NOT_LOGGED_IN'); await ctx.close(); process.exit(2); }
await page.screenshot({ path: join(EVID, '01-pre.png') });

await page.getByText(/\d+\s*more/i).first().click();
await page.waitForTimeout(900);
const search = page.getByPlaceholder(/search for a view/i).first();
const sBox = await search.boundingBox();
await search.fill(TARGET);
await page.waitForTimeout(800);

if (!sBox) { console.log('NO_SEARCH_BOX'); await page.screenshot({ path: join(EVID,'ERR-nobox.png') }); await ctx.close(); process.exit(3); }
// The first filtered result sits ~21px below the search box. Target it
// geometrically (NOT getByText, which matches background table cells).
const rowY = sBox.y + sBox.height + 21;
await page.mouse.move(sBox.x + 20, rowY);
await page.waitForTimeout(400);
await page.screenshot({ path: join(EVID, '01b-filtered.png') });
await page.mouse.click(sBox.x + sBox.width - 14, rowY);
await page.waitForTimeout(900);
await page.screenshot({ path: join(EVID, '02-menu.png') });

const del = page.getByText('Delete view', { exact: true }).first();
if (!(await del.count())) { console.log('DELETE_VIEW_ITEM_NOT_FOUND'); await ctx.close(); process.exit(4); }
await del.click();
await page.waitForTimeout(800);
await page.screenshot({ path: join(EVID, '02b-confirm-dialog.png') });

// confirmation dialog: "Delete this view?" with a red "Delete view" button
let confirmed = false;
const confirmBtn = page.getByText('Delete view', { exact: true }).last();
if (await confirmBtn.count().catch(() => 0) && await confirmBtn.isVisible().catch(() => false)) {
  await confirmBtn.click();
  confirmed = true;
  await page.waitForTimeout(800);
}
console.log('CONFIRM_CLICKED', confirmed);
await page.waitForTimeout(800);
await page.screenshot({ path: join(EVID, '03-post.png') });
console.log('DELETED_ATTEMPTED', TARGET);
console.log('EVID', EVID);
await ctx.close();
process.exit(0);
