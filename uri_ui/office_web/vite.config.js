import { defineConfig } from 'vite';

// Built into uri_ui/assets/office/ and served by the WebView2 host from the virtual host office.uri.local (AC15).
// Relative base, no CDN, no remote imports; everything the page needs is in that folder.
export default defineConfig({
  base: './',
  build: {
    outDir: '../assets/office',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 8000,
    modulePreload: { polyfill: false },
  },
});
