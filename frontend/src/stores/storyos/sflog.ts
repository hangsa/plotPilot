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

  async function loadRaw(projectId: string, chapter: number): Promise<void> {
    isLoading.value = true
    try {
      currentRaw.value = await sflogApi.raw(projectId, chapter)
    } finally {
      isLoading.value = false
    }
  }

  async function reparse(projectId: string, chapterId: number): Promise<void> {
    isLoading.value = true
    try {
      currentReparse.value = await sflogApi.reparse(projectId, chapterId)
    } finally {
      isLoading.value = false
    }
  }

  return {
    currentRaw,
    currentReparse,
    isLoading,
    loadRaw,
    reparse,
  }
})