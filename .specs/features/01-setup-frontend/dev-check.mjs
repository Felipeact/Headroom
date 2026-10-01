// Proof for C2: `npm run dev` serves the create-next-app starter page with status 200.
import { spawn, execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "../../../frontend");
const port = 3123;
const url = `http://localhost:${port}/`;

const dev = spawn("npm", ["run", "dev", "--", "--port", String(port)], {
  cwd: frontend,
  shell: true,
  stdio: "ignore",
});

function stop() {
  if (process.platform === "win32") {
    execSync(`taskkill /pid ${dev.pid} /T /F`, { stdio: "ignore" });
  } else {
    dev.kill("SIGTERM");
  }
}

let code = 1;
try {
  const deadline = Date.now() + 120_000;
  let res;
  while (Date.now() < deadline) {
    try {
      res = await fetch(url);
      break;
    } catch {
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  if (!res) throw new Error(`no response from ${url} within 120 s`);
  const body = await res.text();
  if (res.status !== 200) throw new Error(`status ${res.status}`);
  if (!body.includes("To get started, edit the")) throw new Error("starter page text not found");
  console.log(`GET ${url} -> 200, starter page`);
  code = 0;
} catch (err) {
  console.error(String(err));
} finally {
  stop();
}
process.exit(code);
