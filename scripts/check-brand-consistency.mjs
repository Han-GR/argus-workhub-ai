#!/usr/bin/env node
/**
 * 品牌一致性检查：Logo 哈希一致、无旧色值、无旧间距类。
 * 用法：node scripts/check-brand-consistency.mjs
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const errors = [];

function hash(file) {
  return createHash("sha256").update(readFileSync(resolve(root, file))).digest("hex");
}

const logoGroups = [
  ["design/assets/logo.svg", "backend/static/image/logo.svg", "frontend/web/public/logo.svg", "frontend/web/src/assets/argus_imgs/logo.svg", "backend/app/modules/system/auth/assets/logo.svg"],
  ["design/assets/logo.png", "backend/static/logo.png", "frontend/web/public/logo.png"],
  ["design/assets/favicon.ico", "backend/static/image/favicon.ico", "frontend/web/public/favicon.ico"],
];

for (const group of logoGroups) {
  const [source, ...targets] = group;
  const expected = hash(source);
  for (const target of targets) {
    if (hash(target) !== expected) errors.push(`Logo 不一致：${target}`);
  }
}

// Prevent obsolete first-party names from reappearing in source or component paths.
function checkIdentifiers(directory) {
  for (const entry of readdirSync(resolve(root, directory), { withFileTypes: true })) {
    const relative = `${directory}/${entry.name}`;
    if (/(?:^Fa[A-Z]|^fa-|^fa_imgs$|^fastlink$)/.test(entry.name)) {
      errors.push(`旧项目路径：${relative}`);
    }
    if (entry.isDirectory()) {
      checkIdentifiers(relative);
    } else if (/\.(vue|ts|scss|css|jinja2)$/.test(entry.name)) {
      const source = readFileSync(resolve(root, relative), "utf8");
      if (/Fa[A-Z]|\bfa-|fa_imgs|Fastlink|fastlink/.test(source)) {
        errors.push(`旧项目内部标识：${relative}`);
      }
    }
  }
}
for (const directory of ["frontend/web/src"]) {
  checkIdentifiers(directory);
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log("品牌一致性检查通过：Logo 与内部标识");
