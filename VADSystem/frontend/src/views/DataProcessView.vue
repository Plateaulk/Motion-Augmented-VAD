<template>
  <div class="data-process-view">
    <!-- Three Panel Layout -->
    <div class="three-panel-grid">
      <!-- Left: Generated Videos from ComfyUI -->
      <div class="panel left-panel">
        <div class="panel-header">
          <div class="header-title">
            <el-icon :size="18"><Film /></el-icon>
            <span>Videos</span>
          </div>
          <div class="header-actions">
            <el-select 
              v-model="selectedVideoFolder" 
              
              size="small"
              @change="onVideoFolderChange"
              class="folder-select"
            >
              <el-option 
                v-for="folder in videoFolders" 
                :key="folder.path" 
                :label="folder.count !== undefined ? `${folder.name} (${folder.count})` : folder.name"
                :value="folder.path" 
              />
            </el-select>
            <el-input 
              v-model="videoSearch" 
              placeholder="Search..." 
              size="small" 
              clearable
              class="search-input-header"
              @input="onVideoSearch"
              @clear="refreshVideos"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button size="small" @click="refreshVideos" :icon="Refresh">Refresh</el-button>
          </div>
        </div>
        <div class="panel-body video-list">
          <div 
            v-for="video in filteredVideos" 
            :key="video.id" 
            :class="['video-item', { selected: selectedVideo?.id === video.id }]" 
            @click="selectVideo(video)"
          >
            <div class="video-thumb">
              <img v-if="video.thumbUrl" :src="video.thumbUrl" :alt="video.name" loading="lazy" class="thumb-video" />
              <video v-else
                :src="video.url + '#t=0.1'" 
                preload="metadata"
                muted
                class="thumb-video"
              />
              <div class="play-icon">
                <el-icon><VideoPlay /></el-icon>
              </div>
            </div>
            <div class="video-info">
              <span class="video-name">{{ video.name }}</span>
            </div>
          </div>
          <div v-if="!filteredVideos.length" class="empty-state">
            <el-icon :size="32"><Film /></el-icon>
            <p>{{ videoSearch ? 'No matching videos' : 'No videos' }}</p>
          </div>
        </div>
      </div>

      <!-- Right Column -->
      <div class="right-column">
        <!-- Top Right: Video Preview (larger) -->
        <div class="panel preview-panel">
          <div class="panel-header">
            <div class="header-title">
              <el-icon :size="18"><VideoPlay /></el-icon>
              <span>Video Preview</span>
            </div>
          </div>
          <div class="panel-body preview-area">
            <template v-if="selectedVideo">
              <div class="video-player">
                <video :src="selectedVideo.url" controls />
              </div>
              <div class="video-details">
                <div class="detail-row">
                  <span class="label">Filename:</span>
                  <span class="value">{{ selectedVideo.name }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Motion ID:</span>
                  <span class="value">{{ selectedVideo.motion_id }}</span>
                </div>
                <div class="detail-row" v-if="selectedVideo.render_id">
                  <span class="label">Render:</span>
                  <span class="value">{{ selectedVideo.render_id }}</span>
                </div>
              </div>
            </template>
            <div v-else class="empty-state">
              <el-icon :size="48"><VideoPlay /></el-icon>
              <p>Select a video to preview</p>
            </div>
          </div>
        </div>

        <!-- Bottom Right: Feature Extraction with Tabs -->
        <div class="panel extract-panel">
          <div class="panel-header">
            <div class="header-title">
              <el-icon :size="18"><Cpu /></el-icon>
              <span>Feature Extract</span>
            </div>
            <el-select v-model="extractionDataset" :disabled="extracting" size="small" aria-label="Extraction dataset" class="extract-dataset">
              <el-option label="ShanghaiTech" value="shanghaitech" />
              <el-option label="UCF-Crime" value="ucf-crime" />
            </el-select>
          </div>
          <div class="panel-body extract-form compact">
            <template v-if="selectedVideo">
              <!-- VAD Feature Extraction -->
              <div class="extract-row">
                <div class="extract-info">
                  <span class="extract-label">Video:</span>
                  <span class="extract-value">{{ selectedVideo.name }}</span>
                </div>
                <div class="extract-inputs">
                  <el-input v-model="featureName" :disabled="extracting" size="small" placeholder="Generated sample ID (Gen...)" aria-label="Feature name" class="name-input" />
                  <el-select v-model="targetDataset" :disabled="extracting" size="small" placeholder="Save to" aria-label="Feature destination" class="target-select">
                    <el-option v-for="dir in extractionDirectories" :key="dir.name" :label="dir.folder" :value="dir.name" />
                  </el-select>
                  <button 
                    class="action-btn primary" 
                    :disabled="extracting || !featureName.trim() || !targetDataset"
                    @click="extractFeature"
                  >
                    <el-icon v-if="extracting" class="spin"><Loading /></el-icon>
                    <el-icon v-else><Cpu /></el-icon>
                    <span>Extract</span>
                  </button>
                </div>
              </div>
              
              <p class="protocol-note">CLIP ViT-B/16 · 10 crops per complete 16-frame segment · {{ extractionDataset === 'shanghaitech' ? 'float32' : 'float16' }}<span v-if="extractionDataset === 'ucf-crime'"><br />For normal synthetic videos, include _normal_ in the sample ID.</span></p>
              <div v-if="extractResult" class="result-msg success">
                <el-icon><CircleCheckFilled /></el-icon>
                <span>Saved {{ extractResult.num_crops }} crops × {{ extractResult.feature_frames }} sampled frames ({{ extractResult.protocol.dtype }})</span>
              </div>
            </template>
            <div v-else class="empty-hint">
              <el-icon><Cpu /></el-icon>
              <span>Select video to extract features</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Preview Dialog -->
    <el-dialog v-model="previewVisible" :title="currentVideo?.name" width="720px" destroy-on-close>
      <div class="preview-video">
        <video v-if="currentVideo" :src="currentVideo.url" controls autoplay />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Cpu, Refresh } from '@element-plus/icons-vue'
import { videoAPI, inferAPI, dataAPI } from '../api'

const dataset = inject('dataset')
const requireLogin = inject('requireLogin')

const videos = ref([])
const videoFolders = ref([])
const selectedVideoFolder = ref('')
const videoSearch = ref('')
const features = ref([])
const featureDirectories = ref([])
const selectedFeatureDir = ref('')
const selectedVideo = ref(null)
const selectedFeatures = ref([])
const featureName = ref('')
const targetDataset = ref('')
const extractionDataset = ref(dataset.value)
const extractionDirectories = computed(() => {
  const folder = extractionDataset.value === 'shanghaitech' ? 'SH_clip_video_features' : 'UCFClipFeatures'
  const prefix = `${extractionDataset.value}/${folder}`
  return featureDirectories.value.filter(dir => dir.name === prefix || dir.name.startsWith(`${prefix}/`))
})
const selectExtractionDirectory = () => {
  targetDataset.value = extractionDirectories.value.find(dir => dir.is_system)?.name || ''
  extractResult.value = null
}
watch(extractionDataset, selectExtractionDirectory)
watch(dataset, value => { if (!extracting.value) extractionDataset.value = value })
const featureSearch = ref('')
const extracting = ref(false)
const extractResult = ref(null)
const previewVisible = ref(false)
const currentVideo = ref(null)
const copyTarget = ref('')
const moveTarget = ref('')

const syntheticCount = computed(() => features.value.filter(f => f.is_synthetic).length)

const filteredVideos = computed(() => {
  // Search handled by backend
  return videos.value
})

const filteredFeatures = computed(() => {
  if (!featureSearch.value) return features.value
  const search = featureSearch.value.toLowerCase()
  return features.value.filter(f => f.name.toLowerCase().includes(search))
})

// Load video folders
const loadVideoFolders = async () => {
  try {
    const response = await videoAPI.videoFolders()
    videoFolders.value = response.data.folders || []
    // Default to "system" folder
    if (!selectedVideoFolder.value && videoFolders.value.length > 0) {
      const systemFolder = videoFolders.value.find(f => f.name.toLowerCase().includes('system'))
      selectedVideoFolder.value = (systemFolder || videoFolders.value[0]).path
    }
  } catch (error) {
    console.error('Failed to load video folders:', error)
  }
}

// Folder changed
const onVideoFolderChange = () => {
  selectedVideo.value = null
  refreshVideos()
}

// Debounced search
let videoSearchTimeout = null
const onVideoSearch = () => {
  if (videoSearchTimeout) clearTimeout(videoSearchTimeout)
  videoSearchTimeout = setTimeout(() => {
    refreshVideos()
  }, 300)
}

const loadFeatureDirectories = async () => {
  try {
    const response = await dataAPI.featureDirs()
    featureDirectories.value = response.data.directories || []
    selectExtractionDirectory()
    if (!selectedFeatureDir.value && featureDirectories.value.length > 0) {
      selectedFeatureDir.value = featureDirectories.value[0].name
    }
  } catch (error) {
    console.error('Failed to load feature directories:', error)
  }
}

const onFeatureDirChange = () => {
  selectedFeatures.value = []
  refreshFeatures()
}

const refreshVideos = async () => {
  try {
    const response = await videoAPI.list(selectedVideoFolder.value, videoSearch.value)
    const videoList = (response.data.videos || []).map(v => {
      // Build URL, encode folder and filename
      const urlPath = v.folder 
        ? `${encodeURIComponent(v.folder)}/${encodeURIComponent(v.name)}`
        : encodeURIComponent(v.name)
      return {
        id: v.path,  // Use full path as ID
        name: v.name,
        folder: v.folder,
        url: `/api/video/file/${urlPath}`,
        thumbUrl: v.thumb_url,
        video_path: v.path,
        created: v.created
      }
    })
    
    // Already sorted by backend
    videos.value = videoList
  } catch (error) {
    console.error('Failed to load videos:', error)
  }
}

const refreshFeatures = async () => {
  try {
    let response
    if (selectedFeatureDir.value) {
      response = await dataAPI.listFeatures({ directory: selectedFeatureDir.value })
    } else {
      response = await dataAPI.listFeatures({ dataset: extractionDataset.value })
    }
    features.value = response.data.features || []
  } catch (error) {
    console.error('Failed to load features:', error)
    features.value = []
  }
}

const selectVideo = (video) => {
  if (extracting.value) return
  selectedVideo.value = video
  // Generate feature name from filename
  const baseName = video.name.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '_')
  featureName.value = (baseName.startsWith('Gen') ? baseName : `Gen${baseName}`).substring(0, 128)
  extractResult.value = null
}

const toggleFeatureSelect = (feature) => {
  const idx = selectedFeatures.value.indexOf(feature.name)
  if (idx >= 0) {
    selectedFeatures.value.splice(idx, 1)
  } else {
    selectedFeatures.value.push(feature.name)
  }
}

const selectAllFeatures = () => {
  selectedFeatures.value = filteredFeatures.value.map(f => f.name)
}

const clearSelection = () => {
  selectedFeatures.value = []
}

const unselectFeature = (name) => {
  const idx = selectedFeatures.value.indexOf(name)
  if (idx >= 0) {
    selectedFeatures.value.splice(idx, 1)
  }
}

const extractFeature = async () => {
  if (extracting.value) return
  if (!requireLogin()) return
  if (!selectedVideo.value || !featureName.value.trim()) {
    ElMessage.warning('Select video and enter feature name')
    return
  }
  
  if (!/^Gen[A-Za-z0-9_-]*$/.test(featureName.value.trim()) || !targetDataset.value) {
    ElMessage.warning('Use a generated sample ID starting with Gen and select a destination')
    return
  }

  extracting.value = true
  // Check name duplicates
  try {
    const checkRes = await videoAPI.checkName({
      name: featureName.value.trim(),
      context: 'feature',
      directory: targetDataset.value || ''
    })
    if (checkRes.data.exists) {
      ElMessage.error(`Feature name "${featureName.value}" already exists`)
      extracting.value = false
      return
    }
  } catch (e) {
    ElMessage.error('Name check failed; extraction was not started')
    extracting.value = false
    return
  }
  
  extractResult.value = null
  
  try {
    const response = await inferAPI.extract({
      video_path: selectedVideo.value.video_path,
      video_name: featureName.value.trim(),
      target_dir: targetDataset.value,
      dataset: extractionDataset.value
    })
    
    if (response.data.error) {
      throw new Error(response.data.error)
    }
    
    extractResult.value = response.data
    ElMessage.success('Feature extraction complete')
    // Switch to target dir to see new features
    if (targetDataset.value && targetDataset.value !== selectedFeatureDir.value) {
      selectedFeatureDir.value = targetDataset.value
    }
    refreshFeatures()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || error.message || 'Feature extraction failed')
  } finally {
    extracting.value = false
  }
}

const copyFeatures = async () => {
  if (!selectedFeatures.value.length || !copyTarget.value) return
  
  try {
    const response = await dataAPI.copyFeatures({
      features: selectedFeatures.value,
      source_dir: selectedFeatureDir.value,
      target_dir: copyTarget.value
    })
    
    if (response.data.error) throw new Error(response.data.error)
    
    ElMessage.success(`Copied ${selectedFeatures.value.length} file(s)`)
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveFeatures = async () => {
  if (!selectedFeatures.value.length || !moveTarget.value) return
  
  try {
    await ElMessageBox.confirm(`Move ${selectedFeatures.value.length} file(s) to ${moveTarget.value}?`, 'Confirm Move')
    
    const response = await dataAPI.moveFeatures({
      features: selectedFeatures.value,
      source_dir: selectedFeatureDir.value,
      target_dir: moveTarget.value
    })
    
    if (response.data.error) throw new Error(response.data.error)
    
    ElMessage.success(`Moved ${selectedFeatures.value.length} file(s)`)
    selectedFeatures.value = []
    refreshFeatures()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

const deleteFeatures = async () => {
  if (!selectedFeatures.value.length) return
  
  try {
    await ElMessageBox.confirm(`Delete ${selectedFeatures.value.length} feature file(s)?`, 'Confirm Delete', { type: 'warning' })
    
    for (const name of selectedFeatures.value) {
      await dataAPI.deleteFeature(name, selectedFeatureDir.value)
    }
    
    ElMessage.success(`Deleted ${selectedFeatures.value.length} file(s)`)
    selectedFeatures.value = []
    refreshFeatures()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Delete failed')
    }
  }
}

const previewVideo = (video) => {
  currentVideo.value = video
  previewVisible.value = true
}

onMounted(async () => {
  await loadFeatureDirectories()
  await loadVideoFolders()
  refreshVideos()
  refreshFeatures()
})
</script>

<style scoped>
.data-process-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  --bg-card: rgba(30, 41, 59, 0.8);
  --bg-darker: rgba(15, 23, 42, 0.6);
  --border: rgba(71, 85, 105, 0.5);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --primary: #6366f1;
  --success: #10b981;
  --danger: #ef4444;
}

/* Three Panel Layout */
.three-panel-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 12px;
  height: 100%;
}

.left-panel {
  min-height: 0;
}

.right-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.preview-panel {
  flex: 3;
  min-height: 0;
}

.extract-panel {
  flex: 0 0 auto;
  min-height: 120px;
}

/* Panel Styles */
.panel {
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: 13px;
  color: var(--text-primary);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.feature-tabs {
  display: flex;
  gap: 4px;
}

.feature-tab {
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  background: rgba(51, 65, 85, 0.5);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.feature-tab:hover {
  background: rgba(51, 65, 85, 0.8);
}

.feature-tab.active {
  background: #6366f1;
  color: white;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.folder-select {
  width: 130px;
}

.folder-select :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
  height: 28px;
}

.folder-select :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 11px;
}

.search-input-header {
  width: 140px;
}

.header-select {
  margin-left: auto;
  width: 160px;
}

.header-select :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
  height: 28px;
}

.header-select :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 11px;
}

.selection-badge {
  margin-left: 8px;
  font-size: 11px;
  color: white;
  background: var(--primary);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: normal;
}

.panel-body {
  flex: 1;
  overflow: hidden;
  padding: 10px;
}

/* Video List (Top Left) */
.video-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  overflow-y: auto;
  align-content: start;
}

.video-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.video-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.video-item.selected {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.15);
}

.video-thumb {
  position: relative;
  aspect-ratio: 16/9;
  border-radius: 6px;
  overflow: hidden;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
}

.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
}

.video-thumb .thumb-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-thumb .play-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 28px;
  height: 28px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-item:hover .play-icon {
  opacity: 1;
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.video-name {
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-type {
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 3px;
  width: fit-content;
}

.video-type.composite {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.video-type.mask {
  background: rgba(168, 85, 247, 0.2);
  color: #a855f7;
}

/* Preview Area */
.preview-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.video-player {
  flex: 1;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-player video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--bg-darker);
  border-radius: 6px;
}

.detail-row {
  display: flex;
  gap: 8px;
  font-size: 11px;
}

.detail-row .label {
  color: var(--text-muted);
  width: 70px;
  flex-shrink: 0;
}

.detail-row .value {
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Extract Form */
.extract-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.extract-form.compact {
  justify-content: center;
  gap: 8px;
}

.extract-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.extract-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.extract-label {
  color: var(--text-secondary);
}

.extract-value {
  color: var(--primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.protocol-note {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
  margin: 8px 0;
}

.extract-dataset {
  width: 140px;
}

.extract-inputs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.extract-inputs .name-input {
  flex: 1;
  min-width: 120px;
}

.extract-inputs .target-select {
  width: 140px;
}

.extract-inputs .target-select :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
}

.extract-inputs .target-select :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 12px;
}

.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
  height: 100%;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-row label {
  font-size: 12px;
  color: var(--text-secondary);
  width: 70px;
  flex-shrink: 0;
}

.form-row .value {
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.form-row .value.highlight {
  color: var(--primary);
  font-weight: 500;
}

.form-row .flex-1 {
  flex: 1;
}

.form-row :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
}

.form-row :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 12px;
}

/* Action Buttons */
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(51, 65, 85, 0.5);
  color: var(--text-primary);
}

.action-btn.full-width {
  width: 100%;
}

.action-btn.small {
  padding: 6px 10px;
  font-size: 11px;
}

.action-btn:hover:not(:disabled) {
  background: rgba(51, 65, 85, 0.8);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.primary {
  background: var(--primary);
  color: white;
}

.action-btn.primary:hover:not(:disabled) {
  background: #4f46e5;
}

.action-btn.danger {
  background: rgba(239, 68, 68, 0.2);
  color: var(--danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.action-btn.danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
}

.result-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 8px;
  border-radius: 6px;
}

.result-msg.success {
  background: rgba(16, 185, 129, 0.15);
  color: var(--success);
}

/* Feature Panel (Bottom Right) */
.feature-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.feature-toolbar .search-input {
  flex: 1;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: rgba(51, 65, 85, 0.5);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.icon-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  color: var(--primary);
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.feature-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.feature-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.feature-item.selected {
  background: rgba(99, 102, 241, 0.2);
}

.feature-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.feature-name {
  flex: 1;
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feature-count {
  font-size: 10px;
  color: var(--text-muted);
  background: rgba(100, 116, 139, 0.3);
  padding: 2px 6px;
  border-radius: 4px;
}

.feature-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.action-row {
  display: flex;
  gap: 6px;
}

.action-select {
  flex: 1;
}

.action-select :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
  height: 28px;
}

.action-select :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 11px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 80px;
  color: var(--text-muted);
  gap: 8px;
}

.empty-state p {
  margin: 0;
  font-size: 12px;
}

.empty-state.small {
  min-height: 60px;
}

.empty-state.small p {
  font-size: 11px;
}

/* Search Input */
.search-input :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
}

.search-input :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 11px;
}

/* Preview Dialog */
.preview-video {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.preview-video video {
  width: 100%;
  max-height: 400px;
}

/* Spin Animation */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Element Plus Overrides */
:deep(.el-checkbox__inner) {
  background: transparent;
  border-color: var(--border);
}

:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background: var(--primary);
  border-color: var(--primary);
}

:deep(.el-dialog) {
  background: var(--bg-card);
  border: 1px solid var(--border);
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border);
}

:deep(.el-dialog__title) {
  color: var(--text-primary);
}
</style>
