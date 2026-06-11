/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f7fafc',
          100: '#edf2f7',
          200: '#e2e8f0',
          300: '#cbd5e0',
          400: '#a0aec0',
          500: '#718096',
          600: '#4A5568',
          700: '#2d3748',
          800: '#1a202c',
          900: '#171923',
        },
        success: {
          50: '#f0fff4',
          100: '#c6f6d5',
          500: '#48bb78',
          600: '#38a169',
          700: '#2f855a',
        },
        error: {
          50: '#fff5f5',
          100: '#fed7d7',
          500: '#f56565',
          600: '#e53e3e',
          700: '#c53030',
        },
        warning: {
          50: '#fffff0',
          100: '#feebc8',
          500: '#ecc94b',
          600: '#d69e2e',
          700: '#b7791f',
        },
        background: {
          primary: '#ffffff',
          secondary: '#f7fafc',
          tertiary: '#edf2f7',
        },
        text: {
          primary: '#1a202c',
          secondary: '#4A5568',
          muted: '#718096',
        },
        border: {
          primary: '#e2e8f0',
          secondary: '#cbd5e0',
          focus: '#4A5568',
        },
      },
      borderRadius: {
        DEFAULT: '10px',
        lg: '12px',
        md: '8px',
        sm: '4px',
      },
      boxShadow: {
        DEFAULT: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
    },
  },
  plugins: [],
}
