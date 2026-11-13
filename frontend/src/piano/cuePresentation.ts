import type { Cue } from './session.ts'
import type { KeyBinding } from './samples.ts'

/** Visible task bindings, including demos and both simultaneous hands. */
export function cueBindings(cue: Cue | null | undefined): KeyBinding[] {
  if (!cue || cue.hasCue === false || cue.cueType === 'NO_GO') return []
  return cue.secondaryBinding ? [cue.binding, cue.secondaryBinding] : [cue.binding]
}
