export function formatDisplayName(input: string | null | undefined): string {
  if (typeof input !== 'string') return ''
  return input.includes('H') ? input.replace(/H/g, 'C') : input
}

export function formatDisplayNameOrFallback(
  input: string | null | undefined,
  fallback: string
): string {
  const formatted = formatDisplayName(input)
  return formatted || fallback
}
