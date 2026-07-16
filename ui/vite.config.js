import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// Migrated off Create React App. The two JSX entry files (main.jsx, App.jsx)
// were renamed from `.js` so Rollup's build-time import analysis parses them as
// JSX; everything else already used the `.jsx` extension.
export default defineConfig({
  plugins: [react()],
  resolve: {
    // One import root. Every cross-directory import in src/ is written as
    // "@/tabs/GuideTab", "@/components/ui", "@/styles/theme" — so a file can
    // move between folders without a wave of ../../ churn, and so an import
    // line says WHAT layer it reaches into (kit / tab / lib / config).
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    open: false,
  },
  build: {
    // Keep CRA's output directory so any existing tooling/muscle memory holds.
    outDir: 'build',
  },
  // Tests run through this same config, so they resolve "@/..." exactly the way
  // the app does — no second alias table to drift out of sync.
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    // Only our own tests. Without this, vitest walks node_modules.
    include: ['src/**/*.test.{js,jsx}'],
  },
});
