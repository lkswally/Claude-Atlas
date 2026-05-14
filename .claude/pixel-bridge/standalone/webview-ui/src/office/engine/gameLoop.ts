import { MAX_DELTA_TIME_SEC } from '../../constants.js'

export interface GameLoopCallbacks {
  update: (dt: number) => void
  render: (ctx: CanvasRenderingContext2D) => void
}

export function startGameLoop(
  canvas: HTMLCanvasElement,
  callbacks: GameLoopCallbacks,
): () => void {
  const ctx = canvas.getContext('2d')!
  ctx.imageSmoothingEnabled = false

  let lastTime = performance.now()
  let rafId = 0
  let intervalId = 0
  let stopped = false

  // rAF callback — used when tab is visible
  const rafFrame = (time: number) => {
    if (stopped) return
    const dt = Math.min((time - lastTime) / 1000, MAX_DELTA_TIME_SEC)
    lastTime = time
    callbacks.update(dt)
    ctx.imageSmoothingEnabled = false
    callbacks.render(ctx)
    rafId = requestAnimationFrame(rafFrame)
  }

  // setInterval callback — used when tab is hidden so the loop keeps ticking
  const intervalFrame = () => {
    if (stopped) return
    const now = performance.now()
    const dt = Math.min((now - lastTime) / 1000, MAX_DELTA_TIME_SEC)
    lastTime = now
    callbacks.update(dt)
    // No render while hidden — skip the canvas draw to save CPU
  }

  const startRaf = () => {
    if (intervalId) { clearInterval(intervalId); intervalId = 0 }
    lastTime = performance.now()
    rafId = requestAnimationFrame(rafFrame)
  }

  const startInterval = () => {
    if (rafId) { cancelAnimationFrame(rafId); rafId = 0 }
    intervalId = window.setInterval(intervalFrame, 50) // ~20 fps tick rate
  }

  // Pick the right mode based on current visibility
  if (document.hidden) {
    startInterval()
  } else {
    startRaf()
  }

  // Switch modes when visibility changes
  const onVisibilityChange = () => {
    if (stopped) return
    if (document.hidden) {
      startInterval()
    } else {
      startRaf()
    }
  }
  document.addEventListener('visibilitychange', onVisibilityChange)

  return () => {
    stopped = true
    cancelAnimationFrame(rafId)
    clearInterval(intervalId)
    document.removeEventListener('visibilitychange', onVisibilityChange)
  }
}
