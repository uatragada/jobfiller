import { spawn } from "node:child_process";
import process from "node:process";

const suites = [
  ["smoke", "tests/rebuild-smoke.mjs"],
  ["buttons", "tests/button-flows.mjs"],
  ["downloads", "tests/downloads.mjs"],
  ["api-auth", "tests/api-auth.mjs"],
  ["performance", "tests/performance.mjs"],
];

function runSuite([label, script]) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [script], {
      cwd: process.cwd(),
      env: process.env,
      stdio: "inherit",
      shell: false,
    });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${label} suite failed with ${signal || `exit code ${code}`}`));
    });
  });
}

for (const suite of suites) {
  console.log(`\n== JobFiller frontend ${suite[0]} suite ==`);
  await runSuite(suite);
}

console.log("\nAll JobFiller frontend suites passed.");
