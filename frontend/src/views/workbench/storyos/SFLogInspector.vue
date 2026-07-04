<template>
  <div class="sf-log-inspector">
    <div class="sf-log-toolbar">
      <label>章节：<input v-model.number="chapterId" type="number" min="1" class="chapter-input" @change="loadRaw" /></label>
      <n-button @click="onReparse" :loading="sflog.isLoading">Re-parse</n-button>
    </div>
    <div class="sf-log-body">
      <div class="sf-log-raw-pane">
        <h4>原始文本（高亮 SF_LOG）</h4>
        <div class="sf-log-raw-text" v-html="highlightedRaw"></div>
      </div>
      <div class="sf-log-records-pane">
        <h4>解析结果（{{ sflog.currentRaw?.sfLogCount ?? 0 }} 条）</h4>
        <div
          v-for="rec in sflog.currentRaw?.records ?? []"
          :key="rec.charPosition"
          class="sf-log-record-item"
        >
          <div class="sf-log-record-header">
            <span class="sf-log-record-type">{{ rec.logType }}</span>
            <span class="sf-log-record-pos">@{{ rec.charPosition }}</span>
          </div>
          <pre class="sf-log-record-params">{{ JSON.stringify(rec.params, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { NButton } from 'naive-ui'
import { useStoryosSflogStore } from '@/stores/storyos/sflog'

const props = defineProps<{ slug: string; chapterId: number }>()
const sflog = useStoryosSflogStore()
const chapterId = ref(props.chapterId)

const highlightedRaw = computed(() => {
  if (!sflog.currentRaw) return ''
  return sflog.currentRaw.rawText.replace(
    /<!--\s*(SF_LOG[^>]*?)\s*-->/g,
    (_m, inner) => `<mark class="sf-log-highlight">${inner}</mark>`,
  )
})

async function loadRaw() {
  await sflog.loadRaw(props.slug, Number(chapterId.value))
}

async function onReparse() {
  await sflog.reparse(props.slug, chapterId.value)
}

onMounted(loadRaw)
watch(() => props.chapterId, (v) => { chapterId.value = v; loadRaw() })
</script>

<style scoped>
.sf-log-inspector { display: flex; flex-direction: column; height: 100%; }
.sf-log-toolbar { display: flex; gap: 12px; padding: 12px; border-bottom: 1px solid #e0e0e6; }
.sf-log-body { display: flex; flex: 1; overflow: hidden; }
.sf-log-raw-pane, .sf-log-records-pane { flex: 1; padding: 12px; overflow: auto; }
.sf-log-raw-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.6;
}
:deep(.sf-log-highlight) {
  background: #fff3a0;
  border: 1px solid #faad14;
  border-radius: 3px;
  padding: 0 2px;
}
.sf-log-record-item {
  border: 1px solid #e0e0e6;
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
}
.sf-log-record-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.sf-log-record-type { font-weight: 500; color: #1890ff; }
.sf-log-record-pos { font-size: 11px; color: #999; }
.sf-log-record-params {
  font-size: 11px;
  background: #f5f5f5;
  padding: 4px;
  border-radius: 3px;
  margin: 0;
}
</style>