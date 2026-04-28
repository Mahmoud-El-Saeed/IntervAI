/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        app: '#10131a',
        surface: '#10131a',
        'surface-container-lowest': '#0b0e15',
        'surface-container-low': '#191b23',
        'surface-container': '#1d2027',
        'surface-container-high': '#272a31',
        'surface-container-highest': '#32353c',
        'on-surface': '#e1e2ec',
        'on-surface-variant': '#c2c6d6',
        'outline-variant': '#424754',
        outline: '#8c909f',
        primary: '#adc6ff',
        'primary-container': '#4d8eff',
        'on-primary-container': '#00285d',
        secondary: '#b9c7df',
        tertiary: '#ffb786',
        error: '#ffb4ab',
        'error-container': '#93000a',
        success: '#22c55e',
      },
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        code: ['Space Grotesk', 'sans-serif'],
      },
      borderRadius: {
        sm: '0.25rem',
        md: '0.5rem',
        lg: '1rem',
        xl: '1.5rem',
      },
      boxShadow: {
        glow: '0 0 20px rgba(59, 130, 246, 0.3)',
        card: 'inset 0 0 0 1px rgba(255, 255, 255, 0.08)',
      },
      maxWidth: {
        container: '1280px',
      },
      spacing: {
        xs: '0.5rem',
        sm: '1rem',
        md: '1.5rem',
        lg: '2.5rem',
        xl: '4rem',
      },
    },
  },
  plugins: [],
};

