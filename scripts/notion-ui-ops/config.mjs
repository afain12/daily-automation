import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

export const PROFILE_DIR = join(__dirname, 'profile');
export const EXECUTABLE_PATH =
  process.env.LOCALAPPDATA + '\\ms-playwright\\chromium-1208\\chrome-win64\\chrome.exe';

// Master Tasks DB (canonical IDs from config/sources.yaml)
export const MASTER_TASKS_URL =
  'https://www.notion.so/ece9b1235e674172b9a08f558c53ccfa';

// Returns true once the Notion app shell (logged-in) is on screen.
export async function isLoggedIn(page) {
  const url = page.url();
  if (/accounts\.google\.com/.test(url)) return false;
  if (/notion\.so\/(login|signup|native\/login)/.test(url)) return false;
  // app shell markers
  const marker = await page
    .locator('.notion-sidebar-container, .notion-topbar, [placeholder="Search"]')
    .first()
    .count()
    .catch(() => 0);
  return marker > 0;
}

export async function launchPersistent(playwright, { headless = false } = {}) {
  // Use real system Chrome (channel) + strip automation flags so Google SSO
  // doesn't throw "this browser may not be secure".
  return playwright.chromium.launchPersistentContext(PROFILE_DIR, {
    headless,
    channel: 'chrome',
    viewport: null,
    ignoreDefaultArgs: ['--enable-automation'],
    args: [
      '--disable-blink-features=AutomationControlled',
      '--start-maximized',
    ],
  });
}
