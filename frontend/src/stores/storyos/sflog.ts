import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sflogApi } from '@/api/storyos'
import type {
  SFLogRawResponse,
  SFLogReparseResponse,
} from '@/types/storyos'

export const useStoryosSflogStore = defineStore('storyos-sflog', () => {
  const currentRaw = ref<SFLogRawResponse | null>(null)
  const currentReparse = ref<SFLogReparseResponse | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Monotonic request token — incremented on every loadRaw/reparse call. The
  // captured token at request start is compared on response; if a newer call
  // has started, the response is discarded so a slow earlier request can't
  // overwrite a faster later one (e.g. rapid chapter input).
  let rawToken = 0
  let reparseToken = 0

  async function loadRaw(projectId: string, chapter: number): Promise<void> {
    const myToken = ++rawToken
    isLoading.value = true
    error.value = null
    try {
      const result = await sflogApi.raw(projectId, chapter)
      if (myToken === rawToken) currentRaw.value = result
    } catch (e: unknown) {
      if (myToken === rawToken) {
        error.value = e instanceof Error ? e.message : String(e)
      }
    } finally {
      if (myToken === rawToken) isLoading.value = false
    }
  }

  async function reparse(projectId: string, chapterId: number): Promise<void> {
    const myToken = ++reparseToken
    isLoading.value = true
    error.value = null
    try {
      const result = await sflogApi.reparse(projectId, chapterId)
      if (myToken === reparseToken) currentReparse.value = result
    } catch (e: unknown) {
      if (myToken === reparseToken) {
        error.value = e instanceof Error ? e.message : String(e)
      }
    } finally {
      if (myToken === reparseToken) isLoading.value = false
    }
  }

  return {
    currentRaw,
    currentReparse,
    isLoading,
    error,
    loadRaw,
    reparse,
  }
})