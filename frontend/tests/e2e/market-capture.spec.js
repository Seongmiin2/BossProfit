import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const artifactDir = path.resolve('../artifacts/ui')
fs.mkdirSync(artifactDir, { recursive: true })

function issueLocalTestTokens() {
  const backendDir = path.resolve('../bossprofit')
  const python = path.resolve('../.venv/Scripts/python.exe')
  const username = process.env.BOSSPROFIT_E2E_USERNAME || 'ksm960mm'
  const script = [
    'import json',
    'from django.contrib.auth import get_user_model',
    'from rest_framework_simplejwt.tokens import RefreshToken',
    `user=get_user_model().objects.get(username=${JSON.stringify(username)})`,
    'refresh=RefreshToken.for_user(user)',
    'print(json.dumps({"access": str(refresh.access_token), "refresh": str(refresh)}))',
  ].join(';')
  const output = execFileSync(
    python,
    ['manage.py', 'shell', '-c', script],
    { cwd: backendDir, encoding: 'utf8' },
  )
  return JSON.parse(output.trim().split(/\r?\n/).at(-1))
}

async function authenticate(page) {
  const tokens = issueLocalTestTokens()
  await page.addInitScript(({ access, refresh }) => {
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }, tokens)
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1100 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } })

    test(`market detail ${viewport.name}`, async ({ page }) => {
      await authenticate(page)
      await page.goto('http://localhost:5173/market/rankings/tomorrow')
      await page.waitForLoadState('networkidle')
      // 상세 패널(1·7·30일 전망 막대)이 그려질 때까지 대기
      await expect(page.locator('.ranking-outlook')).toBeVisible()
      await page.screenshot({
        path: path.join(artifactDir, `market-${viewport.name}.png`),
        fullPage: true,
      })
    })
  })
}
