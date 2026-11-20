<template>
  <div class="analysis-view">
    <!-- Top Row: Test ROC AUC and run statistics -->
    <div class="top-row">
      <!-- Test ROC AUC panel -->
      <div class="panel chart-panel">
        <div class="panel-header">
          <div class="panel-icon green">
            <el-icon :size="20"><TrendCharts /></el-icon>
          </div>
          <span>Test ROC AUC by Iteration</span>
          
          <!-- Model Selectors -->
          <div class="model-selectors">
            <div class="selector-group">
              <span class="selector-label">Model A:</span>
              <el-select 
                v-model="selectedModelA" 
                placeholder="Select model" 
                size="small"
                @visible-change="refreshModelMenu"
              >
                <el-option
                  v-for="model in models"
                  :key="model.id"
                  :label="modelLabel(model)"
                  :value="model.id"
                />
              </el-select>
            </div>
            <div class="selector-group">
              <span class="selector-label">Model B:</span>
              <el-select 
                v-model="selectedModelB" 
                placeholder="Select model" 
                size="small"
                @visible-change="refreshModelMenu"
              >
                <el-option
                  v-for="model in models"
                  :key="model.id"
                  :label="modelLabel(model)"
                  :value="model.id"
                />
              </el-select>
            </div>
          </div>
          
          <div class="chart-legend">
            <span class="legend-item model-a">
              <span class="legend-dot" :style="{ background: selectedModelAColor }"></span>{{ selectedModelAName }}
            </span>
            <span class="legend-item model-b">
              <span class="legend-dot" :style="{ background: selectedModelBColor }"></span>{{ selectedModelBName }}
            </span>
          </div>
        </div>
        
        <div class="panel-body">
          <div ref="chartRef" class="chart-container"></div>
        </div>
      </div>
      
      <!-- Stats Column -->
      <div class="stats-column">
        <div class="stat-card">
          <div class="stat-icon blue">
            <el-icon :size="16"><VideoCamera /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ totalVideos ?? '—' }}</span>
            <span class="stat-label">Test Videos</span>
          </div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-icon green">
            <el-icon :size="16"><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ bestModel ? (bestModel.auc * 100).toFixed(2) + '%' : '—' }}</span>
            <span class="stat-label">Peak Test ROC AUC</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon orange">
            <el-icon :size="16"><Top /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value" :class="{ positive: peakDifference > 0 }">
              {{ peakDifference == null ? '—' : (peakDifference > 0 ? '+' : '') + (peakDifference * 100).toFixed(2) + ' pp' }}
            </span>
            <span class="stat-label" title="Difference between the selected runs’ peak test ROC AUC values, in percentage points.">Augmented − baseline</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon purple">
            <el-icon :size="16"><Timer /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ bestModel?.iters ?? '—' }}</span>
            <span class="stat-label">Last Eval. Iter.</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Bottom Row: Inference Score Plots -->
    <div class="bottom-row">
      <!-- Model A Inference Plot -->
      <div class="panel inference-panel">
        <div class="panel-header compact">
          <span class="legend-dot model-a" :style="{ background: selectedModelAColor }"></span>
          <span class="score-title" :title="selectedModelAName">{{ selectedModelAName }} — Anomaly Score</span>
          <el-select-v2 v-model="selectedVideo" :options="videoOptions" filterable size="small"
            class="test-video-select" aria-label="Test video for Model A" placeholder="Test video"
            :disabled="!videoOptions.length" />
        </div>
        <div class="panel-body">
          <div ref="inferChartARef" class="infer-chart-container"></div>
        </div>
      </div>
      
      <!-- Model B Inference Plot -->
      <div class="panel inference-panel">
        <div class="panel-header compact">
          <span class="legend-dot model-b" :style="{ background: selectedModelBColor }"></span>
          <span class="score-title" :title="selectedModelBName">{{ selectedModelBName }} — Anomaly Score</span>
          <el-select-v2 v-model="selectedVideo" :options="videoOptions" filterable size="small"
            class="test-video-select" aria-label="Test video for Model B" placeholder="Test video"
            :disabled="!videoOptions.length" />
        </div>
        <div class="panel-body">
          <div ref="inferChartBRef" class="infer-chart-container"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, inject, watch } from 'vue'
import { analysisAPI, inferAPI } from '../api'
import * as echarts from 'echarts'

const dataset = inject('dataset')
const chartRef = ref(null)
const inferChartARef = ref(null)
const inferChartBRef = ref(null)
let chartInstance = null
let inferChartAInstance = null
let inferChartBInstance = null

const selectedVideo = ref('')
const videoOptions = ref([])
const videoListMessage = ref('Loading test videos…')

const totalVideos = ref(null)
let comparisonRequest = 0
let inferenceRequest = 0
let videoListRequest = 0

const models = ref([])
const curves = ref({})

const selectedModelA = ref(null)
const selectedModelB = ref(null)

const modelA = computed(() => models.value.find(model => model.id === selectedModelA.value))
const modelB = computed(() => models.value.find(model => model.id === selectedModelB.value))
const selectedModelAName = computed(() => modelA.value?.name || 'Model A')
const selectedModelBName = computed(() => modelB.value?.name || 'Model B')
const compared = computed(() => [modelA.value, modelB.value].filter(model => Number.isFinite(model?.auc)))
const bestModel = computed(() => compared.value.reduce((best, model) => !best || model.auc > best.auc ? model : best, null))
const peakDifference = computed(() => {
  const baseline = compared.value.find(model => model.synthetic === false)
  const augmented = compared.value.find(model => model.synthetic === true)
  return baseline && augmented ? augmented.auc - baseline.auc : null
})

const modelRoleStyle = (modelId) => {
  const model = models.value.find(m => m.id === modelId)
  if (model?.synthetic) {
    return {
      line: '#10b981',
      areaTop: 'rgba(16, 185, 129, 0.4)',
      areaBottom: 'rgba(16, 185, 129, 0.05)',
      curveAreaTop: 'rgba(16, 185, 129, 0.3)',
      curveAreaBottom: 'rgba(16, 185, 129, 0.05)'
    }
  }
  return {
    line: '#64748b',
    areaTop: 'rgba(100, 116, 139, 0.4)',
    areaBottom: 'rgba(100, 116, 139, 0.05)',
    curveAreaTop: 'rgba(100, 116, 139, 0.3)',
    curveAreaBottom: 'rgba(100, 116, 139, 0.05)'
  }
}

const selectedModelAColor = computed(() => modelRoleStyle(selectedModelA.value).line)
const selectedModelBColor = computed(() => modelRoleStyle(selectedModelB.value).line)

const modelLabel = (model) => Number.isFinite(model.auc)
  ? `${model.name} (${(model.auc * 100).toFixed(2)}%)` : model.name

const loadModels = async () => {
  const request = ++comparisonRequest
  try {
    const { data } = await analysisAPI.comparison(dataset.value)
    if (request !== comparisonRequest || !data.success) return
    models.value = data.models
    curves.value = data.curves
    totalVideos.value = data.ground_truth?.total_videos ?? null
    const recorded = data.models.filter(model => Number.isFinite(model.auc) || model.available)
      .sort((a, b) => Number(b.available) - Number(a.available))
    const augmented = recorded.find(model => model.synthetic === true)
    const baseline = recorded.find(model => model.synthetic === false)
    if (!modelA.value) selectedModelA.value = (augmented || recorded[0])?.id ?? null
    if (!modelB.value) {
      selectedModelB.value = (baseline?.id !== selectedModelA.value ? baseline : null)?.id
        ?? recorded.find(model => model.id !== selectedModelA.value)?.id ?? null
    }
  } catch (error) {
    console.error('Failed to load analysis data:', error)
  }
}

const refreshModelMenu = (open) => {
  if (open) loadModels()
}

const loadData = async () => {
  const request = ++videoListRequest
  const ds = dataset.value
  totalVideos.value = null
  models.value = []
  curves.value = {}
  selectedModelA.value = null
  selectedModelB.value = null
  videoOptions.value = []
  selectedVideo.value = ''
  videoListMessage.value = 'Loading test videos…'
  loadModels()
  try {
    const { data } = await inferAPI.videos(ds)
    if (request !== videoListRequest) return
    videoOptions.value = data.videos.map(name => ({ label: name, value: name }))
    const preferred = ds === 'ucf-crime' ? 'Robbery050_x264' : '01_0025'
    selectedVideo.value = data.videos.includes(preferred) ? preferred : data.videos[0] || ''
    videoListMessage.value = selectedVideo.value ? '' : 'No test videos in this split'
  } catch {
    if (request === videoListRequest) videoListMessage.value = 'Test video list unavailable'
  }
}

const renderTrainingChart = () => {
  if (!chartRef.value) return
  
  if (chartInstance) {
    chartInstance.dispose()
  }
  
  chartInstance = echarts.init(chartRef.value)
  
  const series = []
  const styleA = modelRoleStyle(selectedModelA.value)
  const styleB = modelRoleStyle(selectedModelB.value)
  
  // Draw selected two model curves
  const selectedModels = [
    { id: selectedModelA.value, color: styleA.line, areaTop: styleA.curveAreaTop, areaBottom: styleA.curveAreaBottom, key: 'A' },
    { id: selectedModelB.value, color: styleB.line, areaTop: styleB.curveAreaTop, areaBottom: styleB.curveAreaBottom, key: 'B' }
  ]

  for (const selected of selectedModels) {
    if (!selected.id) continue
    const curveData = curves.value[selected.id]
    const model = models.value.find(m => m.id === selected.id)
    if (!model) continue

    if (curveData?.iterations?.length) {
      series.push({
        name: model.name,
        type: 'line',
        symbol: 'none',
        data: curveData.iterations.map((iter, idx) => [iter, curveData.auc_values[idx]]),
        lineStyle: {
          width: selected.key === 'B' ? 3 : 2,
          color: selected.color
        },
        areaStyle: selected.key === 'B' ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: selected.areaTop },
            { offset: 1, color: selected.areaBottom }
          ])
        } : null
      })
    }
  }

  const option = {
    backgroundColor: 'transparent',
    title: series.length ? undefined : { text: 'No evaluation records', left: 'center', top: 'middle',
      textStyle: { color: '#94a3b8', fontSize: 12, fontWeight: 'normal' } },
    grid: {
      left: 55,
      right: 20,
      top: 15,
      bottom: 35
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 41, 59, 0.95)',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc' },
      formatter: (params) => {
        let html = `<div style="font-weight:600;margin-bottom:8px">Iter ${params[0].data[0]}</div>`
        params.forEach(p => {
          const color = selectedModels[p.seriesIndex]?.color || '#94a3b8'
          html += `<div style="display:flex;align-items:center;gap:8px">
            <span style="width:10px;height:10px;background:${color};border-radius:50%"></span>
            <span>${p.seriesName}: ${(p.data[1] * 100).toFixed(2)}%</span>
          </div>`
        })
        return html
      }
    },
    xAxis: {
      type: 'value',
      name: 'Iterations',
      nameTextStyle: { color: '#64748b', padding: [0, 0, 0, -20] },
      nameLocation: 'end',
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#1e293b' } },
      min: 0
    },
    yAxis: {
      type: 'value',
      name: 'ROC AUC (%)',
      nameTextStyle: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { 
        color: '#94a3b8',
        fontSize: 11,
        formatter: (val) => (val * 100).toFixed(0)
      },
      splitLine: { lineStyle: { color: '#1e293b' } },
      min: 0,
      max: 1.0,
      interval: 0.1
    },
    series: series
  }
  
  chartInstance.setOption(option)
}

const renderInferenceChart = (target, payload, color, areaTopColor, areaBottomColor) => {
  const chartEl = target === 'A' ? inferChartARef.value : inferChartBRef.value
  if (!chartEl) return

  if (target === 'A' && inferChartAInstance) inferChartAInstance.dispose()
  if (target === 'B' && inferChartBInstance) inferChartBInstance.dispose()

  const chart = echarts.init(chartEl)
  if (target === 'A') inferChartAInstance = chart
  if (target === 'B') inferChartBInstance = chart

  if (!payload?.success) {
    chart.setOption({
      backgroundColor: 'transparent',
      title: {
        text: payload?.error || 'No inference data',
        left: 'center',
        top: 'middle',
        textStyle: { color: '#94a3b8', fontSize: 12, fontWeight: 400 }
      }
    })
    return
  }

  const scoreData = payload.frame_scores.map((score, frame) => [frame, score])
  const gtAreas = payload.gt_regions.map(region => ([
    {
      xAxis: region.start_frame,
      itemStyle: { color: 'rgba(239, 68, 68, 0.18)' },
      label: {
        show: true,
        formatter: 'GT',
        position: 'insideBottom',
        distance: 18,
        color: '#fecaca',
        fontSize: 10,
        backgroundColor: 'rgba(127, 29, 29, 0.72)',
        borderRadius: 3,
        padding: [2, 5]
      }
    },
    { xAxis: region.end_frame }
  ]))
  const frameLabels = payload.frame_labels || []

  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 45, right: 15, top: 10, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 41, 59, 0.95)',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 11 },
      formatter: (params) => {
        const frame = params[0].data[0]
        const score = params[0].data[1]
        const gt = frameLabels[frame] > 0 ? 'Anomaly' : 'Normal'
        return `Frame ${frame}<br/>Anomaly score: ${score.toFixed(4)}<br/>Ground truth: ${gt}`
      }
    },
    xAxis: {
      type: 'value',
      name: 'Frame',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { show: false },
      min: 0
    },
    yAxis: {
      type: 'value',
      name: 'Score',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      min: 0,
      max: 1,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [{
      type: 'line',
      step: 'end',
      symbol: 'none',
      data: scoreData,
      lineStyle: { width: 1.5, color },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: areaTopColor },
          { offset: 1, color: areaBottomColor }
        ])
      },
      markArea: {
        silent: true,
        data: gtAreas
      }
    }]
  })
}

const renderInferenceCharts = async () => {
  const request = ++inferenceRequest
  const selectedDataset = dataset.value
  const video = selectedVideo.value
  const slots = [['A', modelA.value], ['B', modelB.value]]
  const draw = ([slot, model], payload) => {
    const style = modelRoleStyle(model?.id)
    renderInferenceChart(slot, payload, style.line, style.areaTop, style.areaBottom)
  }
  const results = await Promise.all(slots.map(async (slot) => {
    const model = slot[1]
    if (!video) return { error: videoListMessage.value }
    if (!model?.available) return { error: model ? 'Checkpoint unavailable' : 'No model selected' }
    draw(slot, { error: 'Loading inference scores…' })
    try {
      const { data } = await analysisAPI.inferScore(selectedDataset, model.id, video)
      return data
    } catch {
      return { error: 'Inference scores unavailable' }
    }
  }))
  if (request === inferenceRequest) {
    slots.forEach((slot, index) => draw(slot, results[index]))
  }
}

// Handle resize
const handleResize = () => {
  if (chartInstance) chartInstance.resize()
  if (inferChartAInstance) inferChartAInstance.resize()
  if (inferChartBInstance) inferChartBInstance.resize()
}

watch([curves, selectedModelA, selectedModelB], renderTrainingChart, { flush: 'post' })
watch([selectedVideo, selectedModelA, selectedModelB, videoListMessage,
  () => modelA.value?.available, () => modelB.value?.available,
  () => modelA.value?.auc, () => modelB.value?.auc], renderInferenceCharts, { flush: 'post' })
watch(dataset, loadData)

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  comparisonRequest++
  inferenceRequest++
  videoListRequest++
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  inferChartAInstance?.dispose()
  inferChartBInstance?.dispose()
})
</script>

<style scoped>
.analysis-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 120px);
}

/* Top Row: Test ROC AUC and run statistics */
.top-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* Stats Column - Single Column */
.stats-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  transition: all 0.2s;
  flex: 1;
  text-align: center;
}

.stat-card.highlight {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
}

.stat-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  margin-left: 8px;
}

.stat-icon.blue {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
}

.stat-icon.green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.stat-icon.orange {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.stat-icon.purple {
  background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
}

.stat-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.stat-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-value.positive {
  color: #10b981;
}

.stat-label {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.2;
}

/* Bottom Row: Inference Plots */
.bottom-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  height: 200px;
  flex-shrink: 0;
}

.panel {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel.chart-panel {
  flex: 1;
  min-height: 0;
}

.panel.inference-panel {
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.panel-header.compact {
  padding: 10px 14px;
  font-size: 13px;
  gap: 8px;
}

.score-title {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.test-video-select {
  width: 48%;
  max-width: 240px;
}

.analysis-view :deep(.el-select__placeholder:not(.is-transparent)),
.test-video-select :deep(.el-select__input) {
  color: var(--text-primary);
}

.panel-header .legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.panel-header .legend-dot.model-a {
  background: #64748b;
}

.panel-header .legend-dot.model-b {
  background: #10b981;
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
  flex-shrink: 0;
}

.panel-icon.green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.panel-body {
  flex: 1;
  padding: 12px;
  overflow: hidden;
  min-height: 0;
}

.chart-container {
  width: 100%;
  height: 100%;
}

.infer-chart-container {
  width: 100%;
  height: 100%;
}

/* Comparison Section */
.comparison-section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
}

.title-icon {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.title-icon.baseline {
  background: #64748b;
}

.title-icon.synthetic {
  background: #10b981;
}

.model-card {
  padding: 16px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 10px;
  border-left: 4px solid #64748b;
}

.model-card.synthetic {
  border-left-color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.model-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.model-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.model-iters {
  font-size: 12px;
  color: var(--text-muted);
  background: rgba(51, 65, 85, 0.5);
  padding: 4px 10px;
  border-radius: 12px;
}

.auc-display {
  display: flex;
  align-items: center;
  gap: 12px;
}

.auc-bar-container {
  flex: 1;
  height: 8px;
  background: rgba(51, 65, 85, 0.5);
  border-radius: 4px;
  overflow: hidden;
}

.auc-bar {
  height: 100%;
  background: linear-gradient(90deg, #64748b, #94a3b8);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.auc-bar.synthetic {
  background: linear-gradient(90deg, #10b981, #34d399);
}

.auc-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  min-width: 80px;
  text-align: right;
}

.comparison-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 20px 0;
}

.divider-text {
  padding: 8px 16px;
  background: var(--bg-hover);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 2px;
}

.peakDifference-summary {
  margin-top: 20px;
  padding: 16px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.peakDifference-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.peakDifference-text {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.peakDifference-text .label {
  font-size: 12px;
  color: var(--text-muted);
}

.peakDifference-text .value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.peakDifference-text .value.positive {
  color: #10b981;
}

.peakDifference-detail {
  width: 100%;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  padding-left: 52px;
}

/* Comparison Table */
.comparison-table {
  margin-top: 20px;
  padding: 16px;
  background: rgba(51, 65, 85, 0.2);
  border-radius: 12px;
}

.table-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.comparison-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  background: rgba(30, 41, 59, 0.6);
  border-radius: 10px;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.comparison-item.baseline {
  border-color: rgba(100, 116, 139, 0.3);
}

.comparison-item.current {
  border-color: rgba(99, 102, 241, 0.3);
}

.comparison-item.best {
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.1);
}

.comparison-item.empty {
  opacity: 0.6;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.item-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.item-dot.baseline {
  background: #64748b;
}

.item-dot.current {
  background: #6366f1;
}

.item-dot.best {
  background: #10b981;
}

.item-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.crown-icon {
  color: #fbbf24;
  margin-left: 4px;
}

.item-auc {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.item-auc.highlight {
  color: #10b981;
}

.item-info {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.item-diff {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(100, 116, 139, 0.2);
  color: var(--text-secondary);
}

.item-diff.positive {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.item-empty {
  font-size: 13px;
  color: var(--text-muted);
  padding: 20px 0;
}

.no-model {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  background: rgba(51, 65, 85, 0.2);
  border-radius: 10px;
}

/* Chart Panel */
.chart-legend {
  display: flex;
  gap: 12px;
  flex: 0 1 280px;
  min-width: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-item.baseline .legend-dot,
.legend-item.model-a .legend-dot {
  background: #64748b;
}

.legend-item.synthetic .legend-dot,
.legend-item.model-b .legend-dot {
  background: #10b981;
}

/* Model Selectors */
.model-selectors {
  display: flex;
  gap: 16px;
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: wrap;
}

.selector-group {
  min-width: 0;
  flex: 1 1 155px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.selector-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}

.selector-group .el-select {
  min-width: 0;
  flex: 1;
}
.chart-panel .panel-header {
  flex-wrap: wrap;
}
</style>
