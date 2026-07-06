import { apiClient } from './config'

export interface CoreRules {
  powerSystem: string
  physicsRules: string
  magicTech: string
}

export interface Geography {
  terrain: string
  climate: string
  resources: string
  ecology: string
}

export interface Society {
  politics: string
  economy: string
  classSystem: string
}

export interface Culture {
  history: string
  religion: string
  taboos: string
}

export interface DailyLife {
  foodClothing: string
  languageSlang: string
  entertainment: string
}

export interface Worldbuilding {
  id: string
  novelId: string
  schemaVersion?: number
  dimensions?: Record<string, Record<string, string>>
  coreRules: CoreRules
  geography: Geography
  society: Society
  culture: Culture
  dailyLife: DailyLife
  createdAt: string
  updatedAt: string
}

export const worldbuildingApi = {
  getWorldbuilding: (slug: string): Promise<Worldbuilding> =>
    // silentGlobalFeedback: the interceptor skips toast for this call;
    // callers handle 404 (not-yet-generated) themselves.
    apiClient.get<Worldbuilding>(`/novels/${slug}/worldbuilding`, { silentGlobalFeedback: true } as never),

  updateWorldbuilding: (slug: string, data: Partial<Worldbuilding>): Promise<Worldbuilding> =>
    apiClient.put<Worldbuilding>(`/novels/${slug}/worldbuilding`, data),
}
