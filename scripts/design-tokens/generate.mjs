#!/usr/bin/env node
/**
 * 从 design/tokens.json 生成Web token 文件。
 * 运行：node scripts/design-tokens/generate.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const tokens = JSON.parse(readFileSync(resolve(root, "design/tokens.json"), "utf8"));
const { brand, brandRamp, neutral, radius, space, font, fontFamily, shadow, control, table, layout, component } = tokens;

function write(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, "utf8");
  console.log("generated", path.replace(root + "/", ""));
}

const radiusVars = Object.entries(radius)
  .map(([k, v]) => `  --argus-radius-${k}: ${v}px;`)
  .join("\n");
const spaceVars = Object.entries(space)
  .map(([k, v]) => `  --argus-space-${k}: ${v}px;`)
  .join("\n");
const fontVars = Object.entries(font)
  .map(([k, v]) => `  --argus-font-${k}: ${v}px;`)
  .join("\n");
const controlVars = Object.entries(control)
  .map(([k, v]) => `  --argus-control-h-${k}: ${v}px;`)
  .join("\n");

// ---- Web ----
write(
  resolve(root, "frontend/web/src/styles/core/_brand-tokens.generated.scss"),
  `// 由 design/tokens.json 生成，请勿手改。
:root {
  --argus-brand-blue: ${brand.blue};
  --argus-brand-violet: ${brand.violet};
  --argus-brand-gradient: ${brand.gradient};
  --argus-canvas: ${neutral.canvas};
${radiusVars}
${spaceVars}
${fontVars}
${controlVars}
  --argus-table-row-h: ${table.rowHeight}px;
  --argus-table-header-h: ${table.headerHeight}px;
  --argus-page-padding: ${layout.pagePadding}px;
  --argus-header-h: ${layout.headerHeight}px;
  --argus-shadow-card: ${shadow.card};
  --argus-shadow-pop: ${shadow.pop};
  --argus-shadow-modal: ${shadow.modal};
  --argus-font-sans: ${fontFamily.sans};
  --argus-table-header-bg: ${table.headerBgLight};
  --argus-input-bg: ${component.inputBgLight};
  --argus-dialog-bg: ${component.dialogBgLight};
  --argus-popover-bg: ${component.popoverBgLight};
  --argus-overlay-bg: ${component.overlayLight};
  --el-fill-color-blank: var(--argus-input-bg);
  --el-dialog-bg-color: var(--argus-dialog-bg);
  --el-bg-color-overlay: var(--argus-popover-bg);
  --el-overlay-color-lighter: var(--argus-overlay-bg);
}

html.dark {
  --argus-canvas: ${neutral.canvasDark};
  --argus-surface: ${neutral.darkSurface1};
  --argus-surface-2: ${neutral.darkSurface2};
  --argus-border: ${neutral.darkBorder};
  --argus-text-1: ${neutral.darkText1};
  --argus-text-2: ${neutral.darkText2};
  --argus-text-3: ${neutral.darkText3};
  --argus-shadow-card: ${shadow.darkCard};
  --argus-shadow-pop: ${shadow.darkPop};
  --argus-shadow-modal: ${shadow.darkModal};
  --argus-table-header-bg: ${table.headerBgDark};
  --argus-input-bg: ${component.inputBgDark};
  --argus-dialog-bg: ${component.dialogBgDark};
  --argus-popover-bg: ${component.popoverBgDark};
  --argus-overlay-bg: ${component.overlayDark};
}
`
);

console.log("done");
