import type { AxiosRequestConfig } from 'axios'

import { apiClient } from './config'

export type InvocationPolicy =
  | 'DIRECT'
  | 'REVIEW_BEFORE_CALL'
  | 'REVIEW_AFTER_CALL'
  | 'FULL_INTERACTIVE'
  | 'INTERACTIVE_WHEN_AVAILABLE'
  | 'AUTOPILOT_PAUSE'

export type InvocationSessionStatus =
  | 'requested'
  | 'spec_resolved'
  | 'context_resolved'
  | 'variables_resolved'
  | 'prompt_compiled'
  | 'awaiting_pre_call_review'
  | 'generating'
  | 'awaiting_acceptance'
  | 'awaiting_commit'
  | 'committing'
  | 'completed'
  | 'blocked'
  | 'failed'
  | 'cancelled'

export interface InvocationPromptSnapshot {
  prompt?: {
    system?: string
    user?: string
  }
  templatePrompt?: {
    system?: string
    user?: string
  }
  draftPrompt?: {
    system?: string
    user?: string
  }
  nodeKey?: string
  nodeVersionId?: string
  assetLinkSetId?: string
  inputBindingSetId?: string
  outputBindingSetId?: string
  variableSnapshotHash?: string
  templateHash?: string
  compositionHash?: string
  renderedPromptHash?: string
  missingVariables?: string[]
  diagnostics?: string[]
  assetVersionIds?: string[]
}

export interface InvocationVariablePlan {
  aliases?: Record<string, unknown>
  resolutionItems?: InvocationVariableResolutionItem[]
  requiredMissing?: string[]
  diagnostics?: string[]
  lineage?: Record<string, string>
  snapshotHash?: string
  snapshotItems?: InvocationVariableSnapshotItem[]
  snapshotGroups?: InvocationVariableSnapshotGroup[]
  bindings?: InvocationVariableBinding[]
}

export interface InvocationVariableResolutionItem {
  alias?: string
  variableKey?: string
  displayName?: string
  status?: string
  currentValue?: unknown
  valueType?: string
  versionNumber?: number
  source?: string
  contextKey?: string
  required?: boolean
}

export interface InvocationVariableBinding {
  alias: string
  variableKey?: string
  required?: boolean
  default?: unknown
  source?: string
  enabled?: boolean
  valueType?: string
  scope?: string
  stage?: string
  displayName?: string
  targetDisplayName?: string
  sourcePath?: string
  projectionKey?: string
  renderMode?: string
  previewSource?: string
}

export interface InvocationVariableSnapshotItem {
  key?: string
  displayName?: string
  value?: unknown
  type?: string
  scope?: string
  stage?: string
  source?: string
  variableKey?: string
  required?: boolean
  sourcePath?: string
  projectionKey?: string
  renderMode?: string
}

export interface InvocationVariableSnapshotGroup {
  id?: string
  scope?: string
  stage?: string
  title?: string
  items?: InvocationVariableSnapshotItem[]
}

export interface InvocationSessionDTO {
  id: string
  operation: string
  nodeKey: string
  policy: InvocationPolicy | string
  status: InvocationSessionStatus | string
  context?: Record<string, unknown>
  metadata?: Record<string, unknown>
  attempts?: string[]
  promptSnapshot?: InvocationPromptSnapshot
  variablePlan?: InvocationVariablePlan
  outputBindings?: InvocationVariableBinding[]
}

export interface InvocationAttemptDTO {
  id: string
  sessionId: string
  status: string
  content: string
  error?: string
}

export interface AdoptionDecisionDTO {
  id: string
  sessionId: string
  attemptId: string
  decision: string
  acceptContent: boolean
  commitPromptVersion: boolean
  commitVariableOutputs: boolean
  commitVariableBindings: boolean
}

export interface AdoptionCommitStepDTO {
  name: string
  status: string
  result?: Record<string, unknown>
  error?: string
}

export interface AdoptionCommitDTO {
  id: string
  sessionId: string
  decisionId: string
  status: string
  steps: AdoptionCommitStepDTO[]
  result?: Record<string, unknown>
  error?: string
}

export interface InvocationResponseDTO {
  session: InvocationSessionDTO
  attempt?: InvocationAttemptDTO | null
  decision?: AdoptionDecisionDTO | null
  commit?: AdoptionCommitDTO | null
  nextAction?: string
}

export interface InvocationCreatePayload {
  operation: string
  nodeKey: string
  variables?: Record<string, unknown>
  context?: Record<string, unknown>
  policy?: InvocationPolicy
  config?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface InvocationAcceptPayload {
  attemptId: string
  acceptedBy?: string
  commitPromptVersion?: boolean
  commitVariableOutputs?: boolean
  commitVariableBindings?: boolean
  metadata?: Record<string, unknown>
}

export interface InvocationResumePayload {
  resumedBy?: string
  config?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface InvocationPromptDraftPayload {
  systemTemplate: string
  userTemplate?: string | null
}

export interface InvocationVariableUpdatePayload {
  values: Record<string, unknown>
  updatedBy?: string
}

export interface InvocationPromptDraftPreviewDTO {
  promptSnapshot: InvocationPromptSnapshot
  variablePlan?: InvocationVariablePlan
}

export const aiInvocationApi = {
  create(payload: InvocationCreatePayload) {
    return apiClient.post<InvocationResponseDTO>('/ai-invocations', payload)
  },
  get(sessionId: string, config?: AxiosRequestConfig) {
    return apiClient.get<InvocationResponseDTO>(`/ai-invocations/${sessionId}`, config)
  },
  accept(sessionId: string, payload: InvocationAcceptPayload) {
    return apiClient.post<InvocationResponseDTO>(`/ai-invocations/${sessionId}/accept`, payload)
  },
  reject(sessionId: string, payload: InvocationAcceptPayload) {
    return apiClient.post<InvocationResponseDTO>(`/ai-invocations/${sessionId}/reject`, payload)
  },
  resume(sessionId: string, payload: InvocationResumePayload) {
    return apiClient.post<InvocationResponseDTO>(`/ai-invocations/${sessionId}/resume`, payload)
  },
  retry(sessionId: string, payload: InvocationResumePayload = {}) {
    return apiClient.post<InvocationResponseDTO>(`/ai-invocations/${sessionId}/retry`, payload)
  },
  previewPromptDraft(sessionId: string, payload: InvocationPromptDraftPayload) {
    return apiClient.post<InvocationPromptDraftPreviewDTO>(
      `/ai-invocations/${sessionId}/prompt-draft/preview`,
      payload,
    )
  },
  savePromptDraft(sessionId: string, payload: InvocationPromptDraftPayload) {
    return apiClient.put<InvocationResponseDTO>(`/ai-invocations/${sessionId}/prompt-draft`, payload)
  },
  updateVariables(sessionId: string, payload: InvocationVariableUpdatePayload) {
    return apiClient.put<InvocationResponseDTO>(`/ai-invocations/${sessionId}/variables`, payload)
  },
  commit(sessionId: string, decisionId: string) {
    return apiClient.post<InvocationResponseDTO>(`/ai-invocations/${sessionId}/commits`, {
      decisionId,
    })
  },
}
