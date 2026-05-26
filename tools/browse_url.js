const fs = require('fs');
const path = require('path');

const MAX_CHARS = 50000;
// Optional: path to a Netscape cookies.txt exported from Chrome
const COOKIES_FILE = process.env.BROWSER_COOKIES_FILE;

function parseCookiesTxt(filePath) {
  const lines = fs.readFileSync(filePath, 'utf8').split('\n');
  return lines
    .filter(l => l && !l.startsWith('#'))
    .map(l => {
      const parts = l.split('\t');
      if (parts.length < 7) return null;
      return {
        domain: parts[0].replace(/^\./, ''),
        path: parts[2],
        secure: parts[3] === 'TRUE',
        expires: parseInt(parts[4], 10) || undefined,
        name: parts[5],
        value: parts[6].trim(),
      };
    })
    .filter(Boolean);
}

async function browseUrl(url) {
  let playwright;
  try {
    playwright = require('playwright');
  } catch {
    return {
      content: null,
      error: 'playwright not installed. Run: npm install playwright && npx playwright install chromium',
    };
  }

  const browser = await playwright.chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    });

    // Load cookies from file if configured (allows accessing paywalled content)
    if (COOKIES_FILE && fs.existsSync(COOKIES_FILE)) {
      const cookies = parseCookiesTxt(COOKIES_FILE);
      if (cookies.length > 0) await context.addCookies(cookies);
    }

    const page = await context.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2000);

    const text = await page.evaluate(() => {
      // Remove nav, footer, ads, scripts
      const remove = ['nav', 'footer', 'header', 'script', 'style', 'aside', '[class*="ad"]', '[class*="banner"]', '[class*="popup"]'];
      remove.forEach(sel => document.querySelectorAll(sel).forEach(el => el.remove()));

      // Try to find main article content
      const selectors = ['article', 'main', '[class*="article"]', '[class*="content"]', '[class*="story"]', '.post', '#content'];
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.length > 500) return el.innerText;
      }
      return document.body.innerText;
    });

    return { content: text.slice(0, MAX_CHARS), error: null, url };
  } catch (err) {
    return { content: null, error: `Browse failed: ${err.message}` };
  } finally {
    await browser.close();
  }
}

module.exports = { browseUrl };
