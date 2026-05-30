/**
 * Numeric formatting utilities for consistent display.
 * Provides centralized formatting functions to replace duplicate implementations.
 */

export const DECIMAL_STANDARD = 2  // Standard for prices, percentages
export const DECIMAL_PRECISION = 4  // For correlations, factor exposure

/**
 * Format number with specified decimal places.
 * Handles null/undefined gracefully by returning '-'.
 */
export function formatNumber(
  val: number | null | undefined,
  decimals: number = DECIMAL_STANDARD,
  suffix: string = ''
): string {
  if (val === null || val === undefined || isNaN(val)) return '-'
  return `${val.toFixed(decimals)}${suffix}`
}

/**
 * Format percentage with 2 decimal places and % suffix.
 */
export function formatPercent(val: number | null | undefined): string {
  return formatNumber(val, DECIMAL_STANDARD, '%')
}

/**
 * Format price with 2 decimal places.
 */
export function formatPrice(val: number | null | undefined): string {
  return formatNumber(val, DECIMAL_STANDARD)
}

/**
 * Format number with sign (+/-) for changes.
 */
export function formatSign(
  val: number | null | undefined,
  suffix: string = ''
): string {
  if (val === null || val === undefined || isNaN(val)) return '-'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(DECIMAL_STANDARD)}${suffix}`
}

/**
 * Format percentage with sign (+/-).
 */
export function formatSignPercent(val: number | null | undefined): string {
  return formatSign(val, '%')
}

/**
 * Format correlation coefficient (4 decimal places).
 */
export function formatCorrelation(val: number | null | undefined): string {
  return formatNumber(val, DECIMAL_PRECISION)
}

/**
 * Format factor exposure weight (4 decimal places).
 */
export function formatFactorWeight(val: number | null | undefined): string {
  return formatNumber(val, DECIMAL_PRECISION)
}
