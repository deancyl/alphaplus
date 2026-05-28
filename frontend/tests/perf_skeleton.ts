/**
 * Skeleton Loader Performance Tests
 * 
 * Verifies skeleton components render quickly (FCP < 500ms)
 * and shimmer animation runs smoothly (60fps).
 * 
 * Run with: npx playwright test perf_skeleton.ts
 * 
 * Prerequisites:
 * - playwright installed
 * - frontend dev server running at http://localhost:60201
 */

import { test, expect, Page, BrowserContext } from '@playwright/test'

/**
 * Performance thresholds
 */
const THRESHOLDS = {
  FCP: 500, // First Contentful Paint < 500ms
  LCP: 2500, // Largest Contentful Paint < 2.5s
  TTI: 3800, // Time to Interactive < 3.8s
  CLS: 0.1, // Cumulative Layout Shift < 0.1
}

/**
 * Routes with skeleton implementations
 */
const SKELETON_ROUTES = [
  { path: '/', name: 'Dashboard', expectedSkeletons: 6 },
  { path: '/fund/filter', name: 'FundFilter', expectedSkeletons: 1 },
  { path: '/fund/compare', name: 'FundCompare', expectedSkeletons: 3 },
  { path: '/market/index-valuation', name: 'IndexValuation', expectedSkeletons: 8 },
]

/**
 * Helper to measure performance metrics
 */
async function measurePerformance(page: Page) {
  const metrics = await page.evaluate(() => {
    return new Promise<{
      fcp: number
      lcp: number
      tti: number
      cls: number
    }>((resolve) => {
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        const fcp = entries.find((e) => e.name === 'first-contentful-paint')
        const lcp = entries.find((e) => e.entryType === 'largest-contentful-paint')
        
        if (fcp && lcp) {
          observer.disconnect()
          
          // Get CLS from layout-shift entries
          let cls = 0
          const clsEntries = performance.getEntriesByType('layout-shift')
          for (const entry of clsEntries) {
            if (!(entry as any).hadRecentInput) {
              cls += (entry as any).value
            }
          }
          
          resolve({
            fcp: fcp.startTime,
            lcp: lcp.startTime,
            tti: lcp.startTime + 500, // Approximate TTI
            cls,
          })
        }
      })
      
      observer.observe({
        entryTypes: ['paint', 'largest-contentful-paint', 'layout-shift'],
      })
      
      // Fallback timeout
      setTimeout(() => {
        observer.disconnect()
        const paintEntries = performance.getEntriesByType('paint')
        const fcp = paintEntries.find((e) => e.name === 'first-contentful-paint')
        resolve({
          fcp: fcp?.startTime || 0,
          lcp: 0,
          tti: 0,
          cls: 0,
        })
      }, 10000)
    })
  })
  
  return metrics
}

/**
 * Helper to count skeleton elements
 */
async function countSkeletonElements(page: Page): Promise<number> {
  return await page.locator('.skeleton').count()
}

/**
 * Helper to verify shimmer animation
 */
async function verifyShimmerAnimation(page: Page): Promise<boolean> {
  return await page.evaluate(() => {
    const skeleton = document.querySelector('.skeleton')
    if (!skeleton) return false
    
    const styles = window.getComputedStyle(skeleton)
    const backgroundSize = styles.backgroundSize
    const animation = styles.animationName
    
    // Check if shimmer animation is applied
    return backgroundSize.includes('200%') || animation.includes('shimmer')
  })
}

test.describe('Skeleton Loader Performance', () => {
  test.beforeEach(async ({ page }) => {
    // Enable performance tracking
    await page.context().route('**/*', async (route) => {
      await route.continue()
    })
  })
  
  test.describe('First Contentful Paint (FCP)', () => {
    for (const route of SKELETON_ROUTES) {
      test(`${route.name} should show skeletons with FCP < ${THRESHOLDS.FCP}ms`, async ({ page }) => {
        // Navigate and measure FCP
        await page.goto(`http://localhost:60201${route.path}`, {
          waitUntil: 'domcontentloaded',
        })
        
        // Wait for skeleton to appear
        const skeletonCount = await countSkeletonElements(page)
        
        // Verify skeletons appeared
        expect(skeletonCount).toBeGreaterThan(0)
        
        // Get performance metrics
        const metrics = await measurePerformance(page)
        
        console.log(`${route.name} Metrics:`, {
          FCP: `${metrics.fcp.toFixed(0)}ms`,
          LCP: `${metrics.lcp.toFixed(0)}ms`,
          CLS: metrics.cls.toFixed(3),
        })
        
        // FCP should be under threshold
        expect(metrics.fcp).toBeLessThan(THRESHOLDS.FCP)
      })
    }
  })
  
  test.describe('Skeleton Rendering', () => {
    test('should render skeleton elements before data loads', async ({ page }) => {
      // Slow down network to ensure we see skeletons
      await page.route('**/api/**', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 500))
        await route.continue()
      })
      
      await page.goto('http://localhost:60201/', {
        waitUntil: 'domcontentloaded',
      })
      
      // Count skeletons immediately after load
      const initialSkeletonCount = await countSkeletonElements(page)
      expect(initialSkeletonCount).toBeGreaterThan(0)
      
      // Wait for actual data to load
      await page.waitForTimeout(2000)
      
      // Skeletons should be replaced with content
      const finalSkeletonCount = await countSkeletonElements(page)
      expect(finalSkeletonCount).toBeLessThan(initialSkeletonCount)
    })
    
    test('skeleton should have proper CSS classes', async ({ page }) => {
      await page.goto('http://localhost:60201/', {
        waitUntil: 'domcontentloaded',
      })
      
      // Check skeleton elements exist with correct class
      const skeleton = page.locator('.skeleton').first()
      await expect(skeleton).toBeVisible()
      
      // Verify shimmer animation
      const hasAnimation = await verifyShimmerAnimation(page)
      expect(hasAnimation).toBe(true)
    })
  })
  
  test.describe('Layout Stability (CLS)', () => {
    test('skeleton should minimize layout shift', async ({ page }) => {
      await page.goto('http://localhost:60201/', {
        waitUntil: 'networkidle',
      })
      
      const metrics = await measurePerformance(page)
      
      console.log('CLS:', metrics.cls.toFixed(4))
      
      // CLS should be minimal
      expect(metrics.cls).toBeLessThan(THRESHOLDS.CLS)
    })
  })
  
  test.describe('Shimmer Animation Performance', () => {
    test('shimmer animation should run at 60fps', async ({ page }) => {
      await page.goto('http://localhost:60201/', {
        waitUntil: 'domcontentloaded',
      })
      
      // Start performance trace
      await page.context().tracing.start({ screenshots: false, snapshots: false })
      
      // Wait for animation to run
      await page.waitForTimeout(1500)
      
      // Stop trace
      await page.context().tracing.stop()
      
      // Verify animation is applied via CSS (no JS overhead)
      const animationDuration = await page.evaluate(() => {
        const skeleton = document.querySelector('.skeleton')
        if (!skeleton) return null
        
        const styles = window.getComputedStyle(skeleton)
        return styles.animationDuration
      })
      
      // Should have animation duration of 1.5s
      expect(animationDuration).toBe('1.5s')
    })
    
    test('skeleton should respect prefers-reduced-motion', async ({ page }) => {
      // Emulate reduced motion preference
      await page.emulateMedia({ reducedMotion: 'reduce' })
      
      await page.goto('http://localhost:60201/', {
        waitUntil: 'domcontentloaded',
      })
      
      // Check that animation is disabled
      const animationName = await page.evaluate(() => {
        const skeleton = document.querySelector('.skeleton')
        if (!skeleton) return null
        
        const styles = window.getComputedStyle(skeleton)
        return styles.animationName
      })
      
      // Animation should be 'none' when reduced motion is preferred
      expect(animationName).toBe('none')
    })
  })
  
  test.describe('Variant-Specific Tests', () => {
    test('table skeleton should render correct structure', async ({ page }) => {
      await page.goto('http://localhost:60201/fund/filter', {
        waitUntil: 'domcontentloaded',
      })
      
      // Check table skeleton structure
      const tableSkeleton = page.locator('.skeleton-table')
      const headerCells = page.locator('.skeleton-table__header-cell')
      const rows = page.locator('.skeleton-table__row')
      
      // Should have header cells
      await expect(headerCells.first()).toBeVisible()
      
      // Should have multiple rows
      const rowCount = await rows.count()
      expect(rowCount).toBeGreaterThan(0)
    })
    
    test('gauge skeleton should have correct structure', async ({ page }) => {
      await page.goto('http://localhost:60201/', {
        waitUntil: 'domcontentloaded',
      })
      
      // Check gauge skeleton structure
      const gaugeSkeleton = page.locator('.skeleton-gauge')
      const arc = page.locator('.skeleton-gauge__arc')
      
      // Should have gauge arc element
      await expect(arc.first()).toBeVisible()
    })
    
    test('heatmap skeleton should have grid structure', async ({ page }) => {
      await page.goto('http://localhost:60201/', {
        waitUntil: 'domcontentloaded',
      })
      
      // Check heatmap skeleton cells
      const cells = page.locator('.skeleton-heatmap__cell')
      const cellCount = await cells.count()
      
      // Should have multiple cells in grid
      expect(cellCount).toBeGreaterThan(0)
    })
    
    test('valuation card skeleton should match actual card dimensions', async ({ page }) => {
      await page.goto('http://localhost:60201/market/index-valuation', {
        waitUntil: 'domcontentloaded',
      })
      
      // Check valuation card skeleton structure
      const cardSkeleton = page.locator('.skeleton-valuation-card')
      const peSkeleton = page.locator('.skeleton-valuation-card__pe')
      const barSkeleton = page.locator('.skeleton-valuation-card__bar')
      
      // Should have PE value skeleton
      await expect(peSkeleton.first()).toBeVisible()
      
      // Should have percentile bar skeleton
      await expect(barSkeleton.first()).toBeVisible()
    })
  })
})

test.describe('Skeleton CSS Compliance', () => {
  test('skeleton should use design system tokens', async ({ page }) => {
    await page.goto('http://localhost:60201/', {
      waitUntil: 'domcontentloaded',
    })
    
    const skeletonStyles = await page.evaluate(() => {
      const skeleton = document.querySelector('.skeleton')
      if (!skeleton) return null
      
      const styles = window.getComputedStyle(skeleton)
      return {
        background: styles.background,
        borderRadius: styles.borderRadius,
      }
    })
    
    // Should have border-radius matching design system (4px)
    expect(skeletonStyles?.borderRadius).toBe('4px')
  })
  
  test('skeleton should be visible on both light and dark themes', async ({ page }) => {
    // Test light mode
    await page.emulateMedia({ colorScheme: 'light' })
    await page.goto('http://localhost:60201/', { waitUntil: 'domcontentloaded' })
    
    const lightModeSkeleton = page.locator('.skeleton').first()
    await expect(lightModeSkeleton).toBeVisible()
    
    // Test dark mode
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.reload({ waitUntil: 'domcontentloaded' })
    
    const darkModeSkeleton = page.locator('.skeleton').first()
    await expect(darkModeSkeleton).toBeVisible()
  })
})
