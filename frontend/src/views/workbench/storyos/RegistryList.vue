<template>
  <div class="registry-list">
    <div class="registry-list-toolbar">
      <n-input v-model:value="search" placeholder="搜索描述..." clearable />
      <select v-model="statusFilter" class="status-filter">
        <option value="">全部状态</option>
        <option v-for="s in allStatuses" :key="s" :value="s">{{ s }}</option>
      </select>
      <n-button type="primary" @click="showCreate = true">+ 新建</n-button>
    </div>
    <div class="registry-list-grid">
      <AssetCard
        v-for="item in (store as any)[currentListKey]"
        :key="item.id"
        :asset="item"
        :selected="selectedId === item.id"
        @click="onCardClick"
      />
    </div>
    <RegistryDetailDrawer
      v-if="selectedId"
      :slug="slug"
      :asset-type="assetType"
      :asset-id="selectedId"
      @close="onDrawerClose"
      @updated="onUpdated"
    />
    <CreateAssetModal
      v-if="showCreate"
      :slug="slug"
      :asset-type="assetType"
      @close="showCreate = false"
      @created="onCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NInput, NButton } from 'naive-ui'
import AssetCard from '@/components/workbench/storyos/AssetCard.vue'
import RegistryDetailDrawer from './RegistryDetailDrawer.vue'
import CreateAssetModal from './CreateAssetModal.vue'
import { useStoryosQueriesStore } from '@/stores/storyos/queries'
import type { AssetType, AssetStatus } from '@/types/storyos'

const route = useRoute()
const store = useStoryosQueriesStore()
const slug = computed(() => route.params.slug as string)
const assetType = computed(() => (route.params.assetType || 'conflict') as AssetType)

const search = ref('')
const statusFilter = ref<string>('')
const selectedId = ref<string | null>(null)
const showCreate = ref(false)

const allStatuses: AssetStatus[] = [
  'active', 'accumulating', 'planted', 'developing',
  'hidden', 'ready_to_fulfill', 'escalated', 'revealed',
  'fulfilled', 'resolved', 'abandoned', 'dead',
]

const LIST_KEY_MAP: Record<AssetType, keyof typeof store> = {
  conflict: 'conflictList',
  mystery: 'mysteryList',
  twist: 'twistList',
  promise: 'promiseList',
  reveal: 'revealList',
  expectation: 'expectationList',
  goal: 'goalList',
  foreshadowing: 'foreshadowingList',
}

const currentListKey = computed<keyof typeof store>(
  () => LIST_KEY_MAP[assetType.value] || 'conflictList',
)

async function loadList() {
  await store.fetchList(slug.value, assetType.value, {
    status: statusFilter.value || undefined,
    page: 1, pageSize: 50,
  })
}

onMounted(loadList)
watch([statusFilter, assetType], loadList)

function onCardClick(asset: any) { selectedId.value = asset.id }
function onDrawerClose() { selectedId.value = null }
function onUpdated() { loadList() }
function onCreated() { showCreate.value = false; loadList() }
</script>

<style scoped>
.registry-list { padding: 24px; }
.registry-list-toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.status-filter { padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; }
.registry-list-grid { display: grid; grid-template-columns: 1fr; gap: 8px; }
</style>
