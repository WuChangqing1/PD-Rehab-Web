/** A recording may finish asynchronously after its view has been discarded. */
export interface CaptureLifetime {generation:number;disposed:boolean}
export function newCaptureLifetime():CaptureLifetime{return {generation:0,disposed:false}}
export function beginCapture(state:CaptureLifetime):number{return ++state.generation}
export function invalidateCapture(state:CaptureLifetime):void{state.generation++}
export function disposeCapture(state:CaptureLifetime):void{state.disposed=true;invalidateCapture(state)}
export function isCurrentCapture(state:CaptureLifetime,ticket:number):boolean{return !state.disposed&&state.generation===ticket}
