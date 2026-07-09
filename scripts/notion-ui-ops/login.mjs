// Opens a headed, PERSISTENT-profile Chromium on Notion Master Tasks and waits
// for the user to complete login. On success the cookies/localStorage persist in
// ./profile so later op scripts reuse the session. Run in background.
import playwright from 'playwright';
import { launchPersistent, isLoggedIn, MASTER_TASKS_URL } from './config.mjs';

const TIMEOUT_MS = 300_000; // 5 min for the user to log in

const ctx = await launchPersistent(playwright);
const page = ctx.pages()[0] || (await ctx.newPage());

try {
  await page.goto(MASTER_TASKS_URL, { waitUntil: 'domcontentloaded', timeout: 60_000 });
} catch (e) {
  console.log('GOTO_WARN', e.message);
}

// Already logged in? (persisted from a prior run)
if (await isLoggedIn(page)) {
  console.log('LOGIN_OK already-authenticated');
  await page.waitForTimeout(1500);
  await ctx.close();
  process.exit(0);
}

console.log('WAITING_FOR_LOGIN — complete Google SSO in the opened window...');
const start = Date.now();
let ok = false;
while (Date.now() - start < TIMEOUT_MS) {
  await page.waitForTimeout(2500);
  // user may have been redirected; make sure we end up on the app
  if (await isLoggedIn(page)) { ok = true; break; }
}

if (ok) {
  // nudge to the master tasks page so the profile caches app state, then persist
  try { await page.goto(MASTER_TASKS_URL, { waitUntil: 'domcontentloaded', timeout: 60_000 }); } catch {}
  await page.waitForTimeout(2000);
  console.log('LOGIN_OK authenticated');
  await ctx.close();
  process.exit(0);
} else {
  console.log('LOGIN_TIMEOUT not authenticated within 5 min');
  await ctx.close();
  process.exit(2);
}
