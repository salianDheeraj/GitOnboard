/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-geist-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        workspace: {
          bg: '#0A0D10',
          surface: '#14181E',
          'surface-raised': '#1E222A',
          border: '#2F343A',
          text: '#E6EDF3',
          'text-muted': '#8B949E',
          accent: '#9333EA',
        },
      },
    },
  },
  plugins: [],
};
