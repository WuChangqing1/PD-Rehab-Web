// Run against the isolated localhost SSH tunnel. The short-lived token is injected at runtime.
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PD_QA_PLAYWRIGHT || 'playwright')

const base = 'http://127.0.0.1:18193'
const browser = await chromium.launch({
  headless: true, ...(process.env.PD_QA_CHROME ? { executablePath: process.env.PD_QA_CHROME } : {}),
})
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: 'Asia/Shanghai' })
  const page = await ctx.newPage()
  await ctx.addInitScript(token => localStorage.setItem('pd-rehab-token', token), process.env.PD_QA_TOKEN)
  const url = new URL('/follow-up', base)
  url.searchParams.set('patientId', process.env.PD_QA_PATIENT)
  await page.goto(url.href)
  await page.getByRole('tab', { name: '软件端记录' }).click()
  await page.getByText('训练计划', { exact: true }).click()
  const date = page.locator('input[type=date]')
  await date.fill('2026-11-04')
  const row = page.getByRole('row').filter({ hasText: 'QA count' }).first()
  await row.getByText('2/3 次', { exact: true }).waitFor()
  await row.getByRole('button', { name: '详情', exact: true }).click()
  await page.getByRole('dialog').getByText('2/3 次', { exact: true }).waitFor()
  await page.keyboard.press('Escape')
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  await date.fill('2026-11-03')
  await row.getByText('进度未知', { exact: true }).waitFor()
  console.log('Browser: latest snapshot 2/3 on 2026-11-04; missing date displays 进度未知.')
  assert.equal(await row.count(), 1)
} finally {
  await browser.close()
}
