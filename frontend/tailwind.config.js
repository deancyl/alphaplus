/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors from PRD
        'brand-navy-dark': '#003399',
        'brand-navy-active': '#0B3CC3',
        'brand-gold': '#FFD700',
        'brand-gray': '#F5F5F5',
        
        // Market colors (A-share semantics: red=up, green=down)
        'market-up': '#E63935',
        'market-down': '#2E7D32',
        'market-flat': '#999999',
        
        // Background colors
        'bg-system': '#F4F6F9',
        'bg-card': '#FFFFFF',
        
        // Border colors
        'border-line': '#E5E8ED',
        
        // Text colors
        'text-primary': '#1A1A1A',
        'text-regular': '#4A4A4A',
        'text-muted': '#999999',
      },
      spacing: {
        'xs': '4px',
        'sm': '8px',
        'md': '16px',
        'lg': '24px',
        'xl': '32px',
      },
      screens: {
        'mobile': '480px',
        'tablet': '768px',
        'desktop': '1024px',
        'wide': '1400px',
      },
      minHeight: {
        'touch': '44px',
      },
      minWidth: {
        'touch': '44px',
      },
    },
  },
  plugins: [],
  // Preserve existing CSS - hybrid approach
  corePlugins: {
    preflight: false, // Disable Tailwind's base reset to keep existing CSS
  },
}
