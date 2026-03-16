import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx,js,jsx}'],
  theme: {
    extend: {
      boxShadow: {
        panel: '0 12px 30px rgba(24, 24, 27, 0.04)',
        floating: '0 20px 48px rgba(24, 24, 27, 0.12)',
        subtle: '0 8px 20px rgba(24, 24, 27, 0.05)'
      },
      keyframes: {
        'o-fade-in': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        'o-scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' }
        },
        'o-spin-slow': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' }
        }
      },
      animation: {
        'o-fade-in': 'o-fade-in 0.24s ease-out',
        'o-scale-in': 'o-scale-in 0.24s ease-out',
        'o-spin-slow': 'o-spin-slow 1s linear infinite'
      }
    }
  },
  plugins: []
} satisfies Config;
