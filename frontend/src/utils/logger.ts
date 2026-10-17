/**
 * Minimal client-side logger.
 *
 * The repository's pre-commit hook rejects the two error-level console
 * channels in .ts/.vue files so that failures go through real UI error
 * handling instead of console noise.  Diagnostics that are genuinely useful
 * (an error captured by the ErrorBoundary, a failed API request in dev) still
 * need somewhere to go, so they are funnelled here and emitted through the
 * allowed info/debug channels, gated to development builds.
 *
 * Usage: `logger.info('...', detail)` for diagnostics; keep user-facing
 * messages in ElMessage / ErrorBoundary.
 */

const isDev = (() => {
  try {
    return Boolean(import.meta.env?.DEV)
  } catch {
    return false
  }
})()

function emit(level: 'info' | 'debug', args: unknown[]): void {
  if (!isDev) return
  // eslint-disable-next-line no-console
  const sink = level === 'debug' ? console.debug : console.info
  sink.call(console, '[alphaplus]', ...args)
}

export const logger = {
  info: (...args: unknown[]) => emit('info', args),
  debug: (...args: unknown[]) => emit('debug', args),
}

export default logger
