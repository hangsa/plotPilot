<template>
  <div class="cascade-graph">
    <div class="cascade-graph-toolbar">
      <n-select
        v-model:value="triggerForm.trigger"
        :options="triggerOptions"
        placeholder="选择 trigger"
        style="width: 220px"
      />
      <n-select
        v-model:value="triggerForm.sourceAssetType"
        :options="assetTypeOptions"
        placeholder="源资产类型"
        style="width: 160px"
      />
      <n-input v-model:value="triggerForm.sourceAssetId" placeholder="源资产 ID" />
      <n-button type="primary" :loading="cascade.isSimulating" @click="onSimulate" class="simulate-btn">
        Simulate
      </n-button>
    </div>
    <div v-if="cascade.lastSimulation" class="cascade-graph-summary">
      <n-tag :type="cascade.lastSimulation.summary.wouldBlock ? 'error' : 'success'">
        {{ cascade.lastSimulation.summary.wouldBlock ? 'Block' : 'Pass' }}
      </n-tag>
      <span>Max Depth: {{ cascade.lastSimulation.summary.maxDepthReached }}</span>
      <span>Steps: {{ cascade.lastSimulation.summary.stepsCount }}</span>
    </div>
    <div class="cascade-graph-canvas" data-testid="vue-flow">
      <VueFlow
        v-model:nodes="vueFlowNodes"
        v-model:edges="vueFlowEdges"
        :node-types="nodeTypes"
        fit-view-on-init
      >
        <Background />
        <Controls />
      </VueFlow>
    </div>
    <div v-if="cascade.lastSimulation" class="cascade-graph-intensity">
      <IntensityChart :steps="cascade.lastSimulation.steps" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { NSelect, NInput, NButton, NTag } from 'naive-ui'
import CascadeStepNode from '@/components/workbench/storyos/CascadeStepNode.vue'
import IntensityChart from '@/components/workbench/storyos/IntensityChart.vue'
import { useStoryosCascadeStore } from '@/stores/storyos/cascade'
import type { CascadeTrigger, AssetType, CascadeStep } from '@/types/storyos'

const props = defineProps<{ slug: string }>()
const cascade = useStoryosCascadeStore()

const triggerForm = ref<{ trigger: CascadeTrigger | null; sourceAssetType: AssetType | null; sourceAssetId: string }>({
  trigger: null, sourceAssetType: null, sourceAssetId: '',
})

const triggerOptions = [
  { label: 'mystery_revealed', value: 'mystery_revealed' },
  { label: 'twist_revealed', value: 'twist_revealed' },
  { label: 'reveal_revealed', value: 'reveal_revealed' },
  { label: 'promise_fulfilled', value: 'promise_fulfilled' },
  { label: 'conflict_resolved', value: 'conflict_resolved' },
  { label: 'conflict_escalated', value: 'conflict_escalated' },
]

const assetTypeOptions = [
  { label: 'conflict', value: 'conflict' },
  { label: 'mystery', value: 'mystery' },
  { label: 'twist', value: 'twist' },
  { label: 'expectation', value: 'expectation' },
]

const nodeTypes = { cascadeStep: CascadeStepNode }

const vueFlowNodes = ref<any[]>([])
const vueFlowEdges = ref<any[]>([])

async function onSimulate() {
  if (!triggerForm.value.trigger || !triggerForm.value.sourceAssetType || !triggerForm.value.sourceAssetId) return
  await cascade.simulate(props.slug, {
    trigger: triggerForm.value.trigger,
    sourceAssetType: triggerForm.value.sourceAssetType,
    sourceAssetId: triggerForm.value.sourceAssetId,
  })
  rebuildGraph()
}

function rebuildGraph() {
  const steps = cascade.lastSimulation?.steps ?? []

  // Build node-id index keyed by targetAssetId so edges can resolve fan-in/fan-out
  // (e.g. when one source triggers multiple targets, or several steps converge on
  // the same target). Without this lookup the previous "prevTargetId" chain would
  // miswire all non-linear cascades once 1E exposes real data.
  const targetIdToNodeId = new Map<string, string>()
  vueFlowNodes.value = steps.map((s, i) => {
    const nodeId = `s${i}-${s.targetAssetId}`
    targetIdToNodeId.set(s.targetAssetId, nodeId)
    return {
      id: nodeId,
      type: 'cascadeStep',
      position: { x: (i + 1) * 220, y: 100 },
      data: s,
    }
  })
  vueFlowNodes.value.unshift({
    id: `root-${steps[0]?.sourceAssetId ?? 'unknown'}`,
    type: 'cascadeStep',
    position: { x: 0, y: 100 },
    data: { label: 'Source', assetId: steps[0]?.sourceAssetId },
  })

  const edges: typeof vueFlowEdges.value = []
  steps.forEach((s, i) => {
    const nodeId = `s${i}-${s.targetAssetId}`
    const upstream = targetIdToNodeId.get(s.sourceAssetId)
    const sourceId = upstream ?? `root-${s.sourceAssetId}`
    edges.push({
      id: `e${i}`,
      source: sourceId,
      target: nodeId,
      label: s.trigger,
      animated: true,
    })
  })
  vueFlowEdges.value = edges
}

defineExpose({ vueFlowNodes, vueFlowEdges })
</script>

<style scoped>
.cascade-graph { display: flex; flex-direction: column; height: 100%; }
.cascade-graph-toolbar { display: flex; gap: 8px; padding: 12px; }
.cascade-graph-summary { display: flex; gap: 12px; padding: 0 12px; font-size: 12px; }
.cascade-graph-canvas { flex: 1; min-height: 400px; }
.cascade-graph-intensity { padding: 12px; }
</style>