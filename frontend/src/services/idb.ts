/**
 * IndexedDB Service for Backtest History Persistence
 * Enables offline access and faster reload of backtest results
 * 
 * Database: alphaplus-backtest
 * Store: backtest-history
 * 
 * Dependencies: idb (lightweight Promise-based IndexedDB wrapper)
 */
import { openDB, IDBPDatabase } from 'idb'
import type { BacktestResult } from '@/api/portfolio'

// Database configuration
const DB_NAME = 'alphaplus-backtest'
const DB_VERSION = 1
const STORE_NAME = 'backtest-history'

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
 * Database schema for type safety
 */
interface BacktestDBSchema {
  'backtest-history': {
    key: string
    value: BacktestHistoryRecord
    indexes: {
      'by-portfolio': string
      'by-date': string
    }
  }
}

// Database instance (singleton)
let dbPromise: Promise<IDBPDatabase<BacktestDBSchema>> | null = null

/**
 * Get or create database connection
 * Implements singleton pattern to avoid multiple connections
 */
async function getDB(): Promise<IDBPDatabase<BacktestDBSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<BacktestDBSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
          // Create indexes for efficient querying
          store.createIndex('by-portfolio', 'portfolio_name')
          store.createIndex('by-date', 'created_at')
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
    
    await db.put(STORE_NAME, record)
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
    const record = await db.get(STORE_NAME, id)
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
    const records = await db.getAll(STORE_NAME)
    
    // Sort by created_at descending (newest first)
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
    const records = await db.getAllFromIndex(STORE_NAME, 'by-portfolio', portfolioName)
    
    // Sort by created_at descending (newest first)
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
    await db.delete(STORE_NAME, id)
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
    await db.clear(STORE_NAME)
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
    return await db.count(STORE_NAME)
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
}
