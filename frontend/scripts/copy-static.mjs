import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

if (process.env.VERCEL) {
  console.log("Vercel deployment detected. Skipping static copy to backend.");
  process.exit(0);
}

const src = join(__dirname, "../out");
const dest = join(__dirname, "../../app/static");

// Clean dest first (avoid stale files)
if (existsSync(dest)) {
  rmSync(dest, { recursive: true, force: true });
}
mkdirSync(dest, { recursive: true });

if (existsSync(src)) {
  cpSync(src, dest, { recursive: true });
  console.log("Static files copied to app/static successfully!");
} else {
  console.error('Error: Source directory "out" not found. Run next build first.');
  process.exit(1);
}
