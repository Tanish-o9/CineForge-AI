/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        studio: {
          darkest: '#000000',
          darker: '#080808',
          dark: '#121212',
          card: '#1a1a1a',
          gold: '#D4AF37',
          goldLight: '#E5C158',
          accent: '#b45309'
        }
      }
    },
  },
  plugins: [],
}
