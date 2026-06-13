import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Migrated off Create React App. The two JSX entry files (index.jsx, App.jsx)
// were renamed from `.js` so Rollup's build-time import analysis parses them as
// JSX; everything else already used the `.jsx` extension.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: false,
  },
  build: {
    // Keep CRA's output directory so any existing tooling/muscle memory holds.
    outDir: 'build',
  },
});
