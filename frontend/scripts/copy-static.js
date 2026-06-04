const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, '../out');
const dest = path.join(__dirname, '../../app/static');

function copyRecursiveSync(src, dest) {
  const exists = fs.existsSync(src);
  const stats = exists && fs.statSync(src);
  const isDirectory = exists && stats.isDirectory();
  if (isDirectory) {
    if (!fs.existsSync(dest)) {
      fs.mkdirSync(dest, { recursive: true });
    }
    fs.readdirSync(src).forEach((childItemName) => {
      copyRecursiveSync(path.join(src, childItemName), path.join(dest, childItemName));
    });
  } else {
    fs.copyFileSync(src, dest);
  }
}

// Clean dest first (avoid stale files)
if (fs.existsSync(dest)) {
  fs.rmSync(dest, { recursive: true, force: true });
}
fs.mkdirSync(dest, { recursive: true });

if (fs.existsSync(src)) {
  copyRecursiveSync(src, dest);
  console.log('Static files copied to app/static successfully!');
} else {
  console.error('Error: Source directory "out" not found. Run next build first.');
  process.exit(1);
}
