<template>
  <div class="storyos-hub">
    <div class="storyos-header">
      <span class="storyos-title">{{ $t('storyos.title') }}</span>
      <span class="storyos-project-id">{{ slug }}</span>
      <n-button @click="goBack" size="small">{{ $t('common.back') }}</n-button>
    </div>
    <n-split direction="horizontal" :min="200" :max="320" :default-size="240">
      <template #1>
        <div class="storyos-sidebar">
          <div class="storyos-sidebar-section">
            <h4>{{ $t('storyos.section.registries') }}</h4>
            <div
              v-for="asset in assetTypes"
              :key="asset"
              class="storyos-sidebar-item"
              :data-asset="asset"
              :class="{ active: $route.params.assetType === asset }"
              @click="navigateTo(asset)"
            >
              <StatusBadge v-if="asset" :status="getRepresentativeStatus(asset)" />
              <span>{{ $t(`storyos.asset.${asset}`) }}</span>
            </div>
          </div>
          <div class="storyos-sidebar-section">
            <h4>{{ $t('storyos.section.observability') }}</h4>
            <div
              class="storyos-sidebar-link"
              data-asset="cascade"
              :class="{ active: $route.name === 'WorkbenchStoryosCascade' }"
              @click="navigateToCascade"
            >
              <span>{{ $t('storyos.asset.cascadeGraph') }}</span>
            </div>
            <div class="storyos-sidebar-link" @click="navigateToSflog">
              <span>{{ $t('storyos.asset.sflogInspector') }}</span>
            </div>
            <div class="storyos-sidebar-link" @click="navigateToPredeclared">
              <span>{{ $t('storyos.asset.predeclaredDiff') }}</span>
            </div>
          </div>
        </div>
      </template>
      <template #2>
        <div class="storyos-main">
          <router-view />
        </div>
      </template>
    </n-split>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NSplit } from 'naive-ui'
import StatusBadge from '@/components/workbench/storyos/StatusBadge.vue'
import type { AssetType, AssetStatus } from '@/types/storyos'

const props = defineProps<{ slug: string }>()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const assetTypes: AssetType[] = [
  'conflict', 'mystery', 'twist', 'promise',
  'reveal', 'expectation', 'goal', 'foreshadowing',
]

const _ = ref(0)

function getRepresentativeStatus(asset: AssetType): AssetStatus {
  return 'active'
}

function navigateTo(asset: AssetType) {
  router.push({ name: 'WorkbenchStoryosAssetType', params: { slug: props.slug, assetType: asset } })
}

function navigateToCascade() {
  router.push({ name: 'WorkbenchStoryosCascade', params: { slug: props.slug } })
}

function navigateToSflog() {
  router.push({ name: 'WorkbenchStoryosSflog', params: { slug: props.slug, chapterId: 1 } })
}

function navigateToPredeclared() {
  router.push({ name: 'WorkbenchStoryosPredeclared', params: { slug: props.slug, chapterId: 1 } })
}

function goBack() {
  router.push({ name: 'Workbench', params: { slug: props.slug } })
}
</script>

<style scoped>
.storyos-hub {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.storyos-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  border-bottom: 1px solid #e0e0e6;
}
.storyos-title {
  font-size: 18px;
  font-weight: 600;
}
.storyos-project-id {
  color: #888;
  font-size: 12px;
}
.storyos-sidebar {
  padding: 16px 0;
}
.storyos-sidebar-section h4 {
  padding: 0 16px;
  margin: 12px 0 8px;
  font-size: 11px;
  text-transform: uppercase;
  color: #999;
}
.storyos-sidebar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  user-select: none;
}
.storyos-sidebar-item:hover {
  background: rgba(0, 0, 0, 0.04);
}
.storyos-sidebar-item.active {
  background: rgba(24, 160, 88, 0.1);
  color: #18a058;
}
.storyos-sidebar-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  user-select: none;
}
.storyos-sidebar-link:hover {
  background: rgba(0, 0, 0, 0.04);
}
.storyos-sidebar-link.active {
  background: rgba(24, 160, 88, 0.1);
  color: #18a058;
}
.storyos-main {
  height: 100%;
  overflow: auto;
}
</style>