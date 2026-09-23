import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests/browser', timeout: 60000, workers: 1, expect: {timeout: 15000},
  use: { baseURL: 'http://127.0.0.1:4173', viewport: { width: 1440, height: 1000 },
    launchOptions: { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } },
  webServer: { command: 'python3 -m http.server 4173 --bind 127.0.0.1 --directory build/web', url: 'http://127.0.0.1:4173', reuseExistingServer: true },
});
