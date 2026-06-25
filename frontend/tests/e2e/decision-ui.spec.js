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

async function assertNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  )
  expect(overflow).toBeFalsy()
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1100 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } })

    test(`landing ${viewport.name}`, async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')
      await expect(page.getByRole('heading', {
        name: /오르기 전에/,
      })).toBeVisible()
      await expect(page.getByText('시장 가격 예측', { exact: true })).toBeVisible()
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(artifactDir, `landing-${viewport.name}.png`),
        fullPage: true,
      })
    })

    test(`authenticated pages ${viewport.name}`, async ({ page }) => {
      await authenticate(page)
      const pages = [
        ['/app', /내 가게 재료/, 'dashboard'],
        ['/menus', /어떤 메뉴가 가장 많이 팔리고 있을까요/, 'menus'],
        ['/history', /AI 매장 분석 리포트/, 'report'],
      ]
      for (const [url, heading, name] of pages) {
        await page.goto(url)
        await page.waitForLoadState('networkidle')
        await expect(page.getByRole('heading', { name: heading })).toBeVisible()
        if (name === 'menus') {
          await expect(page.locator('.bp-photo-menu-grid > button')).toHaveCount(5)
        }
        await assertNoHorizontalOverflow(page)
        await page.screenshot({
          path: path.join(artifactDir, `${name}-${viewport.name}.png`),
          fullPage: true,
        })
      }
    })
  })
}
