/**
 * snake_case <-> camelCase key transform helpers.
 *
 * The backend (FastAPI / Pydantic) emits snake_case JSON; the frontend
 * codebase is written in camelCase. Rather than fork the schemas on both
 * sides, we run an axios interceptor that converts request payloads
 * (camelCase -> snake_case) and response payloads (snake_case -> camelCase)
 * at the wire boundary.
 *
 * Edge cases handled:
 *  - nested objects
 *  - arrays of objects (each element transformed)
 *  - null / undefined (preserved; null is NOT stripped)
 *  - primitives (returned as-is)
 *  - top-level non-object (returned as-is)
 *  - Date / Blob / File / ArrayBuffer / TypedArray (returned as-is)
 *    — these are not JSON-serializable raw objects and axios will handle
 *    them via FormData / multipart passthrough.
 *  - objects whose [[Prototype]] is not Object.prototype (e.g. class
 *    instances) — returned as-is to avoid corrupting their internals.
 *
 * The transform is structural only: it does NOT touch values. This means
 * enum-like strings (e.g. "ready_to_fulfill") are left intact, which is
 * what the StoryOS frontend expects.
 */

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

/**
 * Returns true when `value` is a "plain" JSON-deserializable object that we
 * should recurse into. We deliberately treat Date / Blob / ArrayBuffer /
 * TypedArray / File as opaque so the transform doesn't corrupt binary or
 * temporal data passed through FormData or as raw request bodies.
 */
function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== 'object') return false
  if (Array.isArray(value)) return false

  const proto = Object.getPrototypeOf(value)
  if (proto === null) return true
  if (proto === Object.prototype) return true

  // Class instances (e.g. Date, Blob, File, Map, Set, Buffer, TypedArray,
  // custom error subclasses, etc.) — do not recurse.
  return false
}

// ---------------------------------------------------------------------------
// snake_case <-> camelCase
// ---------------------------------------------------------------------------

/**
 * Convert a single key from snake_case to camelCase. Keys that contain no
 * underscore are returned unchanged (so 'id', 'status' pass through).
 */
function snakeToCamelKey(key: string): string {
  if (!key.includes('_')) return key
  return key.replace(/_([a-z0-9])/g, (_match, ch: string) => ch.toUpperCase())
}

/**
 * Convert a single key from camelCase to snake_case. Keys that contain no
 * uppercase ASCII letters are returned unchanged.
 */
function camelToSnakeKey(key: string): string {
  if (!/[A-Z]/.test(key)) return key
  return key.replace(/[A-Z]/g, ch => `_${ch.toLowerCase()}`)
}

// ---------------------------------------------------------------------------
// Public transforms
// ---------------------------------------------------------------------------

/**
 * Recursively convert every object key from snake_case to camelCase.
 *
 * - Objects: keys rewritten, values recursed.
 * - Arrays: each element transformed.
 * - null / primitives: returned as-is.
 * - Date / Blob / non-plain objects: returned as-is.
 */
export function snakeToCamel<T = unknown>(input: T): T {
  if (input === null || input === undefined) return input
  if (Array.isArray(input)) {
    return input.map(item => snakeToCamel(item)) as unknown as T
  }
  if (!isPlainObject(input)) return input

  const out: Record<string, unknown> = {}
  for (const key of Object.keys(input)) {
    const value = (input as Record<string, unknown>)[key]
    out[snakeToCamelKey(key)] = snakeToCamel(value)
  }
  return out as T
}

/**
 * Recursively convert every object key from camelCase to snake_case.
 *
 * Inverse of {@link snakeToCamel}. Same edge-case rules apply.
 */
export function camelToSnake<T = unknown>(input: T): T {
  if (input === null || input === undefined) return input
  if (Array.isArray(input)) {
    return input.map(item => camelToSnake(item)) as unknown as T
  }
  if (!isPlainObject(input)) return input

  const out: Record<string, unknown> = {}
  for (const key of Object.keys(input)) {
    const value = (input as Record<string, unknown>)[key]
    out[camelToSnakeKey(key)] = camelToSnake(value)
  }
  return out as T
}