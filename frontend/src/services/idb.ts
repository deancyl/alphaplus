/**
 * IndexedDB Service for Backtest History & Filter Templates Persistence
 * Enables offline access and faster reload of backtest results and filter configs
 * 
 * Database: alphaplus-backtest
 * Stores: backtest-history, filter-templates
 * 
 * Dependencies: idb (lightweight Promise-based IndexedDB wrapper)
 */
import { openDB, IDBPDatabase } from 'idb'
import type { BacktestResult } from '@/api/portfolio'
import type { FundFilterParams } from '@/api/fund'

// Database configuration
const DB_NAME = 'alphaplus-backtest'
const DB_VERSION = 2  // Bumped for new store
const STORE_BACKTEST = 'backtest-history'
const STORE_TEMPLATES = 'filter-templates'

/**
 * Backtest history record with metadata
 */
export interface BacktestHistoryRecord {
  id: string
  portfolio_name: string
  created_at: string
  result: BacktestResult
}

/**
 * Filter template record for cloud fallback
 */
export interface FilterTemplateRecord {
  key: string              // Template unique key (pref_key)
  name: string             // Template display name (pref_name)
  params: FundFilterParams // Filter parameters (pref_value)
  is_default: boolean      // Is default template
  created_at: string       // Creation timestamp
  updated_at: string       // Last update timestamp
  synced: boolean          // Whether synced to cloud
}

/**
 * Database schema for type safety
 */
interface AlphaplusDBSchema {
  'backtest-history': {
    key: string
    value: BacktestHistoryRecord
    indexes: {
      'by-portfolio': string
      'by-date': string
    }
  }
  'filter-templates': {
    key: string
    value: FilterTemplateRecord
    indexes: {
      'by-name': string
      'by-date': string
      'by-default': number
    }
  }
}

// Database instance (singleton)
let dbPromise: Promise<IDBPDatabase<AlphaplusDBSchema>> | null = null

/**
 * Get or create database connection
 * Implements singleton pattern to avoid multiple connections
 */
async function getDB(): Promise<IDBPDatabase<AlphaplusDBSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<AlphaplusDBSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_BACKTEST)) {
          const backtestStore = db.createObjectStore(STORE_BACKTEST, { keyPath: 'id' })
          backtestStore.createIndex('by-portfolio', 'portfolio_name')
          backtestStore.createIndex('by-date', 'created_at')
        }
        
        if (!db.objectStoreNames.contains(STORE_TEMPLATES)) {
          const templateStore = db.createObjectStore(STORE_TEMPLATES, { keyPath: 'key' })
          templateStore.createIndex('by-name', 'name')
          templateStore.createIndex('by-date', 'updated_at')
          templateStore.createIndex('by-default', 'is_default')
        }
      },
    })
  }
  return dbPromise
}

/**
 * Save a backtest result to IndexedDB
 * @param id - Unique identifier for the backtest
 * @param result - Backtest result data
 */
export async function saveBacktest(
  id: string,
  result: BacktestResult
): Promise<void> {
  try {
    const db = await getDB()
    
    const record: BacktestHistoryRecord = {
      id,
      portfolio_name: result.portfolio_name,
      created_at: new Date().toISOString(),
      result,
    }
    
    await db.put(STORE_BACKTEST, record)
  } catch (error) {
    throw new Error(`Failed to save backtest: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Get a specific backtest by ID
 * @param id - Backtest ID
 * @returns Backtest record or null if not found
 */
export async function getBacktest(
  id: string
): Promise<BacktestHistoryRecord | null> {
  try {
    const db = await getDB()
    const record = await db.get(STORE_BACKTEST, id)
    return record || null
  } catch {
    return null
  }
}

/**
 * Get all backtest records
 * @returns Array of all backtest records, sorted by date (newest first)
 */
export async function getAllBacktests(): Promise<BacktestHistoryRecord[]> {
  try {
    const db = await getDB()
    const records = await db.getAll(STORE_BACKTEST)
    
    return records.sort((a, b) => 
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
  } catch {
    return []
  }
}

/**
 * Get backtests by portfolio name
 * @param portfolioName - Portfolio name to filter by
 * @returns Array of matching backtest records
 */
export async function getBacktestsByPortfolio(
  portfolioName: string
): Promise<BacktestHistoryRecord[]> {
  try {
    const db = await getDB()
    const records = await db.getAllFromIndex(STORE_BACKTEST, 'by-portfolio', portfolioName)
    
    return records.sort((a, b) => 
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
  } catch {
    return []
  }
}

/**
 * Delete a specific backtest by ID
 * @param id - Backtest ID to delete
 */
export async function deleteBacktest(id: string): Promise<void> {
  try {
    const db = await getDB()
    await db.delete(STORE_BACKTEST, id)
  } catch (error) {
    throw new Error(`Failed to delete backtest: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Clear all backtest records from the store
 * Use with caution - this removes all cached data
 */
export async function clearAll(): Promise<void> {
  try {
    const db = await getDB()
    await db.clear(STORE_BACKTEST)
    await db.clear(STORE_TEMPLATES)
  } catch (error) {
    throw new Error(`Failed to clear all: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Get backtest count
 * @returns Number of stored backtests
 */
export async function getBacktestCount(): Promise<number> {
  try {
    const db = await getDB()
    return await db.count(STORE_BACKTEST)
  } catch {
    return 0
  }
}

/**
 * Close database connection
 * Useful for cleanup or when switching contexts
 */
export async function closeDB(): Promise<void> {
  if (dbPromise) {
    const db = await dbPromise
    db.close()
    dbPromise = null
  }
}

/**
 * Check if IndexedDB is available in the browser
 * Useful for feature detection before using the service
 */
export function isIndexedDBAvailable(): boolean {
  try {
    return typeof indexedDB !== 'undefined' && indexedDB !== null
  } catch {
    return false
  }
}

export async function saveFilterTemplate(
  key: string,
  name: string,
  params: FundFilterParams,
  isDefault: boolean = false
): Promise<void> {
  try {
    const db = await getDB()
    const now = new Date().toISOString()
    
    const existing = await db.get(STORE_TEMPLATES, key)
    
    const record: FilterTemplateRecord = {
      key,
      name,
      params,
      is_default: isDefault,
      created_at: existing?.created_at || now,
      updated_at: now,
      synced: false,
    }
    
    await db.put(STORE_TEMPLATES, record)
  } catch (error) {
    throw new Error(`Failed to save filter template: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function getFilterTemplate(
  key: string
): Promise<FilterTemplateRecord | null> {
  try {
    const db = await getDB()
    return await db.get(STORE_TEMPLATES, key) || null
  } catch {
    return null
  }
}

export async function getAllFilterTemplates(): Promise<FilterTemplateRecord[]> {
  try {
    const db = await getDB()
    const records = await db.getAll(STORE_TEMPLATES)
    
    return records.sort((a, b) => 
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
  } catch {
    return []
  }
}

export async function getDefaultFilterTemplate(): Promise<FilterTemplateRecord | null> {
  try {
    const db = await getDB()
    const records = await db.getAllFromIndex(STORE_TEMPLATES, 'by-default', 1)
    return records[0] || null
  } catch {
    return null
  }
}

export async function deleteFilterTemplate(key: string): Promise<void> {
  try {
    const db = await getDB()
    await db.delete(STORE_TEMPLATES, key)
  } catch (error) {
    throw new Error(`Failed to delete filter template: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function setDefaultFilterTemplate(key: string): Promise<void> {
  try {
    const db = await getDB()
    const allTemplates = await db.getAll(STORE_TEMPLATES)
    
    const tx = db.transaction(STORE_TEMPLATES, 'readwrite')
    
    for (const template of allTemplates) {
      template.is_default = template.key === key
      template.updated_at = new Date().toISOString()
      template.synced = false
      await tx.store.put(template)
    }
    
    await tx.done
  } catch (error) {
    throw new Error(`Failed to set default template: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function markTemplateSynced(key: string): Promise<void> {
  try {
    const db = await getDB()
    const template = await db.get(STORE_TEMPLATES, key)
    if (template) {
      template.synced = true
      await db.put(STORE_TEMPLATES, template)
    }
  } catch {
  }
}

export async function getUnsyncedTemplates(): Promise<FilterTemplateRecord[]> {
  try {
    const db = await getDB()
    const allTemplates = await db.getAll(STORE_TEMPLATES)
    return allTemplates.filter(t => !t.synced)
  } catch {
    return []
  }
}

// Export types and service
export default {
  saveBacktest,
  getBacktest,
  getAllBacktests,
  getBacktestsByPortfolio,
  deleteBacktest,
  clearAll,
  getBacktestCount,
  closeDB,
  isIndexedDBAvailable,
  saveFilterTemplate,
  getFilterTemplate,
  getAllFilterTemplates,
  getDefaultFilterTemplate,
  deleteFilterTemplate,
  setDefaultFilterTemplate,
  markTemplateSynced,
  getUnsyncedTemplates,
}
