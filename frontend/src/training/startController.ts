export interface StartState {
  phase: 'idle' | 'preparing' | 'countdown'
  remaining: number
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms)
    function done() {
      clearTimeout(timer)
      signal.removeEventListener('abort', done)
      resolve()
    }
    signal.addEventListener('abort', done, { once: true })
  })
}

/** Coordinates preparation only; measurement timing remains in the original engines. */
export class TrainingStartController {
  private active: AbortController | null = null
  private publish: (state: StartState) => void
  private sleep: (ms: number, signal: AbortSignal) => Promise<void>

  constructor(publish: (state: StartState) => void, sleep = wait) {
    this.publish = publish
    this.sleep = sleep
  }

  async run(prepare: (signal: AbortSignal) => Promise<void>, start: () => void) {
    if (this.active) return
    const operation = new AbortController()
    this.active = operation
    const signal = operation.signal
    this.publish({ phase: 'preparing', remaining: 0 })
    try {
      await prepare(signal)
      for (const remaining of [3, 2, 1]) {
        if (signal.aborted) return
        this.publish({ phase: 'countdown', remaining })
        await this.sleep(1000, signal)
      }
      if (!signal.aborted) start()
    } catch (error) {
      if (!signal.aborted) throw error
    } finally {
      if (this.active === operation) {
        this.active = null
        this.publish({ phase: 'idle', remaining: 0 })
      }
    }
  }

  cancel() {
    this.active?.abort()
    this.active = null
    this.publish({ phase: 'idle', remaining: 0 })
  }
}
