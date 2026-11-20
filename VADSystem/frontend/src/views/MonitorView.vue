<template>
  <div class="monitor-view">
    <div class="monitor-grid">
      <!-- Left: Controls (full height) -->
      <div class="panel control-panel">
        <div class="panel-header">
          <div class="panel-icon">
            <el-icon :size="20"><Monitor /></el-icon>
          </div>
          <span>Monitor Settings</span>
          <div class="status-badge" :class="statusClass">
            {{ statusText }}
          </div>
        </div>

        <div class="panel-body">
          <!-- Camera Selection -->
          <div class="form-section">
            <label class="form-label">Camera</label>
            <el-select
              v-model="selectedDevice"
              placeholder="Select camera"
              style="width: 100%"
              :disabled="monitoring || changingSession"
              @change="onDeviceChange"
            >
              <el-option
                v-for="dev in cameraDevices"
                :key="dev.deviceId"
                :label="dev.label || `Camera ${dev.index}`"
                :value="dev.deviceId"
              />
            </el-select>
            <div class="hint" v-if="cameraDevices.length === 0 && !cameraError && !mediaAPIUnavailable">
              Click below to authorize camera access
            </div>
            <div class="hint error" v-if="cameraError">
              {{ cameraError }}
            </div>
            <div class="hint error" v-if="mediaAPIUnavailable">
              Browser does not support camera access (requires HTTPS or localhost).
              <br />Protocol: {{ pageProtocol }}, Host: {{ pageHost }}
              <br />Try using <b>Chrome</b> and access via <code>https://</code> or <code>http://localhost</code> / <code>http://127.0.0.1</code>.
            </div>
          </div>

          <!-- Model Selection -->
          <div class="form-section">
            <label class="form-label">Detection Model</label>
            <el-select
              v-model="selectedModel"
              placeholder="Select detection model"
              style="width: 100%"
              :disabled="monitoring || changingSession"
            >
              <el-option
                v-for="model in models"
                :key="model.id"
                :label="model.name"
                :value="model.id"
              >
                <div class="model-option">
                  <span class="model-option-name">{{ model.name }}</span>
                </div>
              </el-option>
            </el-select>
          </div>

          <!-- Threshold -->
          <div class="form-section">
            <label class="form-label">Threshold <span class="label-value">{{ threshold.toFixed(2) }}</span></label>
            <div class="threshold-row">
              <el-slider
                v-model="threshold"
                :min="0.1"
                :max="0.9"
                :step="0.05"
                :disabled="monitoring || changingSession"
                :show-tooltip="false"
              />
              <el-input-number
                v-model="threshold"
                :min="0.1"
                :max="0.9"
                :step="0.05"
                :precision="2"
                size="small"
                :disabled="monitoring || changingSession"
                style="width: 90px; margin-left: 12px"
              />
            </div>
          </div>

          <!-- Real-time Stats -->
          <div class="form-section" v-if="monitoring || allScores.length > 0">
            <label class="form-label">Live Stats</label>
            <div class="stats-grid">
              <div class="stat-item" :class="{ 'alert-bg': alertActive }">
                <span class="stat-value" :class="{ 'danger-text': alertActive }">
                  {{ allScores.length ? formatScore(currentScore) : '--' }}
                </span>
                <span class="stat-label">Current</span>
              </div>
              <div class="stat-item">
                <span class="stat-value accent-text">
                  {{ allScores.length ? formatScore(maxScore) : '--' }}
                </span>
                <span class="stat-label">Max Score</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ allScores.length }}</span>
                <span class="stat-label">Scored<span v-if="skipped"> ({{ skipped }} skipped)</span></span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ alertCount }}</span>
                <span class="stat-label danger-text">Alerts</span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="btn-group" v-if="!cameraReady">
            <button
              class="action-btn secondary"
              :disabled="mediaAPIUnavailable"
              @click="requestCamera"
            >
              <el-icon><VideoCamera /></el-icon>
              <span>{{ mediaAPIUnavailable ? 'Camera N/A' : 'Authorize Camera' }}</span>
            </button>
          </div>
          <div class="btn-group" v-else-if="!monitoring">
            <button
              class="action-btn primary"
              :disabled="!selectedDevice || !selectedModel || changingSession"
              @click="startMonitor"
            >
              <el-icon v-if="preloadingMonitor" class="spin"><Loading /></el-icon>
              <el-icon v-else><CaretRight /></el-icon>
              <span>{{ preloadingMonitor ? 'Preloading...' : 'Start Monitor' }}</span>
            </button>
          </div>
          <div class="btn-group multi" v-else>
            <button class="action-btn danger" @click="stopMonitor">
              <el-icon><Close /></el-icon>
              <span>Stop</span>
            </button>
            <button class="action-btn save" @click="handleSaveResults" :disabled="allScores.length === 0">
              <el-icon><Download /></el-icon>
              <span>Save</span>
            </button>
          </div>
          <!-- Save available after stop -->
          <div class="btn-group multi" v-if="!monitoring && cameraReady && allScores.length > 0">
            <button class="action-btn save" @click="handleSaveResults">
              <el-icon><Download /></el-icon>
              <span>Save Results</span>
            </button>
          </div>

          <!-- Error -->
          <div v-if="errorMsg" class="error-msg">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ errorMsg }}</span>
          </div>
        </div>
      </div>

      <!-- Right column: camera + chart -->
      <div class="right-column">
        <!-- Camera Feed -->
        <div class="panel video-panel" :class="{ 'alert-border': alertActive }">
          <div class="panel-header">
            <div class="panel-icon" :class="alertActive ? 'red' : (monitoring ? 'green' : '')">
              <el-icon :size="20"><VideoCamera /></el-icon>
            </div>
            <span>{{ cameraLabel || 'Camera Feed' }}</span>
            <div class="header-actions" v-if="monitoring">
              <div class="live-dot" :class="{ alert: alertActive }"></div>
              <span class="live-text" :class="{ alert: alertActive }">{{ alertActive ? 'ALERT' : 'LIVE' }}</span>
            </div>
          </div>
          <div class="video-body">
            <video ref="videoRef" class="video-player" autoplay playsinline muted></video>
            <canvas ref="canvasRef" style="display:none"></canvas>
            <div v-if="!cameraReady" class="empty-state video-empty">
              <el-icon :size="64"><VideoCamera /></el-icon>
              <p>Please authorize and select a camera</p>
              <span>The system will access your camera via the browser</span>
            </div>
            <transition name="fade">
              <div v-if="alertActive && monitoring" class="alert-overlay">
                <div class="alert-icon">⚠</div>
                <div class="alert-text">Anomaly Detected</div>
                <div class="alert-score">Score: {{ formatScore(currentScore) }}</div>
              </div>
            </transition>
          </div>
        </div>

        <!-- Anomaly Score Chart (below camera) -->
        <div class="panel chart-panel" :class="{ 'alert-border': alertActive }">
          <div class="panel-header">
            <div class="panel-icon" :class="alertActive ? 'red' : 'blue'">
              <el-icon :size="20"><TrendCharts /></el-icon>
            </div>
            <span>Anomaly Score Curve</span>
            <div class="header-actions">
              <el-tag v-if="allScores.length > 0" size="small" type="info" style="margin-right: 6px">{{ allScores.length }} segs</el-tag>
              <button v-if="allScores.length > 0" class="save-chart-btn" @click="handleSaveChart" title="Save curve image">
                <el-icon :size="14"><Download /></el-icon>
                <span>Save Curve</span>
              </button>
            </div>
          </div>
          <div class="chart-body">
            <div v-if="allScores.length > 0" class="chart-wrapper">
              <div ref="chartRef" class="chart-container"></div>
            </div>
            <div v-else class="empty-state">
              <el-icon :size="36"><TrendCharts /></el-icon>
              <p>Awaiting live data</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject, watch, nextTick, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import { inferAPI, monitorAPI } from '../api'
import * as echarts from 'echarts'

const dataset = inject('dataset')
const isLoggedIn = inject('isLoggedIn')
const requireLogin = inject('requireLogin')

// ---- Camera ----
const videoRef = ref(null)
const canvasRef = ref(null)
const cameraDevices = ref([])
const selectedDevice = ref('')
const cameraReady = ref(false)
const cameraError = ref('')
const mediaAPIUnavailable = ref(false)
const pageProtocol = ref(typeof window !== 'undefined' ? window.location.protocol : '')
const pageHost = ref(typeof window !== 'undefined' ? window.location.hostname : '')
let mediaStream = null

const cameraLabel = computed(() => {
  if (!selectedDevice.value) return ''
  const dev = cameraDevices.value.find(d => d.deviceId === selectedDevice.value)
  return dev?.label || 'Camera'
})

// ---- Models ----
const allModels = ref([])
const selectedModel = ref('')
const models = computed(() => allModels.value.filter(m => m.dataset === dataset.value && m.available !== false))

// ---- Config ----
const threshold = ref(0.9)

// ---- Monitor state ----
const monitoring = ref(false)
const preloadingMonitor = ref(false)
const preloadedModel = ref('')
const alertActive = ref(false)
const currentScore = ref(0)
const maxScore = ref(0)
const errorMsg = ref('')
const allScores = ref([])
const samples = ref([])
const skipped = ref(0)
const changingSession = ref(false)
let frameRequest = null
let session = 0
let analyzingFrame = false
let preloadPromise = null
let preloadModelId = ''
const FRAMES_PER_SEGMENT = 16

const alertCount = computed(() => allScores.value.filter(s => s > threshold.value).length)
const formatScore = (score) => score > 0 && score < 0.0001 ? score.toExponential(2) : score.toFixed(4)

const statusClass = computed(() => {
  if (alertActive.value) return 'alert'
  if (monitoring.value) return 'running'
  if (preloadingMonitor.value) return 'warming'
  if (selectedModel.value && preloadedModel.value === selectedModel.value) return 'ready'
  return 'idle'
})

const statusText = computed(() => {
  if (alertActive.value) return '⚠ Alert'
  if (monitoring.value) return 'Monitoring'
  if (preloadingMonitor.value) return 'Preloading'
  if (selectedModel.value && preloadedModel.value === selectedModel.value) return 'Ready'
  return 'Idle'
})

// ---- Chart ----
const chartRef = ref(null)
let chartInstance = shallowRef(null)
let chartFollowLatest = true
let chartZoomTouched = false
let chartZoomStart = 0
let chartZoomEnd = 100

// ================================================================
// Camera access via browser getUserMedia
// ================================================================
const checkMediaAPI = () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    mediaAPIUnavailable.value = true
    console.warn('navigator.mediaDevices is not available. isSecureContext:', window.isSecureContext,
      'protocol:', window.location.protocol, 'hostname:', window.location.hostname)
    return false
  }
  return true
}

const requestCamera = async () => {
  cameraError.value = ''
  mediaAPIUnavailable.value = false

  if (!checkMediaAPI()) return

  try {
    // Request permission with simple constraints first
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    // Release the temporary camera stream after permission is granted.
    stream.getTracks().forEach(t => t.stop())

    // Now enumerate devices
    const devices = await navigator.mediaDevices.enumerateDevices()
    const videoDevices = devices.filter(d => d.kind === 'videoinput')
    cameraDevices.value = videoDevices.map((d, i) => ({
      deviceId: d.deviceId,
      label: d.label || `Camera ${i + 1}`,
      index: i + 1
    }))

    if (cameraDevices.value.length > 0) {
      selectedDevice.value = cameraDevices.value[0].deviceId
      cameraReady.value = true
      await startCameraPreview()
      ElMessage.success(`Found ${cameraDevices.value.length} camera(s)`)
    } else {
      cameraError.value = 'No camera detected. Ensure a camera is connected.'
    }
  } catch (err) {
    console.error('Camera access error:', err)
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      cameraError.value = 'Camera access denied. Allow camera permission in browser settings, then refresh.'
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      cameraError.value = 'No camera found. Ensure a camera is available.'
    } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
      cameraError.value = 'Camera in use by another app. Close it and retry.'
    } else if (err.name === 'OverconstrainedError') {
      cameraError.value = 'Camera params unsupported, retrying with defaults...'
      // Retry with no constraints
      try {
        const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true })
        fallbackStream.getTracks().forEach(t => t.stop())
        await requestCamera()
      } catch {
        cameraError.value = 'Camera access failed. Try another device.'
      }
    } else if (err.name === 'TypeError') {
      cameraError.value = 'Browser does not support camera (requires HTTPS or localhost)'
      mediaAPIUnavailable.value = true
    } else {
      cameraError.value = `Camera access failed: ${err.name} - ${err.message}`
    }
  }
}

const startCameraPreview = async () => {
  if (!selectedDevice.value) return

  // Stop existing stream
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
  }

  try {
    // Use 'ideal' for deviceId instead of 'exact' to be more resilient
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: selectedDevice.value ? { ideal: selectedDevice.value } : true,
        width: { ideal: 640 },
        height: { ideal: 480 }
      },
      audio: false
    })

    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream
    }
  } catch (err) {
    console.error('Camera preview error:', err)
    // Fallback: try without deviceId constraint
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      if (videoRef.value) {
        videoRef.value.srcObject = mediaStream
      }
    } catch (fallbackErr) {
      cameraError.value = `Cannot open camera: ${fallbackErr.message}`
    }
  }
}

const onDeviceChange = () => {
  startCameraPreview()
}

// ================================================================
// Frame capture & send to backend
// ================================================================
const captureFrame = (video) => {
  const canvas = canvasRef.value
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  return canvas.toDataURL('image/png')
}

const analyzeFrame = async (sample, id) => {
  analyzingFrame = true
  try {
    const { data } = await monitorAPI.analyzeFrame({
      frame: sample.frame, model_id: selectedModel.value, threshold: threshold.value
    })
    if (id !== session) return
    if (!data.success || !Number.isFinite(data.score)) throw new Error(data.error || 'Frame analysis failed')
    samples.value.push({ segment: sample.segment, time: sample.time })
    allScores.value.push(data.score)
    currentScore.value = data.score
    maxScore.value = Math.max(maxScore.value, data.score)
    alertActive.value = data.score > threshold.value
    await nextTick()
    if (id === session) updateChart()
  } catch (error) {
    if (id === session) {
      skipped.value++
      errorMsg.value = error.response?.data?.error || error.message
    }
  } finally {
    if (id === session) analyzingFrame = false
  }
}

const captureSegments = (video, id) => {
  let firstFrame, startTime, sample
  let completed = 0
  const onFrame = (_, meta) => {
    if (id !== session) return
    frameRequest = video.requestVideoFrameCallback(onFrame)
    if (firstFrame === undefined) {
      firstFrame = meta.presentedFrames
      startTime = meta.presentationTime
    }
    const index = meta.presentedFrames - firstFrame
    const finished = Math.floor((index + 1) / FRAMES_PER_SEGMENT)
    if (finished > completed) {
      skipped.value += finished - completed
      if (sample && !analyzingFrame) {
        skipped.value--
        analyzeFrame(sample, id)
      }
      completed = finished
      sample = null
    }
    if (index % FRAMES_PER_SEGMENT === 0) {
      sample = { segment: Math.floor(index / FRAMES_PER_SEGMENT),
        time: (meta.presentationTime - startTime) / 1000, frame: captureFrame(video) }
    }
  }
  frameRequest = video.requestVideoFrameCallback(onFrame)
}

const startMonitor = async () => {
  if (!requireLogin() || changingSession.value || monitoring.value) return
  if (!selectedDevice.value || !selectedModel.value) return
  const id = ++session
  const modelId = selectedModel.value
  changingSession.value = true
  errorMsg.value = ''
  try {
    if (!mediaStream) await startCameraPreview()
    const video = videoRef.value
    if (!mediaStream || !video?.requestVideoFrameCallback) {
      throw new Error('Monitoring requires a camera and browser video frame callbacks')
    }
    if (preloadPromise && preloadModelId === modelId) await preloadPromise
    if (id !== session) return
    const { data } = await monitorAPI.start({ model_id: modelId, threshold: threshold.value })
    if (!data.success) throw new Error(data.error || 'Monitor start failed')
    if (id !== session) {
      await monitorAPI.stop()
      return
    }
    allScores.value = []
    samples.value = []
    currentScore.value = 0
    maxScore.value = 0
    skipped.value = 0
    analyzingFrame = false
    alertActive.value = false
    resetChartZoom()
    monitoring.value = true
    captureSegments(video, id)
    ElMessage.success('Monitor started')
  } catch (error) {
    if (id === session) errorMsg.value = error.response?.data?.error || error.message
  } finally {
    changingSession.value = false
  }
}

const stopMonitor = async () => {
  session++
  monitoring.value = false
  alertActive.value = false
  if (frameRequest !== null) videoRef.value?.cancelVideoFrameCallback(frameRequest)
  frameRequest = null
  changingSession.value = true
  try {
    await monitorAPI.stop()
  } finally {
    changingSession.value = false
  }
}

// Wrapper: require login before saving
const handleSaveResults = () => {
  if (!requireLogin()) return
  saveResults()
}

const handleSaveChart = () => {
  if (!requireLogin()) return
  saveChart()
}

// ================================================================
// Save chart as image
// ================================================================
const saveChart = () => {
  if (!chartInstance.value) {
    ElMessage.warning('No curve to save')
    return
  }
  const url = chartInstance.value.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#1e293b'
  })
  const link = document.createElement('a')
  const now = new Date()
  const ts = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}${String(now.getSeconds()).padStart(2,'0')}`
  link.href = url
  link.download = `anomaly_curve_${ts}.png`
  link.click()
  ElMessage.success('Curve image saved')
}

// Save results
// ================================================================
const saveResults = () => {
  if (allScores.value.length === 0) {
    ElMessage.warning('No data to save')
    return
  }

  const now = new Date()
  const timestamp = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}${String(now.getSeconds()).padStart(2,'0')}`

  // Build CSV content
  const lines = ['Segment,Time(s),AnomalyScore,IsAnomaly']
  allScores.value.forEach((score, i) => {
    const timeSec = samples.value[i].time.toFixed(3)
    const isAnomaly = score > threshold.value ? 'Yes' : 'No'
    lines.push(`${samples.value[i].segment},${timeSec},${score},${isAnomaly}`)
  })

  // Summary
  lines.push('')
  lines.push(`TotalSegments,${allScores.value.length}`)
  lines.push(`Threshold,${threshold.value}`)
  lines.push(`AlertCount,${alertCount.value}`)
  lines.push(`MaxScore,${maxScore.value}`)
  lines.push(`Model,${selectedModel.value}`)

  const csvContent = lines.join('\n')
  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `monitor_${timestamp}.csv`
  link.click()
  URL.revokeObjectURL(url)

  ElMessage.success(`Saved ${allScores.value.length} records`)
}

// ================================================================
// Models
// ================================================================
const loadModels = async () => {
  try {
    const res = await inferAPI.models()
    allModels.value = res.data.models || []
    const synth = models.value.find(m => m.synthetic)
    selectedModel.value = synth ? synth.id : models.value[0]?.id || ''
    preloadMonitorModel().catch(() => {})
  } catch {}
}

const preloadMonitorModel = async () => {
  if (!selectedModel.value) return

  const modelId = selectedModel.value
  if (preloadedModel.value === modelId && !preloadPromise) return
  if (preloadPromise && preloadModelId === modelId) return preloadPromise

  preloadModelId = modelId
  preloadingMonitor.value = true
  preloadPromise = monitorAPI.preload({ model_id: modelId })
    .then((res) => {
      if (res.data?.success && selectedModel.value === modelId) {
        preloadedModel.value = modelId
      }
      return res
    })
    .catch((error) => {
      if (preloadedModel.value === modelId) preloadedModel.value = ''
      console.warn('Monitor preload skipped:', error)
      throw error
    })
    .finally(() => {
      if (preloadModelId === modelId) {
        preloadingMonitor.value = false
        preloadPromise = null
      }
    })

  return preloadPromise
}

// ================================================================
// Chart
// ================================================================
const initChart = () => {
  if (!chartRef.value) return
  if (chartInstance.value) chartInstance.value.dispose()
  chartInstance.value = echarts.init(chartRef.value)
  chartInstance.value.on('datazoom', (params) => {
    const zoom = params.batch?.[0] || params
    if (typeof zoom.start !== 'number' || typeof zoom.end !== 'number') return
    chartZoomTouched = true
    chartZoomStart = zoom.start
    chartZoomEnd = zoom.end
    chartFollowLatest = zoom.end >= 99.5
  })
  window.addEventListener('resize', handleResize)
}

const handleResize = () => {
  chartInstance.value?.resize()
}

const resetChartZoom = () => {
  chartFollowLatest = true
  chartZoomTouched = false
  chartZoomStart = 0
  chartZoomEnd = 100
}

const updateChart = () => {
  if (!chartInstance.value) initChart()
  if (!chartInstance.value || allScores.value.length === 0) return

  const scores = allScores.value
  const xData = scores.map((_, i) => i)

  // Find anomaly areas
  const anomalyAreas = []
  let inAnomaly = false, aStart = 0
  for (let i = 0; i < scores.length; i++) {
    if (scores[i] > threshold.value && !inAnomaly) { inAnomaly = true; aStart = i }
    else if (scores[i] <= threshold.value && inAnomaly) { inAnomaly = false; anomalyAreas.push([{ xAxis: aStart }, { xAxis: i }]) }
  }
  if (inAnomaly) anomalyAreas.push([{ xAxis: aStart }, { xAxis: scores.length - 1 }])

  // Match Inference chart zoom behavior, keeping the latest window in view unless the user drags the slider.
  const viewWindow = 500
  const total = scores.length
  const startPct = total > viewWindow ? ((total - viewWindow) / total) * 100 : 0
  let zoomStart = chartZoomStart
  let zoomEnd = chartZoomEnd

  if (chartFollowLatest) {
    if (chartZoomTouched) {
      const zoomWidth = Math.max(1, chartZoomEnd - chartZoomStart)
      zoomStart = Math.max(0, 100 - zoomWidth)
    } else {
      zoomStart = startPct
    }
    zoomEnd = 100
    chartZoomStart = zoomStart
    chartZoomEnd = zoomEnd
  }

  const option = {
    animation: false,
    backgroundColor: 'transparent',
    grid: { left: 50, right: 16, top: 20, bottom: 50 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30,41,59,0.95)',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params) => {
        const idx = params[0]?.dataIndex
        if (idx == null) return ''
        const s = formatScore(scores[idx])
        const sec = samples.value[idx].time.toFixed(2)
        const isA = scores[idx] > threshold.value
        return `<div style="font-size:12px">
          <div style="color:#94a3b8">Seg #${samples.value[idx].segment} (${sec}s)</div>
          <div>Score: <b style="color:${isA ? '#ef4444' : '#6366f1'}">${s}</b></div>
          <div>Status: <b style="color:${isA ? '#ef4444' : '#10b981'}">${isA ? '⚠ Anomaly' : '✓ Normal'}</b></div>
        </div>`
      }
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xData,
      axisLabel: {
        color: '#94a3b8', fontSize: 10,
        formatter: (_, i) => samples.value[i].time.toFixed(1) + 's',
        interval: Math.max(1, Math.floor(scores.length / 20))
      },
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value', min: 0, max: 1, interval: 0.2,
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { lineStyle: { color: 'rgba(51,65,85,0.4)', type: 'dashed' } }
    },
    dataZoom: [
      {
        type: 'slider', start: zoomStart, end: zoomEnd, height: 20, bottom: 4,
        realtime: true, throttle: 16,
        borderColor: '#334155', backgroundColor: 'rgba(30,41,59,0.6)',
        fillerColor: 'rgba(99,102,241,0.15)',
        handleStyle: { color: '#6366f1', borderColor: '#6366f1' },
        textStyle: { color: '#94a3b8' },
        dataBackground: { lineStyle: { color: '#6366f1', opacity: 0.3 }, areaStyle: { color: '#6366f1', opacity: 0.1 } }
      },
      { type: 'inside', start: zoomStart, end: zoomEnd, realtime: true, throttle: 16 }
    ],
    series: [{
      name: 'Anomaly Score',
      type: 'line',
      data: scores,
      symbol: 'none',
      lineStyle: { color: '#6366f1', width: 1.5 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(99,102,241,0.25)' },
          { offset: 1, color: 'rgba(99,102,241,0.02)' }
        ])
      },
      markLine: {
        silent: true, symbol: 'none',
        data: [{
          yAxis: threshold.value,
          label: { formatter: `Threshold ${threshold.value}`, color: '#ef4444', fontSize: 11, position: 'insideEndTop' },
          lineStyle: { color: '#ef4444', type: 'dashed', width: 1.5 }
        }]
      },
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(239,68,68,0.15)' },
        data: anomalyAreas
      }
    }]
  }

  chartInstance.value.setOption(option, { notMerge: false, lazyUpdate: true })
}

// ================================================================
// Lifecycle
// ================================================================
watch(dataset, async () => {
  if (monitoring.value) await stopMonitor()
  else session++
  const synth = models.value.find(m => m.synthetic)
  selectedModel.value = synth ? synth.id : models.value[0]?.id || ''
  preloadMonitorModel().catch(() => {})
})

watch(selectedModel, () => {
  preloadMonitorModel().catch(() => {})
})

onMounted(async () => {
  await loadModels()

  // Check if mediaDevices API is available
  if (!checkMediaAPI()) {
    console.warn('MediaDevices API not available - camera features disabled')
    return
  }

  // Try to enumerate devices (may need permission first)
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    const videoDevices = devices.filter(d => d.kind === 'videoinput')
    if (videoDevices.length > 0 && videoDevices[0].label) {
      // Permission already granted
      cameraDevices.value = videoDevices.map((d, i) => ({
        deviceId: d.deviceId,
        label: d.label || `Camera ${i + 1}`,
        index: i + 1
      }))
      selectedDevice.value = cameraDevices.value[0].deviceId
      cameraReady.value = true
      await startCameraPreview()
    } else if (videoDevices.length > 0) {
      // Devices found but no labels = permission not yet granted
      // Don't auto-request, let user click the button
      console.log('Camera devices found but permission not yet granted')
    }
  } catch (e) {
    console.warn('Device enumeration failed:', e)
  }
})

onUnmounted(() => {
  // Cleanup
  if (monitoring.value) stopMonitor().catch(() => {})
  else session++
  if (mediaStream) mediaStream.getTracks().forEach(t => t.stop())
  window.removeEventListener('resize', handleResize)
  if (chartInstance.value) { chartInstance.value.dispose(); chartInstance.value = null }
})
</script>

<style scoped>
.monitor-view {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.monitor-grid {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.right-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.panel {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: border-color 0.3s;
}

.panel.alert-border {
  border-color: rgba(239, 68, 68, 0.6);
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.15);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.panel-icon {
  width: 34px;
  height: 34px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.panel-icon.green { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
.panel-icon.blue { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
.panel-icon.red {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  animation: pulse-red 1.5s ease-in-out infinite;
}

@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.panel-body {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.form-section { margin-bottom: 16px; }

.form-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.label-value {
  float: right;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}

.hint.error { color: #ef4444; }

.threshold-row {
  display: flex;
  align-items: center;
}

.threshold-row .el-slider { flex: 1; }

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.model-option-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stat-item {
  padding: 10px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  text-align: center;
  transition: background 0.3s;
}

.stat-item.alert-bg {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.danger-text { color: #ef4444 !important; }
.accent-text { color: #a78bfa; }

.status-badge {
  margin-left: auto;
  padding: 3px 10px;
  border-radius: 16px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.status-badge.running { background: rgba(16, 185, 129, 0.15); color: var(--success); }
.status-badge.alert { background: rgba(239, 68, 68, 0.2); color: #ef4444; animation: blink 1s ease-in-out infinite; }
.status-badge.warming { background: rgba(245, 158, 11, 0.18); color: var(--warning); }
.status-badge.ready { background: rgba(99, 102, 241, 0.18); color: var(--primary-light); }
.status-badge.idle { background: rgba(100, 116, 139, 0.15); color: var(--text-muted); }

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  animation: live-pulse 2s ease-in-out infinite;
}

.live-dot.alert { background: #ef4444; animation: alert-pulse 0.8s ease-in-out infinite; }

.live-text { font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 1px; }
.live-text.alert { color: #ef4444; }

@keyframes live-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.8); } }
@keyframes alert-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.3; transform: scale(1.3); } }

.video-body {
  flex: 1;
  position: relative;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-empty {
  position: absolute;
  inset: 0;
  background: rgba(30, 41, 59, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.alert-overlay {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(239, 68, 68, 0.9);
  border: 2px solid #ef4444;
  border-radius: 12px;
  padding: 12px 20px;
  text-align: center;
  color: white;
  animation: alert-bounce 0.5s ease-in-out;
  z-index: 10;
}

@keyframes alert-bounce {
  0% { transform: scale(0.8); opacity: 0; }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); opacity: 1; }
}

.alert-icon { font-size: 28px; line-height: 1; }
.alert-text { font-size: 14px; font-weight: 700; margin-top: 4px; }
.alert-score { font-size: 12px; opacity: 0.9; margin-top: 2px; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.btn-group { margin-top: 8px; padding-top: 8px; display: flex; gap: 10px; }
.btn-group.multi { display: flex; gap: 10px; }

.action-btn {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.action-btn.primary {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
}

.action-btn.secondary {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
}

.action-btn.primary:hover:not(:disabled),
.action-btn.secondary:hover:not(:disabled) {
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
  transform: translateY(-1px);
}

.action-btn.danger {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
}

.action-btn.save {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.action-btn.save:hover:not(:disabled) {
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.4);
  transform: translateY(-1px);
}

.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.error-msg {
  margin-top: 8px;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  font-size: 12px;
  color: var(--danger);
  display: flex;
  align-items: center;
  gap: 6px;
}

.video-panel { flex: 1; min-height: 0; }
.chart-panel { height: 240px; flex-shrink: 0; }
.save-chart-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border: 1px solid rgba(16, 185, 129, 0.4);
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}
.save-chart-btn:hover {
  background: rgba(16, 185, 129, 0.25);
  border-color: rgba(16, 185, 129, 0.6);
}
.chart-body { flex: 1; padding: 8px; min-height: 0; }
.chart-wrapper { width: 100%; height: 100%; }
.chart-container { width: 100%; height: 100%; min-height: 140px; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  gap: 6px;
}

.empty-state p { font-size: 15px; color: var(--text-secondary); margin: 6px 0 0 0; }
.empty-state span { font-size: 12px; text-align: center; max-width: 280px; }
</style>
