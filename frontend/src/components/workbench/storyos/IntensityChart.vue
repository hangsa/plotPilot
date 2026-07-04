<template>
  <div class="intensity-chart" :style="{ height: height + 'px' }">
    <VChart :option="chartOption" :autoresize="true" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  TitleComponent,
} from 'echarts/components'
import type { CascadeStep } from '@/types/storyos'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, TitleComponent])

const props = withDefaults(
  defineProps<{ steps: CascadeStep[]; height?: number }>(),
  { height: 300 },
)

/**
 * Backend does not yet return a numeric intensity per step, so we synthesize a
 * coarse ordinal value from `newStatus` so the chart remains useful as a
 * visual aid (escalated > ready_to_fulfill > resolved/fulfilled > default).
 * When backend exposes a numeric intensity, swap this helper for that field.
 */
function intensityFor(step: CascadeStep): number {
  switch (step.newStatus) {
    case 'escalated':
      return 80
    case 'ready_to_fulfill':
      return 60
    case 'resolved':
    case 'fulfilled':
    case 'revealed':
      return 30
    case 'dead':
    case 'abandoned':
      return 10
    default:
      return 40
  }
}

const chartOption = computed(() => {
  const data = props.steps.map(intensityFor)
  const labels = props.steps.map((_, i) => `Step ${i + 1}`)
  return {
    title: {
      text: 'Cascade Intensity',
      left: 'left',
      textStyle: { fontSize: 14, fontWeight: 600 },
    },
    tooltip: {
      trigger: 'axis',
    },
    grid: { left: 48, right: 16, top: 48, bottom: 32 },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      name: 'Intensity',
    },
    series: [
      {
        type: 'line',
        data,
        smooth: true,
        areaStyle: { opacity: 0.2 },
        lineStyle: { width: 2 },
      },
    ],
  }
})
</script>

<style scoped>
.intensity-chart {
  width: 100%;
  min-height: 200px;
}
</style>