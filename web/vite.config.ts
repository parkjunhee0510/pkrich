import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Use the repository subpath only for production builds.
  base: command === 'serve' ? '/' : '/pkrich/',
}))
