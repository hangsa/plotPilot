<template>
  <div class="predeclared-diff">
    <div v-if="sflog.error" class="diff-error">
      {{ sflog.error }}
    </div>
    <div v-else-if="report" class="diff-summary">
      <h4 class="match-rate">匹配率：{{ (report.matchRate * 100).toFixed(0) }}%</h4>
      <span>{{ report.predeclaredImplemented }} / {{ report.predeclaredTotal }} 实现</span>
    </div>
    <template v-if="report">
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useStoryosSflogStore } from '@/stores/storyos/sflog'
import type { MatchReport } from '@/types/storyos'

const props = defineProps<{ slug: string; chapterId: number }>()
const sflog = useStoryosSflogStore()

const report = computed<MatchReport | null>(() => sflog.currentReparse?.matchReport ?? null)

watch(() => [props.slug, props.chapterId], ([slug, ch]) => {
  sflog.reparse(slug, ch)
}, { immediate: true })
</script>

<style scoped>
.diff-missing { background: #fff1f0; color: #ff4d4f; padding: 4px 8px; border-radius: 3px; margin: 2px 0; }
.diff-unexpected { background: #fffbe6; color: #faad14; padding: 4px 8px; border-radius: 3px; margin: 2px 0; }
.match-rate { color: #52c41a; }
.diff-error { background: #fff1f0; color: #ff4d4f; padding: 8px 12px; border: 1px solid #ffccc7; border-radius: 4px; }
</style>