<template>
  <span class="status-badge" :class="[`badge-${colorClass}`, `badge-${size}`]">
    {{ status }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AssetStatus } from '@/types/storyos'

const props = withDefaults(defineProps<{
  status: AssetStatus
  size?: 'small' | 'medium'
}>(), { size: 'medium' })

const COLOR_MAP: Record<AssetStatus, 'blue' | 'yellow' | 'green' | 'red'> = {
  active: 'blue',
  accumulating: 'blue',
  developing: 'blue',
  hidden: 'blue',
  planted: 'yellow',
  ready_to_fulfill: 'yellow',
  escalated: 'yellow',
  revealed: 'green',
  fulfilled: 'green',
  resolved: 'green',
  abandoned: 'red',
  dead: 'red',
}

const colorClass = computed(() => COLOR_MAP[props.status])
</script>

<style scoped>
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
}
.badge-small { font-size: 10px; padding: 1px 6px; }
.badge-blue { background: #e6f7ff; color: #1890ff; }
.badge-yellow { background: #fffbe6; color: #faad14; }
.badge-green { background: #f6ffed; color: #52c41a; }
.badge-red { background: #fff1f0; color: #ff4d4f; }
</style>
