// C8: open the staging web app at 375 px in Chromium and check it renders cleanly.
// Usage: node web-check.mjs <web staging domain>
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "../../../frontend/package.json"));
const { chromium } = require("@playwright/test");

const domain = process.argv[2];
if (!domain) {
  console.error("usage: node web-check.mjs <domain>");
  process.exit(2);
}

const browser = await chromium.launch();
const failures = [];
try {
  const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  const response = await page.goto(`https://${domain}/`, { waitUntil: "networkidle" });
  if (response?.status() !== 200) failures.push(`status ${response?.status()}`);
  if (!(await page.locator("main").first().isVisible())) failures.push("no visible <main>");
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  if (scrollWidth > 375) failures.push(`scrollWidth ${scrollWidth} > 375`);
  if (consoleErrors.length) failures.push(`console errors: ${consoleErrors.join(" | ")}`);
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
