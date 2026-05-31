/**
 * Pool API endpoints for fund pool management
 */
import api from './index'

// Types
export interface PoolFund {
  id: number
  pool_type: 'entry' | 'focus' | 'exit'
  fund_code: string
  fund_name: string
  status: 'active' | 'removed'
  added_date: string
  removed_date?: string
  notes?: string
  // Extended fields for display
  return_1y?: number
  scale?: number
  manager?: string
}

export interface PoolAddRequest {
  pool_type: string
  fund_code: string
  fund_name: string
  notes?: string
}

export interface PoolListResponse {
  funds: PoolFund[]
  total: number
}

export interface PoolBulkAddRequest {
  pool_type: string
  funds: PoolAddRequest[]
}

export interface PoolTransferRequest {
  id: number
  new_pool_type: string
}

export interface PoolStatusUpdateRequest {
  id: number
  status: string
  removed_date?: string
}

// List funds in pool (optionally filtered by pool type and status)
export const listPoolFunds = async (
  poolType?: string,
  status?: string
): Promise<PoolListResponse> => {
  const params: Record<string, string> = {}
  if (poolType) params.pool_type = poolType
  if (status) params.status = status
  const response = await api.get('/pool', { params })
  return response.data!
}

// Add a fund to pool
export const addFundToPool = async (data: PoolAddRequest): Promise<PoolFund> => {
  const response = await api.post('/pool/add', data)
  return response.data!
}

// Bulk add funds to pool
export const bulkAddFundsToPool = async (data: PoolBulkAddRequest): Promise<PoolListResponse> => {
  const response = await api.post('/pool/bulk-add', data)
  return response.data!
}

// Remove a fund from pool
export const removeFundFromPool = async (id: number): Promise<void> => {
  const response = await api.delete(`/pool/${id}`)
  return response.data!
}

// Transfer fund between pools
export const transferFundBetweenPools = async (data: PoolTransferRequest): Promise<PoolFund> => {
  const response = await api.post('/pool/transfer', data)
  return response.data!
}

// Update fund status in pool
export const updatePoolFundStatus = async (data: PoolStatusUpdateRequest): Promise<PoolFund> => {
  const response = await api.put('/pool/status', data)
  return response.data!
}

export const poolApi = {
  list: listPoolFunds,
  add: addFundToPool,
  bulkAdd: bulkAddFundsToPool,
  remove: removeFundFromPool,
  transfer: transferFundBetweenPools,
  updateStatus: updatePoolFundStatus,
}
