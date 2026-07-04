<template>
  <div class="asset-card" :class="{ selected }" @click="$emit('click', asset)">
    <div class="asset-card-header">
      <span class="asset-card-id">#{{ asset.id }}</span>
      <StatusBadge :status="asset.status" size="small" />
    </div>
    <div class="asset-card-description">{{ asset.description }}</div>
    <div class="asset-card-meta">
      <span>{{ t('storyos.meta.chapter') }}: {{ asset.createdChapter }}</span>
      <span v-if="(asset as ConflictAsset).intensity !== undefined">
        {{ t('storyos.meta.intensity') }}: {{ (asset as ConflictAsset).intensity }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import StatusBadge from './StatusBadge.vue'
import type { ConflictAsset } from '@/types/storyos'

const { t } = useI18n()

defineProps<{
  asset: any
  selected?: boolean
}>()
defineEmits<{ click: [asset: any] }>()
</script>

<style scoped>
.asset-card {
  border: 1px solid #e0e0e6;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.asset-card:hover { border-color: #18a058; }
.asset-card.selected { background: rgba(24, 160, 88, 0.05); border-color: #18a058; }
.asset-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.asset-card-id { font-size: 11px; color: #999; }
.asset-card-description {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
}
.asset-card-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #888;
}
</style>
