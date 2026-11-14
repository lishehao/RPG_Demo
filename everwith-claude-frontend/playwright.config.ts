import {defineConfig} from '@playwright/test'

/**
 * E2E against the production build served locally (`vite preview`, 127.0.0.1:4173).
 * Everything runs on the in-browser mock adapter; no network service is contacted.
 * On Linux CI without a GPU, WebGL (Live2D) uses SwiftShader software rendering.
 */
const softwareGL = process.platform === 'linux' ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] : []

export default defineConfig({
  testDir: 'e2e',
  outputDir: 'test-results',
  timeout: 120_000,
  expect: {timeout: 15_000},
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', {outputFile: 'test-results/e2e-report.json'}]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    channel: 'chromium',
    viewport: {width: 1280, height: 800},
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    launchOptions: {args: softwareGL},
    // Tracing screencasts every frame; with software-GL Live2D that starves timers. Opt in with TRACE=1.
    trace: process.env.TRACE ? 'retain-on-failure' : 'off',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run build && npm run preview',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
