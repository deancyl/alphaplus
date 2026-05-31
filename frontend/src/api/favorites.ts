/**
 * Favorites API endpoints
 */
import api from './index'

// Types
export interface Favorite {
  id?: number
  product_type: string
  product_code: string
  product_name: string
  sort_order: number
}

export interface FavoritesResponse {
  favorites: Favorite[]
  total: number
}

// List favorites (optionally filtered by product type)
export const listFavorites = async (productType?: string): Promise<FavoritesResponse> => {
  const params: Record<string, string> = {}
  if (productType) params.product_type = productType
  const response = await api.get('/favorites', { params })
  return response.data ?? { favorites: [], total: 0 }
}

// Add a favorite
export const addFavorite = async (data: Favorite): Promise<Favorite> => {
  const response = await api.post('/favorites', data)
  return response.data!
}

// Remove a favorite
export const removeFavorite = async (id: number): Promise<void> => {
  const response = await api.delete(`/favorites/${id}`)
  return response.data!
}

// Reorder a favorite
export const reorderFavorite = async (id: number, newSortOrder: number): Promise<void> => {
  const response = await api.put('/favorites/reorder', { id, new_sort_order: newSortOrder })
  return response.data!
}

// Sync local favorites to cloud
export const syncFavoritesToCloud = async (favorites: Favorite[]): Promise<FavoritesResponse> => {
  const response = await api.post('/favorites/sync', { favorites })
  return response.data ?? { favorites: [], total: 0 }
}

export const favoritesApi = {
  list: listFavorites,
  add: addFavorite,
  remove: removeFavorite,
  reorder: reorderFavorite,
  sync: syncFavoritesToCloud,
}
