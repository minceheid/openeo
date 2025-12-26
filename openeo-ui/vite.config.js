import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(),tailwindcss()],
  server: {
	  cors: true,
    host: true,      // same as 0.0.0.0
    port: 5173,
    strictPort: true
  },
  rollupOptions: {
              output: {
                  dir: 'dist/assets',
                  entryFileNames: 'ui.js',
                  assetFileNames: 'ui.css',
              }}})
