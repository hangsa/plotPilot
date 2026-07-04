<template>
  <div class="predeclared-diff" v-if="report">
    <div class="diff-summary">
      <h4 class="match-rate">匹配率：{{ (report.matchRate * 100).toFixed(0) }}%</h4>
      <span>{{ report.predeclaredImplemented }} / {{ report.predeclaredTotal }} 实现</span>
    </div>
    <div v-if="report.missingChanges.length" class="diff-section diff-missing-section">
      <h4>缺失（predeclared 未实现 → RETRY）</h4>
      <div v-for="m in report.missingChanges" :key="String(m)" class="diff-item diff-missing">
        {{ JSON.stringify(m) }}
      </div>
    </div>
    <div v-if="report.unexpectedRecords.length" class="diff-section diff-unexpected-section">
      <h4>意外（实际产出但 predeclared 无 → WARN）</h4>
      <div v-for="u in report.unexpectedRecords" :key="u.charPosition" class="diff-item diff-unexpected">
        {{ u.logType }} @ {{ u.charPosition }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { sflogApi } from '@/api/storyos'
import type { MatchReport } from '@/types/storyos'

const props = defineProps<{ slug: string; chapterId: number }>()
const report = ref<MatchReport | null>(null)

async function load() {
  const res = await sflogApi.reparse(props.slug, props.chapterId)
  report.value = res.matchReport
}

watch(() => props.chapterId, load, { immediate: true })
</script>

<style scoped>
.diff-missing { background: #fff1f0; color: #ff4d4f; padding: 4px 8px; border-radius: 3px; margin: 2px 0; }
.diff-unexpected { background: #fffbe6; color: #faad14; padding: 4px 8px; border-radius: 3px; margin: 2px 0; }
.match-rate { color: #52c41a; }
</style>