/**
 * StoryOS TypeScript 类型（与后端 Pydantic DTO 同源）。
 * 字段命名用 camelCase（前端），由 API client 在调用时转 snake_case。
 */

export type AssetStatus =
  | 'active' | 'accumulating' | 'planted' | 'developing'
  | 'hidden' | 'ready_to_fulfill' | 'escalated' | 'revealed'
  | 'fulfilled' | 'resolved' | 'abandoned' | 'dead'

export type SFLogType =
  | 'character_emotion' | 'character_relation_change' | 'character_location_change'
  | 'character_physical_change' | 'knowledge_gain' | 'conflict_escalate'
  | 'mystery_clue' | 'twist_reveal' | 'expectation_fulfill'
  | 'goal_milestone' | 'registry_create'

export type CascadeTrigger =
  | 'mystery_revealed' | 'twist_revealed' | 'reveal_revealed'
  | 'promise_fulfilled' | 'conflict_resolved' | 'conflict_escalated'

export interface StoryOSAsset {
  id: string
  projectId: string
  description: string
  status: AssetStatus
  createdChapter: number
  linkedAssets: Record<string, string>
  cascadeUpdatedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ConflictAsset extends StoryOSAsset {
  intensity: number
  participants: string[]
  resolutionChapter: number | null
}

export interface MysteryAsset extends StoryOSAsset {
  category: 'truth' | 'relationship' | 'identity' | 'ability' | 'other'
  clues: ClueItem[]
  solutionChapter: number | null
}

export interface ClueItem {
  id: string
  mysteryId: string
  description: string
  sourceChapter: number
  sourceLocation: string
  category: string
  status: AssetStatus
  discoveredInChapter: number | null
  invalidatedInChapter: number | null
}

export interface TwistAsset extends StoryOSAsset {
  twistType: 'identity_reveal' | 'betrayal' | 'fortune_reversal' | 'world_rule_reveal' | 'sacrifice' | 'truth_revealed'
  triggerChapter: number
  foreshadowingRefs: string[]
}

export interface PromiseAsset extends StoryOSAsset {
  fulfillmentChapter: number | null
  importance: 1 | 2 | 3 | 4
  linkedConflictId: string | null
}

export interface RevealAsset extends StoryOSAsset {
  revealType: 'truth' | 'identity' | 'rule' | 'ability' | 'other'
  revealedChapter: number
  relatedMysteryId: string
}

export interface ExpectationAsset extends StoryOSAsset {
  intensity: number
  linkedTwistId: string | null
  linkedConflictId: string | null
  readyChapter: number | null
}

export interface GoalAsset extends StoryOSAsset {
  progressMarker: 'T0' | 'T1' | 'T2' | 'T3' | 'T4' | 'T5' | 'T6' | 'T7' | 'T8' | 'T9'
  linkedCharacterId: string
  completionChapter: number | null
}

export interface ForeshadowingAsset extends StoryOSAsset {
  importance: 1 | 2 | 3 | 4
  payoffChapter: number | null
  migratedFromLegacyId: string | null
}

export type AssetType =
  | 'conflict' | 'mystery' | 'twist' | 'promise'
  | 'reveal' | 'expectation' | 'goal' | 'foreshadowing'

export interface PaginationMeta {
  total: number
  page: number
  pageSize: number
  totalPages: number
  hasNext: boolean
  hasPrev: boolean
}

export interface ListResponse<T> {
  data: T[]
  meta: PaginationMeta
}

export interface ErrorResponse {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

// Cascade
export interface CascadeStep {
  trigger: CascadeTrigger
  sourceAssetType: AssetType
  sourceAssetId: string
  targetAssetType: AssetType
  targetAssetId: string
  newStatus: AssetStatus | null
  intensityDelta: number | null
  reason: string
}

export interface CascadeSimulateRequest {
  trigger: CascadeTrigger
  sourceAssetType: AssetType
  sourceAssetId: string
  proposedNewStatus?: AssetStatus
  maxDepth?: number
}

export interface CascadeSimulateSummary {
  wouldBlock: boolean
  maxDepthReached: number
  stepsCount: number
  blockedStepsCount: number
  wouldCreateCycle: boolean
}

export interface CascadeSimulateResponse {
  steps: CascadeStep[]
  blockedSteps: CascadeStep[]
  summary: CascadeSimulateSummary
}

// SFLog
export interface SFLogRecord {
  logType: SFLogType
  params: Record<string, string>
  raw: string
  chapterId: number
  charPosition: number
  assetId: string | null
}

export interface SFLogRawResponse {
  projectId: string
  chapterId: number
  rawText: string
  records: SFLogRecord[]
  sfLogCount: number
}

export interface MatchReport {
  predeclaredTotal: number
  predeclaredImplemented: number
  missingChanges: unknown[]
  unexpectedRecords: SFLogRecord[]
  matchRate: number
}

export interface SFLogReparseResponse {
  projectId: string
  chapterId: number
  parsedCount: number
  formatErrors: unknown[]
  matchReport: MatchReport
}

// Migration
export interface MigrationPreviewResponse {
  total: number
  scanned: number
  migratable: number
  skipped: number
  invalid: number
  sampleErrors: Array<{ legacyId: string; reason: string }>
}

export interface MigrationExecuteRequest {
  batchSize?: number
  dryRun?: boolean
}

export interface MigrationExecuteResponse {
  migrationId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  batchesTotal: number
  batchesDone: number
  errors: Array<{ batchId: string; reason: string }>
}

// Health/Metrics
export interface HealthComponent {
  status: 'ok' | 'degraded' | 'down'
  error?: string
}

export interface HealthResponse {
  projectId: string
  status: 'ok' | 'degraded' | 'down'
  components: Record<'registry' | 'cascade' | 'sflog_parser' | 'bridge', HealthComponent>
  timestamp: string
}

export interface StoryOSMetrics {
  sflogFormatComplianceRate: number
  sflogPredeclaredMatchRate: number
  cascadeBlockRate: number
  bridgeFailureRate: number
  avgCascadeDepth: number
  forcePassCountPerChapter: number
}