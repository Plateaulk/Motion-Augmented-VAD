<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="700px"
    destroy-on-close
    class="file-browser-dialog"
  >
    <!-- Breadcrumb navigation -->
    <div class="browser-header">
      <div class="breadcrumb">
        <span 
          v-for="(crumb, index) in breadcrumbs" 
          :key="index"
          class="crumb"
          @click="navigateTo(crumb.path)"
        >
          <span class="crumb-name">{{ crumb.name }}</span>
          <span v-if="index < breadcrumbs.length - 1" class="crumb-sep">/</span>
        </span>
      </div>
      <div class="browser-actions">
        <el-button 
          :icon="ArrowUp" 
          size="small" 
          :disabled="!parentPath"
          @click="goUp"
        >
          Up
        </el-button>
        <el-button 
          :icon="Refresh" 
          size="small"
          @click="refresh"
        >
          Refresh
        </el-button>
      </div>
    </div>

    <!-- Current path display -->
    <div class="current-path">
      <el-icon><FolderOpened /></el-icon>
      <span>{{ currentPath || '/' }}</span>
    </div>

    <!-- File list -->
    <div class="file-list" v-loading="loading">
      <div 
        v-for="item in items" 
        :key="item.path"
        :class="['file-item', { 
          selected: selectedItem?.path === item.path,
          directory: item.type === 'directory'
        }]"
        @click="selectItem(item)"
        @dblclick="openItem(item)"
      >
        <div class="item-icon">
          <el-icon v-if="item.type === 'directory'" :size="20"><Folder /></el-icon>
          <el-icon v-else-if="item.file_type === 'video'" :size="20"><VideoCamera /></el-icon>
          <el-icon v-else-if="item.file_type === 'image'" :size="20"><Picture /></el-icon>
          <el-icon v-else :size="20"><Document /></el-icon>
        </div>
        <div class="item-info">
          <span class="item-name">{{ item.name }}</span>
          <span class="item-meta">
            <template v-if="item.type === 'directory'">
              {{ item.child_count }} items
            </template>
            <template v-else>
              {{ formatSize(item.size) }}
            </template>
          </span>
        </div>
        <div v-if="item.type === 'directory'" class="item-arrow">
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
      
      <div v-if="!loading && items.length === 0" class="empty-state">
        <el-icon :size="40"><FolderOpened /></el-icon>
        <p>Empty folder</p>
      </div>
    </div>

    <!-- Selected path display -->
    <div v-if="selectedItem" class="selected-info">
      <span class="label">Selected:</span>
      <span class="path">{{ selectedItem.path }}</span>
    </div>

    <!-- Footer -->
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="cancel">Cancel</el-button>
        <el-button 
          type="primary" 
          :disabled="!canConfirm"
          @click="confirm"
        >
          {{ confirmText }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { 
  Folder, FolderOpened, Document, VideoCamera, Picture,
  ArrowUp, ArrowRight, Refresh
} from '@element-plus/icons-vue'
import { filesAPI } from '../api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: Boolean,
  title: {
    type: String,
    default: 'Select File'
  },
  initialPath: {
    type: String,
    default: '/root'
  },
  mode: {
    type: String,
    default: 'file', // 'file', 'directory', 'both'
    validator: (v) => ['file', 'directory', 'both'].includes(v)
  },
  fileTypes: {
    type: Array,
    default: () => [] // Empty means all types, e.g. ['video', 'image']
  },
  confirmText: {
    type: String,
    default: 'OK'
  }
})

const emit = defineEmits(['update:modelValue', 'select'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const currentPath = ref(props.initialPath)
const parentPath = ref(null)
const items = ref([])
const selectedItem = ref(null)

const breadcrumbs = computed(() => {
  if (!currentPath.value) return [{ name: '/', path: '/' }]
  
  const parts = currentPath.value.split('/').filter(Boolean)
  const crumbs = [{ name: '/', path: '/' }]
  
  let path = ''
  for (const part of parts) {
    path += '/' + part
    crumbs.push({ name: part, path })
  }
  
  return crumbs
})

const canConfirm = computed(() => {
  if (!selectedItem.value) return false
  
  if (props.mode === 'directory') {
    return selectedItem.value.type === 'directory'
  } else if (props.mode === 'file') {
    return selectedItem.value.type === 'file'
  }
  return true
})

const loadDirectory = async (path) => {
  loading.value = true
  selectedItem.value = null
  
  try {
    const response = await filesAPI.browse(path || '')
    currentPath.value = response.data.path
    parentPath.value = response.data.parent
    
    let filteredItems = response.data.items || []
    
    // Filter by file types if specified
    if (props.fileTypes.length > 0) {
      filteredItems = filteredItems.filter(item => {
        if (item.type === 'directory') return true
        return props.fileTypes.includes(item.file_type)
      })
    }
    
    // In directory mode, only show directories
    if (props.mode === 'directory') {
      filteredItems = filteredItems.filter(item => item.type === 'directory')
    }
    
    items.value = filteredItems
  } catch (error) {
    console.error('Failed to load directory:', error)
    ElMessage.error('Failed to load directory: ' + (error.response?.data?.error || error.message))
  } finally {
    loading.value = false
  }
}

const navigateTo = (path) => {
  loadDirectory(path)
}

const goUp = () => {
  if (parentPath.value) {
    loadDirectory(parentPath.value)
  }
}

const refresh = () => {
  loadDirectory(currentPath.value)
}

const selectItem = (item) => {
  selectedItem.value = item
}

const openItem = (item) => {
  if (item.type === 'directory') {
    loadDirectory(item.path)
  } else {
    // Double click on file = select and confirm
    selectedItem.value = item
    confirm()
  }
}

const cancel = () => {
  visible.value = false
}

const confirm = () => {
  if (selectedItem.value) {
    emit('select', selectedItem.value)
    visible.value = false
  }
}

const formatSize = (bytes) => {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

// Watch for visibility changes to load initial directory
watch(visible, (val) => {
  if (val) {
    loadDirectory(props.initialPath)
  }
})
</script>

<style scoped>
.file-browser-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.browser-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #334155;
  background: #1e293b;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: #94a3b8;
  transition: color 0.2s;
}

.crumb:hover {
  color: #60a5fa;
}

.crumb:last-child {
  color: #f1f5f9;
  cursor: default;
}

.crumb-sep {
  color: #475569;
}

.browser-actions {
  display: flex;
  gap: 8px;
}

.current-path {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #0f172a;
  color: #64748b;
  font-size: 12px;
  font-family: monospace;
}

.file-list {
  height: 400px;
  overflow-y: auto;
  background: #1e293b;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid #334155;
  transition: background 0.15s;
}

.file-item:hover {
  background: rgba(59, 130, 246, 0.1);
}

.file-item.selected {
  background: rgba(59, 130, 246, 0.2);
}

.file-item.directory {
  font-weight: 500;
}

.item-icon {
  color: #64748b;
}

.file-item.directory .item-icon {
  color: #fbbf24;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-name {
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  font-size: 12px;
  color: #64748b;
}

.item-arrow {
  color: #475569;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #64748b;
}

.empty-state p {
  margin-top: 12px;
}

.selected-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(59, 130, 246, 0.1);
  border-top: 1px solid #334155;
}

.selected-info .label {
  color: #94a3b8;
  font-size: 13px;
}

.selected-info .path {
  color: #60a5fa;
  font-family: monospace;
  font-size: 13px;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
