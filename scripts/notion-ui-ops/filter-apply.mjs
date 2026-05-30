import playwright from 'playwright';
import { mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPersistent, isLoggedIn } from './config.mjs';
const __dirname = dirname(fileURLToPath(import.meta.url));
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const EVID = join(__dirname, '..', '..', '.context', 'applied', 'notion-ui-ops', `fapply-${stamp}`);
mkdirSync(EVID, { recursive: true });
const ctx = await launchPersistent(playwright);
const page = ctx.pages()[0] || (await ctx.newPage());
await page.goto('https://www.notion.so/36fa315859b4814eab92dd7f5c885ab0', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(4500);
if (!(await isLoggedIn(page))) { console.log('NOT_LOGGED_IN'); await ctx.close(); process.exit(2); }
await page.evaluate(() => { const b=document.querySelector('.notion-collection_view-block,[class*="collection_view-block"]'); if(b) b.scrollIntoView({block:'start'}); });
await page.waitForTimeout(1000);
await page.mouse.move(900, 200);
await page.waitForTimeout(600);
// 1. click Filter
await page.mouse.click(851, 64);
await page.waitForTimeout(900);
await page.screenshot({ path: join(EVID, '01-filter-menu.png') });
// 2. pick "Status" property (foreground popover -> .last())
const statusOpt = page.getByText('Status', { exact: true }).last();
if (await statusOpt.count().catch(()=>0)) { await statusOpt.click(); await page.waitForTimeout(900); }
await page.screenshot({ path: join(EVID, '02-after-status.png') });
// 3. pick "Waiting" value
const waiting = page.getByText('Waiting', { exact: true }).last();
let pickedWaiting = false;
if (await waiting.count().catch(()=>0) && await waiting.isVisible().catch(()=>false)) { await waiting.click(); pickedWaiting=true; await page.waitForTimeout(800); }
console.log('PICKED_WAITING', pickedWaiting);
await page.screenshot({ path: join(EVID, '03-after-waiting.png') });
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(500);
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(500);
await page.screenshot({ path: join(EVID, '04-final.png') });
console.log('EVID', EVID);
await ctx.close();
process.exit(0);
