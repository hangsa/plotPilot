import { describe, it, expect } from 'vitest'
import { snakeToCamel, camelToSnake } from '../transform'

describe('snakeToCamel', () => {
  it('converts flat snake_case keys', () => {
    expect(snakeToCamel({ created_chapter: 1, project_id: 'a' })).toEqual({
      createdChapter: 1,
      projectId: 'a',
    })
  })

  it('preserves keys that are already camelCase / single word', () => {
    expect(snakeToCamel({ id: 'x', status: 'active' })).toEqual({
      id: 'x',
      status: 'active',
    })
  })

  it('recurses into nested objects', () => {
    expect(
      snakeToCamel({
        created_chapter: 2,
        linked_assets: { conflict_id: 'cf-1', mystery_ref: 'm-1' },
      }),
    ).toEqual({
      createdChapter: 2,
      linkedAssets: { conflictId: 'cf-1', mysteryRef: 'm-1' },
    })
  })

  it('recurses into arrays of objects', () => {
    expect(
      snakeToCamel({
        data: [
          { asset_id: 'a-1', created_chapter: 1 },
          { asset_id: 'a-2', created_chapter: 2 },
        ],
        meta: { total_count: 2, page_size: 20 },
      }),
    ).toEqual({
      data: [
        { assetId: 'a-1', createdChapter: 1 },
        { assetId: 'a-2', createdChapter: 2 },
      ],
      meta: { totalCount: 2, pageSize: 20 },
    })
  })

  it('handles deeply nested structures', () => {
    const input = {
      outer_key: {
        inner_key: {
          deepest_key: [{ some_id: 1 }, { some_id: 2 }],
        },
      },
    }
    expect(snakeToCamel(input)).toEqual({
      outerKey: {
        innerKey: {
          deepestKey: [{ someId: 1 }, { someId: 2 }],
        },
      },
    })
  })

  it('handles empty objects and empty arrays', () => {
    expect(snakeToCamel({})).toEqual({})
    expect(snakeToCamel([])).toEqual([])
    expect(snakeToCamel({ data: [], meta: {} })).toEqual({ data: [], meta: {} })
  })

  it('preserves null and undefined values', () => {
    expect(snakeToCamel({ a: null, b: undefined, c: { d: null } })).toEqual({
      a: null,
      b: undefined,
      c: { d: null },
    })
  })

  it('passes primitives through unchanged', () => {
    expect(snakeToCamel(42 as unknown)).toBe(42)
    expect(snakeToCamel('hello' as unknown)).toBe('hello')
    expect(snakeToCamel(true as unknown)).toBe(true)
    expect(snakeToCamel(null as unknown)).toBeNull()
    expect(snakeToCamel(undefined as unknown)).toBeUndefined()
  })

  it('passes Date instances through unchanged', () => {
    const d = new Date('2026-01-01T00:00:00Z')
    const result = snakeToCamel({ created_at: d, snake_key: d }) as Record<string, unknown>
    expect(result.createdAt).toBe(d)
    expect(result.snakeKey).toBe(d)
    expect(result.createdAt).toBeInstanceOf(Date)
  })

  it('handles keys with leading, trailing, and consecutive underscores', () => {
    // Leading underscore: `_a` -> `A` (the captured group after `_`).
    // Trailing underscore: `b_` -> `b_` (no `_X` pattern).
    // Consecutive underscores: only the trailing `_X` is consumed by the
    // regex (`a__b` -> `a_B`); the first `_` has no `[a-z0-9]` after it.
    expect(snakeToCamel({ _a: 1, b_: 2, a__b: 3 })).toEqual({
      A: 1,
      b_: 2,
      a_B: 3,
    })
  })

  it('converts keys with digits after underscores', () => {
    expect(snakeToCamel({ chapter_2_id: 'x', v1_flag: true })).toEqual({
      chapter2Id: 'x',
      v1Flag: true,
    })
  })

  it('preserves enum-like string values untouched', () => {
    expect(snakeToCamel({ new_status: 'ready_to_fulfill' })).toEqual({
      newStatus: 'ready_to_fulfill',
    })
  })

  it('does not mutate the input', () => {
    const input = { created_chapter: 1, nested: { project_id: 'a' } }
    const snapshot = JSON.parse(JSON.stringify(input))
    snakeToCamel(input)
    expect(input).toEqual(snapshot)
  })
})

describe('camelToSnake', () => {
  it('converts flat camelCase keys', () => {
    expect(camelToSnake({ createdChapter: 1, projectId: 'a' })).toEqual({
      created_chapter: 1,
      project_id: 'a',
    })
  })

  it('preserves single-word keys', () => {
    expect(camelToSnake({ id: 'x', status: 'active' })).toEqual({
      id: 'x',
      status: 'active',
    })
  })

  it('recurses into nested objects', () => {
    expect(
      camelToSnake({
        createdChapter: 2,
        linkedAssets: { conflictId: 'cf-1', mysteryRef: 'm-1' },
      }),
    ).toEqual({
      created_chapter: 2,
      linked_assets: { conflict_id: 'cf-1', mystery_ref: 'm-1' },
    })
  })

  it('recurses into arrays of objects', () => {
    expect(
      camelToSnake({
        data: [
          { assetId: 'a-1', createdChapter: 1 },
          { assetId: 'a-2', createdChapter: 2 },
        ],
        meta: { totalCount: 2, pageSize: 20 },
      }),
    ).toEqual({
      data: [
        { asset_id: 'a-1', created_chapter: 1 },
        { asset_id: 'a-2', created_chapter: 2 },
      ],
      meta: { total_count: 2, page_size: 20 },
    })
  })

  it('passes primitives through unchanged', () => {
    expect(camelToSnake(42 as unknown)).toBe(42)
    expect(camelToSnake('hello' as unknown)).toBe('hello')
    expect(camelToSnake(true as unknown)).toBe(true)
    expect(camelToSnake(null as unknown)).toBeNull()
    expect(camelToSnake(undefined as unknown)).toBeUndefined()
  })

  it('preserves Date instances', () => {
    const d = new Date('2026-01-01T00:00:00Z')
    const result = camelToSnake({ createdAt: d }) as Record<string, unknown>
    expect(result.created_at).toBe(d)
    expect(result.created_at).toBeInstanceOf(Date)
  })

  it('handles consecutive capital letters', () => {
    // Each uppercase letter is preceded by `_`. A leading uppercase yields
    // a leading `_` (matches common snake_case implementations like lodash).
    expect(camelToSnake({ HTTPStatus: 200, userID: 1 })).toEqual({
      _h_t_t_p_status: 200,
      user_i_d: 1,
    })
  })
})

describe('round-trip', () => {
  it('snakeToCamel is inverse of camelToSnake for plain objects', () => {
    const snakeInput = {
      asset_id: 'a-1',
      created_chapter: 3,
      linked_assets: { conflict_id: 'cf-1' },
      meta: { total_count: 5 },
    }
    expect(camelToSnake(snakeToCamel(snakeInput))).toEqual(snakeInput)
  })

  it('camelToSnake is inverse of snakeToCamel for plain objects', () => {
    const camelInput = {
      assetId: 'a-1',
      createdChapter: 3,
      linkedAssets: { conflictId: 'cf-1' },
      meta: { totalCount: 5 },
    }
    expect(snakeToCamel(camelToSnake(camelInput))).toEqual(camelInput)
  })
})