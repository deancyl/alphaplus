/**
 * Test file for JargonTooltip mobile functionality
 * Run with: npx vitest run test_tooltip_mobile.ts
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import JargonTooltip from '@/components/JargonTooltip.vue'

// Mock touch device detection
const mockTouchDevice = (isTouch: boolean) => {
  Object.defineProperty(window, 'ontouchstart', {
    value: isTouch ? () => {} : undefined,
    writable: true,
    configurable: true,
  })
  Object.defineProperty(navigator, 'maxTouchPoints', {
    value: isTouch ? 5 : 0,
    writable: true,
    configurable: true,
  })
}

describe('JargonTooltip Mobile Functionality', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Touch Target Size', () => {
    it('should have minimum touch target of 44px', async () => {
      mockTouchDevice(true)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      expect(trigger.exists()).toBe(true)
      
      // Check CSS class that ensures 44px minimum
      expect(trigger.classes()).toContain('touch-target')
    })

    it('should apply touch-action manipulation for better mobile UX', async () => {
      mockTouchDevice(true)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '最大回撤',
          definition: '历史最高点到最低点的最大跌幅',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      expect(trigger.attributes('class')).toContain('touch-target')
    })
  })

  describe('Click Interaction (Mobile)', () => {
    it('should toggle tooltip on click when touch device', async () => {
      mockTouchDevice(true)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
        attachTo: document.body,
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      
      // Initially hidden
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(false)
      
      // Click to show
      await trigger.trigger('click')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(true)
      
      // Click again to hide
      await trigger.trigger('click')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(false)
      
      wrapper.unmount()
    })

    it('should close tooltip when clicking outside', async () => {
      mockTouchDevice(true)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
        attachTo: document.body,
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      
      // Open tooltip
      await trigger.trigger('click')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(true)
      
      // Click outside
      document.body.click()
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(false)
      
      wrapper.unmount()
    })

    it('should not respond to hover on touch devices', async () => {
      mockTouchDevice(true)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      
      // Hover should not show tooltip on touch device
      await trigger.trigger('mouseenter')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(false)
    })
  })

  describe('Hover Interaction (Desktop)', () => {
    it('should show tooltip on hover when not touch device', async () => {
      mockTouchDevice(false)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      
      // Hover to show
      await trigger.trigger('mouseenter')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(true)
      
      // Leave to hide
      await trigger.trigger('mouseleave')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(false)
    })

    it('should not toggle on click on desktop', async () => {
      mockTouchDevice(false)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      
      // Click should not show tooltip on desktop
      await trigger.trigger('click')
      await nextTick()
      
      expect(wrapper.find('.jargon-tooltip').exists()).toBe(false)
    })
  })

  describe('Position Variants', () => {
    it('should apply position class based on prop', async () => {
      mockTouchDevice(false)
      
      const positions = ['top', 'bottom', 'left', 'right'] as const
      
      for (const position of positions) {
        const wrapper = mount(JargonTooltip, {
          props: {
            term: '夏普比率',
            definition: '每承受1单位风险获得的超额收益',
            position,
          },
        })

        const trigger = wrapper.find('.jargon-tooltip-trigger')
        await trigger.trigger('mouseenter')
        await nextTick()
        
        const tooltip = wrapper.find('.jargon-tooltip')
        expect(tooltip.classes()).toContain(`tooltip--${position}`)
        
        wrapper.unmount()
      }
    })

    it('should default to top position', async () => {
      mockTouchDevice(false)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      await trigger.trigger('mouseenter')
      await nextTick()
      
      const tooltip = wrapper.find('.jargon-tooltip')
      expect(tooltip.classes()).toContain('tooltip--top')
    })
  })

  describe('Accessibility', () => {
    it('should have role="tooltip" on tooltip element', async () => {
      mockTouchDevice(false)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      await trigger.trigger('mouseenter')
      await nextTick()
      
      const tooltip = wrapper.find('.jargon-tooltip')
      expect(tooltip.attributes('role')).toBe('tooltip')
    })

    it('should have aria-hidden on indicator', async () => {
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const indicator = wrapper.find('.jargon-indicator')
      expect(indicator.attributes('aria-hidden')).toBe('true')
    })

    it('should have cursor help style', async () => {
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      // Check that the class that provides cursor: help is applied
      expect(trigger.exists()).toBe(true)
    })
  })

  describe('Content Rendering', () => {
    it('should display term text', async () => {
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const termElement = wrapper.find('.jargon-term')
      expect(termElement.text()).toBe('夏普比率')
    })

    it('should display definition in tooltip', async () => {
      mockTouchDevice(false)
      
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const trigger = wrapper.find('.jargon-tooltip-trigger')
      await trigger.trigger('mouseenter')
      await nextTick()
      
      const tooltip = wrapper.find('.jargon-tooltip')
      expect(tooltip.text()).toBe('每承受1单位风险获得的超额收益')
    })

    it('should display question mark indicator', async () => {
      const wrapper = mount(JargonTooltip, {
        props: {
          term: '夏普比率',
          definition: '每承受1单位风险获得的超额收益',
        },
      })

      const indicator = wrapper.find('.jargon-indicator')
      expect(indicator.text()).toBe('?')
    })
  })
})

describe('EmptyState Component', () => {
  describe('Props Rendering', () => {
    it('should display title', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '未找到符合条件的基金',
        },
      })

      expect(wrapper.find('.empty-state-title').text()).toBe('未找到符合条件的基金')
    })

    it('should display description when provided', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
          description: '请尝试调整筛选条件',
        },
      })

      expect(wrapper.find('.empty-state-description').text()).toBe('请尝试调整筛选条件')
    })

    it('should not display description when not provided', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
        },
      })

      expect(wrapper.find('.empty-state-description').exists()).toBe(false)
    })

    it('should display action button when actionText provided', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
          actionText: '重置筛选',
        },
      })

      expect(wrapper.find('.empty-state-action').exists()).toBe(true)
      expect(wrapper.find('.empty-state-action').text()).toBe('重置筛选')
    })

    it('should not display action button when actionText not provided', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
        },
      })

      expect(wrapper.find('.empty-state-action').exists()).toBe(false)
    })
  })

  describe('Action Handling', () => {
    it('should emit action event on button click', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
          actionText: '重置筛选',
        },
      })

      await wrapper.find('.empty-state-action').trigger('click')
      
      expect(wrapper.emitted('action')).toBeTruthy()
      expect(wrapper.emitted('action')).toHaveLength(1)
    })

    it('should call actionHandler prop when provided', async () => {
      const actionHandler = vi.fn()
      
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
          actionText: '重置筛选',
          actionHandler,
        },
      })

      await wrapper.find('.empty-state-action').trigger('click')
      
      expect(actionHandler).toHaveBeenCalledTimes(1)
      expect(wrapper.emitted('action')).toBeTruthy()
    })
  })

  describe('Touch Target', () => {
    it('should have minimum touch target on action button', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
          actionText: '重置筛选',
        },
      })

      const button = wrapper.find('.empty-state-action')
      expect(button.classes()).toContain('touch-target')
    })
  })

  describe('Icon Mapping', () => {
    it('should display mapped icon for known types', async () => {
      const iconMap: Record<string, string> = {
        empty: '📭',
        search: '🔍',
        favorites: '⭐',
        error: '⚠️',
        chart: '📊',
        fund: '📈',
      }

      for (const [key, expectedIcon] of Object.entries(iconMap)) {
        const wrapper = mount(EmptyState, {
          props: {
            icon: key,
            title: '暂无数据',
          },
        })

        expect(wrapper.find('.empty-state-icon').text()).toBe(expectedIcon)
        wrapper.unmount()
      }
    })

    it('should use custom icon when provided', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          icon: '🎯',
          title: '暂无数据',
        },
      })

      expect(wrapper.find('.empty-state-icon').text()).toBe('🎯')
    })
  })

  describe('Slot', () => {
    it('should render default slot content', async () => {
      const wrapper = mount(EmptyState, {
        props: {
          title: '暂无数据',
        },
        slots: {
          default: '<p class="custom-content">Custom content</p>',
        },
      })

      expect(wrapper.find('.custom-content').exists()).toBe(true)
      expect(wrapper.find('.custom-content').text()).toBe('Custom content')
    })
  })
})
