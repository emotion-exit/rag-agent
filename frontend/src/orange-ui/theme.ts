import type { CSSProperties, InjectionKey, Ref } from 'vue';

export interface OrangeThemeTokens {
  colorBackground: string;
  colorBackgroundSoft: string;
  colorBackgroundMute: string;
  colorSurface: string;
  colorSurfaceSoft: string;
  colorSurfaceMuted: string;
  colorBorder: string;
  colorBorderSoft: string;
  colorBorderStrong: string;
  colorHeading: string;
  colorText: string;
  colorTextSecondary: string;
  colorTextMuted: string;
  colorTextSubtle: string;
  colorPrimary: string;
  colorPrimarySoft: string;
  colorPrimaryStrong: string;
  colorSuccess: string;
  colorSuccessSoft: string;
  colorSuccessBorder: string;
  colorDanger: string;
  colorDangerSoft: string;
  colorDangerBorder: string;
  colorWarning: string;
  colorWarningSoft: string;
  colorWarningBorder: string;
  colorOnPrimary: string;
  colorOnSuccess: string;
  shadowPanel: string;
  shadowFloating: string;
  shadowSubtle: string;
  radiusXs: string;
  radiusSm: string;
  radiusMd: string;
  radiusLg: string;
  radiusXl: string;
  radiusFull: string;
}

export const defaultOrangeTheme: OrangeThemeTokens = {
  colorBackground: '#ffffff',
  colorBackgroundSoft: '#ffffff',
  colorBackgroundMute: '#ededed',
  colorSurface: '#ffffff',
  colorSurfaceSoft: '#f8f8f8',
  colorSurfaceMuted: '#f3f4f6',
  colorBorder: '#d4d4d8',
  colorBorderSoft: '#e4e4e7',
  colorBorderStrong: '#a1a1aa',
  colorHeading: '#18181b',
  colorText: '#18181b',
  colorTextSecondary: '#3f3f46',
  colorTextMuted: '#71717a',
  colorTextSubtle: '#a1a1aa',
  colorPrimary: '#18181b',
  colorPrimarySoft: '#f4f4f5',
  colorPrimaryStrong: '#09090b',
  colorSuccess: '#2f6b4f',
  colorSuccessSoft: '#eef7f1',
  colorSuccessBorder: '#d7e9dd',
  colorDanger: '#b1372a',
  colorDangerSoft: '#fef2f2',
  colorDangerBorder: '#fee2e2',
  colorWarning: '#d97706',
  colorWarningSoft: '#fff7ed',
  colorWarningBorder: '#ffedd5',
  colorOnPrimary: '#ffffff',
  colorOnSuccess: '#ffffff',
  shadowPanel:
    '0 12px 30px rgba(24, 24, 27, 0.04), 0 4px 12px rgba(24, 24, 27, 0.02)',
  shadowFloating:
    '0 20px 60px rgba(24, 24, 27, 0.16), 0 8px 24px rgba(24, 24, 27, 0.08)',
  shadowSubtle:
    '0 8px 20px rgba(24, 24, 27, 0.05), 0 2px 6px rgba(24, 24, 27, 0.02)',
  radiusXs: '10px',
  radiusSm: '14px',
  radiusMd: '18px',
  radiusLg: '22px',
  radiusXl: '24px',
  radiusFull: '999px'
};

export const orangeThemeKey = Symbol('orange-theme') as InjectionKey<
  Ref<OrangeThemeTokens>
>;

export function resolveOrangeTheme(overrides?: Partial<OrangeThemeTokens>) {
  return {
    ...defaultOrangeTheme,
    ...(overrides || {})
  } satisfies OrangeThemeTokens;
}

export function toOrangeThemeVars(theme: OrangeThemeTokens): CSSProperties {
  return {
    '--oui-color-bg': theme.colorBackground,
    '--oui-color-bg-soft': theme.colorBackgroundSoft,
    '--oui-color-bg-mute': theme.colorBackgroundMute,
    '--oui-color-surface': theme.colorSurface,
    '--oui-color-surface-soft': theme.colorSurfaceSoft,
    '--oui-color-surface-muted': theme.colorSurfaceMuted,
    '--oui-color-border': theme.colorBorder,
    '--oui-color-border-soft': theme.colorBorderSoft,
    '--oui-color-border-strong': theme.colorBorderStrong,
    '--oui-color-heading': theme.colorHeading,
    '--oui-color-text': theme.colorText,
    '--oui-color-text-secondary': theme.colorTextSecondary,
    '--oui-color-text-muted': theme.colorTextMuted,
    '--oui-color-text-subtle': theme.colorTextSubtle,
    '--oui-color-primary': theme.colorPrimary,
    '--oui-color-primary-soft': theme.colorPrimarySoft,
    '--oui-color-primary-strong': theme.colorPrimaryStrong,
    '--oui-color-success': theme.colorSuccess,
    '--oui-color-success-soft': theme.colorSuccessSoft,
    '--oui-color-success-border': theme.colorSuccessBorder,
    '--oui-color-danger': theme.colorDanger,
    '--oui-color-danger-soft': theme.colorDangerSoft,
    '--oui-color-danger-border': theme.colorDangerBorder,
    '--oui-color-warning': theme.colorWarning,
    '--oui-color-warning-soft': theme.colorWarningSoft,
    '--oui-color-warning-border': theme.colorWarningBorder,
    '--oui-color-on-primary': theme.colorOnPrimary,
    '--oui-color-on-success': theme.colorOnSuccess,
    '--oui-shadow-panel': theme.shadowPanel,
    '--oui-shadow-floating': theme.shadowFloating,
    '--oui-shadow-subtle': theme.shadowSubtle,
    '--oui-radius-xs': theme.radiusXs,
    '--oui-radius-sm': theme.radiusSm,
    '--oui-radius-md': theme.radiusMd,
    '--oui-radius-lg': theme.radiusLg,
    '--oui-radius-xl': theme.radiusXl,
    '--oui-radius-full': theme.radiusFull,
    '--color-background': theme.colorBackground,
    '--color-background-soft': theme.colorBackgroundSoft,
    '--color-background-mute': theme.colorBackgroundMute,
    '--color-surface': theme.colorSurface,
    '--color-surface-soft': theme.colorSurfaceSoft,
    '--color-surface-muted': theme.colorSurfaceMuted,
    '--color-border': theme.colorBorder,
    '--color-border-soft': theme.colorBorderSoft,
    '--color-border-strong': theme.colorBorderStrong,
    '--color-heading': theme.colorHeading,
    '--color-text': theme.colorText,
    '--color-text-secondary': theme.colorTextSecondary,
    '--color-text-muted': theme.colorTextMuted,
    '--color-text-subtle': theme.colorTextSubtle,
    '--color-success': theme.colorSuccess,
    '--color-success-soft': theme.colorSuccessSoft,
    '--color-success-border': theme.colorSuccessBorder,
    '--color-danger': theme.colorDanger,
    '--color-danger-soft': theme.colorDangerSoft,
    '--color-danger-border': theme.colorDangerBorder,
    '--color-warning': theme.colorWarning,
    '--color-warning-soft': theme.colorWarningSoft,
    '--color-warning-border': theme.colorWarningBorder,
    '--color-on-success': theme.colorOnSuccess,
    '--shadow-panel': theme.shadowPanel,
    '--shadow-floating': theme.shadowFloating,
    '--shadow-subtle': theme.shadowSubtle
  } as CSSProperties;
}
