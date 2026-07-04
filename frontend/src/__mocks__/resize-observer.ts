/**
 * Test-only polyfills for browser APIs that JSDOM does not provide.
 * Vue Flow uses ResizeObserver to size its canvas; echarts uses
 * ResizeObserver for autoresize. We provide a no-op stub so components
 * mount cleanly. Visual output is meaningless in JSDOM but mount-time
 * errors are not.
 */
class StubResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

;(globalThis as unknown as { ResizeObserver: typeof StubResizeObserver }).ResizeObserver =
  StubResizeObserver

/**
 * JSDOM does not implement HTMLCanvasElement.getContext(); echarts/zrender
 * needs at least a stub that returns a no-op 2D context, otherwise its
 * animation loop throws "Cannot read properties of null" on every frame
 * and fails tests that mount components containing charts.
 */
const noopCtx = {
  fillRect(): void {},
  clearRect(): void {},
  getImageData(): { data: Uint8ClampedArray } { return { data: new Uint8ClampedArray() } },
  putImageData(): void {},
  createImageData(): { data: Uint8ClampedArray } { return { data: new Uint8ClampedArray() } },
  setTransform(): void {},
  drawImage(): void {},
  save(): void {},
  fillText(): void {},
  restore(): void {},
  beginPath(): void {},
  moveTo(): void {},
  lineTo(): void {},
  closePath(): void {},
  stroke(): void {},
  translate(): void {},
  scale(): void {},
  rotate(): void {},
  arc(): void {},
  fill(): void {},
  measureText(): { width: number } { return { width: 0 } },
  transform(): void {},
  rect(): void {},
  clip(): void {},
  getTransform(): DOMMatrix { return {} as DOMMatrix },
  setLineDash(): void {},
  createLinearGradient(): CanvasGradient { return {} as CanvasGradient },
  createRadialGradient(): CanvasGradient { return {} as CanvasGradient },
  createPattern(): CanvasPattern | null { return null },
  bezierCurveTo(): void {},
  quadraticCurveTo(): void {},
  isPointInPath(): boolean { return false },
  isPointInStroke(): boolean { return false },
} as unknown as CanvasRenderingContext2D

const proto = (HTMLCanvasElement.prototype as unknown as {
  getContext: (id: string) => CanvasRenderingContext2D | null
})
proto.getContext = function getContext(): CanvasRenderingContext2D {
  return noopCtx
}

/**
 * Vue Flow walks the DOM tree during render and calls getBBox() on SVG
 * elements. JSDOM does not implement SVGGeometryElement.getBBox, which
 * otherwise surfaces as an uncaught exception during teardown. Provide a
 * zero-rect stub so the lookup is non-throwing.
 */
const stubBBox = (): DOMRect => ({
  x: 0,
  y: 0,
  width: 0,
  height: 0,
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  toJSON: () => ({}),
} as DOMRect)

const svgElementProto = (globalThis as { SVGElement?: { prototype: unknown } })
  .SVGElement
if (svgElementProto) {
  ;(svgElementProto.prototype as { getBBox: () => DOMRect }).getBBox = stubBBox
}