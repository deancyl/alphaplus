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
  return api.get('/favorites', { params })
}

// Add a favorite
export const addFavorite = async (data: Favorite): Promise<Favorite> => {
  return api.post('/favorites', data)
}

// Remove a favorite
export const removeFavorite = async (id: number): Promise<void> => {
  return api.delete(`/favorites/${id}`)
}

// Reorder a favorite
export const reorderFavorite = async (id: number, newSortOrder: number): Promise<void> => {
  return api.put('/favorites/reorder', { id, new_sort_order: newSortOrder })
}

// Sync local favorites to cloud
export const syncFavoritesToCloud = async (favorites: Favorite[]): Promise<FavoritesResponse> => {
  return api.post('/favorites/sync', { favorites })
}

export const favoritesApi = {
  list: listFavorites,
  add: addFavorite,
  remove: removeFavorite,
  reorder: reorderFavorite,
  sync: syncFavoritesToCloud,
}
