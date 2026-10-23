import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  // Pinned here rather than passed on the command line. PowerShell strips the
  // leading dashes from arguments after `npm run dev --`, so `--port 5176`
  // arrived at Vite as the bare positional `5176` and was ignored, leaving the
  // dev server on its default 5173 while the browser was pointed at 5176.
  // Configuring it in the file means plain `npm run dev` is always correct.
  server: {
    host: '127.0.0.1',
    port: 5176,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 5176,
    strictPort: true,
  },
});
