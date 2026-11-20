<template>
  <div class="train-view">
    <div class="panel-row">
      <!-- Config Panel -->
      <div class="panel config-panel">
        <div class="panel-header">
          <div class="panel-icon">
            <el-icon :size="20"><Setting /></el-icon>
          </div>
          <span>Train Config</span>
        </div>
        
        <div class="panel-body">
          <div class="form-section">
            <label class="form-label">Experiment</label>
            <el-input v-model="trainForm.expName" placeholder="e.g. sht_exp_001" />
          </div>
          
          <div class="form-row">
            <div class="form-section">
              <label class="form-label">Seed</label>
              <el-input-number v-model="trainForm.seed" :min="1" :max="1" disabled style="width: 100%" />
            </div>
            <div class="form-section">
              <label class="form-label">Iterations</label>
              <el-input-number v-model="trainForm.iterations" :min="50" :max="600" :step="10" style="width: 100%" />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-section">
              <label class="form-label">Batch Size</label>
              <el-input-number v-model="trainForm.batchSize" :min="1" :max="1" disabled style="width: 100%" />
            </div>
            <div class="form-section">
              <label class="form-label">Learning Rate</label>
              <el-input-number v-model="trainForm.learningRate" :min="0.00001" :max="0.01" :step="0.0001" :precision="5" style="width: 100%" />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-section">
              <label class="form-label">Crops per Class Bag</label>
              <el-input-number v-model="trainForm.sampleSize" :min="10" :max="100" :step="5" style="width: 100%" />
            </div>
            <div class="form-section">
              <label class="form-label">K Value</label>
              <el-input-number v-model="trainForm.k" :min="1" :max="20" :step="1" style="width: 100%" />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-section">
              <div class="switch-row compact">
                <label class="form-label">Plot</label>
                <el-switch v-model="trainForm.plot" />
              </div>
            </div>
            <div class="form-section">
              <div class="switch-row compact">
                <label class="form-label">Snapshot</label>
                <el-switch v-model="trainForm.snapshot" />
              </div>
            </div>
          </div>
          
          <div class="form-section">
            <div class="switch-row">
              <label class="form-label">Synthetic Samples</label>
              <el-switch v-model="trainForm.useSynthetic" />
            </div>
          </div>
          
          <template v-if="trainForm.useSynthetic">
            <div class="form-section">
              <label class="form-label">Synth. Directory</label>
              <el-select v-model="trainForm.syntheticDir" placeholder="Select synth. directory" style="width: 100%">
                <el-option
                  v-for="dir in filteredSyntheticDirs"
                  :key="dir.name"
                  :label="`${dirDisplayName(dir)} (${dir.synthetic_count} synth.)`"
                  :value="dir.name"
                >
                  <div class="dir-option">
                    <span class="dir-option-name">{{ dirDisplayName(dir) }}</span>
                    <el-tag size="small" :type="dir.is_system ? 'info' : 'success'">
                      {{ dir.is_system ? 'System' : `${dir.synthetic_count} synth.` }}
                    </el-tag>
                  </div>
                </el-option>
              </el-select>
            </div>
            
            <div class="form-section">
              <label class="form-label">Synthetic Crop Ratio</label>
              <div class="slider-with-input">
                <el-slider v-model="trainForm.syntheticRatio" :min="0" :max="1" :step="0.01" :format-tooltip="(v) => `${(v * 100).toFixed(0)}%`" class="ratio-slider" />
                <el-input-number v-model="trainForm.syntheticRatio" :min="0" :max="1" :step="0.01" :precision="2" :controls="false" size="small" class="ratio-input" />
              </div>
            </div>
          </template>
          
          <div class="btn-group">
            <button
              class="train-btn start"
              :disabled="status.running"
              @click="startTraining"
            >
              <el-icon><VideoPlay /></el-icon>
              Start Train
            </button>
            <button
              class="train-btn stop"
              :disabled="!status.running"
              @click="stopTraining"
            >
              <el-icon><VideoPause /></el-icon>
              Stop
            </button>
          </div>
        </div>
      </div>
      
      <!-- Status Panel -->
      <div class="panel status-panel">
        <div class="panel-header">
          <div class="panel-icon" :class="{ green: status.running }">
            <el-icon :size="20"><DataLine /></el-icon>
          </div>
          <span>Train Status</span>
          <div class="status-badge" :class="status.running ? 'running' : 'idle'">
            {{ status.running ? 'Training' : 'Idle' }}
          </div>
        </div>
        
        <div class="panel-body">
          <div v-if="status.running" class="metrics-grid">
            <div class="metric-card">
              <span class="metric-label">Last Evaluated Iteration</span>
              <span class="metric-value">{{ Number.isFinite(status.current_auc) ? status.current_iter : '—' }} / {{ status.total_iters }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Latest Test ROC AUC</span>
              <span class="metric-value highlight">{{ Number.isFinite(status.current_auc) ? (status.current_auc * 100).toFixed(2) + '%' : '—' }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Peak Test ROC AUC</span>
              <span class="metric-value best">{{ Number.isFinite(status.best_auc) ? (status.best_auc * 100).toFixed(2) + '%' : '—' }}</span>
            </div>
            <div class="metric-card full">
              <span class="metric-label">Progress at Last Evaluation</span>
              <el-progress
                :percentage="Math.round((status.current_iter / status.total_iters) * 100)"
                :stroke-width="12"
                striped
                striped-flow
              />
            </div>
          </div>
          
          <div v-else class="idle-state">
            <el-icon :size="48"><Timer /></el-icon>
            <p>Waiting to start</p>
          </div>
          
          <!-- Logs -->
          <div class="logs-section">
            <div class="logs-header">
              <span>Train Log</span>
              <button class="refresh-btn small" @click="refreshLogs">
                <el-icon><Refresh /></el-icon>
              </button>
            </div>
            <div class="logs-content">
              <pre>{{ logs || 'No logs' }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, onDeactivated, inject, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { trainAPI, dataAPI } from '../api'

const dataset = inject('dataset')
const requireLogin = inject('requireLogin')

// Default training params per dataset
const datasetDefaults = {
  'shanghaitech': {
    expName: 'sht_experiment',
    seed: 1,
    iterations: 600,
    batchSize: 1,
    learningRate: 0.0005,
    sampleSize: 30,
    k: 5,
    syntheticRatio: 0.5
  },
  'ucf-crime': {
    expName: 'ucf_experiment',
    seed: 1,
    iterations: 600,
    batchSize: 1,
    learningRate: 0.0005,
    sampleSize: 30,
    k: 5,
    syntheticRatio: 0.05
  }
}

const trainForm = reactive({
  expName: 'sht_experiment',
  seed: 1,
  iterations: 600,
  batchSize: 1,
  learningRate: 0.0005,
  sampleSize: 30,
  k: 5,
  plot: false,
  snapshot: true,
  useSynthetic: true,
  syntheticDir: '',
  syntheticRatio: 0.5
})

const allSyntheticDirs = ref([])

// Unified dir display name
const dirDisplayName = (dir) => {
  if (dir.is_root) return `${dir.dataset} - Synth. Samples`
  if (dir.is_system) return dir.dataset
  return dir.folder
}

// Filter synth dirs by current dataset
const filteredSyntheticDirs = computed(() => {
  const dsKey = dataset.value
  return allSyntheticDirs.value.filter(d => {
    if (d.name.startsWith(dsKey + '/')) return true
    if (d.dataset === dsKey) return true
    if (dsKey === 'shanghaitech' && d.dataset.toUpperCase().includes('SHT')) return true
    if (dsKey === 'ucf-crime' && d.dataset.toUpperCase().includes('UCF')) return true
    return false
  })
})

const status = reactive({
  running: false,
  current_iter: 0,
  total_iters: 600,
  current_auc: null,
  best_auc: null
})

const logs = ref('')
let statusInterval = null
let logsInterval = null

// Load synthetic directories
const loadSyntheticDirs = async () => {
  try {
    const response = await dataAPI.featureDirs()
    allSyntheticDirs.value = response.data.directories || []
    selectDefaultSyntheticDir()
  } catch (error) {
    console.error('Failed to load synthetic directories:', error)
  }
}

const selectDefaultSyntheticDir = () => {
  const dirs = filteredSyntheticDirs.value
  if (dirs.length > 0) {
    // Prefer non-system dir
    const nonSystem = dirs.find(d => !d.is_system)
    trainForm.syntheticDir = nonSystem ? nonSystem.name : dirs[0].name
  } else {
    trainForm.syntheticDir = ''
  }
}

const startTraining = async () => {
  if (!requireLogin()) return
  if (!trainForm.expName.trim()) {
    ElMessage.warning('Enter experiment name')
    return
  }
  
  if (trainForm.useSynthetic && !trainForm.syntheticDir) {
    ElMessage.warning('Select synth. directory')
    return
  }
  
  try {
    const res = await trainAPI.start({
      dataset: dataset.value,
      exp_name: trainForm.expName,
      seed: trainForm.seed,
      iterations: trainForm.iterations,
      batch_size: trainForm.batchSize,
      learning_rate: trainForm.learningRate,
      sample_size: trainForm.sampleSize,
      k: trainForm.k,
      plot: trainForm.plot ? 1 : 0,
      snapshot: trainForm.snapshot ? 1 : 0,
      use_synthetic: trainForm.useSynthetic,
      synthetic_dir: trainForm.syntheticDir,
      synthetic_ratio: trainForm.syntheticRatio
    })
    
    if (res.data.success) {
      ElMessage.success('Training started')
      startPolling()
    } else {
      ElMessage.error(res.data.error || 'Start failed')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Start request failed')
  }
}

const stopTraining = async () => {
  if (!requireLogin()) return
  try {
    await trainAPI.stop()
    ElMessage.success('Training stopped')
    stopPolling()
    checkStatus()
  } catch {
    ElMessage.error('Stop failed')
  }
}

const checkStatus = async () => {
  try {
    const res = await trainAPI.status()
    Object.assign(status, res.data)
    if (!res.data.running && statusInterval) {
      stopPolling()
    }
  } catch {}
}

const refreshLogs = async () => {
  try {
    const res = await trainAPI.logs(100)
    const rawLogs = res.data.logs
    // Backend returns array, join to string
    if (Array.isArray(rawLogs)) {
      logs.value = rawLogs.join('\n')
    } else {
      logs.value = rawLogs || ''
    }
  } catch {}
}

const startPolling = () => {
  checkStatus()
  refreshLogs()
  statusInterval = setInterval(checkStatus, 3000)
  logsInterval = setInterval(refreshLogs, 5000)
}

const stopPolling = () => {
  if (statusInterval) clearInterval(statusInterval)
  if (logsInterval) clearInterval(logsInterval)
  statusInterval = null
  logsInterval = null
}

// Update defaults on dataset change
watch(dataset, (newDs) => {
  const defaults = datasetDefaults[newDs] || datasetDefaults['shanghaitech']
  
  trainForm.expName = defaults.expName
  trainForm.seed = defaults.seed
  trainForm.iterations = defaults.iterations
  trainForm.batchSize = defaults.batchSize
  trainForm.learningRate = defaults.learningRate
  trainForm.sampleSize = defaults.sampleSize
  trainForm.k = defaults.k
  trainForm.syntheticRatio = defaults.syntheticRatio
  selectDefaultSyntheticDir()
}, { immediate: true })

onMounted(async () => {
  loadSyntheticDirs()
  await checkStatus()
  await refreshLogs()
  // Auto-poll if training is running on mount
  if (status.running && !statusInterval) {
    startPolling()
  }
})

// Stop polling on keep-alive deactivate
onDeactivated(() => {
  stopPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.train-view {
  height: calc(100vh - 120px);
}

.panel-row {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
  height: 100%;
  align-items: stretch;
}

.panel {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
}

.panel-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.panel-icon.green {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.status-badge {
  margin-left: auto;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.running {
  background: rgba(16, 185, 129, 0.2);
  color: var(--success);
}

.status-badge.idle {
  background: rgba(100, 116, 139, 0.2);
  color: var(--text-muted);
}

.panel-body {
  flex: 1;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
}

/* Config panel scrollable on overflow */
.config-panel .panel-body {
  overflow-y: auto;
}

/* Status panel internal scroll */
.status-panel .panel-body {
  overflow-y: auto;
}

.form-section {
  margin-bottom: 10px;
}

.form-label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.switch-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.switch-row.compact {
  height: 100%;
  padding: 8px 0;
}

.btn-group {
  display: flex;
  gap: 10px;
  margin-top: 4px;
  padding-top: 10px;
}

.train-btn {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.train-btn.start {
  background: linear-gradient(135deg, var(--success) 0%, #059669 100%);
  color: white;
}

.train-btn.stop {
  background: linear-gradient(135deg, var(--danger) 0%, #dc2626 100%);
  color: white;
}

.train-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.metric-card {
  background: rgba(51, 65, 85, 0.4);
  padding: 16px;
  border-radius: 10px;
  text-align: center;
}

.metric-card.full {
  grid-column: span 3;
}

.metric-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-value.highlight {
  color: var(--primary-light);
}

.metric-value.best {
  color: var(--success);
}

.idle-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--text-muted);
  gap: 12px;
}

.idle-state p {
  margin: 0;
  color: var(--text-secondary);
}

.logs-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 200px;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.refresh-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: var(--bg-hover);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.refresh-btn:hover {
  background: var(--primary);
  color: white;
}

.logs-content {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
  min-height: 120px;
}

.logs-content pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 11px;
  line-height: 1.6;
  color: #a3e635;
  white-space: pre-wrap;
}

.dir-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.dir-option .dir-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
}

.slider-with-input {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ratio-slider {
  flex: 1;
}

.ratio-input {
  width: 72px;
  flex-shrink: 0;
}

.dir-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.dir-option-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
