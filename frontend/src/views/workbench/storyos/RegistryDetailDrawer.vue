<template>
  <div class="registry-detail-drawer">
    <n-drawer :show="!!assetId" :width="500" @update:show="onCloseClick">
      <n-drawer-content title="资产详情">
        <n-form v-if="asset">
          <n-form-item label="描述">
            <n-input v-model:value="form.description" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select v-model:value="form.status" :options="statusOptions" />
          </n-form-item>
          <n-form-item label="章节">
            <n-input-number v-model:value="form.createdChapter" />
          </n-form-item>
        </n-form>
      </n-drawer-content>
    </n-drawer>
    <div v-if="asset" class="drawer-content">
      <span>资产 ID: {{ asset.id }}</span>
      <span>描述: {{ form.description }}</span>
    </div>
    <div class="drawer-controls">
      <button class="close" type="button" @click="onCloseClick">关闭</button>
      <button
        v-if="asset"
        class="save"
        type="button"
        :disabled="isSaving"
        @click="onSave"
      >
        {{ isSaving ? '保存中…' : '保存' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  NDrawer, NDrawerContent, NForm, NFormItem,
  NInput, NSelect, NInputNumber,
} from 'naive-ui'
import { useStoryosQueriesStore } from '@/stores/storyos/queries'
import type { AssetType, AssetStatus } from '@/types/storyos'

const props = defineProps<{
  slug: string
  assetType: AssetType
  assetId: string | null
}>()
const emit = defineEmits<{ close: []; updated: [] }>()

const store = useStoryosQueriesStore()
const asset = ref<any>(null)
const isSaving = ref(false)
const form = ref({ description: '', status: 'active' as AssetStatus, createdChapter: 1 })

const ALL_STATUSES: AssetStatus[] = [
  'active', 'accumulating', 'planted', 'developing',
  'hidden', 'ready_to_fulfill', 'escalated', 'revealed',
  'fulfilled', 'resolved', 'abandoned', 'dead',
]
const statusOptions = ALL_STATUSES.map((s) => ({ label: s, value: s }))

watch(
  () => props.assetId,
  async (id) => {
    if (!id) {
      asset.value = null
      return
    }
    asset.value = await store.fetchOne(props.slug, props.assetType, id)
    if (!asset.value) {
      asset.value = null
      return
    }
    form.value = {
      description: asset.value.description,
      status: asset.value.status,
      createdChapter: asset.value.createdChapter,
    }
  },
  { immediate: true },
)

async function onSave() {
  if (!props.assetId) return
  isSaving.value = true
  try {
    await store.update(props.slug, props.assetType, props.assetId, form.value)
    emit('updated')
  } finally {
    isSaving.value = false
  }
}

function onCloseClick() {
  emit('close')
}
</script>

<style scoped>
.registry-detail-drawer { display: contents; }
.drawer-content { padding: 16px; }
.drawer-controls {
  padding: 12px 16px;
  border-top: 1px solid #e0e0e6;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.drawer-controls button {
  padding: 6px 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}
.drawer-controls button.save {
  background: #18a058;
  border-color: #18a058;
  color: #fff;
}
.drawer-controls button.save:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
