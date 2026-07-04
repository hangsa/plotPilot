<template>
  <div class="cascade-step-node" :class="{ 'is-root': isRoot, 'is-blocked': isBlocked }">
    <Handle type="target" :position="Position.Left" />
    <div class="node-header">
      <span class="node-label">{{ displayLabel }}</span>
    </div>
    <div class="node-body">
      <div v-if="!isRoot" class="node-row">
        <span class="row-key">trigger:</span>
        <span class="row-val">{{ data.trigger }}</span>
      </div>
      <div v-if="!isRoot" class="node-row">
        <span class="row-key">target:</span>
        <span class="row-val">{{ data.targetAssetId }}</span>
      </div>
      <div v-if="!isRoot && data.newStatus" class="node-row">
        <span class="row-key">status:</span>
        <span class="row-val status-tag">{{ data.newStatus }}</span>
      </div>
      <div v-if="isRoot" class="node-row">
        <span class="row-key">source:</span>
        <span class="row-val">{{ data.assetId }}</span>
      </div>
    </div>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

interface NodeData {
  label?: string
  assetId?: string
  trigger?: string
  targetAssetId?: string
  newStatus?: string | null
}

const props = defineProps<{ data: NodeData }>()

const isRoot = computed(() => Boolean(props.data?.label && !props.data?.trigger))
const isBlocked = computed(() => props.data?.newStatus === 'blocked')

const displayLabel = computed(() => {
  if (props.data?.label) return props.data.label
  if (props.data?.trigger && props.data?.targetAssetId) {
    return `${props.data.trigger} → ${props.data.targetAssetId}`
  }
  return 'Step'
})
</script>

<style scoped>
.cascade-step-node {
  width: 180px;
  min-height: 80px;
  background: #ffffff;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
.cascade-step-node.is-root {
  background: #f0f7ff;
  border-color: #2080f0;
}
.cascade-step-node.is-blocked {
  background: #fff1f0;
  border-color: #d03050;
}
.node-header {
  font-weight: 600;
  margin-bottom: 6px;
  color: #333;
  word-break: break-all;
}
.node-row {
  display: flex;
  gap: 4px;
  margin-top: 2px;
  font-size: 11px;
}
.row-key {
  color: #888;
  min-width: 50px;
}
.row-val {
  color: #444;
  word-break: break-all;
}
.status-tag {
  background: #f5f5f5;
  padding: 0 4px;
  border-radius: 3px;
}
</style>