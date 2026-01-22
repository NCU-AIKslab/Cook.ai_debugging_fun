/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Typography
      fontFamily: {
        'sans': ['Inter', 'Noto Sans TC', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.6' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['2rem', { lineHeight: '2.5rem' }],
        '4xl': ['2.5rem', { lineHeight: '3rem' }],
      },

      // Colors - Gamma Style (colorful, gradients, rounded)
      colors: {
        'theme': {
          // Logo gradient
          'gradient-start': '#1E40AF',
          'gradient-middle': '#0EA5E9',
          'gradient-end': '#14B8A6',

          // Primary - Sky Blue (friendly, educational)
          'primary': '#0EA5E9',
          'primary-hover': '#0284C7',
          'primary-active': '#0369A1',
          'primary-light': '#E0F2FE',

          // Accent - Teal (vibrant, modern)
          'accent': '#14B8A6',
          'accent-hover': '#0D9488',
          'accent-light': '#CCFBF1',

          // Secondary
          'secondary': '#64748B',
          'secondary-hover': '#475569',

          // Status colors (LangSmith style badges)
          'success': '#22C55E',
          'success-light': '#DCFCE7',
          'success-text': '#15803D',
          'warning': '#F59E0B',
          'warning-light': '#FEF3C7',
          'warning-text': '#B45309',
          'danger': '#EF4444',
          'danger-light': '#FEE2E2',
          'danger-text': '#DC2626',
          'info': '#0EA5E9',
          'info-light': '#E0F2FE',
          'info-text': '#0369A1',

          // Background & Surface
          'background': '#FAFAFA',
          'surface': '#FFFFFF',
          'surface-hover': '#F5F5F5',

          // Border
          'border': '#E5E7EB',
          'border-light': '#F3F4F6',

          // Checkbox & Focus
          'checkbox': '#0EA5E9',
          'ring': '#0EA5E9',
        },

        'neutral': {
          'text-main': '#1F2937',
          'text-secondary': '#4B5563',
          'text-tertiary': '#9CA3AF',
          'text-on-dark': '#F9FAFB',
          'border': '#E5E7EB',
          'background': '#FAFAFA',
          'icon': '#6B7280',
          'icon-hover': '#374151',

          // Footer
          'footer-bg': '#111827',
          'footer-border': '#374151',
          'footer-text': '#9CA3AF',
        },

        'destructive': {
          'DEFAULT': '#EF4444',
          'hover': '#DC2626',
          'light': '#FEE2E2',
        },
      },

      // Gradient Backgrounds (Gamma style)
      backgroundImage: {
        'gradient-soft': 'linear-gradient(135deg, #E0F2FE 0%, #F0FDFA 50%, #FDF4FF 100%)',
        'gradient-button': 'linear-gradient(135deg, #0EA5E9 0%, #14B8A6 100%)',
        'gradient-card-hover': 'linear-gradient(135deg, #F0F9FF 0%, #F0FDFA 100%)',
      },

      // Standardized Border Radius (Gamma - rounder)
      borderRadius: {
        'none': '0',
        'sm': '6px',
        'DEFAULT': '12px',
        'md': '12px',
        'lg': '16px',
        'xl': '20px',
        '2xl': '24px',
        'full': '9999px',
      },

      // Shadows
      boxShadow: {
        'none': 'none',
        'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'DEFAULT': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
        'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.08)',
        'card-hover': '0 4px 12px 0 rgba(14, 165, 233, 0.15)',
      },

      // Spacing
      spacing: {
        '4.5': '1.125rem',
        '13': '3.25rem',
        '15': '3.75rem',
        '18': '4.5rem',
      },

      // Transitions
      transitionDuration: {
        '200': '200ms',
        '300': '300ms',
        '400': '400ms',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },

      // Animation
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },

  plugins: [
    require('@tailwindcss/forms'),
  ],
}