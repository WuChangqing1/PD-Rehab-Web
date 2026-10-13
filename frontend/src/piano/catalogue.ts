import { MODE_LABELS, MODE_DESCRIPTIONS, TRAINING_MODES, type PianoMode } from './session.ts'
import { RECIPES, type TrainingRecipe } from './recipes.ts'

export type PracticeFamily = 'BASIC' | 'BIMANUAL' | 'SEQUENCE' | 'COGNITIVE'
export interface PracticeDefinition {
  id: string
  label: string
  description: string
  family: PracticeFamily
  mode: PianoMode
  recipe?: TrainingRecipe
  optional?: boolean
}
export const PRACTICE_FAMILIES: { id: PracticeFamily; label: string }[] = [
  {id:'BASIC',label:'入门节奏'}, {id:'BIMANUAL',label:'双手协调'},
  {id:'SEQUENCE',label:'连续动作'}, {id:'COGNITIVE',label:'节奏与认知'},
]
const modeFamily: Partial<Record<PianoMode,PracticeFamily>> = {
  ALTERNATING_HANDS:'BIMANUAL', MAPPED_SEQUENCE:'SEQUENCE', MEMORY_RHYTHM:'COGNITIVE',
}
const recipeFamily: Record<string,PracticeFamily> = {
  CFT_RHYTHM_HOLD:'COGNITIVE', BIMANUAL_SYNC:'BIMANUAL', ACCENT_GROUPING:'COGNITIVE',
  TEMPO_RAMP:'COGNITIVE', HOLD_RELEASE:'SEQUENCE', BIMANUAL_OFFSET:'BIMANUAL',
  REVERSE_SEQUENCE:'SEQUENCE', GO_NO_GO:'COGNITIVE',
}
/** SINGLE and SFT use the same cue policy. One entry, explicit variant choice. */
export const PRACTICES: PracticeDefinition[] = [
  ...TRAINING_MODES.map(mode=>({id:mode,mode,label:MODE_LABELS[mode].replace('（可选）',''),
    description:MODE_DESCRIPTIONS[mode],family:modeFamily[mode]??'BASIC' as PracticeFamily,
    optional:mode==='MEMORY_RHYTHM'})),
  ...RECIPES.filter(r=>r.id!=='SFT_CUE_SYNC').map(recipe=>({id:recipe.id,mode:recipe.baseMode,
    label:recipe.label,description:recipe.summary,family:recipeFamily[recipe.id],recipe,
    optional:recipe.id==='REVERSE_SEQUENCE'})),
]
export function practiceLabel(mode: string, recipeId?: string|null): string {
  return RECIPES.find(r=>r.id===recipeId)?.label ?? MODE_LABELS[mode as PianoMode] ?? mode
}
