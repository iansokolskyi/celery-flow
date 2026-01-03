import { expect, test } from '@playwright/test'

import { setupMockApi } from './fixtures/mock-api'

/**
 * Tests for the Workers page.
 *
 * These tests use mocked API responses, no Docker required.
 * Run with E2E_MODE=real for integration testing against Docker.
 */

const isRealMode = process.env.E2E_MODE === 'real'

test.describe('Workers Page', () => {
  test.beforeEach(async ({ page }) => {
    if (!isRealMode) {
      await setupMockApi(page)
    }
    await page.goto('/workers')
  })

  test('displays workers page', async ({ page }) => {
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('heading', { name: 'Workers', level: 1 })).toBeVisible()
  })

  test('shows worker entries from API', async ({ page }) => {
    await page.waitForLoadState('networkidle')

    if (isRealMode) {
      // Real Docker mode: assert we render at least one worker card from the backend.
      const workerHeadings = page.getByRole('heading', { level: 3 })
      await expect(workerHeadings.first()).toBeVisible()
      await expect(page.getByText(/Online|Offline/).first()).toBeVisible()
      await expect(page.getByText('No workers registered')).toHaveCount(0)
      return
    }

    // Mock mode: default mock data includes worker-1 and worker-2
    await expect(page.getByRole('heading', { name: 'worker-1', level: 3 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'worker-2', level: 3 })).toBeVisible()

    // Status badges should render
    await expect(page.getByText('Online').first()).toBeVisible()
    await expect(page.getByText('Offline').first()).toBeVisible()
  })

  test('shows empty state when no workers', async ({ page }) => {
    if (isRealMode) {
      test.skip()
      return
    }

    const mockApi = await setupMockApi(page, { useDefaults: false })
    mockApi.clearWorkers()

    await page.goto('/workers')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('No workers registered')).toBeVisible()
  })
})
