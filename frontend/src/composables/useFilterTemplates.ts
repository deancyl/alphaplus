import { ref, readonly } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index'
import type { FundFilterParams } from '@/api/fund'
import {
  saveFilterTemplate,
  getAllFilterTemplates,
  deleteFilterTemplate as deleteIdbTemplate,
  setDefaultFilterTemplate as setIdbDefault,
  getDefaultFilterTemplate,
  markTemplateSynced,
  getUnsyncedTemplates,
  isIndexedDBAvailable,
  type FilterTemplateRecord,
} from '@/services/idb'

const PREF_TYPE = 'filter_template'

interface PreferenceResponse {
  id: number
  user_id: number
  pref_type: string
  pref_key: string
  pref_name: string
  pref_value: string
  is_default: boolean
  created_at: string
  updated_at: string
}

const templates = ref<FilterTemplateRecord[]>([])
const defaultTemplateKey = ref<string | null>(null)
const loading = ref(false)
const offlineMode = ref(!navigator.onLine)

function generateTemplateKey(name: string): string {
  const timestamp = Date.now()
  const sanitized = name.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 20)
  return `filter-${sanitized}-${timestamp}`
}

async function loadTemplates(): Promise<void> {
  loading.value = true
  
  try {
    const response = await api.get<PreferenceResponse[]>('/preferences/filter_template')
    
    if (response && Array.isArray(response) && response.length > 0) {
      const loadedTemplates: FilterTemplateRecord[] = response.map((pref) => ({
        key: pref.pref_key,
        name: pref.pref_name,
        params: JSON.parse(pref.pref_value) as FundFilterParams,
        is_default: pref.is_default,
        created_at: pref.created_at,
        updated_at: pref.updated_at,
        synced: true,
      }))
      
      templates.value = loadedTemplates.sort((a, b) => 
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )
      
      const defaultTemplate = loadedTemplates.find(t => t.is_default)
      defaultTemplateKey.value = defaultTemplate?.key || null
      
      for (const template of loadedTemplates) {
        await saveFilterTemplate(
          template.key,
          template.name,
          template.params,
          template.is_default
        )
        await markTemplateSynced(template.key)
      }
      
      return
    }
  } catch {
    offlineMode.value = true
  }
  
  if (isIndexedDBAvailable()) {
    const idbTemplates = await getAllFilterTemplates()
    if (idbTemplates.length > 0) {
      templates.value = idbTemplates
      const defaultT = await getDefaultFilterTemplate()
      defaultTemplateKey.value = defaultT?.key || null
    }
  }
  
  const saved = localStorage.getItem('fundFilterConfig')
  if (saved && templates.value.length === 0) {
    try {
      const params = JSON.parse(saved) as FundFilterParams
      const legacyTemplate: FilterTemplateRecord = {
        key: 'legacy-localstorage',
        name: '历史配置',
        params,
        is_default: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        synced: false,
      }
      templates.value = [legacyTemplate]
      defaultTemplateKey.value = legacyTemplate.key
      
      if (isIndexedDBAvailable()) {
        await saveFilterTemplate(legacyTemplate.key, legacyTemplate.name, params, true)
      }
    } catch {
    }
  }
  
  loading.value = false
}

async function saveTemplate(name: string, params: FundFilterParams): Promise<string> {
  const key = generateTemplateKey(name)
  
  try {
    await api.post('/preferences/filter_template', {
      pref_type: PREF_TYPE,
      pref_key: key,
      pref_name: name,
      pref_value: JSON.stringify(params),
      is_default: false,
    })
    
    ElMessage.success(`模板 "${name}" 已保存`)
    offlineMode.value = false
    
    const template: FilterTemplateRecord = {
      key,
      name,
      params,
      is_default: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      synced: true,
    }
    
    templates.value.unshift(template)
    
    if (isIndexedDBAvailable()) {
      await saveFilterTemplate(key, name, params, false)
      await markTemplateSynced(key)
    }
    
    return key
  } catch {
    offlineMode.value = true
    ElMessage.warning('离线模式：模板已保存到本地')
    
    const template: FilterTemplateRecord = {
      key,
      name,
      params,
      is_default: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      synced: false,
    }
    
    templates.value.unshift(template)
    
    if (isIndexedDBAvailable()) {
      await saveFilterTemplate(key, name, params, false)
    }
    
    return key
  }
}

async function deleteTemplate(key: string): Promise<void> {
  const template = templates.value.find(t => t.key === key)
  const templateName = template?.name || '模板'
  
  try {
    await api.delete(`/preferences/filter_template/${key}`)
    ElMessage.success(`模板 "${templateName}" 已删除`)
    offlineMode.value = false
  } catch {
    offlineMode.value = true
    ElMessage.warning('离线模式：模板已从本地删除')
  }
  
  templates.value = templates.value.filter(t => t.key !== key)
  
  if (defaultTemplateKey.value === key) {
    defaultTemplateKey.value = null
  }
  
  if (isIndexedDBAvailable()) {
    await deleteIdbTemplate(key)
  }
  
  if (key === 'legacy-localstorage') {
    localStorage.removeItem('fundFilterConfig')
  }
}

async function setDefault(key: string): Promise<void> {
  const template = templates.value.find(t => t.key === key)
  const templateName = template?.name || '模板'
  
  try {
    await api.post(`/preferences/filter_template/${key}/set-default`)
    ElMessage.success(`已将 "${templateName}" 设为默认模板`)
    offlineMode.value = false
  } catch {
    offlineMode.value = true
    ElMessage.warning('离线模式：默认模板已更新到本地')
  }
  
  defaultTemplateKey.value = key
  
  for (const t of templates.value) {
    t.is_default = t.key === key
  }
  
  if (isIndexedDBAvailable()) {
    await setIdbDefault(key)
  }
}

async function syncUnsyncedTemplates(): Promise<void> {
  if (!navigator.onLine) return
  
  const unsynced = await getUnsyncedTemplates()
  
  for (const template of unsynced) {
    try {
      await api.post('/preferences/filter_template', {
        pref_type: PREF_TYPE,
        pref_key: template.key,
        pref_name: template.name,
        pref_value: JSON.stringify(template.params),
        is_default: template.is_default,
      })
      
      await markTemplateSynced(template.key)
      
      const index = templates.value.findIndex(t => t.key === template.key)
      if (index !== -1) {
        templates.value[index].synced = true
      }
    } catch {
    }
  }
  
  if (unsynced.length > 0) {
    ElMessage.success(`${unsynced.length} 个离线模板已同步`)
    offlineMode.value = false
  }
}

function loadTemplateParams(key: string): FundFilterParams | null {
  const template = templates.value.find(t => t.key === key)
  return template?.params || null
}

window.addEventListener('online', async () => {
  offlineMode.value = false
  await syncUnsyncedTemplates()
})

window.addEventListener('offline', () => {
  offlineMode.value = true
})

export function useFilterTemplates() {
  return {
    templates: readonly(templates),
    defaultTemplateKey: readonly(defaultTemplateKey),
    loading: readonly(loading),
    offlineMode: readonly(offlineMode),
    loadTemplates,
    saveTemplate,
    deleteTemplate,
    setDefault,
    loadTemplateParams,
    syncUnsyncedTemplates,
  }
}