/** System helpers (flattened). */

import type { App } from "vue";
import mitt, { type Emitter } from "mitt";
import { StorageConfig } from "@utils";
import { BANNER } from "../../../build/banner";

// -----------------------------
// Console banner：ANSI 转义码生成网站  https://patorjk.com/software/taag/#p=testall&f=Fire+Font-k&t=ARGUS%0A&x=none&v=4&h=4&w=80&we=false
// -----------------------------

export function printConsoleBanner(): void {
  console.log(`${BANNER} | ${StorageConfig.appName} v${StorageConfig.CURRENT_VERSION}`);
}

// -----------------------------
// Mitt bus
// -----------------------------

type SysEvents = {
  triggerFireworks: string | undefined;
  openSetting: void;
  openSearchDialog: void;
  openLockScreen: void;
};

export const mittBus: Emitter<SysEvents> = mitt<SysEvents>();

// -----------------------------
// Error handling
// -----------------------------

const IGNORABLE_SCRIPT_ERRORS = [
  "ResizeObserver loop completed with undelivered notifications.",
  "ResizeObserver loop limit exceeded",
];

function normalizeErrorMessage(message: Event | string): string {
  if (typeof message === "string") return message;
  if ("message" in message && typeof message.message === "string") return message.message;
  return "";
}

function isIgnorableScriptError(message: Event | string, source?: string): boolean {
  const normalizedMessage = normalizeErrorMessage(message);
  if (!normalizedMessage) return false;

  if (IGNORABLE_SCRIPT_ERRORS.some((item) => normalizedMessage.includes(item))) {
    // 浏览器/扩展在布局抖动时常见的 ResizeObserver 噪声，不作为真实异常处理
    return true;
  }

  // 浏览器扩展注入脚本偶发的跨域 Script error 也没有排查价值
  if (normalizedMessage === "Script error." && source === "") return true;
  return false;
}

export function vueErrorHandler(err: unknown, instance: any, info: string) {
  console.error("[VueError]", err, info, instance);
}

export function scriptErrorHandler(
  message: Event | string,
  source?: string,
  lineno?: number,
  colno?: number,
  error?: Error
): boolean {
  if (isIgnorableScriptError(message, source)) return true;
  console.error("[ScriptError]", { message, source, lineno, colno, error });
  return true;
}

export function registerPromiseErrorHandler() {
  window.addEventListener("unhandledrejection", (event) => {
    console.error("[PromiseError]", event.reason);
  });
}

export function registerResourceErrorHandler() {
  window.addEventListener(
    "error",
    (event: Event) => {
      const target = event.target as HTMLElement;
      if (
        target &&
        (target.tagName === "IMG" || target.tagName === "SCRIPT" || target.tagName === "LINK")
      ) {
        console.error("[ResourceError]", {
          tagName: target.tagName,
          src:
            (target as HTMLImageElement).src ||
            (target as HTMLScriptElement).src ||
            (target as HTMLLinkElement).href,
        });
      }
    },
    true
  );
}

export function initErrorHandle(app: App) {
  app.config.errorHandler = vueErrorHandler;
  window.onerror = scriptErrorHandler;
  registerPromiseErrorHandler();
  registerResourceErrorHandler();
}
