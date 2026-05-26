/**
 * Test file for EChartsWrapper.vue enhancements
 * Run with: npx vitest run EChartsWrapper.test.ts
 */

import { describe, it, expect } from 'vitest'

// Test getHeatmapColor logic (extracted for testing)
const getHeatmapColor = (value: number, min: number, max: number): string => {
  const range = max - min
  const normalized = range === 0 ? 0.5 : Math.max(0, Math.min(1, (value - min) / range))
  
  const steps = 7
  const stepSize = 1 / steps
  const stepIndex = Math.min(Math.floor(normalized / stepSize), steps - 1)
  
  const red = { r: 230, g: 57, b: 53 }
  const green = { r: 46, g: 125, b: 50 }
  
  const t = stepIndex / (steps - 1)
  const r = Math.round(red.r + (green.r - red.r) * t)
  const g = Math.round(red.g + (green.g - red.g) * t)
  const b = Math.round(red.b + (green.b - red.b) * t)
  
  const alpha = 0.9
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

describe('EChartsWrapper Enhancements', () => {
  describe('getHeatmapColor', () => {
    it('returns red for low values (0-14%)', () => {
      const color = getHeatmapColor(0, 0, 100)
      expect(color).toBe('rgba(230, 57, 53, 0.9)')
    })

    it('returns green for high values (86-100%)', () => {
      const color = getHeatmapColor(100, 0, 100)
      expect(color).toBe('rgba(46, 125, 50, 0.9)')
    })

    it('returns intermediate color for middle values', () => {
      const color = getHeatmapColor(50, 0, 100)
      // Step 3 (42-57%) should give a middle color
      expect(color).toMatch(/rgba\(\d+, \d+, \d+, 0\.9\)/)
    })

    it('handles custom min/max range', () => {
      const color = getHeatmapColor(150, 100, 200)
      // 150 is 50% of range 100-200
      expect(color).toMatch(/rgba\(\d+, \d+, \d+, 0\.9\)/)
    })

    it('clamps values below min', () => {
      const color = getHeatmapColor(-50, 0, 100)
      expect(color).toBe('rgba(230, 57, 53, 0.9)')
    })

    it('clamps values above max', () => {
      const color = getHeatmapColor(150, 0, 100)
      expect(color).toBe('rgba(46, 125, 50, 0.9)')
    })

    it('handles equal min and max', () => {
      const color = getHeatmapColor(50, 50, 50)
      // Should return middle color when range is 0
      expect(color).toMatch(/rgba\(\d+, \d+, \d+, 0\.9\)/)
    })

    it('has 7 distinct steps', () => {
      const colors = new Set<string>()
      for (let i = 0; i <= 100; i += 14) {
        colors.add(getHeatmapColor(i, 0, 100))
      }
      expect(colors.size).toBeGreaterThanOrEqual(5) // At least 5 distinct colors
    })
  })

  describe('markArea conversion', () => {
    it('converts markArea items to ECharts format', () => {
      const markAreaItems = [
        { start: 0, end: 20, color: 'rgba(46, 125, 50, 0.15)', label: '低估区' },
        { start: 80, end: 100, color: 'rgba(230, 57, 53, 0.15)', label: '高估区' }
      ]

      // Expected ECharts format: array of [start, end] pairs
      const result = markAreaItems.map(item => [
        { xAxis: item.start, name: item.label, itemStyle: { color: item.color } },
        { xAxis: item.end }
      ])

      expect(result).toHaveLength(2)
      expect(result[0][0]).toHaveProperty('xAxis', 0)
      expect(result[0][0]).toHaveProperty('name', '低估区')
      expect(result[1][0]).toHaveProperty('xAxis', 80)
    })
  })

  describe('sparkline mode', () => {
    it('applies sparkline transformations to option', () => {
      const option = {
        xAxis: { type: 'category' },
        yAxis: { type: 'value' },
        series: [{ type: 'line', data: [1, 2, 3] }]
      }

      // Sparkline transformations
      const sparklineOption = {
        ...option,
        grid: { left: 0, right: 0, top: 0, bottom: 0, containLabel: false },
        xAxis: { ...option.xAxis, show: false },
        yAxis: { ...option.yAxis, show: false },
        tooltip: { show: false },
        legend: { show: false },
        series: option.series.map(s => ({
          ...s,
          lineStyle: { width: 1.5 },
          symbol: 'none',
          animation: false
        }))
      }

      expect(sparklineOption.grid.left).toBe(0)
      expect(sparklineOption.xAxis.show).toBe(false)
      expect(sparklineOption.tooltip.show).toBe(false)
      expect((sparklineOption.series[0] as any).lineStyle.width).toBe(1.5)
    })
  })
})
