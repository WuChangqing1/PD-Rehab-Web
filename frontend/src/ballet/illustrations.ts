/** AI illustrations are static visual aids, never approved live-action demos. */
export function illustrationPath(exercise: string, mode: string): string | null {
  const names: Record<string, string> = {
    BALLET_PORT_DE_BRAS: 'arms', BALLET_FIRST_POSITION: 'first',
    BALLET_TENDU: 'tendu', BALLET_DEMI_PLIE: 'plie', BALLET_WEIGHT_SHIFT: 'shift',
  }
  if (!names[exercise] || !['SEATED', 'STANDING_SUPPORTED'].includes(mode)) return null
  if (exercise === 'BALLET_DEMI_PLIE' && mode === 'SEATED') return null
  return `assets/ballet/ai-v1/${mode === 'SEATED' ? 'seated' : 'standing'}_${names[exercise]}.webp`
}
