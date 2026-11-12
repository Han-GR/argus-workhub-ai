export interface SystemBasicConfig {
  name: string;
  description?: string;
  logo?: string;
  favicon?: string;
  copyright?: string;
}

import type { SystemThemeEnum, MenuTypeEnum } from "@/enums/appEnum";
import type { MenuThemeType } from "@/types/store";

/** 主题设置 */
export interface ThemeSetting {
  name: string;
  theme: SystemThemeEnum;
  color: string[];
  leftLineColor: string;
  rightLineColor: string;
  img: string;
}

/** 菜单布局 */
export interface MenuLayout {
  name: string;
  value: MenuTypeEnum;
  img: string;
  description?: string;
}

export interface SystemConfig {
  systemInfo: SystemBasicConfig;
  systemThemeStyles: Record<"dark" | "light", { className: string }>;
  settingThemeList: ThemeSetting[];
  menuLayoutList: MenuLayout[];
  themeList: MenuThemeType[];
  darkMenuStyles: MenuThemeType[];
  systemMainColor: readonly string[];
  headerBar?: HeaderBarFeatureConfig;
}

/** 环境配置 */
export interface EnvConfig {
  NODE_ENV: string;
  VITE_VERSION: string;
  VITE_PORT: string;
  VITE_BASE_URL: string;
  VITE_API_URL: string;
  VITE_USE_MOCK?: string;
  VITE_USE_GZIP?: string;
  VITE_USE_CDN?: string;
}

/** 应用配置 */
export interface AppConfig extends SystemConfig {
  env: EnvConfig;
  isDev: boolean;
  isProd: boolean;
  isTest: boolean;
}

/** 功能配置项基础接口 */
export interface FeatureConfigItem {
  enabled: boolean;
  description: string;
}

/** 顶部栏功能配置接口 */
export interface HeaderBarFeatureConfig {
  menuButton: FeatureConfigItem;
  refreshButton: FeatureConfigItem;
  breadcrumb: FeatureConfigItem;
  globalSearch: FeatureConfigItem;
  fullscreen: FeatureConfigItem;
  language: FeatureConfigItem;
  settings: FeatureConfigItem;
  themeToggle: FeatureConfigItem;
  sizeSelect: FeatureConfigItem;
}
