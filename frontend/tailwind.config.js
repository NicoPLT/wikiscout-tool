/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--bg-primary)',
          surface: 'var(--bg-surface)',
          'surface-hover': 'var(--bg-surface-hover)',
        },
        border: {
          subtle: 'var(--border-subtle)',
        },
        accent: {
          primary: 'var(--accent-primary)',
          hover: 'var(--accent-primary-hover)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          onaccent: 'var(--text-on-accent)',
        },
        success: 'var(--success)',
        danger: 'var(--danger)',
      },
      fontFamily: {
        sans: ['"Albert Sans"', 'sans-serif'],
      },
      borderRadius: {
        sm: '4px',
        md: '6px',
        card: '10px',
      },
      letterSpacing: {
        tighter2: '-1px',
      },
      spacing: {
        18: '4.5rem',
      },
    },
  },
  plugins: [],
}
