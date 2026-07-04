import type { RouteRecordRaw } from 'vue-router'

/** StoryOS 嵌套路由（在 /book/:slug/workbench 之外的可选独立路由）。*/
export const workbenchStoryosRoutes: RouteRecordRaw[] = [
  {
    path: '/book/:slug/storyos',
    name: 'WorkbenchStoryos',
    component: () => import('@/views/workbench/storyos/StoryOSHub.vue'),
    meta: { requiresProject: true },
    children: [
      {
        path: '',
        name: 'WorkbenchStoryosRegistryList',
        component: () => import('@/views/workbench/storyos/RegistryList.vue'),
      },
      {
        path: ':assetType',
        name: 'WorkbenchStoryosAssetType',
        component: () => import('@/views/workbench/storyos/RegistryList.vue'),
        props: true,
      },
      {
        path: 'cascade',
        name: 'WorkbenchStoryosCascade',
        component: () => import('@/views/workbench/storyos/CascadeGraph.vue'),
      },
      {
        path: 'sflog/:chapterId',
        name: 'WorkbenchStoryosSflog',
        component: () => import('@/views/workbench/storyos/SFLogInspector.vue'),
        props: true,
      },
      {
        path: 'predeclared/:chapterId',
        name: 'WorkbenchStoryosPredeclared',
        component: () => import('@/views/workbench/storyos/PredeclaredDiff.vue'),
        props: true,
      },
    ],
  },
]
