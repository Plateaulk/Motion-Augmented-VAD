import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add auth token to requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
    }
    return Promise.reject(error)
  }
)

// Motion API
export const motionAPI = {
  generate: (data) => api.post('/motion/generate', data),
  renderMask: (data) => api.post('/motion/render_mask', data),
  taskProgress: (taskId) => api.get(`/motion/task/${taskId}`),
  directories: () => api.get('/motion/directories'),
  list: (params = {}) => {
    // Support both legacy (dataset) and new (directory) parameters
    if (typeof params === 'string') {
      // Legacy: dataset string
      return api.get('/motion/list', { params: { dataset: params } })
    }
    return api.get('/motion/list', { params })
  },
  renders: (motionId, dataset = 'sht') => api.get(`/motion/renders/${motionId}`, { params: { dataset } }),
  status: (motionId) => api.get(`/motion/status/${motionId}`),
  delete: (motionId) => api.post(`/motion/delete/${motionId}`),
  getVideoUrl: (motionId, type = 'composite', renderId = null, directory = '') => {
    const params = new URLSearchParams()
    if (renderId) params.set('render_id', renderId)
    if (directory) params.set('directory', directory)
    const url = `/api/motion/video/${encodeURIComponent(motionId)}/${type}`
    return params.size ? `${url}?${params}` : url
  }
}

// Video API
export const videoAPI = {
  backgrounds: (dataset, folder = '', search = '') => api.get('/video/backgrounds', { params: { dataset, folder, search } }),
  backgroundFolders: (dataset) => api.get('/video/background_folders', { params: { dataset } }),
  deleteBackground: (name) => api.post('/video/delete_background', { name }),
  copyBackground: (data) => api.post('/video/copy_background', data),
  moveBackground: (data) => api.post('/video/move_background', data),
  t2v: (data) => api.post('/video/t2v', data),
  i2v: (data) => api.post('/video/i2v', data),
  v2v: (data) => api.post('/video/v2v', data),
  status: (jobId) => api.get(`/video/status/${jobId}`),
  progress: (promptId) => api.get(`/video/progress/${promptId}`),
  queue: () => api.get('/video/queue'),
  list: (folder = '', search = '') => api.get('/video/list', { params: { folder, search } }),
  videoFolders: () => api.get('/video/video_folders'),
  comfyuiStatus: () => api.get('/video/comfyui/status'),
  startComfyui: () => api.post('/video/comfyui/start'),
  stopComfyui: () => api.post('/video/comfyui/stop'),
  copyVideo: (data) => api.post('/video/copy', data),
  moveVideo: (data) => api.post('/video/move', data),
  deleteVideo: (path) => api.post('/video/delete', { path }),
  renameFile: (data) => api.post('/video/rename_file', data),
  renameFolder: (data) => api.post('/video/rename_folder', data),
  deleteFolder: (data) => api.post('/video/delete_folder', data),
  checkName: (params) => api.get('/video/check_name', { params })
}

// Training API
export const trainAPI = {
  start: (data) => api.post('/train/start', data),
  stop: () => api.post('/train/stop'),
  status: () => api.get('/train/status'),
  logs: (n = 100) => api.get('/train/logs', { params: { n } }),
  models: () => api.get('/train/models'),
  syntheticSamples: (dataset) => api.get('/train/synthetic_samples', { params: { dataset } }),
  deleteModel: (modelName) => api.post('/train/delete_model', { model_name: modelName }),
  renameModel: (data) => api.post('/train/rename_model', data)
}

// Inference API
export const inferAPI = {
  models: () => api.get('/infer/models'),
  extract: (data) => api.post('/infer/extract', data),
  predict: (data) => api.post('/infer/predict', data),
  predictBatch: (data) => api.post('/infer/predict_batch', data),
  compare: (data) => api.post('/infer/compare', data),
  videos: (dataset) => api.get('/infer/videos', { params: { dataset } })
}

// Monitor API (Real-time camera monitoring via browser getUserMedia)
export const monitorAPI = {
  preload: (data) => api.post('/monitor/preload', data),
  start: (data) => api.post('/monitor/start', data),
  stop: () => api.post('/monitor/stop'),
  analyzeFrame: (data) => api.post('/monitor/analyze_frame', data),
  status: () => api.get('/monitor/status')
}

// Analysis API
export const analysisAPI = {
  auc: (data) => api.post('/analysis/auc', data),
  compare: (data) => api.post('/analysis/compare', data),
  frameScores: (data) => api.post('/analysis/frame_scores', data),
  heatmap: (data) => api.post('/analysis/heatmap', data),
  groundTruth: (dataset, videoName) => api.get('/analysis/ground_truth', { 
    params: { dataset, video_name: videoName } 
  }),
  inferScore: (dataset, modelId, videoName) => api.get('/analysis/infer_score', {
    params: { dataset, model_id: modelId, video_name: videoName }
  }),
  summary: (dataset) => api.get('/analysis/summary', { params: { dataset } }),
  trainingCurve: (modelId) => api.get(`/analysis/training_curve/${modelId}`),
  comparison: (dataset) => api.get('/analysis/comparison', { params: { dataset } })
}

// Data Processing API
export const dataAPI = {
  featureDirs: () => api.get('/data/feature_dirs'),
  listFeatures: (params = {}) => {
    // Support both legacy (dataset string) and new (params object)
    if (typeof params === 'string') {
      return api.get('/data/features', { params: { dataset: params } })
    }
    return api.get('/data/features', { params })
  },
  featureInfo: (videoName, dataset) => api.get('/data/feature_info', { 
    params: { video_name: videoName, dataset } 
  }),
  deleteFeature: (videoName, datasetOrDirectory) => api.post('/data/delete_feature', { 
    video_name: videoName,
    ...(datasetOrDirectory && datasetOrDirectory.includes('/') ? { directory: datasetOrDirectory } : { dataset: datasetOrDirectory || 'shanghaitech' })
  }),
  copyFeatures: (data) => api.post('/data/copy_features', data),
  moveFeatures: (data) => api.post('/data/move_features', data)
}

// Auth API
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  changePassword: (data) => api.post('/auth/change-password', data),
  users: () => api.get('/auth/users')
}

// File Management API (Database-backed)
export const filesAPI = {
  paths: () => api.get('/files/paths'),
  list: (params = {}) => api.get('/files/list', { params }),
  add: (data) => api.post('/files/add', data),
  addBatch: (data) => api.post('/files/add_batch', data),
  update: (fileId, data) => api.put(`/files/update/${fileId}`, data),
  delete: (fileId) => api.delete(`/files/delete/${fileId}`),
  restore: (fileId) => api.post(`/files/restore/${fileId}`),
  copyToCategory: (data) => api.post('/files/copy_to_category', data),
  moveToCategory: (data) => api.post('/files/move_to_category', data),
  categories: () => api.get('/files/categories'),
  scan: (data) => api.post('/files/scan', data),
  logs: () => api.get('/files/logs'),
  // File browser
  browse: (path, showHidden = false) => api.get('/files/browse', { params: { path, show_hidden: showHidden } }),
  // Download
  downloadUrl: (filePath) => `/api/files/download?path=${encodeURIComponent(filePath)}`,
  // Collections
  collections: () => api.get('/files/collections'),
  createCollection: (data) => api.post('/files/collections', data),
  addToCollection: (collectionId, data) => api.post(`/files/collections/${collectionId}/files`, data),
  getCollectionFiles: (collectionId) => api.get(`/files/collections/${collectionId}/files`)
}

// Trash / Recycle Bin API
export const trashAPI = {
  list: () => api.get('/trash/list'),
  restore: (id) => api.post('/trash/restore', { id }),
  restoreBatch: (ids) => api.post('/trash/restore_batch', { ids }),
  delete: (id) => api.post('/trash/delete', { id }),
  deleteBatch: (ids) => api.post('/trash/delete_batch', { ids }),
  empty: () => api.post('/trash/empty'),
}

export default api
