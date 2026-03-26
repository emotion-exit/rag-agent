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
  colorBackground: '#fafafa',
  colorBackgroundSoft: '#f5f5f5',
  colorBackgroundMute: '#e5e5e5',
  colorSurface: '#ffffff',
  colorSurfaceSoft: '#fafafa',
  colorSurfaceMuted: '#f5f5f5',
  colorBorder: '#e5e5e5',
  colorBorderSoft: '#f5f5f5',
  colorBorderStrong: '#d4d4d4',
  colorHeading: '#0a0a0a',
  colorText: '#171717',
  colorTextSecondary: '#525252',
  colorTextMuted: '#737373',
  colorTextSubtle: '#a3a3a3',
  colorPrimary: '#0a0a0a',
  colorPrimarySoft: '#f5f5f5',
  colorPrimaryStrong: '#000000',
  colorSuccess: '#16a34a',
  colorSuccessSoft: '#dcfce7',
  colorSuccessBorder: '#bbf7d0',
  colorDanger: '#dc2626',
  colorDangerSoft: '#fee2e2',
  colorDangerBorder: '#fecaca',
  colorWarning: '#d97706',
  colorWarningSoft: '#fff7ed',
  colorWarningBorder: '#ffedd5',
  colorOnPrimary: '#ffffff',
  colorOnSuccess: '#ffffff',
  shadowPanel: '0 4px 24px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)',
  shadowFloating:
    '0 12px 32px rgba(0, 0, 0, 0.08), 0 4px 8px rgba(0, 0, 0, 0.04)',
  shadowSubtle: '0 2px 8px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)',
  radiusXs: '4px',
  radiusSm: '6px',
  radiusMd: '8px',
  radiusLg: '12px',
  radiusXl: '16px',
  radiusFull: '9999px'
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
