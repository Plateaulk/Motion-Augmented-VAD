<template>
  <div class="video-gen-view">
    <!-- Main Panel with Status Bar -->
    <div class="main-panel">
      <!-- Header with title and status -->
      <div class="panel-header">
        <div class="header-left">
          <div class="panel-icon">
            <el-icon :size="20"><VideoCamera /></el-icon>
          </div>
          <span class="panel-title">Video Gen</span>
        </div>
        <div class="header-right">
          <div class="status-indicator" :class="{ active: comfyuiRunning }">
            <span class="status-dot"></span>
            <span>ComfyUI {{ comfyuiRunning ? 'Running' : 'Stopped' }}</span>
          </div>
          <button
            class="status-btn"
            :class="comfyuiRunning ? 'danger' : 'primary'"
            @click="toggleComfyui"
            :disabled="comfyuiLoading"
          >
            <el-icon v-if="comfyuiLoading" class="spin"><Loading /></el-icon>
            <span>{{ comfyuiRunning ? 'Stop' : 'Start' }}</span>
          </button>
        </div>
      </div>
      
      <!-- Panel Body -->
      <div class="panel-body">
          <div class="gen-layout">
            <!-- Left: Form -->
            <div class="gen-form-section">
              <div class="gen-tabs">
                <button
                  v-for="tab in tabs"
                  :key="tab.key"
                  :class="['tab-btn', { active: activeTab === tab.key }]"
                  @click="activeTab = tab.key"
                >
                  {{ tab.label }}
                </button>
              </div>
              
              <!-- T2V Form -->
              <div v-if="activeTab === 't2v'" class="form-content">
                <div class="form-section">
                  <label class="form-label">Output <span class="required">*</span></label>
                  <div class="output-row">
                    <el-select v-model="t2vForm.outputFolder" size="small" class="output-folder-select">
                      <el-option v-for="folder in videoOutputFolders" :key="folder.path" :label="folder.name" :value="folder.path" />
                    </el-select>
                    <el-input v-model="t2vForm.outputName" placeholder="Filename (required)" size="small" class="output-name-input" />
                  </div>
                </div>
                <div class="form-section">
                  <label class="form-label">Prompt</label>
                  <el-input v-model="t2vForm.prompt" type="textarea" :rows="3" placeholder="Describe video content..." resize="none" />
                </div>
                <div class="form-section">
                  <label class="form-label">Neg. Prompt</label>
                  <el-input v-model="t2vForm.negativePrompt" type="textarea" :rows="2" placeholder="Unwanted content..." resize="none" />
                </div>
                <div class="form-section">
                  <label class="form-label">Duration (s)</label>
                  <el-input-number v-model="t2vForm.duration" :min="1" :max="10" :step="1" style="width: 100%" />
                </div>
                <div class="form-section resolution-section">
                  <label class="form-label">Resolution</label>
                  <div class="resolution-inputs">
                    <el-input-number v-model="t2vForm.videoWidth" :min="resolutionLimits.minWidth" :max="resolutionLimits.maxWidth" :step="16" size="small" controls-position="right" />
                    <span class="resolution-x">×</span>
                    <el-input-number v-model="t2vForm.videoHeight" :min="resolutionLimits.minHeight" :max="resolutionLimits.maxHeight" :step="16" size="small" controls-position="right" />
                  </div>
                  <div class="resolution-presets">
                    <button class="preset-btn" type="button" @click="setT2VResolution(512, 512)">512×512</button>
                    <button class="preset-btn" type="button" @click="setT2VResolution(768, 432)">768×432</button>
                    <button class="preset-btn" type="button" @click="setT2VResolution(864, 480)">864×480</button>
                  </div>
                </div>
              </div>
              
              <!-- I2V Form -->
              <div v-if="activeTab === 'i2v'" class="form-content">
                <div class="form-section">
                  <label class="form-label">Output <span class="required">*</span></label>
                  <div class="output-row">
                    <el-select v-model="i2vForm.outputFolder" size="small" class="output-folder-select">
                      <el-option v-for="folder in videoOutputFolders" :key="folder.path" :label="folder.name" :value="folder.path" />
                    </el-select>
                    <el-input v-model="i2vForm.outputName" placeholder="Filename (required)" size="small" class="output-name-input" />
                  </div>
                </div>
                <div class="form-section">
                  <label class="form-label">Background</label>
                  <div class="bg-toolbar">
                    <el-select v-model="selectedBgFolder" size="small" @change="onBgFolderChange" class="bg-folder-select">
                      <el-option v-for="folder in bgFolders" :key="folder.path" :label="folder.name + (folder.count !== undefined ? ` (${folder.count})` : '')" :value="folder.path" />
                    </el-select>
                    <el-input v-model="bgSearchText" placeholder="Search..." size="small" clearable @input="onBgSearch" @clear="loadBackgrounds" class="bg-search-input">
                      <template #prefix><el-icon><Search /></el-icon></template>
                    </el-input>
                  </div>
                  <div class="bg-grid">
                    <div v-for="bg in backgrounds" :key="bg.path" :class="['bg-card', { selected: i2vForm.background === bg.relative_path }]" @click="i2vForm.background = bg.relative_path" @mouseenter="hoverBackground = bg" @mouseleave="hoverBackground = null">
                      <img :src="bg.thumb_url || bg.url" :alt="bg.name" loading="lazy" decoding="async" />
                      <div class="bg-check" v-if="i2vForm.background === bg.relative_path"><el-icon><Check /></el-icon></div>
                    </div>
                  </div>
                  <div v-if="backgrounds.length === 0" class="bg-empty">
                    <span>{{ bgSearchText ? 'No matching backgrounds' : 'No backgrounds' }}</span>
                  </div>
                </div>
                <div class="form-section">
                  <label class="form-label">Prompt</label>
                  <el-input v-model="i2vForm.prompt" type="textarea" :rows="2" placeholder="Describe action..." resize="none" />
                </div>
                <div class="form-section">
                  <label class="form-label">Neg. Prompt</label>
                  <el-input v-model="i2vForm.negativePrompt" type="textarea" :rows="2" placeholder="Unwanted content..." resize="none" />
                </div>
                <div class="form-section">
                  <label class="form-label">Duration (s)</label>
                  <el-input-number v-model="i2vForm.duration" :min="1" :max="10" :step="1" size="small" />
                </div>
                <div class="form-section resolution-section">
                  <label class="form-label">Resolution <span v-if="i2vForm.background && i2vBgResolutionHint" class="resolution-auto-hint">📐 Synced w/ BG ({{ i2vBgResolutionHint }})</span></label>
                  <div class="resolution-inputs">
                    <el-input-number v-model="i2vForm.videoWidth" :min="resolutionLimits.minWidth" :max="resolutionLimits.maxWidth" :step="16" size="small" controls-position="right" />
                    <span class="resolution-x">×</span>
                    <el-input-number v-model="i2vForm.videoHeight" :min="resolutionLimits.minHeight" :max="resolutionLimits.maxHeight" :step="16" size="small" controls-position="right" />
                  </div>
                  <div class="resolution-presets">
                    <button class="preset-btn" type="button" @click="setI2VResolution(512, 512)">512×512</button>
                    <button class="preset-btn" type="button" @click="setI2VResolution(768, 432)">768×432</button>
                    <button class="preset-btn" type="button" @click="setI2VResolution(848, 480)">848×480</button>
                    <button class="preset-btn" type="button" @click="setI2VResolution(1280, 720)">1280×720</button>
                  </div>
                </div>
              </div>
              
              <!-- V2V Form -->
              <div v-if="activeTab === 'v2v'" class="form-content">
                <div class="form-section">
                  <label class="form-label">Output <span class="required">*</span></label>
                  <div class="output-row">
                    <el-select v-model="v2vForm.outputFolder" size="small" class="output-folder-select">
                      <el-option v-for="folder in videoOutputFolders" :key="folder.path" :label="folder.name" :value="folder.path" />
                    </el-select>
                    <el-input v-model="v2vForm.outputName" placeholder="Filename (required)" size="small" class="output-name-input" />
                  </div>
                </div>
                <div class="form-section">
                  <label class="form-label">Background (optional)</label>
                  <div class="bg-toolbar">
                    <el-select v-model="selectedBgFolder" size="small" @change="onBgFolderChange" class="bg-folder-select">
                      <el-option v-for="folder in bgFolders" :key="folder.path" :label="folder.name" :value="folder.path" />
                    </el-select>
                    <el-input v-model="bgSearchText" placeholder="Search backgrounds..." size="small" clearable @input="onBgSearch" @clear="loadBackgrounds" class="bg-search-input">
                      <template #prefix><el-icon><Search /></el-icon></template>
                    </el-input>
                  </div>
                  <div class="bg-grid">
                    <div v-for="bg in backgrounds" :key="bg.path" :class="['bg-card', { selected: v2vForm.background === bg.relative_path }]" @click="v2vForm.background = v2vForm.background === bg.relative_path ? '' : bg.relative_path" @mouseenter="hoverBackground = bg" @mouseleave="hoverBackground = null">
                      <img :src="bg.thumb_url || bg.url" :alt="bg.name" loading="lazy" decoding="async" />
                      <div class="bg-check" v-if="v2vForm.background === bg.relative_path"><el-icon><Check /></el-icon></div>
                    </div>
                  </div>
                  <div v-if="backgrounds.length === 0" class="bg-empty">
                    <span>{{ bgSearchText ? 'No matching backgrounds' : 'No backgrounds' }}</span>
                  </div>
                </div>
                <div class="form-section motion-pair-form">
                  <div class="motion-pair-header">
                    <label class="form-label">Motion Pair <span class="pair-count">{{ filteredMaskVideos.length }}</span></label>
                    <el-select v-model="selectedMotionFolder" size="small" class="folder-mini-select" @change="onMotionFolderChange">
                      <el-option label="All" value="" />
                      <el-option v-for="folder in motionFolders" :key="folder.name" :label="folder.name" :value="folder.name" />
                    </el-select>
                  </div>
                  <el-input v-model="maskSearchText" placeholder="Search Motion Pair..." size="small" clearable class="mask-search-input">
                    <template #prefix><el-icon><Search /></el-icon></template>
                  </el-input>
                  <div class="motion-pair-grid">
                    <div 
                      v-for="pair in filteredMaskVideos" 
                      :key="pair.uniqueId"
                      :class="['motion-pair-item', { selected: v2vForm.selectedPairId === pair.uniqueId }]"
                      @click="selectVideoPair(pair)"
                    >
                      <div class="pair-thumbs">
                        <div class="mini-thumb" @click.stop="previewVideo(pair.id, 'composite', pair.renderLabel + ' - Reference', pair.renderId)">
                          <video :src="motionVideoUrl(pair.id, 'composite', pair.renderId)" muted preload="metadata" />
                        </div>
                        <div class="mini-thumb" @click.stop="previewVideo(pair.id, 'mask', pair.renderLabel + ' - Mask', pair.renderId)">
                          <video :src="motionVideoUrl(pair.id, 'mask', pair.renderId)" muted preload="metadata" />
                        </div>
                      </div>
                      <span class="pair-id">{{ pair.renderLabel }}</span>
                      <el-icon v-if="v2vForm.selectedPairId === pair.uniqueId" class="check-icon"><Check /></el-icon>
                    </div>
                  </div>
                  <div v-if="filteredMaskVideos.length === 0" class="motion-pair-empty">
                    <span>No Motion Pairs</span>
                  </div>
                </div>
                <div class="form-section">
                  <label class="form-label">Prompt</label>
                  <el-input v-model="v2vForm.prompt" type="textarea" :rows="2" placeholder="Describe anomaly..." resize="none" />
                </div>
                <div class="form-section">
                  <label class="form-label">Neg. Prompt</label>
                  <el-input v-model="v2vForm.negativePrompt" type="textarea" :rows="2" placeholder="Unwanted content..." resize="none" />
                </div>
                <div class="form-section">
                  <label class="form-label">Duration (s)</label>
                  <el-input-number v-model="v2vForm.duration" :min="1" :max="10" :step="1" size="small" />
                </div>
                <div class="form-section resolution-section">
                  <label class="form-label">Resolution <span v-if="v2vForm.background && v2vBgResolutionHint" class="resolution-auto-hint">📐 Synced w/ BG ({{ v2vBgResolutionHint }})</span></label>
                  <div class="resolution-inputs">
                    <el-input-number v-model="v2vForm.videoWidth" :min="resolutionLimits.minWidth" :max="resolutionLimits.maxWidth" :step="16" size="small" controls-position="right" />
                    <span class="resolution-x">×</span>
                    <el-input-number v-model="v2vForm.videoHeight" :min="resolutionLimits.minHeight" :max="resolutionLimits.maxHeight" :step="16" size="small" controls-position="right" />
                  </div>
                  <div class="resolution-presets">
                    <button class="preset-btn" type="button" @click="setV2VResolution(512, 512)">512×512</button>
                    <button class="preset-btn" type="button" @click="setV2VResolution(768, 432)">768×432</button>
                    <button class="preset-btn" type="button" @click="setV2VResolution(848, 480)">848×480</button>
                    <button class="preset-btn" type="button" @click="setV2VResolution(1280, 720)">1280×720</button>
                  </div>
                </div>
              </div>
              
              <!-- Progress Bar -->
              <div v-if="generating" class="progress-section">
                <div class="progress-header">
                  <span>Progress</span>
                  <span class="progress-text">{{ progressText }}</span>
                </div>
                <el-progress :percentage="generateProgress" :stroke-width="8" :show-text="false" />
              </div>
              
              <button class="generate-btn" :disabled="!comfyuiRunning || generating" @click="generate">
                <el-icon v-if="generating" class="spin"><Loading /></el-icon>
                <el-icon v-else><VideoPlay /></el-icon>
                <span>{{ generating ? 'Generating...' : 'Start Generate' }}</span>
              </button>
            </div>
            
            <!-- Right: Preview Area (V2V only) -->
            <div v-if="activeTab === 'v2v'" class="preview-section">
              <div class="section-header">
                <span>Preview</span>
                <span v-if="generatedVideoUrl" class="preview-mode-tag generated">Generated</span>
                <span v-else-if="selectedVideoPair" class="preview-mode-tag pair">Pair</span>
              </div>
              
              <!-- Background Hover Preview (highest priority - temporary) -->
              <div v-if="hoverBackground" class="preview-content bg-hover">
                <img :src="hoverBackground.url" :alt="hoverBackground.name" />
                <div class="preview-name">{{ hoverBackground.name }}</div>
              </div>
              
              <!-- Generated Video Preview (after generation complete) -->
              <div v-else-if="generatedVideoUrl" class="preview-content generated-video-preview">
                <div class="preview-label">🎬 Result</div>
                <div class="generated-video-wrapper">
                  <video :src="generatedVideoUrl" controls autoplay loop class="generated-video" />
                </div>
                <div class="generated-video-actions">
                  <button class="preview-action-btn" @click="openGeneratedInDialog">
                    <el-icon><VideoPlay /></el-icon> Fullscreen
                  </button>
                  <button class="preview-action-btn secondary" @click="generatedVideoUrl = ''">
                    <el-icon><Close /></el-icon> Close
                  </button>
                </div>
              </div>
              
              <!-- Selected Video Pair Preview -->
              <div v-else-if="selectedVideoPair" class="preview-content video-preview">
                <div class="preview-label">Selected: {{ selectedVideoPair.renderLabel }}</div>
                <div class="video-preview-large">
                  <div class="preview-video-item" @click="previewVideo(selectedVideoPair.id, 'composite', selectedVideoPair.renderLabel + ' - Reference', selectedVideoPair.renderId)">
                    <video :src="motionVideoUrl(selectedVideoPair.id, 'composite', selectedVideoPair.renderId)" muted preload="metadata" />
                    <span class="video-label">Reference</span>
                  </div>
                  <div class="preview-video-item" @click="previewVideo(selectedVideoPair.id, 'mask', selectedVideoPair.renderLabel + ' - Mask', selectedVideoPair.renderId)">
                    <video :src="motionVideoUrl(selectedVideoPair.id, 'mask', selectedVideoPair.renderId)" muted preload="metadata" />
                    <span class="video-label">Mask</span>
                  </div>
                </div>
              </div>
              
              <!-- Empty State -->
              <div v-else class="empty-preview">
                <el-icon :size="40"><Picture /></el-icon>
                <p>Select a Motion Pair or hover BG to preview</p>
              </div>
            </div>
            
            <!-- Right: Background Preview (I2V) -->
            <div v-else-if="activeTab === 'i2v'" class="bg-preview-section">
              <div class="section-header">
                <span>{{ generatedVideoUrl ? 'Result' : 'BG Preview' }}</span>
              </div>
              
              <!-- Background Hover (temporary) -->
              <div v-if="hoverBackground" class="bg-preview-large">
                <img :src="hoverBackground.url" :alt="hoverBackground.name" />
                <div class="preview-info">
                  <span class="preview-name">{{ hoverBackground.name }}</span>
                </div>
              </div>
              
              <!-- Generated Video -->
              <div v-else-if="generatedVideoUrl" class="preview-content generated-video-preview">
                <div class="generated-video-wrapper">
                  <video :src="generatedVideoUrl" controls autoplay loop class="generated-video" />
                </div>
                <div class="generated-video-actions">
                  <button class="preview-action-btn" @click="openGeneratedInDialog">
                    <el-icon><VideoPlay /></el-icon> Fullscreen
                  </button>
                  <button class="preview-action-btn secondary" @click="generatedVideoUrl = ''">
                    <el-icon><Close /></el-icon> Close
                  </button>
                </div>
              </div>
              
              <!-- Empty -->
              <div v-else class="empty-preview">
                <el-icon :size="48"><Picture /></el-icon>
                <p>Hover BG to preview</p>
              </div>
            </div>
            
            <!-- Right: Preview Area (T2V - only when generated) -->
            <div v-else-if="activeTab === 't2v' && generatedVideoUrl" class="preview-section">
              <div class="section-header">
                <span>Result</span>
              </div>
              <div class="preview-content generated-video-preview">
                <div class="preview-label">🎬 Result</div>
                <div class="generated-video-wrapper">
                  <video :src="generatedVideoUrl" controls autoplay loop class="generated-video" />
                </div>
                <div class="generated-video-actions">
                  <button class="preview-action-btn" @click="openGeneratedInDialog">
                    <el-icon><VideoPlay /></el-icon> Fullscreen
                  </button>
                  <button class="preview-action-btn secondary" @click="generatedVideoUrl = ''">
                    <el-icon><Close /></el-icon> Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    
    <!-- Preview Dialog -->
    <el-dialog v-model="previewVisible" :title="previewTitle" width="800px" destroy-on-close>
      <div class="preview-video">
        <video v-if="currentVideoUrl" :src="currentVideoUrl" controls autoplay />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, onActivated, onDeactivated, inject, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Check, Close } from '@element-plus/icons-vue'
import { videoAPI, motionAPI } from '../api'

const route = useRoute()
const dataset = inject('dataset')
const requireLogin = inject('requireLogin')

const tabs = [
  { key: 't2v', label: 'T2V' },
  { key: 'i2v', label: 'I2V' },
  { key: 'v2v', label: 'V2V' }
]

const activeTab = ref('v2v')
const comfyuiRunning = ref(false)
const comfyuiLoading = ref(false)
const generating = ref(false)
const generateProgress = ref(0)
const progressText = ref('')

const defaultNegativePrompt = 'blurry, low quality, camera shake, camera movement, camera rotation, shaky, panning, zooming'

const t2vForm = reactive({
  prompt: '',
  negativePrompt: defaultNegativePrompt,
  duration: 3,
  videoWidth: 512,
  videoHeight: 512,
  outputName: '',
  outputFolder: 'system_generated'
})

const i2vForm = reactive({
  background: '',
  prompt: '',
  negativePrompt: defaultNegativePrompt,
  duration: 3,
  videoWidth: 848,
  videoHeight: 480,
  outputName: '',
  outputFolder: 'system_generated'
})

const v2vForm = reactive({
  background: '',
  maskId: '',
  renderId: '',
  selectedPairId: '',
  prompt: '',
  negativePrompt: defaultNegativePrompt,
  duration: 3,
  videoWidth: 848,
  videoHeight: 480,
  outputName: '',
  outputFolder: 'system_generated'
})

// Video output folders
const videoOutputFolders = ref([])
const loadVideoOutputFolders = async () => {
  try {
    const res = await videoAPI.videoFolders()
    videoOutputFolders.value = res.data.folders || []
    // Ensure system_generated in list
    if (!videoOutputFolders.value.find(f => f.path === 'system_generated')) {
      videoOutputFolders.value.unshift({ name: 'System Generated', path: 'system_generated' })
    }
  } catch {}
}

// Resolution limits
const resolutionLimits = {
  minWidth: 256,
  maxWidth: 1920,
  minHeight: 256,
  maxHeight: 1088  // Must be multiple of 16 for WAN model
}

// Set preset resolution
const setT2VResolution = (w, h) => { t2vForm.videoWidth = w; t2vForm.videoHeight = h }
const setI2VResolution = (w, h) => { i2vForm.videoWidth = w; i2vForm.videoHeight = h }
const setV2VResolution = (w, h) => { v2vForm.videoWidth = w; v2vForm.videoHeight = h }

const backgrounds = ref([])
const bgFolders = ref([])
const selectedBgFolder = ref('')
const bgSearchText = ref('')
const maskVideos = ref([])
const maskSearchText = ref('')
const selectedVideoPair = ref(null)
const previewVisible = ref(false)
const previewTitle = ref('')
const currentVideoUrl = ref('')
const hoverBackground = ref(null)
const generatedVideoUrl = ref('')
const motionFolders = ref([])
const selectedMotionFolder = ref('')

// Align to multiple of 16 (floor)
const alignTo16 = (val) => Math.max(256, Math.min(1920, Math.floor(val / 16) * 16))

// Auto-sync resolution on BG select
watch(() => i2vForm.background, (bgName) => {
  if (!bgName) return
  const bg = backgrounds.value.find(b => b.relative_path === bgName)
  if (bg && bg.width && bg.height) {
    i2vForm.videoWidth = alignTo16(bg.width)
    i2vForm.videoHeight = alignTo16(bg.height)
  }
})

watch(() => v2vForm.background, (bgName) => {
  if (!bgName) return
  const bg = backgrounds.value.find(b => b.relative_path === bgName)
  if (bg && bg.width && bg.height) {
    v2vForm.videoWidth = alignTo16(bg.width)
    v2vForm.videoHeight = alignTo16(bg.height)
  }
})

let statusInterval = null
let progressInterval = null

const checkComfyuiStatus = async () => {
  try {
    const res = await videoAPI.comfyuiStatus()
    comfyuiRunning.value = res.data.status === 'running'
  } catch {
    comfyuiRunning.value = false
  }
}

const toggleComfyui = async () => {
  if (!requireLogin()) return
  comfyuiLoading.value = true
  try {
    if (comfyuiRunning.value) {
      await videoAPI.stopComfyui()
    } else {
      await videoAPI.startComfyui()
    }
    await checkComfyuiStatus()
  } catch {
    ElMessage.error('Operation failed')
  } finally {
    comfyuiLoading.value = false
  }
}

// Show selected BG original resolution
const i2vBgResolutionHint = computed(() => {
  if (!i2vForm.background) return ''
  const bg = backgrounds.value.find(b => b.relative_path === i2vForm.background)
  if (bg && bg.width && bg.height) return `${bg.width}×${bg.height}`
  return ''
})
const v2vBgResolutionHint = computed(() => {
  if (!v2vForm.background) return ''
  const bg = backgrounds.value.find(b => b.relative_path === v2vForm.background)
  if (bg && bg.width && bg.height) return `${bg.width}×${bg.height}`
  return ''
})

// Mask video search filter
const filteredMaskVideos = computed(() => {
  if (!maskSearchText.value) return maskVideos.value
  const search = maskSearchText.value.toLowerCase()
  return maskVideos.value.filter(m => 
    m.text.toLowerCase().includes(search) || 
    m.id.toLowerCase().includes(search) ||
    m.renderLabel.toLowerCase().includes(search)
  )
})

const loadBgFolders = async () => {
  try {
    const ds = dataset.value === 'ucf-crime' ? 'ucf' : 'sht'
    const res = await videoAPI.backgroundFolders(ds)
    bgFolders.value = res.data.folders || []
  } catch {}
}

const loadBackgrounds = async () => {
  try {
    const ds = dataset.value === 'ucf-crime' ? 'ucf' : 'sht'
    const res = await videoAPI.backgrounds(ds, selectedBgFolder.value, bgSearchText.value)
    backgrounds.value = res.data.backgrounds || []
  } catch {}
}

const onBgFolderChange = () => {
  loadBackgrounds()
}

let bgSearchTimeout = null
const onBgSearch = () => {
  if (bgSearchTimeout) clearTimeout(bgSearchTimeout)
  bgSearchTimeout = setTimeout(() => {
    loadBackgrounds()
  }, 300)
}

const loadMotionFolders = async () => {
  try {
    const res = await motionAPI.directories()
    motionFolders.value = res.data.directories || []
    if (!selectedMotionFolder.value && motionFolders.value.length > 0) {
      const systemDir = motionFolders.value.find(d => d.name.includes('system'))
      selectedMotionFolder.value = (systemDir || motionFolders.value[0]).name
    }
  } catch {}
}

const loadMaskVideos = async () => {
  const directory = selectedMotionFolder.value
  try {
    const params = directory ? { directory } : {}
    const res = await motionAPI.list(params)
    if (directory !== selectedMotionFolder.value) return
    const motions = res.data.motions || []
    
    // Expand each motion's renders into entries
    const pairs = []
    motions.forEach(m => {
      if (m.renders && m.renders.length > 0) {
        m.renders.forEach(render => {
          if (render.has_mask && render.has_composite) {
            pairs.push({
              id: m.motion_id,
              renderId: render.render_id,
              text: m.text || m.motion_id,
              renderLabel: render.render_id,
              background: render.background,
              uniqueId: `${m.motion_id}_${render.render_id}`
            })
          }
        })
      } else if (m.mask_video) {
        // Legacy: no renders but has mask_video
        pairs.push({
          id: m.motion_id,
          renderId: null,
          text: m.text || m.motion_id,
          renderLabel: m.motion_id,
          uniqueId: m.motion_id
        })
      }
    })
    maskVideos.value = pairs
  } catch {}
}

const onMotionFolderChange = () => {
  selectedVideoPair.value = null
  maskVideos.value = []
  v2vForm.selectedPairId = ''
  v2vForm.maskId = ''
  v2vForm.renderId = ''
  loadMaskVideos()
}

const selectVideoPair = (pair) => {
  v2vForm.maskId = pair.id
  v2vForm.renderId = pair.renderId || ''
  v2vForm.selectedPairId = pair.uniqueId
  selectedVideoPair.value = pair
  // Switch to pair preview, clear generated video
  generatedVideoUrl.value = ''
}

const motionVideoUrl = (motionId, type, renderId) =>
  motionAPI.getVideoUrl(motionId, type, renderId, selectedMotionFolder.value)

const previewVideo = (motionId, type, title, renderId = null) => {
  previewTitle.value = title
  currentVideoUrl.value = motionVideoUrl(motionId, type, renderId)
  previewVisible.value = true
}

const openGeneratedInDialog = () => {
  if (generatedVideoUrl.value) {
    previewTitle.value = 'Result'
    currentVideoUrl.value = generatedVideoUrl.value
    previewVisible.value = true
  }
}

const generate = async () => {
  if (!requireLogin()) return
  const form = { t2v: t2vForm, i2v: i2vForm, v2v: v2vForm }[activeTab.value]
  if (!form.outputName.trim()) {
    ElMessage.warning('Enter output filename')
    return
  }
  if (!Number.isFinite(form.duration) || form.duration < 1 || form.duration > 10) {
    ElMessage.warning('Enter a duration between 1 and 10 seconds')
    return
  }
  
  // Check name duplicates
  try {
    const checkRes = await videoAPI.checkName({
      name: form.outputName.trim(),
      folder: form.outputFolder || 'system_generated',
      context: 'video'
    })
    if (checkRes.data.exists) {
      ElMessage.error(`Filename "${form.outputName}" already exists in target folder`)
      return
    }
  } catch (e) {
    console.error('Name check failed:', e)
  }
  
  generating.value = true
  generateProgress.value = 0
  progressText.value = 'Submitting...'
  generatedVideoUrl.value = ''  // Clear previous preview on new task
  
  try {
    let res
    if (activeTab.value === 't2v') {
      res = await videoAPI.t2v({
        prompt: t2vForm.prompt,
        negative_prompt: t2vForm.negativePrompt,
        duration_seconds: t2vForm.duration,
        width: t2vForm.videoWidth,
        height: t2vForm.videoHeight,
        output_name: t2vForm.outputName,
        output_folder: t2vForm.outputFolder
      })
      if (res.data.success) t2vForm.outputName = ''
    } else if (activeTab.value === 'i2v') {
      res = await videoAPI.i2v({
        prompt: i2vForm.prompt,
        negative_prompt: i2vForm.negativePrompt,
        background: i2vForm.background,
        dataset: dataset.value === 'ucf-crime' ? 'ucf' : 'sht',
        duration_seconds: i2vForm.duration,
        width: i2vForm.videoWidth,
        height: i2vForm.videoHeight,
        output_name: i2vForm.outputName,
        output_folder: i2vForm.outputFolder
      })
      if (res.data.success) i2vForm.outputName = ''
    } else {
      res = await videoAPI.v2v({
        prompt: v2vForm.prompt,
        negative_prompt: v2vForm.negativePrompt,
        background: v2vForm.background,
        motion_id: v2vForm.maskId,
        motion_directory: selectedMotionFolder.value,
        render_id: v2vForm.renderId || null,
        dataset: dataset.value === 'ucf-crime' ? 'ucf' : 'sht',
        duration_seconds: v2vForm.duration,
        width: v2vForm.videoWidth,
        height: v2vForm.videoHeight,
        output_name: v2vForm.outputName,
        output_folder: v2vForm.outputFolder
      })
      if (res.data.success) v2vForm.outputName = ''
    }
    
    if (res.data.success && res.data.prompt_id) {
      // Task submitted, start polling
      const promptId = res.data.prompt_id
      generateProgress.value = 1
      progressText.value = 'Submitted, waiting...'
      
      const pollProgress = async () => {
        try {
          const progressRes = await videoAPI.progress(promptId)
          const data = progressRes.data
          
          if (data.status === 'completed') {
            generateProgress.value = 100
            progressText.value = 'Done!'
            ElMessage.success('Video generated')
            clearInterval(progressInterval)
            if (data.video_url) {
              generatedVideoUrl.value = data.video_url
            }
            setTimeout(() => {
              generating.value = false
              generateProgress.value = 0
            }, 1500)
          } else if (data.status === 'running') {
            generateProgress.value = data.progress ?? generateProgress.value
            progressText.value = data.message || 'Generating...'
          } else if (data.status === 'pending') {
            generateProgress.value = 0
            progressText.value = data.message || 'Queued...'
          } else if (data.status === 'error') {
            ElMessage.error(data.message || 'Generation error')
            clearInterval(progressInterval)
            generating.value = false
            generateProgress.value = 0
          }
        } catch (e) {
          console.warn('Progress poll failed:', e)
        }
      }
      
      progressInterval = setInterval(pollProgress, 1000)
      pollProgress()
      
    } else if (res.data.success) {
      // Success but no prompt_id (unexpected)
      ElMessage.success('Task submitted')
      generating.value = false
    } else {
      ElMessage.error(res.data.error || 'Generation failed')
      generating.value = false
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Request failed')
    generating.value = false
    generateProgress.value = 0
  }
}

watch(dataset, () => {
  selectedBgFolder.value = ''
  loadBgFolders()
  loadBackgrounds()
  i2vForm.background = ''
  v2vForm.background = ''
  bgSearchText.value = ''
})

onMounted(async () => {
  if (typeof route.query.directory === 'string') selectedMotionFolder.value = route.query.directory
  // Load all data in parallel
  await Promise.all([
    checkComfyuiStatus(),
    loadBgFolders().then(() => loadBackgrounds()),
    loadMotionFolders().then(() => loadMaskVideos()),
    loadVideoOutputFolders()
  ])
  
  if (route.query.mask) {
    activeTab.value = 'v2v'
    const pair = maskVideos.value.find(entry => entry.id === route.query.mask &&
      (!route.query.render || entry.renderId === route.query.render))
    if (pair) selectVideoPair(pair)
    else ElMessage.warning('Selected motion render was not found')
  }
  
  startStatusInterval()
})

// Cleanup timers
const cleanupTimers = () => {
  if (statusInterval) {
    clearInterval(statusInterval)
    statusInterval = null
  }
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

// Start status check timer
const startStatusInterval = () => {
  if (!statusInterval) {
    statusInterval = setInterval(checkComfyuiStatus, 5000)
  }
}

// Restart timer on keep-alive activate
onActivated(() => {
  checkComfyuiStatus()
  startStatusInterval()
})

// Cleanup timers on keep-alive deactivate
onDeactivated(() => {
  cleanupTimers()
})

// Cleanup on unmount
onUnmounted(() => {
  cleanupTimers()
})
</script>

<style scoped>
.video-gen-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
}

/* Main Panel */
.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(71, 85, 105, 0.5);
  overflow: hidden;
}

/* Panel Header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.5);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #f1f5f9;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #94a3b8;
}

.status-indicator.active {
  color: #10b981;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
}

.status-indicator.active .status-dot {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.status-btn {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.status-btn.primary {
  background: #6366f1;
  color: white;
}

.status-btn.danger {
  background: #ef4444;
  color: white;
}

.status-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.panel-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.panel-body {
  flex: 1;
  padding: 16px;
  overflow: hidden;
}

/* Generation Layout */
.gen-layout {
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: 16px;
  height: 100%;
}

.gen-form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.preview-section {
  display: flex;
  flex-direction: column;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 10px;
  padding: 12px;
  overflow: hidden;
}

/* Motion Pair Form in V2V */
.motion-pair-form {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.motion-pair-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.motion-pair-header .pair-count {
  margin-left: 6px;
}

.folder-mini-select {
  width: 100px;
}

.motion-pair-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  overflow-y: auto;
  padding: 4px 2px;
  max-height: 120px;
}

.motion-pair-grid::-webkit-scrollbar {
  width: 4px;
}

.motion-pair-grid::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.5);
  border-radius: 2px;
}

.motion-pair-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 4px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.motion-pair-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.motion-pair-item.selected {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.15);
}

.pair-thumbs {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.mini-thumb {
  width: 24px;
  height: 14px;
  border-radius: 2px;
  overflow: hidden;
  background: #000;
  cursor: pointer;
}

.mini-thumb video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mini-thumb:hover {
  box-shadow: 0 0 0 1px #6366f1;
}

.pair-id {
  flex: 1;
  font-size: 9px;
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.check-icon {
  color: #6366f1;
  font-size: 10px;
  flex-shrink: 0;
}

.motion-pair-empty {
  padding: 12px;
  text-align: center;
  color: #64748b;
  font-size: 11px;
}

/* Preview Section */
.video-preview-large {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.preview-video-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.preview-video-item video {
  width: 280px;
  height: 158px;
  object-fit: cover;
  border-radius: 8px;
  background: #000;
  transition: box-shadow 0.2s, transform 0.2s;
}

.preview-video-item:hover video {
  box-shadow: 0 0 0 2px #6366f1;
  transform: scale(1.02);
}

.video-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.bg-preview-section {
  display: flex;
  flex-direction: column;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 10px;
  padding: 12px;
  overflow: hidden;
}

.folder-select-row {
  margin-bottom: 8px;
}

.folder-select-row .el-select {
  width: 100%;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #f1f5f9;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.3);
  flex-shrink: 0;
}

.pair-count {
  background: rgba(99, 102, 241, 0.2);
  color: #6366f1;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

/* Video Pair List */
.video-pair-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.video-pair-list::-webkit-scrollbar {
  width: 4px;
}

.video-pair-list::-webkit-scrollbar-track {
  background: rgba(51, 65, 85, 0.3);
  border-radius: 2px;
}

.video-pair-list::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.5);
  border-radius: 2px;
}

.video-pair-list::-webkit-scrollbar-thumb:hover {
  background: rgba(99, 102, 241, 0.7);
}

.video-pair-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  position: relative;
}

.video-pair-card:hover {
  background: rgba(51, 65, 85, 0.5);
}

.video-pair-card.selected {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
}

.pair-videos {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.pair-thumb {
  width: 56px;
  height: 32px;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
  background: #000;
  cursor: pointer;
}

.pair-thumb video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-label {
  position: absolute;
  top: 2px;
  left: 2px;
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 600;
}

.thumb-label.reference {
  background: rgba(34, 197, 94, 0.8);
  color: white;
}

.thumb-label.mask {
  background: rgba(168, 85, 247, 0.8);
  color: white;
}

.play-icon {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  opacity: 0;
  transition: opacity 0.2s;
}

.pair-thumb:hover .play-icon {
  opacity: 1;
}

.pair-info {
  flex: 1;
  min-width: 0;
}

.pair-name {
  font-size: 11px;
  color: #f1f5f9;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selected-check {
  width: 20px;
  height: 20px;
  background: #6366f1;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.empty-pair,
.empty-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  gap: 6px;
  padding: 12px;
}

.empty-pair p,
.empty-preview p {
  font-size: 11px;
  margin: 0;
}

/* Preview Mode Tags */
.preview-mode-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  margin-left: auto;
}

.preview-mode-tag.generated {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.preview-mode-tag.pair {
  background: rgba(99, 102, 241, 0.2);
  color: #6366f1;
}

/* Preview Content */
.preview-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

/* Generated Video Preview */
.generated-video-preview {
  justify-content: flex-start;
  padding-top: 8px;
}

.generated-video-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 0;
}

.generated-video {
  max-width: 100%;
  max-height: 100%;
  border-radius: 8px;
  background: #000;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.generated-video-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  flex-shrink: 0;
}

.preview-action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  background: #6366f1;
  color: white;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.preview-action-btn:hover {
  background: #4f46e5;
}

.preview-action-btn.secondary {
  background: rgba(51, 65, 85, 0.5);
  color: #94a3b8;
}

.preview-action-btn.secondary:hover {
  background: rgba(51, 65, 85, 0.8);
  color: #f1f5f9;
}

.preview-content.bg-hover img {
  max-width: 100%;
  max-height: 200px;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.preview-content .preview-label {
  font-size: 10px;
  color: #6366f1;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.preview-content .preview-name {
  font-size: 11px;
  color: #94a3b8;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-preview-thumbs {
  display: flex;
  gap: 8px;
}

.preview-thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.preview-thumb video {
  width: 100px;
  height: 56px;
  object-fit: cover;
  border-radius: 4px;
  background: #000;
}

.preview-thumb:hover video {
  box-shadow: 0 0 0 2px #6366f1;
}

.preview-thumb span {
  font-size: 9px;
  color: #94a3b8;
}

/* Background Preview */
.bg-preview-large {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.bg-preview-large img {
  max-width: 100%;
  max-height: 200px;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.bg-preview-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.bg-preview-overlay img {
  max-width: 100%;
  max-height: 80%;
  object-fit: contain;
  border-radius: 8px;
}

.preview-info {
  margin-top: 12px;
  color: #f1f5f9;
  font-size: 13px;
}

/* Tabs */
.gen-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  background: rgba(51, 65, 85, 0.5);
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: #6366f1;
  color: white;
}

/* Form */
.form-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

/* Resolution Settings */
.resolution-section {
  padding: 8px;
  background: rgba(30, 41, 59, 0.5);
  border-radius: 6px;
  border: 1px solid rgba(71, 85, 105, 0.3);
}

.resolution-auto-hint {
  font-size: 10px;
  color: #22d3ee;
  font-weight: 400;
  margin-left: 6px;
  opacity: 0.85;
}

.output-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.output-folder-select {
  width: 140px;
  flex-shrink: 0;
}

.output-name-input {
  flex: 1;
}

.resolution-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.resolution-inputs .el-input-number {
  width: 90px;
}

.resolution-x {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.resolution-presets {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.preset-btn {
  padding: 3px 8px;
  font-size: 10px;
  border: 1px solid rgba(71, 85, 105, 0.5);
  background: rgba(30, 41, 59, 0.8);
  color: #94a3b8;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.preset-btn:hover {
  background: #6366f1;
  border-color: #6366f1;
  color: white;
}

.form-label .required {
  color: #ef4444;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* Background Grid */
.bg-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.bg-folder-select {
  width: 140px;
  flex-shrink: 0;
}

.bg-search-input {
  flex: 1;
}

.mask-search-input {
  width: 100%;
  margin-bottom: 6px;
}

.bg-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
  max-height: 100px;
  overflow-y: auto;
  padding: 4px 2px;
}

.bg-card {
  position: relative;
  aspect-ratio: 16/9;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  min-width: 0;
}

.bg-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.bg-card:hover {
  border-color: rgba(99, 102, 241, 0.5);
}

.bg-card.selected {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}

.bg-check {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 16px;
  height: 16px;
  background: #6366f1;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 10px;
}

.bg-empty {
  padding: 12px;
  text-align: center;
  color: #64748b;
  font-size: 11px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 6px;
}

/* Progress */
.progress-section {
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  padding: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.progress-text {
  color: #6366f1;
  font-weight: 500;
}

/* Generate Button */
.generate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: auto;
}

.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}

.generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Preview Dialog */
.preview-video {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.preview-video video {
  width: 100%;
  max-height: 500px;
}

/* Animations */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Element Plus Overrides */
:deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid rgba(71, 85, 105, 0.5);
  box-shadow: none;
}

:deep(.el-input__inner) {
  color: #f1f5f9;
}

:deep(.el-textarea__inner) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid rgba(71, 85, 105, 0.5);
  color: #f1f5f9;
  box-shadow: none;
}

:deep(.el-select .el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
}

:deep(.el-input-number) {
  width: 100%;
}

:deep(.el-progress-bar__outer) {
  background: rgba(51, 65, 85, 0.5);
}

:deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
}

:deep(.el-dialog) {
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid rgba(71, 85, 105, 0.5);
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(71, 85, 105, 0.5);
}

:deep(.el-dialog__title) {
  color: #f1f5f9;
}
</style>
