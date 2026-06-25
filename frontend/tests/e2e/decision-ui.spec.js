import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const artifactDir = path.resolve('../artifacts/ui')
fs.mkdirSync(artifactDir, { recursive: true })

async function authenticate(page) {
  const response = await page.request.post(
    'http://127.0.0.1:8000/api/v1/accounts/login/',
    { data: { username: 'ksm960mm', password: 'ssafy486' } },
  )
  expect(response.ok()).toBeTruthy()
  const tokens = await response.json()
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
        name: /식재료 가격이 오르기 전에/,
      })).toBeVisible()
      await expect(page.getByText('실제 시장 데이터')).toBeVisible()
      await assertNoHorizontalOverflow(page)
      await page.screenshot({
        path: path.join(artifactDir, `landing-${viewport.name}.png`),
        fullPage: true,
      })
    })

    test(`authenticated pages ${viewport.name}`, async ({ page }) => {
      await authenticate(page)
      const pages = [
        ['/app', /오늘 먼저 확인할 재료와 메뉴/, 'dashboard'],
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
