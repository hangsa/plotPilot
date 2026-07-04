<template>
  <n-modal :show="true">
    <n-card title="新建资产 (TODO)">Stub</n-card>
  </n-modal>
</template>

<script setup lang="ts">
import { NModal, NCard } from 'naive-ui'

defineProps<{ slug: string; assetType: string }>()
defineEmits<{ close: []; created: [] }>()
</script>
