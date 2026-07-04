<template>
  <span class="status-badge-stub">{{ status }}</span>
</template>

<script setup lang="ts">
import type { AssetStatus } from '@/types/storyos'
defineProps<{ status: AssetStatus }>()
</script>

<style scoped>
.status-badge-stub { display: inline-block; }
</style>