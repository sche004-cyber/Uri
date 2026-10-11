import { defineConfig } from 'vite';

// Built into uri_ui/assets/office/ during staging (`npm ci && npm run build`), never committed, and served by the
// WebView2 host from the virtual host office.uri.local (AC15). Relative base, no CDN, no remote imports.

// Univer's docs layout loads ~80 hyphenation-dictionary chunks (af, de-1901, hu, nb, ...) through one table,
// PATTERN_LOADERS, in @univerjs/engine-render. The sheets panel never hyphenates (the built-in en-US pattern stays),
// and Univer's loader returns quietly when a language has no entry. This plugin replaces that table with {} so none of
// those chunks is built. It fails the build if the table is not found exactly once, so a Univer upgrade cannot
// silently bring them back or break the replacement.
function dropHyphenationPatterns() {
  const START = 'const PATTERN_LOADERS = {';
  return {
    name: 'uri-office-drop-hyphenation-patterns',
    enforce: 'pre',
    transform(code, id) {
      if (!/[\\/]@univerjs[\\/]engine-render[\\/]lib[\\/]es[\\/]index\.js$/.test(id)) return null;
      const first = code.indexOf(START);
      if (first < 0 || code.indexOf(START, first + 1) >= 0) {
        this.error('PATTERN_LOADERS table not found exactly once in @univerjs/engine-render');
      }
      const end = code.indexOf('\n};', first);
      if (end < 0) this.error('end of PATTERN_LOADERS table not found');
      const table = code.slice(first, end + 3);
      if (!/import\("\.\/af-[^"]+\.js"\)/.test(table)) this.error('PATTERN_LOADERS table has an unexpected shape');
      return { code: code.slice(0, first) + 'const PATTERN_LOADERS = {};' + code.slice(end + 3), map: null };
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [dropHyphenationPatterns()],
  build: {
    outDir: '../assets/office',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 8000,
    modulePreload: { polyfill: false },
  },
});
