<template>
  <div class="infer-view">
    <div class="top-row">
      <div class="panel config-panel">
        <div class="panel-header">
          <div class="panel-icon"><el-icon :size="20"><Cpu /></el-icon></div>
          <span>Infer Settings</span>
        </div>
        <div class="panel-body">
          <div class="form-section">
            <label class="form-label">Model</label>
            <el-select v-model="selectedModel" placeholder="Select model" style="width: 100%" :disabled="inferring">
              <el-option v-for="model in models" :key="model.id" :label="model.name" :value="model.id">
                <div class="model-option">
                  <span class="model-option-name">{{ model.name }}</span>
                  <span class="model-auc" v-if="Number.isFinite(model.auc)">Logged peak: {{ (model.auc * 100).toFixed(2) }}%</span>
                </div>
              </el-option>
            </el-select>
          </div>
          <div class="form-section">
            <label class="form-label">Configured Test Split</label>
            <div class="test-set-info">
              <el-icon><VideoCamera /></el-icon>
              <span>{{ dataset === 'ucf-crime' ? 'UCF-Crime' : 'ShanghaiTech' }} Test Split</span>
            </div>
          </div>
          <div class="btn-group">
            <button class="action-btn primary" :disabled="inferring || !selectedModel" @click="startInference">
              <el-icon v-if="inferring" class="spin"><Loading /></el-icon>
              <el-icon v-else><Aim /></el-icon>
              <span>{{ inferring ? 'Inferring...' : 'Start Infer' }}</span>
            </button>
            <button v-if="inferring" class="action-btn danger" @click="stopInference">
              <el-icon><Close /></el-icon>
              <span>Stop</span>
            </button>
          </div>
        </div>
      </div>
      <div class="panel progress-panel">
        <div class="panel-header">
          <div class="panel-icon" :class="{ green: inferring }"><el-icon :size="20"><DataLine /></el-icon></div>
          <span>Infer Progress</span>
          <div class="status-badge" :class="inferring ? 'running' : (progress.done ? 'done' : 'idle')">
            {{ inferring ? 'Inferring' : (progress.done ? 'Done' : (aucError ? 'Incomplete' : 'Idle')) }}
          </div>
        </div>
        <div class="panel-body progress-body">
          <div v-if="progress.total > 0" class="progress-content">
            <div class="progress-stats">
              <div class="progress-main">
                <span class="progress-num">{{ progress.current }}</span>
                <span class="progress-sep">/</span>
                <span class="progress-total">{{ progress.total }}</span>
              </div>
              <span class="progress-pct">{{ progressPct }}%</span>
            </div>
            <el-progress :percentage="progressPct" :stroke-width="16" :striped="inferring" :striped-flow="inferring" :color="inferring ? '#6366f1' : '#10b981'" :show-text="false" />
            <div class="progress-detail">
              <span>Current: {{ progress.currentVideo || '--' }}</span>
              <span v-if="progress.errors > 0" class="error-count">Errors: {{ progress.errors }}</span>
            </div>
            <div class="anomaly-summary" v-if="results.length > 0" title="A video is predicted anomalous when its maximum segment score exceeds 0.5.">
              <div class="summary-item"><span class="summary-value">{{ anomalyCount }}</span><span class="summary-label">Predicted Anomaly</span></div>
              <div class="summary-item"><span class="summary-value">{{ normalCount }}</span><span class="summary-label">Predicted Normal</span></div>
              <div class="summary-item"><span class="summary-value danger">{{ maxScoreOverall.toFixed(4) }}</span><span class="summary-label">Max Score</span></div>
            </div>
          </div>
          <div v-else class="empty-state small"><el-icon :size="36"><Aim /></el-icon><p>Awaiting inference</p></div>
        </div>
      </div>
    </div>
    <div class="bottom-row">
      <div class="panel auc-panel">
        <div class="panel-header">
          <div class="panel-icon green"><el-icon :size="20"><TrendCharts /></el-icon></div>
          <span>Frame-level ROC AUC</span>
        </div>
        <div class="panel-body auc-body">
          <div v-if="aucResult !== null" class="auc-display">
            <div class="auc-value-big" :class="{ good: aucResult > 0.9 }">{{ (aucResult * 100).toFixed(2) }}<span class="auc-unit">%</span></div>
            <div class="auc-label">Pooled over scored frames</div>
            <div class="auc-detail" v-if="coverage">{{ coverage.num_videos }}/{{ coverage.expected_videos }} test videos<br>{{ coverage.num_frames.toLocaleString() }}/{{ coverage.annotated_frames.toLocaleString() }} annotated frames</div>
          </div>
          <div v-else-if="inferring || aucCalculating" class="auc-loading">
            <el-icon class="spin" :size="24"><Loading /></el-icon>
            <span>{{ aucCalculating ? 'Calculating...' : 'Waiting for all test videos...' }}</span>
          </div>
          <div v-else-if="aucError" class="auc-error">{{ aucError }}</div>
          <div v-else class="empty-state small"><el-icon :size="36"><TrendCharts /></el-icon><p>Available after inference</p></div>
        </div>
      </div>
      <div class="panel plot-panel">
        <div class="panel-header">
          <div class="panel-icon blue"><el-icon :size="20"><PictureFilled /></el-icon></div>
          <span>Anomaly Score Curve</span>
          <div class="header-right" v-if="results.length > 0"><el-tag size="small" type="info">{{ results.length }} videos</el-tag></div>
        </div>
        <div class="panel-body plot-body">
          <div v-if="allPlotScores.length > 0" class="chart-wrapper"><div ref="chartRef" class="chart-container"></div></div>
          <div v-else class="empty-state small"><el-icon :size="36"><PictureFilled /></el-icon><p>Score curve shown after inference</p></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject, watch, nextTick, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import { inferAPI, analysisAPI } from '../api'
import * as echarts from 'echarts'

const dataset = inject('dataset')
const requireLogin = inject('requireLogin')
const allModels = ref([])
const selectedModel = ref('')
const models = computed(() => allModels.value.filter(m => m.dataset === dataset.value && m.available))
const inferring = ref(false)
let runId = 0
const results = ref([])
const allPredictions = ref({})
const allPlotScores = ref([])

const progress = ref({ current: 0, total: 0, errors: 0, done: false, currentVideo: '' })
const progressPct = computed(() => progress.value.total === 0 ? 0 : Math.round((progress.value.current / progress.value.total) * 100))
const anomalyCount = computed(() => results.value.filter(r => r.is_anomaly).length)
const normalCount = computed(() => results.value.filter(r => !r.is_anomaly).length)
const maxScoreOverall = computed(() => results.value.length === 0 ? 0 : Math.max(...results.value.map(r => r.max_score)))

const aucResult = ref(null)
const coverage = ref(null)
const aucCalculating = ref(false)
const aucError = ref('')
const chartRef = ref(null)
let chartInstance = shallowRef(null)
let chartFollowLatest = true
let chartZoomTouched = false
let chartZoomStart = 0
let chartZoomEnd = 100

const loadModels = async () => {
  try {
    const res = await inferAPI.models()
    allModels.value = res.data.models || []
    selectDefaultModel()
  } catch {}
}

const selectDefaultModel = () => {
  const synth = models.value.find(m => m.synthetic)
  selectedModel.value = synth ? synth.id : models.value[0]?.id || ''
}

const resetInference = () => {
  runId++
  inferring.value = false
  results.value = []
  allPredictions.value = {}
  allPlotScores.value = []
  aucResult.value = null
  coverage.value = null
  aucCalculating.value = false
  aucError.value = ''
  chartInstance.value?.dispose()
  chartInstance.value = null
  resetChartZoom()
  progress.value = { current: 0, total: 0, errors: 0, done: false, currentVideo: '' }
}

const startInference = async () => {
  if (!requireLogin() || !selectedModel.value || inferring.value) return
  resetInference()
  const id = runId
  const runDataset = dataset.value
  const modelId = selectedModel.value
  inferring.value = true
  try {
    const { data } = await inferAPI.videos(runDataset)
    if (id !== runId) return
    const videos = data.videos
    if (!videos?.length) throw new Error('No standard test videos found')
    progress.value.total = videos.length
    let firstFailure = ''
    for (const video of videos) {
      if (id !== runId) return
      progress.value.currentVideo = video
      try {
        const { data: prediction } = await inferAPI.predict({ video_name: video, model_id: modelId })
        if (id !== runId) return
        if (!prediction.success) throw new Error(prediction.error || 'Prediction failed')
        const scores = prediction.scores
        results.value.push({
          video_id: video, video_name: video, is_anomaly: prediction.max_score > 0.5,
          avg_score: prediction.mean_score, max_score: prediction.max_score, scores,
          num_segments: prediction.num_segments
        })
        allPredictions.value[video] = scores
        for (const score of scores) allPlotScores.value.push(score)
        await nextTick()
        if (id !== runId) return
        updateChart()
      } catch (error) {
        if (id !== runId) return
        progress.value.errors++
        if (!firstFailure) firstFailure = video + ': ' + (error.response?.data?.error || error.message)
      }
      progress.value.current++
    }
    if (progress.value.errors) {
      aucError.value = results.value.length + '/' + videos.length + ' videos scored. ' + firstFailure
      return
    }
    aucCalculating.value = true
    const { data: metric } = await analysisAPI.auc({ predictions: allPredictions.value, dataset: runDataset })
    if (id !== runId) return
    if (!metric.success || metric.scope !== 'standard' || !Number.isFinite(metric.auc)
        || metric.num_videos !== videos.length || metric.expected_videos !== videos.length) {
      throw new Error(metric.error || 'Incomplete standard test evaluation')
    }
    aucResult.value = metric.auc
    coverage.value = metric
    progress.value.done = true
    ElMessage.success('Inference completed')
  } catch (error) {
    if (id === runId) aucError.value = error.response?.data?.error || error.message
  } finally {
    if (id === runId) {
      inferring.value = false
      aucCalculating.value = false
    }
  }
}

const stopInference = () => {
  runId++
  inferring.value = false
  aucCalculating.value = false
  aucError.value = 'Stopped after scoring ' + results.value.length + '/' + progress.value.total + ' videos.'
}

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
const handleResize = () => { chartInstance.value?.resize() }

const resetChartZoom = () => {
  chartFollowLatest = true
  chartZoomTouched = false
  chartZoomStart = 0
  chartZoomEnd = 100
}

const updateChart = () => {
  if (!chartInstance.value) initChart()
  if (!chartInstance.value || allPlotScores.value.length === 0) return
  const scores = allPlotScores.value
  const xData = scores.map((_, i) => i)
  const anomalyAreas = []
  let inA = false, aStart = 0
  for (let i = 0; i < scores.length; i++) {
    if (scores[i] > 0.5 && !inA) { inA = true; aStart = i }
    else if (scores[i] <= 0.5 && inA) { inA = false; anomalyAreas.push([{ xAxis: aStart }, { xAxis: i }]) }
  }
  if (inA) anomalyAreas.push([{ xAxis: aStart }, { xAxis: scores.length - 1 }])

  const videoMarks = []
  let offset = 0
  for (const r of results.value) {
    if (offset > 0) videoMarks.push({ xAxis: offset, label: { show: false }, lineStyle: { color: '#334155', type: 'dashed', width: 1 } })
    offset += r.scores.length
  }

  const viewWindow = 500
  const startPct = scores.length > viewWindow ? ((scores.length - viewWindow) / scores.length) * 100 : 0
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

  chartInstance.value.setOption({
    animation: false,
    backgroundColor: 'transparent',
    grid: { left: 50, right: 16, top: 20, bottom: 50 },
    tooltip: {
      trigger: 'axis', backgroundColor: 'rgba(30,41,59,0.95)', borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params) => {
        const idx = params[0]?.dataIndex
        if (idx == null) return ''
        const s = scores[idx]?.toFixed(4) || '0'
        const isA = scores[idx] > 0.5
        let cumLen = 0, vName = ''
        for (const r of results.value) { cumLen += r.scores.length; if (idx < cumLen) { vName = r.video_name; break } }
        return '<div style="font-size:12px"><div style="color:#94a3b8">Segment #' + idx + '</div><div style="color:#94a3b8">' + vName + '</div><div>Score: <b style="color:' + (isA ? '#ef4444' : '#6366f1') + '">' + s + '</b></div></div>'
      }
    },
    xAxis: { type: 'category', data: xData, axisLabel: { color: '#94a3b8', fontSize: 10, interval: Math.max(1, Math.floor(scores.length / 20)) }, axisLine: { lineStyle: { color: '#334155' } }, splitLine: { show: false } },
    yAxis: { type: 'value', min: 0, max: 1, interval: 0.2, axisLabel: { color: '#94a3b8', fontSize: 10 }, axisLine: { lineStyle: { color: '#334155' } }, splitLine: { lineStyle: { color: 'rgba(51,65,85,0.4)', type: 'dashed' } } },
    dataZoom: [
      { type: 'slider', start: zoomStart, end: zoomEnd, realtime: true, throttle: 16, height: 20, bottom: 4, borderColor: '#334155', backgroundColor: 'rgba(30,41,59,0.6)', fillerColor: 'rgba(99,102,241,0.15)', handleStyle: { color: '#6366f1', borderColor: '#6366f1' }, textStyle: { color: '#94a3b8' }, dataBackground: { lineStyle: { color: '#6366f1', opacity: 0.3 }, areaStyle: { color: '#6366f1', opacity: 0.1 } } },
      { type: 'inside', start: zoomStart, end: zoomEnd, realtime: true, throttle: 16 }
    ],
    series: [{
      name: 'Anomaly Score', type: 'line', data: scores, symbol: 'none',
      lineStyle: { color: '#6366f1', width: 1 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(99,102,241,0.3)' }, { offset: 1, color: 'rgba(99,102,241,0.02)' }]) },
      markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0.5, label: { formatter: 'Threshold 0.5', color: '#ef4444', fontSize: 10, position: 'insideEndTop' }, lineStyle: { color: '#ef4444', type: 'dashed', width: 1 } }, ...videoMarks] },
      markArea: { silent: true, itemStyle: { color: 'rgba(239,68,68,0.1)' }, data: anomalyAreas }
    }]
  }, { notMerge: false, lazyUpdate: true })
}

watch(dataset, () => {
  resetInference()
  selectDefaultModel()
})
watch(selectedModel, resetInference, { flush: 'sync' })

onMounted(() => { loadModels() })
onUnmounted(() => {
  runId++
  window.removeEventListener('resize', handleResize)
  if (chartInstance.value) { chartInstance.value.dispose(); chartInstance.value = null }
})
</script>

<style scoped>
.infer-view { height: calc(100vh - 120px); display: flex; flex-direction: column; gap: 16px; }
.top-row { display: grid; grid-template-columns: 300px 1fr; gap: 16px; height: 270px; flex-shrink: 0; }
.bottom-row { display: grid; grid-template-columns: 300px 1fr; gap: 16px; flex: 1; min-height: 0; }
.panel { background: rgba(30, 41, 59, 0.6); border: 1px solid var(--border-color); border-radius: var(--radius); display: flex; flex-direction: column; overflow: hidden; }
.panel-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--border-color); font-weight: 600; font-size: 13px; flex-shrink: 0; }
.panel-icon { width: 32px; height: 32px; background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; flex-shrink: 0; }
.panel-icon.green { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
.panel-icon.blue { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
.panel-body { flex: 1; padding: 12px 14px; display: flex; flex-direction: column; overflow: hidden; }
.config-panel .panel-body { overflow: hidden; }
.form-section { margin-bottom: 10px; }
.form-label { display: block; font-size: 11px; font-weight: 500; color: var(--text-muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.model-option { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.model-option-name { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.model-auc { font-size: 11px; color: var(--text-muted); margin-left: 8px; }
.test-set-info { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; font-size: 12px; color: var(--success); }
.btn-group { display: flex; gap: 8px; margin-top: auto; padding-top: 8px; }
.action-btn { flex: 1; padding: 10px; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s; }
.action-btn.primary { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); color: white; }
.action-btn.danger { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.status-badge { margin-left: auto; padding: 3px 10px; border-radius: 16px; font-size: 11px; font-weight: 600; }
.status-badge.running { background: rgba(99, 102, 241, 0.2); color: var(--primary-light); }
.status-badge.done { background: rgba(16, 185, 129, 0.2); color: var(--success); }
.status-badge.idle { background: rgba(100, 116, 139, 0.15); color: var(--text-muted); }
.progress-body { gap: 10px; }
.progress-content { display: flex; flex-direction: column; gap: 10px; }
.progress-stats { display: flex; justify-content: space-between; align-items: baseline; }
.progress-main { display: flex; align-items: baseline; gap: 2px; }
.progress-num { font-size: 28px; font-weight: 700; color: var(--primary-light); }
.progress-sep { font-size: 18px; color: var(--text-muted); margin: 0 4px; }
.progress-total { font-size: 18px; color: var(--text-secondary); }
.progress-pct { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.progress-detail { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); }
.error-count { color: var(--danger); }
.anomaly-summary { display: flex; gap: 12px; margin-top: 4px; }
.summary-item { flex: 1; text-align: center; padding: 6px; background: rgba(51, 65, 85, 0.3); border-radius: 6px; }
.summary-value { display: block; font-size: 16px; font-weight: 700; color: var(--text-primary); }
.summary-value.danger { color: var(--danger); }
.summary-label { font-size: 10px; color: var(--text-muted); }
.auc-body { align-items: center; justify-content: center; }
.auc-display { text-align: center; }
.auc-value-big { font-size: 48px; font-weight: 800; color: var(--text-primary); line-height: 1; font-variant-numeric: tabular-nums; }
.auc-value-big.good { color: #10b981; }
.auc-unit { font-size: 24px; font-weight: 600; opacity: 0.7; }
.auc-label { font-size: 13px; color: var(--text-muted); margin-top: 8px; letter-spacing: 0.5px; }
.auc-detail { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.auc-loading { display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 13px; }
.auc-error { color: var(--danger); font-size: 13px; text-align: center; line-height: 1.5; }
.plot-body { padding: 8px; }
.chart-wrapper { width: 100%; height: 100%; }
.chart-container { width: 100%; height: 100%; min-height: 200px; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); gap: 4px; }
.empty-state.small p { font-size: 13px; margin: 4px 0 0 0; color: var(--text-secondary); }
.header-right { margin-left: auto; }
</style>
