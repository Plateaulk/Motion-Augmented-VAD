<template>
  <div class="motion-view">
    <!-- Top Row: Generation & List -->
    <div class="top-row">
      <!-- Motion Generation Panel -->
      <div class="panel generation-panel">
        <div class="panel-header">
          <div class="panel-icon">
            <el-icon :size="20"><Brush /></el-icon>
          </div>
          <span>Generate Motion</span>
        </div>
        
        <div class="panel-body">
          <div class="form-section">
            <label class="form-label">Description</label>
            <el-input
              v-model="motionForm.text"
              type="textarea"
              :rows="2"
              placeholder="e.g.: a person is fighting violently"
              resize="none"
            />
          </div>
          
          <div class="form-row">
            <div class="form-section flex-1">
              <label class="form-label">Filename <span class="required">*</span></label>
              <el-input
                v-model="motionForm.name"
                placeholder="Enter filename"
                size="small"
              />
            </div>
            <div class="form-section flex-1">
              <label class="form-label">Output Folder</label>
              <el-select
                v-model="motionForm.outputDir"
                size="small"
                style="width: 100%"
              >
                <el-option
                  v-for="dir in motionDirectories"
                  :key="dir.name"
                  :label="dir.name"
                  :value="dir.name"
                />
              </el-select>
            </div>
          </div>
          
          <button
            class="action-btn primary"
            :class="{ loading: generating }"
            :disabled="generating"
            @click="generateMotion"
          >
            <el-icon v-if="!generating"><VideoPlay /></el-icon>
            <el-icon v-else class="spin"><Loading /></el-icon>
            <span>{{ generating ? 'Generating...' : 'Generate' }}</span>
          </button>
          
          <!-- Generate Progress Bar -->
          <div v-if="generating" class="progress-section">
            <div class="progress-header">
              <span>{{ generateProgressText }}</span>
              <span class="progress-percent">{{ Math.round(generateProgress) }}%</span>
            </div>
            <el-progress :percentage="generateProgress" :stroke-width="6" :show-text="false" />
          </div>
        </div>
      </div>
      
      <!-- Motion List Panel -->
      <div class="panel motion-list-panel">
        <div class="panel-header">
          <div class="panel-icon blue">
            <el-icon :size="20"><List /></el-icon>
          </div>
          <span>Motion List</span>
          <el-select
            v-model="selectedDirectory"
            size="small"
            class="directory-select"
            placeholder="Select folder"
            @change="onDirectoryChange"
          >
            <el-option
              v-for="dir in motionDirectories"
              :key="dir.name"
              :label="`${dir.name} (${dir.motion_count})`"
              :value="dir.name"
            />
          </el-select>
          <span class="count-badge">{{ filteredMotions.length }}</span>
          <el-input
            v-model="motionSearchText"
            placeholder="Search..."
            size="small"
            clearable
            class="motion-search-input"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <div class="panel-body">
          <div v-if="filteredMotions.length > 0" class="motion-list">
            <div
              v-for="motion in filteredMotions"
              :key="motion.motion_id"
              :class="['motion-item', { selected: selectedMotion?.motion_id === motion.motion_id }]"
              @click="selectMotion(motion)"
            >
              <div class="motion-icon">
                <el-icon><Coordinate /></el-icon>
              </div>
              <div class="motion-meta">
                <p class="motion-title">{{ motion.text }}</p>
                <p class="motion-info">{{ formatTime(motion.created_at) }}</p>
              </div>
              <el-tag v-if="motion.render_count > 1" type="success" size="small">{{ motion.render_count }} renders</el-tag>
              <el-tag v-else-if="motion.composite_video" type="success" size="small">Rendered</el-tag>
              <el-tag v-else type="info" size="small">Pending</el-tag>
            </div>
          </div>
          <div v-else class="empty-state">
            <el-icon :size="36"><Coordinate /></el-icon>
            <p>No motions</p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Bottom Row: Render Settings & Progress -->
    <div class="bottom-row">
      <!-- Render Settings Panel -->
      <div class="panel render-settings-panel">
        <div class="panel-header">
          <div class="panel-icon green">
            <el-icon :size="20"><PictureFilled /></el-icon>
          </div>
          <span>Render Settings</span>
        </div>
        
        <div class="panel-body render-settings-body">
          <div v-if="selectedMotion" class="render-config">
            <div class="selected-motion-badge">
              <el-icon><Coordinate /></el-icon>
              <span>{{ selectedMotion.text }}</span>
            </div>
            
            <!-- Render Name & Output Dir -->
            <div class="form-row-2">
              <div class="form-section flex-1">
                <label class="form-label">Filename <span class="required">*</span></label>
                <el-input
                  v-model="renderParams.name"
                  placeholder="Enter filename"
                  size="small"
                />
              </div>
              <div class="form-section flex-1">
                <label class="form-label">Output Folder</label>
                <el-select
                  v-model="renderParams.outputDir"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    v-for="dir in motionDirectories"
                    :key="dir.name"
                    :label="dir.name"
                    :value="dir.name"
                  />
                </el-select>
              </div>
            </div>
            
            <!-- Render Parameters -->
            <div class="params-grid">
              <div class="param-item">
                <label>Yaw</label>
                <el-input-number v-model="renderParams.yaw" :min="-180" :max="180" :step="15" size="small" />
                <span class="param-unit">°</span>
              </div>
              <div class="param-item">
                <label>Height</label>
                <el-input-number v-model="renderParams.height" :min="0" :max="3" :step="0.1" :precision="1" size="small" />
                <span class="param-unit">m</span>
              </div>
              <div class="param-item">
                <label>Distance</label>
                <el-input-number v-model="renderParams.distance" :min="1" :max="10" :step="0.5" :precision="1" size="small" />
                <span class="param-unit">m</span>
              </div>
            </div>
            
            <!-- Resolution Settings -->
            <div class="resolution-section">
              <label class="form-label">Resolution</label>
              <div class="resolution-inputs">
                <div class="resolution-item">
                  <span class="resolution-label">W</span>
                  <el-input-number 
                    v-model="renderParams.videoWidth" 
                    :min="resolutionLimits.minWidth" 
                    :max="resolutionLimits.maxWidth" 
                    :step="8" 
                    size="small"
                    controls-position="right"
                  />
                  <span class="resolution-unit">px</span>
                </div>
                <span class="resolution-x">×</span>
                <div class="resolution-item">
                  <span class="resolution-label">H</span>
                  <el-input-number 
                    v-model="renderParams.videoHeight" 
                    :min="resolutionLimits.minHeight" 
                    :max="resolutionLimits.maxHeight" 
                    :step="8" 
                    size="small"
                    controls-position="right"
                  />
                  <span class="resolution-unit">px</span>
                </div>
              </div>
              <div class="resolution-presets">
                <button class="preset-btn" @click="setResolution(512, 512)">512×512</button>
                <button class="preset-btn" @click="setResolution(768, 432)">768×432</button>
                <button class="preset-btn" @click="setResolution(856, 480)">856×480</button>
                <button class="preset-btn" @click="setResolution(1280, 720)">1280×720</button>
              </div>
              <p class="resolution-hint">Use multiples of 8, range: {{ resolutionLimits.minWidth }}-{{ resolutionLimits.maxWidth }} × {{ resolutionLimits.minHeight }}-{{ resolutionLimits.maxHeight }}</p>
            </div>
            
            <div class="form-section bg-section">
              <label class="form-label">Background</label>
              <div class="bg-toolbar">
                <el-select v-model="selectedBgFolder" size="small" @change="onBgFolderChange" class="bg-folder-select">
                  <el-option v-for="folder in bgFolders" :key="folder.path" :label="folder.name + (folder.count !== undefined ? ` (${folder.count})` : '')" :value="folder.path" />
                </el-select>
                <el-input
                  v-model="bgSearchText"
                  placeholder="Search..."
                  size="small"
                  clearable
                  @input="onBgSearch"
                  @clear="loadBackgrounds"
                  class="bg-search-input"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
              </div>
              <div class="bg-grid">
                <div
                  v-for="bg in backgrounds"
                  :key="bg.path"
                  :class="['bg-card', { selected: selectedBackground === bg.relative_path }]"
                  @click="selectedBackground = bg.relative_path"
                  @mouseenter="hoverBackground = bg"
                  @mouseleave="hoverBackground = null"
                >
                  <img :src="bg.thumb_url || bg.url" :alt="bg.name" loading="lazy" decoding="async" />
                  <div class="bg-check" v-if="selectedBackground === bg.relative_path">
                    <el-icon><Check /></el-icon>
                  </div>
                </div>
              </div>
              <div v-if="backgrounds.length === 0" class="bg-empty">
                <span>{{ bgSearchText ? 'No matching backgrounds' : 'No backgrounds' }}</span>
              </div>
            </div>
            
            <button
              class="action-btn green"
              :class="{ loading: rendering }"
              :disabled="rendering || !selectedBackground"
              @click="renderMotion"
            >
              <el-icon v-if="!rendering"><VideoCameraFilled /></el-icon>
              <el-icon v-else class="spin"><Loading /></el-icon>
              <span>{{ rendering ? 'Rendering...' : 'Start Render' }}</span>
            </button>
            
            <!-- Render Progress Bar -->
            <div v-if="rendering" class="progress-section">
              <div class="progress-header">
                <span>{{ renderProgressText }}</span>
                <span class="progress-percent">{{ Math.round(renderProgress) }}%</span>
              </div>
              <el-progress :percentage="renderProgress" :stroke-width="6" :show-text="false" />
            </div>
          </div>
          
          <div v-else class="empty-state">
            <el-icon :size="36"><Select /></el-icon>
            <p>Select a motion first</p>
          </div>
        </div>
      </div>
      
      <!-- Render Result Panel -->
      <div class="panel render-result-panel">
        <div class="panel-header">
          <div class="panel-icon orange">
            <el-icon :size="20"><Film /></el-icon>
          </div>
          <span>Render Result</span>
        </div>
        
        <div class="panel-body result-body">
          <!-- Background Hover Preview Overlay -->
          <transition name="fade">
            <div v-if="hoverBackground" class="bg-preview-overlay">
              <img :src="hoverBackground.url" :alt="hoverBackground.name" />
              <div class="preview-info">
                <span class="preview-name">{{ hoverBackground.name }}</span>
              </div>
            </div>
          </transition>
          <!-- Multiple Renders List -->
          <div v-if="selectedMotion?.renders?.length > 0" class="renders-list">
            <div class="renders-header">
              <span>{{ selectedMotion.renders.length }} render(s)</span>
            </div>
            <div class="renders-scroll">
              <div
                v-for="render in selectedMotion.renders"
                :key="render.render_id"
                :class="['render-item', { selected: selectedRender?.render_id === render.render_id }]"
                @click="selectRender(render)"
              >
                <div class="render-videos-pair">
                  <!-- Reference Video (with background) -->
                  <div class="render-thumb" @click.stop="previewRender(render, 'composite')">
                    <video :src="getVideoUrl(selectedMotion.motion_id, 'composite', render.render_id)" muted preload="metadata" />
                    <div class="video-type-label reference">Reference</div>
                    <div class="play-overlay-small">
                      <el-icon><VideoPlay /></el-icon>
                    </div>
                  </div>
                  <!-- Mask Video (no background) -->
                  <div class="render-thumb" @click.stop="previewRender(render, 'mask')">
                    <video :src="getVideoUrl(selectedMotion.motion_id, 'mask', render.render_id)" muted preload="metadata" />
                    <div class="video-type-label mask">Mask</div>
                    <div class="play-overlay-small">
                      <el-icon><VideoPlay /></el-icon>
                    </div>
                  </div>
                </div>
                <div class="render-meta">
                  <p class="render-bg">{{ render.background || 'Default BG' }}</p>
                  <p class="render-params">
                    yaw: {{ render.yaw_deg }}° | 
                    H: {{ render.height || 1.5 }}m | 
                    D: {{ render.distance || 3.0 }}m
                  </p>
                  <p class="render-time">{{ formatTime(render.created_at) }}</p>
                </div>
                <div class="render-actions-mini">
                  <el-tooltip content="Use for V2V">
                    <el-icon class="action-icon" @click.stop="useRenderForV2V(render)"><Right /></el-icon>
                  </el-tooltip>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else-if="rendering" class="render-progress">
            <div class="progress-animation">
              <el-icon :size="48" class="spin"><Loading /></el-icon>
            </div>
            <p class="progress-text">Rendering video...</p>
            <p class="progress-hint">This may take a while</p>
          </div>
          
          <div v-else class="empty-state">
            <el-icon :size="36"><Film /></el-icon>
            <p>{{ selectedMotion ? 'Awaiting render' : 'Select motion to render' }}</p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Preview Dialog -->
    <el-dialog
      v-model="previewVisible"
      :title="currentVideo?.text"
      width="720px"
      :show-close="true"
      destroy-on-close
    >
      <div class="preview-video">
        <div class="video-type-tabs">
          <button 
            :class="['tab-btn', { active: currentVideoType === 'composite' }]"
            @click="currentVideoType = 'composite'"
          >
            Reference (w/ BG)
          </button>
          <button 
            :class="['tab-btn', { active: currentVideoType === 'mask' }]"
            @click="currentVideoType = 'mask'"
          >
            Mask (no BG)
          </button>
        </div>
        <video
          v-if="currentVideo"
          :key="currentVideoType"
          :src="getVideoUrl(currentVideo.motion_id, currentVideoType, currentRenderId)"
          controls
          autoplay
        />
        <div v-if="currentVideo?.background" class="preview-info">
          <span>BG: {{ currentVideo.background }}</span>
          <span v-if="currentVideo.yaw_deg"> | yaw: {{ currentVideo.yaw_deg }}°</span>
          <span v-if="currentVideo.height"> | H: {{ currentVideo.height }}m</span>
          <span v-if="currentVideo.distance"> | D: {{ currentVideo.distance }}m</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, onDeactivated, inject, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { motionAPI, videoAPI } from '../api'
import { useRouter } from 'vue-router'

const router = useRouter()
const dataset = inject('dataset')
const requireLogin = inject('requireLogin')

const motionForm = reactive({
  text: '',
  name: '',
  outputDir: ''
})

const renderParams = reactive({
  yaw: -60,       // default yaw
  height: 1.0,    // default height (m)
  distance: 1.0,  // default distance (m)
  name: '',       // filename
  outputDir: '',  // output folder
  videoWidth: 856,   // video width
  videoHeight: 480   // video height
})

// Resolution limits
const resolutionLimits = {
  minWidth: 256,
  maxWidth: 1920,
  minHeight: 256,
  maxHeight: 1080
}

// Set preset resolution
const setResolution = (width, height) => {
  renderParams.videoWidth = width
  renderParams.videoHeight = height
}

const generating = ref(false)
const rendering = ref(false)
const generateProgress = ref(0)
const generateProgressText = ref('')
const renderProgress = ref(0)
const renderProgressText = ref('')
let generatePollInterval = null
let renderPollInterval = null
let activeGenerateTaskId = ''
const backgrounds = ref([])
const bgFolders = ref([])
const selectedBgFolder = ref('')
const bgSearchText = ref('')
const motions = ref([])
const motionSearchText = ref('')
const motionDirectories = ref([])
const selectedDirectory = ref('')

// Motion search filter
const filteredMotions = computed(() => {
  if (!motionSearchText.value) return motions.value
  const search = motionSearchText.value.toLowerCase()
  return motions.value.filter(m => 
    m.motion_id.toLowerCase().includes(search) || 
    (m.text && m.text.toLowerCase().includes(search))
  )
})
const selectedMotion = ref(null)
const selectedRender = ref(null)
const selectedBackground = ref('')
const hoverBackground = ref(null)
const previewVisible = ref(false)
const currentVideo = ref(null)
const currentRenderId = ref(null)
const currentVideoType = ref('composite')

const getVideoUrl = (motionId, type, renderId = null) => {
  return motionAPI.getVideoUrl(motionId, type, renderId, selectedDirectory.value)
}

const selectRender = (render) => {
  selectedRender.value = render
}

const previewRender = (render, videoType = 'composite') => {
  currentVideo.value = { ...selectedMotion.value, ...render }
  currentRenderId.value = render.render_id
  currentVideoType.value = videoType
  previewVisible.value = true
}

const useRenderForV2V = (render) => {
  router.push({ path: '/video', query: { directory: selectedDirectory.value, mask: selectedMotion.value.motion_id, render: render.render_id } })
}

const stopGeneratePolling = () => {
  if (generatePollInterval) {
    clearInterval(generatePollInterval)
    generatePollInterval = null
  }
  activeGenerateTaskId = ''
}

const resetGenerateState = () => {
  stopGeneratePolling()
  generating.value = false
  generateProgress.value = 0
  generateProgressText.value = ''
}

const generateMotion = async () => {
  if (!requireLogin()) return
  const text = motionForm.text.trim()
  const motionName = motionForm.name.trim()

  if (!text) {
    ElMessage.warning('Enter action description')
    return
  }
  
  if (!motionName) {
    ElMessage.warning('Enter filename')
    return
  }

  stopGeneratePolling()
  generating.value = true
  generateProgress.value = 1
  generateProgressText.value = 'Checking filename...'
  
  // Check name duplicates
  try {
    const checkRes = await videoAPI.checkName({
      name: motionName,
      context: 'motion',
      directory: motionForm.outputDir || ''
    })
    if (checkRes.data.exists) {
      ElMessage.error(`Name "${motionName}" already exists`)
      resetGenerateState()
      return
    }
  } catch (e) {
    console.error('Name check failed:', e)
    ElMessage.error('Name check failed')
    resetGenerateState()
    return
  }
  
  generateProgress.value = 3
  generateProgressText.value = 'Submitting...'
  
  try {
    const genResponse = await motionAPI.generate({
      text,
      motion_id: motionName,
      output_dir: motionForm.outputDir || undefined
    })
    
    if (!genResponse.data.success) {
      throw new Error(genResponse.data.error || 'Motion generation failed')
    }
    
    const taskId = genResponse.data.task_id
    if (taskId) {
      activeGenerateTaskId = taskId
      generateProgress.value = 5
      generateProgressText.value = 'Task submitted...'
      let finished = false

      const finishGenerate = (status, message) => {
        if (finished || activeGenerateTaskId !== taskId) return
        finished = true
        stopGeneratePolling()

        if (status === 'completed') {
          generateProgress.value = 100
          generateProgressText.value = 'Done!'
          ElMessage.success('Motion generated')
          motionForm.text = ''
          motionForm.name = ''
          refreshMotions()
          setTimeout(() => {
            if (finished && !activeGenerateTaskId) {
              generating.value = false
              generateProgress.value = 0
              generateProgressText.value = ''
            }
          }, 1000)
        } else {
          ElMessage.error(message || 'Motion generation failed')
          generating.value = false
          generateProgress.value = 0
          generateProgressText.value = ''
        }
      }
      
      // Poll for progress
      const pollProgress = async () => {
        if (finished || activeGenerateTaskId !== taskId) return
        try {
          const progressRes = await motionAPI.taskProgress(taskId)
          const data = progressRes.data

          if (finished || activeGenerateTaskId !== taskId) return
          if (data.status === 'unknown') {
            finishGenerate('failed', data.error || 'Motion task was lost, please submit again')
            return
          }
          
          generateProgress.value = data.progress || 0
          generateProgressText.value = data.message || 'Processing...'
          
          if (data.status === 'completed') {
            finishGenerate('completed')
          } else if (data.status === 'failed') {
            finishGenerate('failed', data.message || 'Motion generation failed')
          }
        } catch (e) {
          console.warn('Progress poll failed:', e)
          finishGenerate('failed', e.message || 'Progress poll failed')
        }
      }
      
      generatePollInterval = setInterval(pollProgress, 1000)
      pollProgress()
    } else {
      // Legacy sync mode
      ElMessage.success('Motion generated')
      motionForm.text = ''
      motionForm.name = ''
      refreshMotions()
      resetGenerateState()
    }
    
  } catch (error) {
    ElMessage.error(error.message)
    resetGenerateState()
  }
}

const renderMotion = async () => {
  if (!requireLogin()) return
  if (!selectedMotion.value || !selectedBackground.value) {
    ElMessage.warning('Select motion and background')
    return
  }
  
  if (!renderParams.name.trim()) {
    ElMessage.warning('Enter render filename')
    return
  }
  
  // Check render name duplicates
  const existingRenders = selectedMotion.value.renders || []
  if (existingRenders.some(r => r.render_id === renderParams.name.trim())) {
    ElMessage.error(`Render name "${renderParams.name}" exists`)
    return
  }
  
  rendering.value = true
  renderProgress.value = 0
  renderProgressText.value = 'Submitting render...'
  
  try {
    const renderResponse = await motionAPI.renderMask({
      motion_id: selectedMotion.value.motion_id,
      source_directory: selectedDirectory.value,
      background: selectedBackground.value,
      dataset: dataset.value === 'ucf-crime' ? 'ucf' : 'sht',
      yaw: renderParams.yaw,
      height: renderParams.height,
      distance: renderParams.distance,
      render_name: renderParams.name || undefined,
      output_dir: renderParams.outputDir || undefined,
      video_width: renderParams.videoWidth,
      video_height: renderParams.videoHeight
    })
    
    if (!renderResponse.data.success) {
      throw new Error(renderResponse.data.error || 'Render failed')
    }
    
    const taskId = renderResponse.data.task_id
    if (taskId) {
      renderProgress.value = 5
      renderProgressText.value = 'Task submitted...'
      
      // Poll for progress
      const pollProgress = async () => {
        try {
          const progressRes = await motionAPI.taskProgress(taskId)
          const data = progressRes.data
          
          renderProgress.value = data.progress || 0
          renderProgressText.value = data.message || 'Rendering...'
          
          if (data.status === 'completed') {
            renderProgress.value = 100
            renderProgressText.value = 'Done!'
            ElMessage.success('Render complete')
            renderParams.name = ''
            refreshMotions()
            clearInterval(renderPollInterval)
            setTimeout(() => {
              rendering.value = false
              renderProgress.value = 0
            }, 1000)
          } else if (data.status === 'failed') {
            ElMessage.error(data.message || 'Render failed')
            clearInterval(renderPollInterval)
            rendering.value = false
            renderProgress.value = 0
          }
        } catch (e) {
          console.warn('Progress poll failed:', e)
        }
      }
      
      renderPollInterval = setInterval(pollProgress, 1000)
      pollProgress()
    } else {
      // Legacy sync mode
      ElMessage.success('Render complete')
      renderParams.name = ''
      refreshMotions()
      rendering.value = false
    }
    
  } catch (error) {
    ElMessage.error(error.message)
    rendering.value = false
    renderProgress.value = 0
  }
}

const loadDirectories = async () => {
  try {
    const response = await motionAPI.directories()
    motionDirectories.value = response.data.directories || []
    
    // Set default directory (prefer "system" dir)
    if (!selectedDirectory.value && motionDirectories.value.length > 0) {
      const systemDir = motionDirectories.value.find(d => d.name.includes('system'))
      selectedDirectory.value = (systemDir || motionDirectories.value[0]).name
    }
    
    // Set default output directory for generation and render (prefer "system" dir)
    if (motionDirectories.value.length > 0) {
      const systemDir = motionDirectories.value.find(d => d.name.includes('system'))
      const defaultDir = systemDir || motionDirectories.value[0]
      if (!motionForm.outputDir) {
        motionForm.outputDir = defaultDir.name
      }
      if (!renderParams.outputDir) {
        renderParams.outputDir = defaultDir.name
      }
    }
  } catch (error) {
    console.error('Failed to load directories:', error)
  }
}

const onDirectoryChange = () => {
  selectedMotion.value = null
  selectedRender.value = null
  refreshMotions()
}

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
    const response = await videoAPI.backgrounds(ds, selectedBgFolder.value, bgSearchText.value)
    backgrounds.value = response.data.backgrounds || []
  } catch (error) {
    console.error('Failed to load backgrounds:', error)
  }
}

const onBgFolderChange = () => {
  loadBackgrounds()
}

// Debounced search
let searchTimeout = null
const onBgSearch = () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    loadBackgrounds()
  }, 300)
}

const refreshMotions = async () => {
  try {
    // Use selected directory if available, otherwise fallback to dataset
    let response
    if (selectedDirectory.value) {
      response = await motionAPI.list({ directory: selectedDirectory.value })
    } else {
      const ds = dataset.value === 'ucf-crime' ? 'ucf' : 'sht'
      response = await motionAPI.list({ dataset: ds })
    }
    
    motions.value = response.data.motions || []
    
    // Update selected motion if it still exists
    if (selectedMotion.value) {
      const updated = motions.value.find(m => m.motion_id === selectedMotion.value.motion_id)
      selectedMotion.value = updated || null
    }
  } catch (error) {
    console.error('Failed to load motions:', error)
  }
}

const selectMotion = (motion) => {
  selectedMotion.value = motion
  selectedRender.value = motion.renders?.[0] || null
  selectedBackground.value = motion.background || ''
}

const previewVideo = (motion) => {
  currentVideo.value = motion
  currentRenderId.value = motion.renders?.[0]?.render_id || null
  previewVisible.value = true
}

const useForV2V = (motion) => {
  router.push({ path: '/video', query: { directory: selectedDirectory.value, mask: motion.motion_id } })
}

const deleteMotion = async (motion) => {
  try {
    await ElMessageBox.confirm('Delete this motion?', 'Confirm', { type: 'warning' })
    await motionAPI.delete(motion.motion_id)
    ElMessage.success('Deleted')
    if (selectedMotion.value?.motion_id === motion.motion_id) {
      selectedMotion.value = null
    }
    refreshMotions()
  } catch (e) {}
}

const formatTime = (ts) => {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleString('en-US', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
}

// Only reload backgrounds when dataset changes (for rendering)
// Motion directory is independent of dataset
watch(dataset, () => {
  selectedBgFolder.value = ''
  loadBgFolders()
  loadBackgrounds()
  selectedBackground.value = ''
  bgSearchText.value = ''
})

onMounted(async () => {
  // Load directories first so selectedDirectory is set (default: runs_vad_system)
  // before loading motions; otherwise motions would come from legacy dataset (runs_sht_abnormal)
  await loadDirectories()
  await Promise.all([
    loadBgFolders().then(() => loadBackgrounds()),
    refreshMotions()
  ])
})

// Cleanup timers
const cleanupTimers = () => {
  resetGenerateState()
  if (renderPollInterval) {
    clearInterval(renderPollInterval)
    renderPollInterval = null
  }
}

// Cleanup timers on keep-alive deactivate
onDeactivated(() => {
  cleanupTimers()
})

onUnmounted(() => {
  cleanupTimers()
})
</script>

<style scoped>
.motion-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 120px);
}

.top-row, .bottom-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.panel {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  font-size: 14px;
}

.directory-select {
  margin-left: auto;
  width: 180px;
}

.directory-select :deep(.el-input__wrapper) {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  box-shadow: none;
}

.directory-select :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 12px;
}

.panel-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.panel-icon.blue {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.panel-icon.green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.panel-icon.orange {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.count-badge {
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.motion-search-input {
  width: 140px;
}

.panel-body {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.result-body {
  position: relative;
}

/* Background Preview Overlay */
.bg-preview-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.95);
  border-radius: 0 0 12px 12px;
  padding: 16px;
}

.bg-preview-overlay img {
  max-width: 100%;
  max-height: calc(100% - 40px);
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.preview-info {
  margin-top: 12px;
  text-align: center;
}

.preview-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  background: rgba(99, 102, 241, 0.2);
  padding: 4px 12px;
  border-radius: 4px;
}

/* Fade Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Form Styles */
.form-section {
  margin-bottom: 16px;
}

.form-row,
.form-row-2 {
  display: flex;
  gap: 16px;
}

.flex-1 {
  flex: 1;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-label .required {
  color: #ef4444;
  margin-left: 2px;
}

/* Action Buttons */
.action-btn {
  width: 100%;
  padding: 12px 20px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.action-btn.green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.action-btn.small {
  flex: 1;
  padding: 10px 16px;
  font-size: 13px;
}

.action-btn.danger {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.action-btn.green:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Progress Section */
.progress-section {
  margin-top: 12px;
  padding: 10px 12px;
  background: rgba(30, 41, 59, 0.6);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.progress-percent {
  color: var(--primary);
  font-weight: 600;
}

.progress-section :deep(.el-progress-bar__outer) {
  background: rgba(51, 65, 85, 0.5);
}

.progress-section :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Motion List */
.motion-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.motion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.motion-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.motion-item.selected {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.15);
}

.motion-icon {
  width: 36px;
  height: 36px;
  background: rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-light);
  flex-shrink: 0;
}

.motion-meta {
  flex: 1;
  min-width: 0;
}

.motion-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 2px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.motion-info {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0;
}

/* Render Config */
.render-config {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.selected-motion-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--primary-light);
}

.selected-motion-badge span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Render Parameters Grid */
.params-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-darker);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-item label {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
}

.param-item .el-input-number {
  width: 100%;
}

.param-item .el-input-number :deep(.el-input__wrapper) {
  background: var(--bg-card);
}

.param-unit {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Resolution Settings */
.resolution-section {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-darker);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.resolution-section .form-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.resolution-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.resolution-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.resolution-label {
  font-size: 11px;
  color: var(--text-muted);
  min-width: 20px;
}

.resolution-unit {
  font-size: 10px;
  color: var(--text-muted);
}

.resolution-x {
  font-size: 14px;
  color: var(--text-muted);
  font-weight: 500;
}

.resolution-item .el-input-number {
  width: 100px;
}

.resolution-item .el-input-number :deep(.el-input__wrapper) {
  background: var(--bg-card);
}

.resolution-presets {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.preset-btn {
  padding: 4px 10px;
  font-size: 11px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.preset-btn:hover {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.resolution-hint {
  font-size: 10px;
  color: var(--text-muted);
  margin: 0;
}

/* Background Grid */
.bg-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.bg-folder-select {
  width: 140px;
  flex-shrink: 0;
}

.bg-search-input {
  flex: 1;
}

.bg-search-input-full {
  width: 100%;
  margin-bottom: 8px;
}

.bg-empty {
  padding: 16px;
  text-align: center;
  color: #909399;
  font-size: 12px;
  background: #fafafa;
  border-radius: 6px;
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
  border-color: var(--primary);
}

.bg-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}

.render-settings-panel {
  position: relative;
}

.bg-hover-preview {
  position: absolute;
  top: 50%;
  left: calc(100% + 20px);
  transform: translateY(-50%);
  width: 380px;
  background: var(--bg-card);
  border-radius: 12px;
  box-shadow: 0 16px 64px rgba(0, 0, 0, 0.6);
  border: 2px solid var(--primary);
  overflow: hidden;
  z-index: 1000;
  pointer-events: none;
  animation: fadeIn 0.15s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-50%) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(-50%) scale(1);
  }
}

.bg-hover-preview img {
  width: 100%;
  height: auto;
  display: block;
}

.bg-preview-name {
  display: block;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-hover);
  text-align: center;
}

.bg-check {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  font-size: 10px;
  background: var(--primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 10px;
}

/* Render Result */
.render-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-preview {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  background: #000;
  cursor: pointer;
}

.video-preview video {
  width: 100%;
  height: auto;
  max-height: 180px;
  object-fit: contain;
  display: block;
}

.play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  color: white;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-preview:hover .play-overlay {
  opacity: 1;
}

.result-info {
  padding: 10px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
}

.info-row {
  display: flex;
  font-size: 12px;
  margin-bottom: 4px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-label {
  color: var(--text-muted);
  width: 50px;
}

.info-value {
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-actions {
  display: flex;
  gap: 10px;
}

/* Render Progress */
.render-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}

.progress-animation {
  color: var(--primary);
}

.progress-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.progress-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 100px;
  color: var(--text-muted);
  text-align: center;
  gap: 8px;
}

.empty-state p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* Renders List */
.renders-list {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.renders-header {
  padding: 8px 0;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}

.renders-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.render-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.render-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.render-item.selected {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.15);
}

.render-thumb {
  width: 80px;
  height: 45px;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
  background: #000;
}

.render-thumb video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.play-overlay-small {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s;
}

.render-thumb:hover .play-overlay-small {
  opacity: 1;
}

/* Video pair layout */
.render-videos-pair {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.video-type-label {
  position: absolute;
  top: 2px;
  left: 2px;
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 600;
  text-transform: uppercase;
  z-index: 2;
}

.video-type-label.reference {
  background: rgba(34, 197, 94, 0.85);
  color: white;
}

.video-type-label.mask {
  background: rgba(168, 85, 247, 0.85);
  color: white;
}

/* Video type tabs in preview */
.video-type-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.video-type-tabs .tab-btn {
  flex: 1;
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.video-type-tabs .tab-btn:hover {
  background: var(--bg-darker);
}

.video-type-tabs .tab-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.render-meta {
  flex: 1;
  min-width: 0;
}

.render-bg {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.render-params {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 2px 0 0 0;
}

.render-time {
  font-size: 11px;
  color: var(--text-muted);
  margin: 2px 0 0 0;
}

.render-actions-mini {
  display: flex;
  gap: 8px;
}

.action-icon {
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.action-icon:hover {
  color: var(--primary);
  background: rgba(99, 102, 241, 0.15);
}

/* Preview Dialog */
.preview-video {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.preview-video video {
  width: 100%;
  max-height: 480px;
}

.preview-info {
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.8);
  font-size: 12px;
  color: var(--text-secondary);
}

/* Element Plus Overrides */
:deep(.el-slider__runway) {
  background: var(--bg-hover);
}

:deep(.el-slider__bar) {
  background: var(--primary);
}

:deep(.el-slider__button) {
  border-color: var(--primary);
}

:deep(.el-slider__marks-text) {
  color: var(--text-muted);
}

:deep(.el-tag--success) {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

:deep(.el-tag--info) {
  background: rgba(100, 116, 139, 0.15);
  border-color: rgba(100, 116, 139, 0.3);
  color: #94a3b8;
}
</style>
