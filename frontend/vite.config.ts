import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// base must match the GitHub Pages path (github.com/Jeevan-0508/risk-replay ->
// jeevan-0508.github.io/risk-replay/) so built asset URLs resolve correctly.
export default defineConfig({
  base: '/risk-replay/',
  plugins: [react()],
})
