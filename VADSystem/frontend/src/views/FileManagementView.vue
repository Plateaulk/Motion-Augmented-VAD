<template>
  <div class="file-management-view">
    <div class="file-manager-grid">
      <!-- Left Panel: File Browser -->
      <div class="panel browser-panel">
        <div class="panel-header">
          <div class="header-title">
            <el-icon :size="20"><FolderOpened /></el-icon>
            <span>Files</span>
          </div>
          <div class="header-actions">
            <el-dropdown trigger="click" @command="handleUploadCategory">
              <button class="upload-btn">
                <el-icon><Upload /></el-icon>
                <span>Upload</span>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="cat in uploadableCategories" :key="cat.id" :command="cat.id">
                    <el-icon><component :is="cat.icon" /></el-icon>
                    {{ cat.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-dropdown trigger="click" @command="handleNewFolder">
              <button class="new-folder-btn">
                <el-icon><FolderAdd /></el-icon>
                <span>New Folder</span>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="cat in uploadableCategories" :key="cat.id" :command="cat.id">
                    <el-icon><component :is="cat.icon" /></el-icon>
                    {{ cat.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <button class="download-btn" :disabled="!canDownloadSelected" @click="downloadSelected" title="Download selected files">
              <el-icon><Download /></el-icon>
              <span>Download</span>
            </button>
          </div>
          <input
            ref="fileInputRef"
            type="file"
            :accept="uploadAccept"
            multiple
            style="display: none"
            @change="handleFileUpload"
          />
        </div>
        
        <!-- Category Tabs -->
        <div class="category-tabs">
          <button 
            v-for="cat in categories" 
            :key="cat.id"
            :class="['tab-btn', { active: activeCategory === cat.id }]"
            @click="activeCategory = cat.id"
          >
            <el-icon><component :is="cat.icon" /></el-icon>
            <span>{{ cat.label }}</span>
            <span class="count-badge" v-if="getCategoryCount(cat.id) > 0">{{ getCategoryCount(cat.id) }}</span>
          </button>
        </div>

        <!-- File List -->
        <div class="file-list-container">
          <!-- Breadcrumb Navigation -->
          <div class="breadcrumb-bar" v-if="isInFolder">
            <button class="breadcrumb-btn back-btn" @click="goBack">
              <el-icon><ArrowLeft /></el-icon>
            </button>
            <div class="breadcrumb-path">
              <span class="breadcrumb-item root" @click="goToRoot">
                <el-icon><HomeFilled /></el-icon>
                Root
              </span>
              <template v-for="(segment, index) in currentPath" :key="index">
                <el-icon class="breadcrumb-separator"><ArrowRight /></el-icon>
                <span 
                  :class="['breadcrumb-item', { active: index === currentPath.length - 1 }]"
                  @click="goToBreadcrumb(index)"
                >
                  {{ segment }}
                </span>
              </template>
            </div>
          </div>
          
          <!-- Toolbar -->
          <div class="toolbar">
            <el-input 
              v-model="searchQuery" 
              size="small" 
              :placeholder="isInFolder ? 'Search folder...' : 'Search files...'" 
              clearable
              class="search-input"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <div class="toolbar-actions">
              <el-tooltip content="Select All" v-if="isInFolder">
                <button class="icon-btn" @click="selectAll">
                  <el-icon><Select /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="Clear">
                <button class="icon-btn" @click="clearSelection" :disabled="!selectedFiles.length">
                  <el-icon><Close /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="Refresh">
                <button class="icon-btn" @click="refreshFiles">
                  <el-icon><Refresh /></el-icon>
                </button>
              </el-tooltip>
            </div>
          </div>

          <!-- ═══ Trash View ═══ -->
          <template v-if="activeCategory === 'trash'">
            <!-- Trash toolbar -->
            <div class="trash-toolbar">
              <div class="trash-info">
                <el-icon><Delete /></el-icon>
                <span>{{ trashItems.length }} items</span>
                <span class="trash-size">({{ formatSize(trashTotalSize) }})</span>
              </div>
              <div class="trash-actions-bar">
                <button class="icon-btn" @click="selectAllTrash" title="Select All" :disabled="!trashItems.length">
                  <el-icon><Select /></el-icon>
                </button>
                <button class="icon-btn" @click="clearTrashSelection" :disabled="!selectedTrashItems.length" title="Clear">
                  <el-icon><Close /></el-icon>
                </button>
                <button class="icon-btn" @click="loadTrash" title="Refresh">
                  <el-icon><Refresh /></el-icon>
                </button>
              </div>
            </div>

            <!-- Trash batch actions -->
            <div class="trash-batch-bar" v-if="selectedTrashItems.length">
              <span class="batch-count">{{ selectedTrashItems.length }} selected</span>
              <button class="action-btn primary" @click="restoreSelectedTrash">
                <el-icon><RefreshLeft /></el-icon>
                <span>Restore</span>
              </button>
              <button class="action-btn danger" @click="permanentDeleteSelected">
                <el-icon><Delete /></el-icon>
                <span>Delete</span>
              </button>
            </div>

            <!-- Trash loading -->
            <div v-if="trashLoading" class="loading-state">
              <el-icon :size="48" class="loading-icon"><Loading /></el-icon>
              <p>Loading...</p>
            </div>

            <!-- Trash list -->
            <div class="trash-list" v-else-if="trashItems.length">
              <div 
                v-for="item in trashItems" 
                :key="item.id"
                :class="['trash-item', { selected: selectedTrashItems.includes(item.id) }]"
                @click="toggleTrashSelect(item)"
              >
                <input 
                  type="checkbox"
                  :checked="selectedTrashItems.includes(item.id)"
                  @click.stop="toggleTrashSelect(item)"
                  class="file-checkbox-native"
                />
                <div class="trash-icon">
                  <el-icon :size="28" v-if="item.type === 'folder'"><Folder /></el-icon>
                  <el-icon :size="28" v-else><Document /></el-icon>
                </div>
                <div class="trash-details">
                  <span class="trash-name">{{ item.original_name }}</span>
                  <span class="trash-meta">
                    {{ item.type === 'folder' ? `Folder · ${item.file_count} files · ` : '' }}{{ formatSize(item.size) }} · {{ formatTrashTime(item.deleted_at) }}
                  </span>
                  <span class="trash-path">{{ item.original_path }}</span>
                </div>
                <div class="trash-item-actions" @click.stop>
                  <button class="folder-action-btn" @click="restoreTrashItem(item)" title="Restore">
                    <el-icon :size="14"><RefreshLeft /></el-icon>
                  </button>
                  <button class="folder-action-btn danger" @click="permanentDeleteTrashItem(item)" title="Delete">
                    <el-icon :size="14"><Delete /></el-icon>
                  </button>
                </div>
              </div>
            </div>

            <!-- Trash empty state -->
            <div v-else class="empty-state">
              <el-icon :size="48"><Delete /></el-icon>
              <p>Trash is empty</p>
            </div>

            <!-- Empty trash button -->
            <div class="trash-footer" v-if="trashItems.length && !trashLoading">
              <button class="action-btn danger full-width" @click="emptyTrash">
                <el-icon><Delete /></el-icon>
                <span>Empty Trash</span>
              </button>
            </div>
          </template>

          <!-- ═══ Normal File View ═══ -->
          <template v-else>
          <!-- Loading State -->
          <div v-if="loading" class="loading-state">
            <el-icon :size="48" class="loading-icon"><Loading /></el-icon>
            <p>Loading...</p>
          </div>

          <!-- Folders Grid (root level) -->
          <div class="folder-grid" v-else-if="!isInFolder && currentFolders.length">
            <div 
              v-for="folder in currentFolders" 
              :key="folder.id"
              class="folder-item"
              @click="enterFolder(folder)"
            >
              <div class="folder-icon">
                <el-icon :size="48"><Folder /></el-icon>
              </div>
              <div class="folder-info">
                <span class="folder-name">{{ folder.name }}</span>
                <span class="folder-count">{{ folder.count }} files</span>
              </div>
              <div class="folder-type-badge" :class="folder.type">{{ getTypeLabel(folder.type) }}</div>
              <!-- Folder actions -->
              <div class="folder-actions" @click.stop>
                <button class="folder-action-btn" @click.stop="renameFolder(folder)" title="Rename">
                  <el-icon :size="14"><Edit /></el-icon>
                </button>
                <button class="folder-action-btn danger" @click.stop="deleteFolder(folder)" title="Trash">
                  <el-icon :size="14"><Delete /></el-icon>
                </button>
              </div>
            </div>
          </div>

          <!-- File Grid/List (inside folder) -->
          <div class="file-list" v-else-if="isInFolder && filteredFiles.length">
            <div 
              v-for="file in filteredFiles" 
              :key="file.id"
              :class="['file-item', { selected: selectedFiles.includes(file.id) }]"
              @click="toggleFileSelect(file)"
            >
              <input 
                type="checkbox"
                :checked="selectedFiles.includes(file.id)"
                @click.stop="toggleFileSelect(file)"
                class="file-checkbox-native"
              />
              
              <div class="file-preview">
                <!-- Image preview with thumbnail -->
                <img v-if="file.type === 'background'" :src="file.thumbUrl || file.url" :alt="file.name" loading="lazy" decoding="async" />
                <!-- Video preview with thumbnail -->
                <img v-else-if="isVideoType(file.type) && file.thumbUrl" :src="file.thumbUrl" :alt="file.name" loading="lazy" decoding="async" class="video-thumb-img" />
                <video v-else-if="isVideoType(file.type)" :src="file.url + '#t=0.1'" muted preload="metadata" />
                <!-- Motion/Feature file icon -->
                <div v-else class="file-icon-large">
                  <el-icon :size="32" v-if="file.type === 'motion'"><Coordinate /></el-icon>
                  <el-icon :size="32" v-else><Document /></el-icon>
                </div>
                <div class="file-type-badge" :class="file.type">{{ getTypeLabel(file.type) }}</div>
              </div>
              
              <div class="file-info">
                <span class="file-name">{{ file.name }}</span>
              </div>
            </div>
          </div>
          
          <!-- Empty States -->
          <div v-else-if="!isInFolder && !currentFolders.length && !loading" class="empty-state">
            <el-icon :size="48"><FolderOpened /></el-icon>
            <p>{{ activeCategory === 'all' ? 'No folders' : 'No folders in this category' }}</p>
          </div>
          
          <div v-else-if="isInFolder && !filteredFiles.length && !loading" class="empty-state">
            <el-icon :size="48"><Document /></el-icon>
            <p>{{ searchQuery ? 'No matching files' : 'Folder is empty' }}</p>
          </div>
          </template>
        </div>
      </div>

      <!-- Right Panel: Preview & Actions -->
      <div class="panel actions-panel">
        <div class="panel-header">
          <div class="header-title">
            <el-icon :size="20"><View /></el-icon>
            <span>Preview</span>
          </div>
          <span v-if="selectedFiles.length" class="selection-info">{{ selectedFiles.length }} selected</span>
        </div>

        <div class="panel-body">
          <!-- Single File Preview -->
          <template v-if="previewFile">
            <div class="preview-section">
              <div class="preview-content">
                <img v-if="previewFile.type === 'background'" :src="previewFile.url" :alt="previewFile.name" />
                <video v-else-if="isVideoType(previewFile.type)" :src="previewFile.url" controls />
                <div v-else class="feature-preview">
                  <el-icon :size="64"><Document /></el-icon>
                  <span class="feature-label">{{ getTypeLabel(previewFile.type) }}</span>
                </div>
              </div>
              
              <div class="preview-details">
                <div class="detail-row">
                  <span class="label">Name:</span>
                  <span class="value">{{ previewFile.name }}</span>
                  <button class="rename-btn" @click="renameFile(previewFile)" title="Rename">
                    <el-icon :size="12"><Edit /></el-icon>
                  </button>
                </div>
                <div class="detail-row">
                  <span class="label">Type:</span>
                  <span class="value type-tag" :class="previewFile.type">{{ getTypeLabel(previewFile.type) }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Path:</span>
                  <span class="value path">{{ previewFile.fullPath }}</span>
                </div>
                <div class="detail-row" v-if="previewFile.size">
                  <span class="label">Size:</span>
                  <span class="value">{{ formatSize(previewFile.size) }}</span>
                </div>
              </div>
              
              <!-- Single File Actions -->
              <div class="single-file-actions">
                <!-- Copy/Move for background files -->
                <template v-if="previewFile.type === 'background'">
                  <div class="action-row-inline">
                    <el-select v-model="bgCopyTarget" size="small" placeholder="Copy to..." class="action-select-inline">
                      <el-option label="SHT BG" value="sht" />
                      <el-option label="UCF BG" value="ucf" />
                    </el-select>
                    <button class="action-btn-sm primary" :disabled="!bgCopyTarget" @click="copySingleBackground">
                      <el-icon><CopyDocument /></el-icon>
                    </button>
                  </div>
                  <div class="action-row-inline">
                    <el-select v-model="bgMoveTarget" size="small" placeholder="Move to..." class="action-select-inline">
                      <el-option label="SHT BG" value="sht" />
                      <el-option label="UCF BG" value="ucf" />
                    </el-select>
                    <button class="action-btn-sm" :disabled="!bgMoveTarget" @click="moveSingleBackground">
                      <el-icon><Right /></el-icon>
                    </button>
                  </div>
                </template>
                
                <!-- Copy/Move for feature files -->
                <template v-if="previewFile.type === 'feature'">
                  <div class="action-row-inline">
                    <el-select v-model="singleCopyTarget" size="small" placeholder="Copy to..." class="action-select-inline">
                      <el-option v-for="dir in featureDirectories" :key="dir.name" :label="dir.dataset" :value="dir.name" />
                    </el-select>
                    <button class="action-btn-sm primary" :disabled="!singleCopyTarget" @click="copySingleFile">
                      <el-icon><CopyDocument /></el-icon>
                    </button>
                  </div>
                  <div class="action-row-inline">
                    <el-select v-model="singleMoveTarget" size="small" placeholder="Move to..." class="action-select-inline">
                      <el-option v-for="dir in featureDirectories" :key="dir.name" :label="dir.dataset" :value="dir.name" />
                    </el-select>
                    <button class="action-btn-sm" :disabled="!singleMoveTarget" @click="moveSingleFile">
                      <el-icon><Right /></el-icon>
                    </button>
                  </div>
                </template>
                
                <!-- Copy/Move for video files (same type only) -->
                <template v-if="isVideoType(previewFile.type)">
                  <div class="type-hint">
                    <el-icon><InfoFilled /></el-icon>
                    <span>Videos can only be copied/moved to same-type directories</span>
                  </div>
                  <div class="action-row-inline">
                    <el-input v-model="videoCopyPath" size="small" :placeholder="getVideoPathPlaceholder(previewFile.type, 'copy')" class="action-select-inline" />
                    <button class="action-btn-sm browse" @click="browseForPath(videoCopyPath, 'Select copy target')">
                      <el-icon><FolderOpened /></el-icon>
                    </button>
                    <button class="action-btn-sm primary" :disabled="!videoCopyPath" @click="copySingleVideo">
                      <el-icon><CopyDocument /></el-icon>
                    </button>
                  </div>
                  <div class="action-row-inline">
                    <el-input v-model="videoMovePath" size="small" :placeholder="getVideoPathPlaceholder(previewFile.type, 'move')" class="action-select-inline" />
                    <button class="action-btn-sm browse" @click="browseForPath(videoMovePath, 'Select move target')">
                      <el-icon><FolderOpened /></el-icon>
                    </button>
                    <button class="action-btn-sm" :disabled="!videoMovePath" @click="moveSingleVideo">
                      <el-icon><Right /></el-icon>
                    </button>
                  </div>
                </template>
                
                <button class="action-btn full-width" @click="renameFile(previewFile)">
                  <el-icon><Edit /></el-icon>
                  <span>Rename File</span>
                </button>
              </div>
            </div>
          </template>

          <!-- Batch Actions -->
          <div class="actions-section" v-if="selectedFiles.length">
            <h4 class="section-title">Batch ({{ selectedFiles.length }} files)</h4>
            
            <!-- Universal Copy To -->
            <div class="action-group">
              <el-tooltip :content="pickableFolders.length ? '' : 'No compatible target folders'" :disabled="pickableFolders.length > 0">
                <button 
                  class="action-btn primary full-width" 
                  @click="batchCopyTo"
                  :disabled="!pickableFolders.length"
                >
                  <el-icon><CopyDocument /></el-icon>
                  <span>Copy to...</span>
                </button>
              </el-tooltip>
            </div>

            <!-- Universal Move To -->
            <div class="action-group">
              <el-tooltip :content="pickableFolders.length ? '' : 'No compatible target folders'" :disabled="pickableFolders.length > 0">
                <button 
                  class="action-btn full-width" 
                  @click="batchMoveTo"
                  :disabled="!pickableFolders.length"
                >
                  <el-icon><Right /></el-icon>
                  <span>Move to...</span>
                </button>
              </el-tooltip>
            </div>

            <!-- Move to Trash button -->
            <div class="action-group">
              <button 
                class="action-btn danger full-width" 
                @click="deleteSelected"
                :disabled="!canDelete"
              >
                <el-icon><Delete /></el-icon>
                <span>Trash ({{ deletableCount }})</span>
              </button>
            </div>

            <div class="selected-summary">
              <div class="summary-item" v-for="(count, type) in selectedByType" :key="type">
                <span class="type-dot" :class="type"></span>
                <span>{{ getTypeLabel(type) }}: {{ count }}</span>
              </div>
            </div>
          </div>

          <!-- Empty state -->
          <div v-if="!previewFile && !selectedFiles.length" class="empty-state">
            <el-icon :size="48"><View /></el-icon>
            <p>Select a file to preview</p>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- File Browser Dialog -->
  <FileBrowser
    v-model="fileBrowserVisible"
    :title="fileBrowserTitle"
    :initial-path="fileBrowserInitialPath"
    :mode="fileBrowserMode"
    :confirm-text="fileBrowserConfirmText"
    @select="onFileBrowserSelect"
  />

  <!-- Internal Folder Picker Dialog -->
  <el-dialog
    v-model="folderPickerVisible"
    :title="folderPickerTitle"
    width="480px"
    class="folder-picker-dialog"
    destroy-on-close
  >
    <div class="folder-picker-list">
      <div
        v-for="folder in pickableFolders"
        :key="folder.id"
        :class="['folder-picker-item', { selected: folderPickerSelected === folder.id }]"
        @click="folderPickerSelected = folder.id"
      >
        <el-icon class="folder-icon"><Folder /></el-icon>
        <div class="folder-info">
          <span class="folder-name">{{ folder.name }}</span>
          <span class="folder-type-tag">{{ getTypeLabel(folder.type) }}</span>
        </div>
        <span class="folder-count">{{ folder.count }} files</span>
      </div>
      <div v-if="!pickableFolders.length" class="empty-hint">No available target folders</div>
    </div>
    <template #footer>
      <el-button @click="folderPickerVisible = false">Cancel</el-button>
      <el-button type="primary" :disabled="!folderPickerSelected" @click="confirmFolderPick">
        {{ folderPickerConfirmText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onActivated, onDeactivated, onUnmounted, inject, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { motionAPI, dataAPI, videoAPI, filesAPI, trashAPI, trainAPI } from '../api'
import FileBrowser from '../components/FileBrowser.vue'

// Note: Background deletion uses videoAPI
// filesAPI is for database-backed file management

const dataset = inject('dataset')
const requireLogin = inject('requireLogin')
const isLoggedIn = inject('isLoggedIn')
const currentUser = inject('currentUser')
const isAdmin = computed(() => currentUser.value?.username === 'admin')

// Categories
const baseCategories = [
  { id: 'all', label: 'All', icon: 'FolderOpened' },
  { id: 'background', label: 'Backgrounds', icon: 'Picture' },
  { id: 'motion', label: 'Motion', icon: 'Coordinate' },
  { id: 'mask_pair', label: 'Mask Pair', icon: 'Film' },
  { id: 'video_gen', label: 'Videos', icon: 'VideoPlay' },
  { id: 'feature_vad', label: 'Features', icon: 'Document' },
  { id: 'model', label: 'Models', icon: 'Cpu' },
  { id: 'trash', label: 'Trash', icon: 'Delete' },
  { id: 'log', label: 'Logs', icon: 'Document' }
]
const categories = computed(() => (
  isAdmin.value ? baseCategories : baseCategories.filter(c => c.id !== 'log')
))

// Trash state
const trashItems = ref([])
const trashTotalSize = ref(0)
const selectedTrashItems = ref([])
const trashLoading = ref(false)

// State
const activeCategory = ref('all')
const searchQuery = ref('')
const selectedFiles = ref([])
const allFiles = ref([])
const allFolders = ref([])  // Folder structure
const visibleAllFiles = computed(() => (
  isAdmin.value ? allFiles.value : allFiles.value.filter(f => f.type !== 'log')
))
const visibleAllFolders = computed(() => (
  isAdmin.value ? allFolders.value : allFolders.value.filter(f => f.type !== 'log')
))
const currentPath = ref([])  // Current path e.g. ['backgrounds'] or ['SHT_videos', 'subfolder']
const featureDirectories = ref([])
const loading = ref(false)
const copyTarget = ref('')
const moveTarget = ref('')
const singleCopyTarget = ref('')
const singleMoveTarget = ref('')
// Video copy/move paths (separated by type for type safety)
const videoCopyPath = ref('')
const videoMovePath = ref('')
const refVideoCopyPath = ref('')
const maskVideoCopyPath = ref('')
const genVideoCopyPath = ref('')

// File Browser state
const fileBrowserVisible = ref(false)
const fileBrowserTitle = ref('Select Directory')
const fileBrowserInitialPath = ref('/root')
const fileBrowserMode = ref('directory')
const fileBrowserConfirmText = ref('Select')
const fileBrowserCallback = ref(null)

const openFileBrowser = (options = {}) => {
  fileBrowserTitle.value = options.title || 'Select Directory'
  fileBrowserInitialPath.value = options.initialPath || '/root'
  fileBrowserMode.value = options.mode || 'directory'
  fileBrowserConfirmText.value = options.confirmText || 'Select'
  fileBrowserCallback.value = options.callback || null
  fileBrowserVisible.value = true
}

const onFileBrowserSelect = (item) => {
  if (fileBrowserCallback.value) {
    fileBrowserCallback.value(item)
  }
}

// Helper to create browse button click handler
const browseForPath = (targetRef, title = 'Select target') => {
  openFileBrowser({
    title,
    mode: 'directory',
    callback: (item) => {
      targetRef.value = item.path
    }
  })
}

// Background copy/move targets
const bgCopyTarget = ref('')
const bgMoveTarget = ref('')
const bgBatchCopyTarget = ref('')
const bgBatchMoveTarget = ref('')

// Database-backed file management
const dbFiles = ref([])
const dbCategories = ref([])
const addToDbCategory = ref('')
const showDbPanel = ref(false)

// Upload
const fileInputRef = ref(null)
const uploadCategory = ref('')
const uploadAccept = ref('*/*')

// Folders
const folders = ref({})  // { category: [folder1, folder2, ...] }
const selectedFolder = ref({})  // { category: folderName }

// Uploadable categories (exclude 'all' and 'motion')
const uploadableCategories = computed(() => {
  return categories.value.filter(c => c.id !== 'all' && c.id !== 'motion' && c.id !== 'log')
})

// New folder handling
const handleNewFolder = async (category) => {
  if (!requireLogin()) return
  const { value: folderName } = await ElMessageBox.prompt(
    'Enter folder name',
    'New Folder',
    {
      confirmButtonText: 'Create',
      cancelButtonText: 'Cancel',
      inputPattern: /^[a-zA-Z0-9_\-]+$/,
      inputErrorMessage: 'Only letters, numbers, _ and - allowed'
    }
  ).catch(() => ({ value: null }))
  
  if (!folderName) return
  
  try {
    const response = await fetch('/api/files/create_folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category,
        folder_name: folderName,
        dataset: dataset.value === 'ucf-crime' ? 'ucf' : 'sht'
      })
    })
    const result = await response.json()
    
    if (result.success) {
      ElMessage.success(`Folder "${folderName}" created`)
      loadFolders()
    } else {
      ElMessage.error(result.error || 'Create failed')
    }
  } catch (error) {
    ElMessage.error('Create failed: ' + error.message)
  }
}

const loadFolders = async () => {
  try {
    // Load all folders regardless of dataset
    const response = await fetch('/api/files/folders')
    const result = await response.json()
    if (result.success) {
      folders.value = result.folders || {}
    }
  } catch (error) {
    console.error('Failed to load folders:', error)
  }
}

// Folder navigation
const enterFolder = (folder) => {
  currentPath.value = [...folder.path]
  selectedFiles.value = []
}

const goBack = () => {
  if (currentPath.value.length > 0) {
    currentPath.value = currentPath.value.slice(0, -1)
    selectedFiles.value = []
  }
}

const goToRoot = () => {
  currentPath.value = []
  selectedFiles.value = []
}

const goToBreadcrumb = (index) => {
  currentPath.value = currentPath.value.slice(0, index + 1)
  selectedFiles.value = []
}

// Folders under current path
const currentFolders = computed(() => {
  let folders = visibleAllFolders.value
  
  // Show all top-level folders at root
  if (currentPath.value.length === 0) {
    // Filter by category
    if (activeCategory.value !== 'all') {
        folders = folders.filter(f => f.type === activeCategory.value)
    }
    return folders
  }
  
  // Single-level design: no subfolders
  return []
})

// Computed
const filteredFiles = computed(() => {
  let files = visibleAllFiles.value
  
  // At root, show only folders (no files)
  if (currentPath.value.length === 0) {
    return []
  }
  
  // Filter files under current path
  const pathStr = currentPath.value.join('/')
  files = files.filter(f => {
    const filePath = (f.folderPath || []).join('/')
    return filePath === pathStr
  })
  
  // Filter by category
  if (activeCategory.value !== 'all') {
    if (activeCategory.value === 'feature_vad') {
      files = files.filter(f => f.type === 'feature_vad')
    } else if (activeCategory.value === 'mask_pair') {
      // mask_pair contains video_ref and video_mask
      files = files.filter(f => f.type === 'video_ref' || f.type === 'video_mask')
    } else {
      files = files.filter(f => f.type === activeCategory.value)
    }
  }
  
  // Filter by search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    files = files.filter(f => 
      f.name.toLowerCase().includes(query) || 
      f.fullPath.toLowerCase().includes(query)
    )
  }
  
  return files
})

// Check if inside a folder
const isInFolder = computed(() => currentPath.value.length > 0)

// Current folder name
const currentFolderName = computed(() => {
  if (currentPath.value.length === 0) return ''
  return currentPath.value[currentPath.value.length - 1]
})

const previewFile = computed(() => {
  if (selectedFiles.value.length === 1) {
    return allFiles.value.find(f => f.id === selectedFiles.value[0])
  }
  return null
})

const selectedByType = computed(() => {
  const counts = {}
  selectedFiles.value.forEach(id => {
    const file = allFiles.value.find(f => f.id === id)
    if (file) {
      counts[file.type] = (counts[file.type] || 0) + 1
    }
  })
  return counts
})

const canDelete = computed(() => {
  return selectedFiles.value.length > 0
})

const deletableCount = computed(() => {
  return selectedFiles.value.length
})

const hasFeatureFiles = computed(() => {
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'feature'
  })
})

const selectedFeatureFiles = computed(() => {
  return selectedFiles.value.filter(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'feature'
  }).map(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file
  })
})

// Methods
const getCategoryCount = (catId) => {
  const files = visibleAllFiles.value
  if (catId === 'all') return files.length
  if (catId === 'trash') return trashItems.value.length
  if (catId === 'model') return files.filter(f => f.type === 'model').length
  if (catId === 'log') return files.filter(f => f.type === 'log').length
  if (catId === 'mask_pair') return files.filter(f => f.type === 'video_ref' || f.type === 'video_mask').length
  return files.filter(f => f.type === catId).length
}

const isVideoType = (type) => {
  return ['video_ref', 'video_mask', 'video_gen', 'mask_pair'].includes(type)
}

const getVideoPathPlaceholder = (type, action) => {
  const typeNames = {
    'video_ref': 'Reference',
    'video_mask': 'Mask',
    'video_gen': 'Gen'
  }
  const typeName = typeNames[type] || 'Video'
  return action === 'copy' ? 'Video target path...' : 'Move to directory...'
}

const hasVideoFiles = computed(() => {
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && isVideoType(file.type)
  })
})

const selectedVideoFiles = computed(() => {
  return selectedFiles.value.filter(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && isVideoType(file.type)
  }).map(id => allFiles.value.find(f => f.id === id))
})

// Type-specific video file checks
const hasRefVideos = computed(() => {
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'video_ref'
  })
})

const hasMaskVideos = computed(() => {
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'video_mask'
  })
})

const hasGenVideos = computed(() => {
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'video_gen'
  })
})

const selectedRefVideos = computed(() => {
  return selectedFiles.value.filter(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'video_ref'
  }).map(id => allFiles.value.find(f => f.id === id))
})

const selectedMaskVideos = computed(() => {
  return selectedFiles.value.filter(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'video_mask'
  }).map(id => allFiles.value.find(f => f.id === id))
})

const selectedGenVideos = computed(() => {
  return selectedFiles.value.filter(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'video_gen'
  }).map(id => allFiles.value.find(f => f.id === id))
})

// Background file checks
const hasBackgroundFiles = computed(() => {
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'background'
  })
})

const selectedBackgroundFiles = computed(() => {
  return selectedFiles.value.filter(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.type === 'background'
  }).map(id => allFiles.value.find(f => f.id === id))
})

const getTypeLabel = (type) => {
  const labels = {
    background: 'BG',
    motion: 'Motion',
    mask_pair: 'Pair',
    video_ref: 'Reference',
    video_mask: 'Mask',
    video_gen: 'Gen',
    feature: 'Feature',
    feature_vad: 'VAD Feature',
    model: 'Model',
    log: 'Log'
  }
  return labels[type] || type
}

const formatSize = (bytes) => {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

const toggleFileSelect = (file) => {
  const idx = selectedFiles.value.indexOf(file.id)
  if (idx >= 0) {
    selectedFiles.value.splice(idx, 1)
  } else {
    selectedFiles.value.push(file.id)
  }
}

const selectAll = () => {
  selectedFiles.value = filteredFiles.value.map(f => f.id)
}

const clearSelection = () => {
  selectedFiles.value = []
}

// Download handling
const canDownloadSelected = computed(() => {
  if (selectedFiles.value.length === 0) return false
  // At least one selected file must have a fullPath and not be a folder
  return selectedFiles.value.some(id => {
    const file = allFiles.value.find(f => f.id === id)
    return file && file.fullPath && !file.isFolder
  })
})

const downloadSelected = () => {
  if (!requireLogin()) return
  const filesToDownload = selectedFiles.value
    .map(id => allFiles.value.find(f => f.id === id))
    .filter(f => f && f.fullPath && !f.isFolder)
  
  if (filesToDownload.length === 0) {
    ElMessage.warning('No files to download')
    return
  }
  
  // Download each file by opening download URL in new hidden iframe/link
  filesToDownload.forEach((file, index) => {
    setTimeout(() => {
      const url = filesAPI.downloadUrl(file.fullPath)
      const link = document.createElement('a')
      link.href = url
      link.download = file.name
      link.style.display = 'none'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }, index * 300)  // Stagger downloads to avoid browser blocking
  })
  
  ElMessage.success(`Downloading ${filesToDownload.length} file(s)`)
}

// Upload handling
const handleUploadCategory = (category) => {
  if (!requireLogin()) return
  uploadCategory.value = category
  // Set accept based on category
  if (category === 'background') {
    uploadAccept.value = 'image/*'
  } else if (category.startsWith('video_')) {
    uploadAccept.value = 'video/*'
  } else if (category === 'feature') {
    uploadAccept.value = '.npy'
  } else {
    uploadAccept.value = '*/*'
  }
  // Trigger file input
  nextTick(() => {
    fileInputRef.value?.click()
  })
}

const handleFileUpload = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return
  
  const category = uploadCategory.value
  if (!category) {
    ElMessage.warning('Select upload category')
    return
  }
  
  const formData = new FormData()
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i])
  }
  formData.append('category', category)
  formData.append('dataset', dataset.value === 'ucf-crime' ? 'ucf' : 'sht')
  
  try {
    const response = await fetch('/api/files/upload', {
      method: 'POST',
      body: formData
    })
    const result = await response.json()
    
    if (result.success) {
      ElMessage.success(`Uploaded ${result.uploaded} file(s)`)
      refreshFiles()
    } else {
      ElMessage.error(result.error || 'Upload failed')
    }
  } catch (error) {
    ElMessage.error('Upload failed: ' + error.message)
  }
  
  // Reset file input
  event.target.value = ''
}

// Request version for canceling stale requests
let refreshVersion = 0

const refreshFiles = async () => {
  const currentVersion = ++refreshVersion
  loading.value = true
  
  // Collect data in temp arrays, replace at once to avoid flicker
  let newFolders = []
  let newFiles = []
  
  try {
    // Parallel initial requests - all datasets
    const [bgResponse, motionDirsResponse, genVideoResponse, featDirsResponse, modelsResponse, logsResponse] = await Promise.all([
      videoAPI.backgrounds('all').catch(e => ({ data: { backgrounds: [] } })),
      motionAPI.directories().catch(e => ({ data: { directories: [] } })),
      videoAPI.list('', '').catch(e => ({ data: { videos: [] } })),
      dataAPI.featureDirs().catch(e => ({ data: { directories: [] } })),
      trainAPI.models().catch(e => ({ data: { models: [] } })),
      isAdmin.value ? filesAPI.logs().catch(e => ({ data: { logs: [], groups: [] } })) : Promise.resolve({ data: { logs: [], groups: [] } })
    ])
    
    // Check if request is stale
    if (currentVersion !== refreshVersion) return
    
    // Process backgrounds - group by source folder
    const backgrounds = bgResponse.data.backgrounds || []
    
    // Parse source folder from path
    const getBgFolder = (path) => {
      if (path.includes('system_background')) return 'system_background'
      if (path.includes('sht_background')) return 'sht_background'
      if (path.includes('ucf_background')) return 'ucf_background'
      return 'other'
    }
    
    // Group backgrounds by source folder
    const bgFolderMap = new Map()
    backgrounds.forEach(bg => {
      const folderName = getBgFolder(bg.path)
      if (!bgFolderMap.has(folderName)) {
        bgFolderMap.set(folderName, [])
      }
      bgFolderMap.get(folderName).push(bg)
    })
    
    // Define folder order and labels
    const folderConfig = [
      { key: 'system_background', label: 'System Background', isSystem: true },
      { key: 'sht_background', label: 'SHT Background', isSystem: false },
      { key: 'ucf_background', label: 'UCF Background', isSystem: false }
    ]
    
    // Create folder list - always add all folders
    folderConfig.forEach(({ key, label, isSystem }) => {
      const bgs = bgFolderMap.get(key) || []
      newFolders.push({
        id: `folder_bg_${key}`,
        name: label,
        type: 'background',
        isFolder: true,
        path: [`bg_${key}`],
        count: bgs.length,
        isSystem
      })
    })
    
    // Create file list
    const bgFiles = backgrounds.map(bg => {
      const folderKey = getBgFolder(bg.path)
        return {
          id: `bg_${bg.name}_${folderKey}`,
          name: bg.name,
          type: 'background',
          url: bg.url,
          thumbUrl: bg.thumb_url,
          fullPath: bg.path,
          shortPath: bg.name,
          folderPath: [`bg_${folderKey}`]
        }
      })
      newFiles.push(...bgFiles)
    
    // Process generated videos
    const genVideos = genVideoResponse.data.videos || []
    const genFolderSet = new Set()
    genVideos.forEach(v => { if (v.folder) genFolderSet.add(v.folder) })
    
    const genFolders = []
    
    // System default folder first
    const systemFolder = 'system_generated'
    const systemCount = genVideos.filter(v => v.folder === systemFolder).length
    genFolders.push({
      id: `folder_video_gen_${systemFolder}`,
      name: 'System Generated',
      type: 'video_gen',
      isFolder: true,
      path: [systemFolder],
      count: systemCount,
      isSystem: true
    })
    
    // Other folders
    genFolderSet.forEach(folderName => {
      if (folderName !== systemFolder) {
        const count = genVideos.filter(v => v.folder === folderName).length
        genFolders.push({
          id: `folder_video_gen_${folderName}`,
          name: folderName,
          type: 'video_gen',
          isFolder: true,
          path: [folderName],
          count
        })
      }
    })
    
    const rootVideos = genVideos.filter(v => !v.folder)
    if (rootVideos.length > 0) {
      genFolders.push({
        id: 'folder_video_gen_root',
        name: 'Uncategorized',
        type: 'video_gen',
        isFolder: true,
        path: ['_video_gen_root'],
        count: rootVideos.length
      })
    }
    
    const genFiles = genVideos.map(v => {
      const urlPath = v.folder 
        ? `${encodeURIComponent(v.folder)}/${encodeURIComponent(v.name)}`
        : encodeURIComponent(v.name)
      return {
        id: `video_gen_${v.folder}_${v.name}`,
        name: v.name,
        type: 'video_gen',
        url: `/api/video/file/${urlPath}`,
        thumbUrl: v.thumb_url,
        fullPath: v.path,
        shortPath: v.folder ? `${v.folder}/${v.name}` : v.name,
        folder: v.folder,
        folderPath: v.folder ? [v.folder] : ['_video_gen_root']
      }
    })
    
    newFolders.push(...genFolders)
    newFiles.push(...genFiles)
    
    // First batch loaded, replace and stop loading
    allFolders.value = [...newFolders]
    allFiles.value = [...newFiles]
    loading.value = false
    
    if (currentVersion !== refreshVersion) return
    
    // Load motion dir details in parallel
    const motionDirs = motionDirsResponse.data.directories || []
    const motionPromises = motionDirs.map(dir => 
      motionAPI.list({ directory: dir.name }).catch(e => ({ data: { motions: [] } }))
    )
    const motionResponses = await Promise.all(motionPromises)
    
    if (currentVersion !== refreshVersion) return
    
    // Process motion and mask_pair data
    const motionFolders = []
    const maskPairFolders = []
    const motionFiles = []
    const maskPairFiles = []
    
    motionDirs.forEach((dir, idx) => {
      const motions = motionResponses[idx].data.motions || []
      let motionCount = 0
      let pairCount = 0
      
      motions.forEach(m => {
        // Motion files (raw motion data)
        motionCount++
        motionFiles.push({
          id: `motion_${m.motion_id}`,
          name: m.text || m.motion_id,
          type: 'motion',
          fullPath: m.motion_path,
          shortPath: `${dir.name}/${m.motion_id}`,
          folderPath: [`motion_${dir.name}`]
        })
        
        // Mask pair files (rendered reference and mask videos)
        if (m.renders) {
          m.renders.forEach(render => {
            if (render.has_composite) {
              pairCount++
              maskPairFiles.push({
                id: `video_ref_${m.motion_id}_${render.render_id}`,
                name: `${m.text || m.motion_id} - Reference`,
                type: 'video_ref',
                url: `/api/motion/video/${m.motion_id}/composite?render_id=${render.render_id}`,
                fullPath: render.composite_video,
                shortPath: `${dir.name}/${m.motion_id}/${render.render_id}`,
                folderPath: [`pair_${dir.name}`]
              })
            }
            if (render.has_mask) {
              maskPairFiles.push({
                id: `video_mask_${m.motion_id}_${render.render_id}`,
                name: `${m.text || m.motion_id} - Mask`,
                type: 'video_mask',
                url: `/api/motion/video/${m.motion_id}/mask?render_id=${render.render_id}`,
                fullPath: render.mask_video,
                shortPath: `${dir.name}/${m.motion_id}/${render.render_id}`,
                folderPath: [`pair_${dir.name}`]
              })
            }
          })
        }
      })
      
      // Check if system folder
      const isSystem = dir.name === 'runs_vad_system'
      const displayName = isSystem ? 'System Motion' : dir.name
      const displayNamePair = isSystem ? 'System Mask Pair' : dir.name
      
      // Motion folders - always show
      motionFolders.push({
        id: `folder_motion_${dir.name}`,
        name: displayName,
        type: 'motion',
        isFolder: true,
        path: [`motion_${dir.name}`],
        count: motionCount,
        isSystem
      })
      
      // Mask pair folders - always show
      maskPairFolders.push({
        id: `folder_pair_${dir.name}`,
        name: displayNamePair,
        type: 'mask_pair',
        isFolder: true,
        path: [`pair_${dir.name}`],
        count: pairCount,
        isSystem
      })
    })
    
    newFolders.push(...motionFolders, ...maskPairFolders)
    newFiles.push(...motionFiles, ...maskPairFiles)
    
    // Update view (motion + mask pair loaded)
    allFolders.value = [...newFolders]
    allFiles.value = [...newFiles]
    
    if (currentVersion !== refreshVersion) return
    
    // Load feature dir details in parallel
    // Root: synthetic only; subdir: all files
    featureDirectories.value = featDirsResponse.data.directories || []
    const featurePromises = featureDirectories.value.map(dir => {
      const params = { directory: dir.name }
      if (dir.is_root) params.synthetic_only = 'true'
      return dataAPI.listFeatures(params).catch(e => ({ data: { features: [] } }))
    })
    const featureResponses = await Promise.all(featurePromises)
    
    if (currentVersion !== refreshVersion) return
    
    // Update feature data immediately
    const featureFolders = []
    const featureFiles = []
    
    featureDirectories.value.forEach((dir, idx) => {
      const features = featureResponses[idx].data.features || []
      
      // Check if system folder
      const isSystem = dir.is_system || false
      // Display name consistent with training
      const displayName = dir.is_root
        ? `${dir.dataset} - Synth Samples`
        : dir.is_system
          ? dir.dataset
          : dir.folder
      
      // Always add folder even if empty
      featureFolders.push({
        id: `folder_feature_${dir.name}`,
        name: displayName,
        type: 'feature_vad',
        isFolder: true,
        path: [dir.name],
        count: features.length,
        dataset: dir.dataset,
        isSystem
      })
      
      const featureType = 'feature_vad'
      features.forEach(f => {
        featureFiles.push({
          id: `${featureType}_${dir.name}_${f.name}`,
          name: f.name,
          type: featureType,
          fullPath: f.path,
          shortPath: `${dir.dataset}/${f.name}`,
          cropCount: f.crop_count,
          directory: dir.name,
          folderPath: [dir.name]
        })
      })
    })
    
    newFolders.push(...featureFolders)
    newFiles.push(...featureFiles)
    
    // ─── Training Models ───
    const trainedModels = modelsResponse.data.models || []
    const discoveredLogGroups = isAdmin.value ? (logsResponse.data.groups || []) : []
    const discoveredLogFiles = isAdmin.value ? (logsResponse.data.logs || []) : []
    trainedModels.forEach(model => {
      // Model folders
      newFolders.push({
        id: `folder_model_${model.name}`,
        name: model.display_name || model.name,
        type: 'model',
        isFolder: true,
        path: [model.name],
        count: model.file_count || 0,
        dataset: model.dataset,
        diskPath: model.path,
        modelName: model.name,
        synthetic: model.synthetic,
        auc: model.auc,
        totalSize: model.total_size
      })
      
      // Model files
      const files = model.files || []
      files.forEach(f => {
        newFiles.push({
          id: `model_${model.name}_${f.name}`,
          name: f.name,
          type: 'model',
          fullPath: f.path,
          shortPath: `${model.display_name || model.name}/${f.name}`,
          size: f.size,
          directory: model.name,
          folderPath: [model.name],
          isDir: f.is_dir || false
        })
      })
    })
    if (isAdmin.value) {
      discoveredLogGroups.forEach(group => {
        newFolders.push({
          id: `folder_log_${group.id}`,
          name: group.label,
          type: 'log',
          isFolder: true,
          path: [group.id],
          count: group.count || 0,
          isSystem: true
        })
      })
      newFiles.push(...discoveredLogFiles.map(log => ({
        id: log.id,
        name: log.name,
        type: 'log',
        fullPath: log.fullPath || log.path,
        shortPath: log.shortPath,
        size: log.size,
        modified: log.modified,
        directory: log.directory,
        folderPath: log.folderPath || [log.directory]
      })))
    }
    
    // Final replace (all data loaded)
    allFolders.value = [...newFolders]
    allFiles.value = [...newFiles]
    
  } catch (e) {
    console.error('Failed to refresh files:', e)
  }
}

// ─── Internal Folder Picker ───
const folderPickerVisible = ref(false)
const folderPickerTitle = ref('')
const folderPickerConfirmText = ref('OK')
const folderPickerSelected = ref('')
const folderPickerMode = ref('copy') // 'copy' | 'move'

// Get type set of selected files
const selectedFileTypes = computed(() => {
  const types = new Set()
  for (const id of selectedFiles.value) {
    const file = allFiles.value.find(f => f.id === id)
    if (file) types.add(file.type)
  }
  return types
})

// File type to compatible folder type mapping
const typeCompatMap = {
  'background': ['background'],
  'video_gen': ['video_gen'],
  'video_ref': ['video_gen', 'mask_pair'],
  'video_mask': ['video_gen', 'mask_pair'],
  'motion': ['motion'],
  'feature_vad': ['feature_vad'],
}

const pickableFolders = computed(() => {
  const curPath = currentPath.value?.[0]
  // Determine selectable target folder types
  const allowedFolderTypes = new Set()
  for (const fileType of selectedFileTypes.value) {
    const compatTypes = typeCompatMap[fileType] || []
    compatTypes.forEach(t => allowedFolderTypes.add(t))
  }
  return allFolders.value.filter(f => {
    const diskPath = getFolderDiskPath(f)
    if (!diskPath) return false
    // Exclude current folder
    if (curPath && f.path?.[0] === curPath) return false
    // Show only compatible type folders
    if (allowedFolderTypes.size > 0 && !allowedFolderTypes.has(f.type)) return false
    return true
  })
})

const batchCopyTo = () => {
  if (!requireLogin()) return
  if (!selectedFiles.value.length) return
  folderPickerTitle.value = `Copy ${selectedFiles.value.length} file(s) to...`
  folderPickerConfirmText.value = 'Copy Here'
  folderPickerMode.value = 'copy'
  folderPickerSelected.value = ''
  folderPickerVisible.value = true
}

const batchMoveTo = () => {
  if (!requireLogin()) return
  if (!selectedFiles.value.length) return
  folderPickerTitle.value = `Move ${selectedFiles.value.length} file(s) to...`
  folderPickerConfirmText.value = 'Move Here'
  folderPickerMode.value = 'move'
  folderPickerSelected.value = ''
  folderPickerVisible.value = true
}

const confirmFolderPick = async () => {
  const folder = allFolders.value.find(f => f.id === folderPickerSelected.value)
  if (!folder) return
  const targetDir = getFolderDiskPath(folder)
  if (!targetDir) {
    ElMessage.error('Cannot resolve target folder path')
    return
  }

  const isCopy = folderPickerMode.value === 'copy'
  const actionLabel = isCopy ? 'Copy' : 'Move'

  if (!isCopy) {
    try {
      await ElMessageBox.confirm(
        `Move ${selectedFiles.value.length} file(s) to "${folder.name}"?`,
        'Confirm Move',
        { confirmButtonText: 'Move', cancelButtonText: 'Cancel' }
      )
    } catch { return }
  }

  folderPickerVisible.value = false

  let success = 0
  let failed = 0
  for (const id of selectedFiles.value) {
    const file = allFiles.value.find(f => f.id === id)
    if (!file || !file.fullPath) { failed++; continue }
    try {
      if (isCopy) {
        await videoAPI.copyVideo({ source: file.fullPath, target_dir: targetDir })
      } else {
        await videoAPI.moveVideo({ source: file.fullPath, target_dir: targetDir })
      }
      success++
    } catch (e) {
      failed++
      console.error(`Failed to ${actionLabel} ${file.name}:`, e)
    }
  }

  if (success > 0 && failed === 0) {
    ElMessage.success(`${actionLabel}d ${success} file(s) to "${folder.name}"`)
  } else if (success > 0) {
    ElMessage.warning(`${actionLabel}d ${success}, ${failed} failed`)
  } else {
    ElMessage.error(`${actionLabel} failed`)
  }
  if (!isCopy) selectedFiles.value = []
  refreshFiles()
}

const deleteSelected = async () => {
  if (!requireLogin()) return
  if (!selectedFiles.value.length) {
    ElMessage.warning('Select files to trash')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `Trash ${selectedFiles.value.length} file(s)?`,
      'Trash',
      { type: 'warning', confirmButtonText: 'Trash', cancelButtonText: 'Cancel' }
    )
    
    let deleted = 0
    let failed = 0
    // For mask pairs, ensure reference + mask are always deleted together
    const processedMaskPairs = new Set()

    for (const id of selectedFiles.value) {
      const file = allFiles.value.find(f => f.id === id)
      if (!file) { failed++; continue }
      
      try {
        if (file.type === 'feature' || file.type === 'feature_vad') {
          const dir = file.directory || id.split('_')[1]
          await dataAPI.deleteFeature(file.name, dir)
          deleted++
        } else if (file.type === 'background') {
          await videoAPI.deleteBackground(file.name)
          deleted++
        } else if (isVideoType(file.type) && file.type !== 'video_ref' && file.type !== 'video_mask') {
          await videoAPI.deleteVideo(file.fullPath)
          deleted++
        } else if (file.type === 'video_ref' || file.type === 'video_mask') {
          // Always trash ref + mask together as one logical pair
          const parts = (file.shortPath || '').split('/')
          const renderId = parts[parts.length - 1]
          const motionIdPart = parts[parts.length - 2]
          const pairKey = `${motionIdPart}__${renderId}`
          if (processedMaskPairs.has(pairKey)) {
            continue
          }
          processedMaskPairs.add(pairKey)
          
          const siblings = allFiles.value.filter(f =>
            (f.type === 'video_ref' || f.type === 'video_mask') &&
            f.shortPath &&
            f.shortPath.endsWith(`/${motionIdPart}/${renderId}`)
          )
          
          if (!siblings.length) {
            failed++
          } else {
            for (const s of siblings) {
              if (s.fullPath) {
                await videoAPI.deleteVideo(s.fullPath)
              }
            }
            deleted++
          }
        } else if (file.type === 'motion') {
          const motionId = id.replace('motion_', '')
          const res = await motionAPI.delete(motionId)
          if (res.data?.success) {
            deleted++
          } else {
            failed++
            console.error(`Failed to delete motion ${motionId}:`, res.data?.error || 'unknown error')
          }
        } else {
          // Fallback: try to delete by fullPath
          if (file.fullPath) {
            await videoAPI.deleteVideo(file.fullPath)
            deleted++
          } else {
            failed++
          }
        }
      } catch (e) {
        failed++
        console.error(`Failed to delete ${file.name}:`, e)
      }
    }
    
    if (deleted > 0 && failed === 0) {
      ElMessage.success(`Trashed ${deleted} file(s)`)
      loadTrash()
      setTimeout(loadTrash, 300)
    } else if (deleted > 0) {
      ElMessage.warning(`Trashed ${deleted}, ${failed} failed`)
      loadTrash()
      setTimeout(loadTrash, 300)
    } else {
      ElMessage.error(`Failed to trash (${failed} files)`)
    }
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Trash failed')
    }
  }
}

const copyFeatures = async () => {
  if (!copyTarget.value) {
    ElMessage.warning('Select target directory')
    return
  }
  
  const featureFiles = selectedFeatureFiles.value
  if (!featureFiles.length) {
    ElMessage.warning('No feature files selected')
    return
  }
  
  try {
    // Group files by source directory
    const filesByDir = {}
    featureFiles.forEach(f => {
      const dir = f.directory || f.id.split('_')[1]
      if (!filesByDir[dir]) filesByDir[dir] = []
      filesByDir[dir].push(f.name)
    })
    
    let copied = 0
    for (const [sourceDir, names] of Object.entries(filesByDir)) {
      if (sourceDir === copyTarget.value) continue
      
      const response = await dataAPI.copyFeatures({
        features: names,
        source_dir: sourceDir,
        target_dir: copyTarget.value
      })
      
      if (!response.data.error) {
        copied += names.length
      }
    }
    
    ElMessage.success(`Copied ${copied} feature file(s)`)
    copyTarget.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveFeatures = async () => {
  if (!moveTarget.value) {
    ElMessage.warning('Select target directory')
    return
  }
  
  const featureFiles = selectedFeatureFiles.value
  if (!featureFiles.length) {
    ElMessage.warning('No feature files selected')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `Move ${featureFiles.length} feature(s) to ${moveTarget.value}?`,
      'Confirm Move'
    )
    
    // Group files by source directory
    const filesByDir = {}
    featureFiles.forEach(f => {
      const dir = f.directory || f.id.split('_')[1]
      if (!filesByDir[dir]) filesByDir[dir] = []
      filesByDir[dir].push(f.name)
    })
    
    let moved = 0
    for (const [sourceDir, names] of Object.entries(filesByDir)) {
      if (sourceDir === moveTarget.value) continue
      
      const response = await dataAPI.moveFeatures({
        features: names,
        source_dir: sourceDir,
        target_dir: moveTarget.value
      })
      
      if (!response.data.error) {
        moved += names.length
      }
    }
    
    ElMessage.success(`Moved ${moved} feature file(s)`)
    moveTarget.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

// Single file actions
const copySingleFile = async () => {
  if (!requireLogin()) return
  if (!previewFile.value || !singleCopyTarget.value) return
  
  if (previewFile.value.type !== 'feature') {
    ElMessage.warning('Only feature files can be copied')
    return
  }
  
  try {
    const sourceDir = previewFile.value.directory || previewFile.value.id.split('_')[1]
    await dataAPI.copyFeatures({
      features: [previewFile.value.name],
      source_dir: sourceDir,
      target_dir: singleCopyTarget.value
    })
    
    ElMessage.success(`Copied to ${singleCopyTarget.value}`)
    singleCopyTarget.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveSingleFile = async () => {
  if (!requireLogin()) return
  if (!previewFile.value || !singleMoveTarget.value) return
  
  if (previewFile.value.type !== 'feature') {
    ElMessage.warning('Only feature files can be moved')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `Move ${previewFile.value.name} to ${singleMoveTarget.value}?`,
      'Confirm Move'
    )
    
    const sourceDir = previewFile.value.directory || previewFile.value.id.split('_')[1]
    await dataAPI.moveFeatures({
      features: [previewFile.value.name],
      source_dir: sourceDir,
      target_dir: singleMoveTarget.value
    })
    
    ElMessage.success(`Moved to ${singleMoveTarget.value}`)
    singleMoveTarget.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

// Single video file actions
const copySingleVideo = async () => {
  if (!requireLogin()) return
  if (!previewFile.value || !videoCopyPath.value) return
  
  if (!isVideoType(previewFile.value.type)) {
    ElMessage.warning('Only video files can be copied')
    return
  }
  
  try {
    await videoAPI.copyVideo({
      source: previewFile.value.fullPath,
      target_dir: videoCopyPath.value
    })
    
    ElMessage.success(`Copied to ${videoCopyPath.value}`)
    videoCopyPath.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveSingleVideo = async () => {
  if (!requireLogin()) return
  if (!previewFile.value || !videoMovePath.value) return
  
  if (!isVideoType(previewFile.value.type)) {
    ElMessage.warning('Only video files can be moved')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `Move ${previewFile.value.name} to ${videoMovePath.value}?`,
      'Confirm Move'
    )
    
    await videoAPI.moveVideo({
      source: previewFile.value.fullPath,
      target_dir: videoMovePath.value
    })
    
    ElMessage.success(`Moved to ${videoMovePath.value}`)
    videoMovePath.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

// Background file actions
const copySingleBackground = async () => {
  if (!requireLogin()) return
  if (!previewFile.value || !bgCopyTarget.value) return
  
  try {
    await videoAPI.copyBackground({
      name: previewFile.value.name,
      target_dataset: bgCopyTarget.value
    })
    
    ElMessage.success(`Copied to ${bgCopyTarget.value === 'sht' ? 'SHT' : 'UCF'} BG folder`)
    bgCopyTarget.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Copy failed')
  }
}

const moveSingleBackground = async () => {
  if (!requireLogin()) return
  if (!previewFile.value || !bgMoveTarget.value) return
  
  try {
    await ElMessageBox.confirm(
      `Move ${previewFile.value.name} to ${bgMoveTarget.value === 'sht' ? 'SHT' : 'UCF'} BG folder?`,
      'Confirm Move'
    )
    
    await videoAPI.moveBackground({
      name: previewFile.value.name,
      target_dataset: bgMoveTarget.value
    })
    
    ElMessage.success(`Moved to ${bgMoveTarget.value === 'sht' ? 'SHT' : 'UCF'} BG folder`)
    bgMoveTarget.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || 'Move failed')
    }
  }
}

const copyBackgrounds = async () => {
  if (!bgBatchCopyTarget.value || selectedBackgroundFiles.value.length === 0) return
  
  try {
    for (const file of selectedBackgroundFiles.value) {
      await videoAPI.copyBackground({
        name: file.name,
        target_dataset: bgBatchCopyTarget.value
      })
    }
    
    ElMessage.success(`Copied ${selectedBackgroundFiles.value.length} BG(s) to ${bgBatchCopyTarget.value === 'sht' ? 'SHT' : 'UCF'} folder`)
    bgBatchCopyTarget.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Copy failed')
  }
}

const moveBackgrounds = async () => {
  if (!bgBatchMoveTarget.value || selectedBackgroundFiles.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `Move ${selectedBackgroundFiles.value.length} BG(s) to ${bgBatchMoveTarget.value === 'sht' ? 'SHT' : 'UCF'} folder?`,
      'Confirm Move'
    )
    
    for (const file of selectedBackgroundFiles.value) {
      await videoAPI.moveBackground({
        name: file.name,
        target_dataset: bgBatchMoveTarget.value
      })
    }
    
    ElMessage.success(`Moved ${selectedBackgroundFiles.value.length} BG(s)`)
    bgBatchMoveTarget.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || 'Move failed')
    }
  }
}

// Type-specific video batch actions (Reference videos)
const copyRefVideos = async () => {
  if (!refVideoCopyPath.value || selectedRefVideos.value.length === 0) return
  
  try {
    for (const file of selectedRefVideos.value) {
      await videoAPI.copyVideo({
        source: file.fullPath,
        target_dir: refVideoCopyPath.value
      })
    }
    
    ElMessage.success(`Copied ${selectedRefVideos.value.length} ref video(s)`)
    refVideoCopyPath.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveRefVideos = async () => {
  if (!refVideoCopyPath.value || selectedRefVideos.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `Move ${selectedRefVideos.value.length} ref video(s)?`,
      'Confirm Move'
    )
    
    for (const file of selectedRefVideos.value) {
      await videoAPI.moveVideo({
        source: file.fullPath,
        target_dir: refVideoCopyPath.value
      })
    }
    
    ElMessage.success(`Moved ${selectedRefVideos.value.length} ref video(s)`)
    refVideoCopyPath.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

// Type-specific video batch actions (Mask videos)
const copyMaskVideos = async () => {
  if (!maskVideoCopyPath.value || selectedMaskVideos.value.length === 0) return
  
  try {
    for (const file of selectedMaskVideos.value) {
      await videoAPI.copyVideo({
        source: file.fullPath,
        target_dir: maskVideoCopyPath.value
      })
    }
    
    ElMessage.success(`Copied ${selectedMaskVideos.value.length} mask video(s)`)
    maskVideoCopyPath.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveMaskVideos = async () => {
  if (!maskVideoCopyPath.value || selectedMaskVideos.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `Move ${selectedMaskVideos.value.length} mask video(s)?`,
      'Confirm Move'
    )
    
    for (const file of selectedMaskVideos.value) {
      await videoAPI.moveVideo({
        source: file.fullPath,
        target_dir: maskVideoCopyPath.value
      })
    }
    
    ElMessage.success(`Moved ${selectedMaskVideos.value.length} mask video(s)`)
    maskVideoCopyPath.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

// Type-specific video batch actions (Generated videos)
const copyGenVideos = async () => {
  if (!genVideoCopyPath.value || selectedGenVideos.value.length === 0) return
  
  try {
    for (const file of selectedGenVideos.value) {
      await videoAPI.copyVideo({
        source: file.fullPath,
        target_dir: genVideoCopyPath.value
      })
    }
    
    ElMessage.success(`Copied ${selectedGenVideos.value.length} gen video(s)`)
    genVideoCopyPath.value = ''
    refreshFiles()
  } catch (error) {
    ElMessage.error(error.message || 'Copy failed')
  }
}

const moveGenVideos = async () => {
  if (!genVideoCopyPath.value || selectedGenVideos.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `Move ${selectedGenVideos.value.length} gen video(s)?`,
      'Confirm Move'
    )
    
    for (const file of selectedGenVideos.value) {
      await videoAPI.moveVideo({
        source: file.fullPath,
        target_dir: genVideoCopyPath.value
      })
    }
    
    ElMessage.success(`Moved ${selectedGenVideos.value.length} gen video(s)`)
    genVideoCopyPath.value = ''
    selectedFiles.value = []
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || 'Move failed')
    }
  }
}

// Rename file
const renameFile = async (file) => {
  if (!requireLogin()) return
  if (!file) return
  
  const currentName = file.name
  const { value: newName } = await ElMessageBox.prompt(
    'Enter new filename',
    'Rename File',
    {
      confirmButtonText: 'OK',
      cancelButtonText: 'Cancel',
      inputValue: currentName,
      inputPattern: /^[\w\u4e00-\u9fff\-. ]+$/,
      inputErrorMessage: 'Invalid characters'
    }
  ).catch(() => ({ value: null }))
  
  if (!newName || newName === currentName) return
  
  try {
    const res = await videoAPI.renameFile({ path: file.fullPath, new_name: newName })
    if (res.data.success) {
      ElMessage.success(`Renamed to ${res.data.new_name}`)
      selectedFiles.value = []
      refreshFiles()
    } else {
      ElMessage.error(res.data.error || 'Rename failed')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Rename failed')
  }
}

// Rename folder
const renameFolder = async (folder) => {
  if (!folder) return
  
  // Model type uses dedicated API
  if (folder.type === 'model') {
    const { value: newName } = await ElMessageBox.prompt(
      'Enter new model name',
      'Rename Model',
      {
        confirmButtonText: 'OK',
        cancelButtonText: 'Cancel',
        inputValue: folder.modelName || folder.path?.[0],
        inputPattern: /^[\w\u4e00-\u9fff\-. ]+$/,
        inputErrorMessage: 'Invalid characters'
      }
    ).catch(() => ({ value: null }))
    
    if (!newName || newName === (folder.modelName || folder.path?.[0])) return
    
    try {
      const res = await trainAPI.renameModel({ old_name: folder.modelName || folder.path?.[0], new_name: newName })
      if (res.data.success) {
        ElMessage.success(`Renamed to ${newName}`)
        refreshFiles()
      } else {
        ElMessage.error(res.data.error || 'Rename failed')
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.error || 'Rename failed')
    }
    return
  }
  
  // Get folder disk path
  const folderDiskPath = getFolderDiskPath(folder)
  if (!folderDiskPath) {
    ElMessage.warning('This folder cannot be renamed')
    return
  }
  
  const { value: newName } = await ElMessageBox.prompt(
    'Enter new folder name',
    'Rename Folder',
    {
      confirmButtonText: 'OK',
      cancelButtonText: 'Cancel',
      inputValue: folder.name,
      inputPattern: /^[\w\u4e00-\u9fff\-. ]+$/,
      inputErrorMessage: 'Invalid characters'
    }
  ).catch(() => ({ value: null }))
  
  if (!newName || newName === folder.name) return
  
  try {
    const res = await videoAPI.renameFolder({ path: folderDiskPath, new_name: newName })
    if (res.data.success) {
      ElMessage.success(`Renamed to ${res.data.new_name}`)
      refreshFiles()
    } else {
      ElMessage.error(res.data.error || 'Rename failed')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Rename failed')
  }
}

// Delete folder
const deleteFolder = async (folder) => {
  if (!folder) return
  
  // Model type uses dedicated API
  if (folder.type === 'model') {
    try {
      await ElMessageBox.confirm(
        `Trash model "${folder.name}"?`,
        'Trash',
        { type: 'warning', confirmButtonText: 'Trash', cancelButtonText: 'Cancel' }
      )
      const res = await trainAPI.deleteModel(folder.modelName || folder.path?.[0])
      if (res.data.success) {
        ElMessage.success(`Model "${folder.name}" trashed`)
        currentPath.value = []
        loadTrash()
        refreshFiles()
      } else {
        ElMessage.error(res.data.error || 'Trash failed')
      }
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error(error.response?.data?.error || 'Trash failed')
      }
    }
    return
  }
  
  const folderDiskPath = getFolderDiskPath(folder)
  if (!folderDiskPath) {
    ElMessage.warning('This folder does not support this operation')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `Trash folder "${folder.name}" and all contents?`,
      'Trash',
      { type: 'warning', confirmButtonText: 'Trash', cancelButtonText: 'Cancel' }
    )
    
    const res = await videoAPI.deleteFolder({ path: folderDiskPath })
    if (res.data.success) {
      ElMessage.success(`Folder "${folder.name}" trashed (${res.data.file_count} files)`)
      currentPath.value = []
      loadTrash()
      refreshFiles()
    } else {
      ElMessage.error(res.data.error || 'Trash failed')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || 'Trash failed')
    }
  }
}

const configuredPaths = ref(null)

// Get disk path from folder info
const getFolderDiskPath = (folder) => {
  if (!configuredPaths.value) return null
  const pathSegments = folder.path || []
  const folderKey = pathSegments[0] || ''
  
  // Background folders
  if (folderKey.startsWith('bg_')) {
    const bgKey = folderKey.replace('bg_', '')
    const bgDirMap = {
      'system_background': `${configuredPaths.value.comfyui}/system_background`,
      'sht_background': `${configuredPaths.value.comfyui}/sht_background`,
      'ucf_background': `${configuredPaths.value.comfyui}/ucf_background`
    }
    return bgDirMap[bgKey] || null
  }
  
  // Generated video folders
  if (folder.type === 'video_gen') {
    return `${configuredPaths.value.comfyui}/output/video/${folderKey}`
  }
  
  // Motion folders
  if (folderKey.startsWith('motion_')) {
    return `${configuredPaths.value.motionstreamer}/${folderKey.replace('motion_', '')}`
  }
  
  // Mask pair folders
  if (folderKey.startsWith('pair_')) {
    return `${configuredPaths.value.motionstreamer}/${folderKey.replace('pair_', '')}`
  }
  
  // Feature folders
  if (folder.type === 'feature_vad') {
    // folder.path = [dir.name], dir.name is like "shanghaitech/SH_clip_video_features/system_extracted"
    return `${configuredPaths.value.dataset}/${folderKey}`
  }
  
  // Training model folders
  if (folder.type === 'model') {
    return folder.diskPath || `${configuredPaths.value.checkpoints}/${folderKey}`
  }
  
  return null
}

const deleteSingleFile = async () => {
  if (!previewFile.value) return
  
  const file = previewFile.value
  try {
    await ElMessageBox.confirm(
      `Trash "${file.name}"?`,
      'Trash',
      { type: 'warning', confirmButtonText: 'Trash', cancelButtonText: 'Cancel' }
    )
    
    if (file.type === 'feature') {
      const dir = file.directory || file.id.split('_')[1]
      await dataAPI.deleteFeature(file.name, dir)
    } else if (file.type === 'background') {
      await videoAPI.deleteBackground(file.name)
    } else if (isVideoType(file.type) && file.type !== 'video_ref' && file.type !== 'video_mask') {
      await videoAPI.deleteVideo(file.fullPath)
    } else if (file.type === 'video_ref' || file.type === 'video_mask') {
      // Single mask pair item: always move both ref + mask to trash if they exist
      const parts = (file.shortPath || '').split('/')
      const renderId = parts[parts.length - 1]
      const motionIdPart = parts[parts.length - 2]
      const siblings = allFiles.value.filter(f =>
        (f.type === 'video_ref' || f.type === 'video_mask') &&
        f.shortPath &&
        f.shortPath.endsWith(`/${motionIdPart}/${renderId}`)
      )
      if (!siblings.length) {
        throw new Error('Mask pair not found')
      }
      for (const s of siblings) {
        if (s.fullPath) {
          await videoAPI.deleteVideo(s.fullPath)
        }
      }
    }
    
    ElMessage.success('Moved to trash')
    selectedFiles.value = []
    loadTrash()
    refreshFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Trash failed')
    }
  }
}

// Database-backed file management methods
const loadDbFiles = async () => {
  try {
    const response = await filesAPI.list()
    dbFiles.value = response.data.files || []
  } catch (error) {
    console.error('Failed to load database files:', error)
  }
}

const loadDbCategories = async () => {
  try {
    const response = await filesAPI.categories()
    dbCategories.value = response.data.categories || []
  } catch (error) {
    console.error('Failed to load categories:', error)
  }
}

const addSelectedToDatabase = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('Select files first')
    return
  }
  
  const filesToAdd = selectedFiles.value.map(id => {
    const file = allFiles.value.find(f => f.id === id)
    if (!file) return null
    return {
      name: file.name,
      original_path: file.fullPath,
      file_type: file.type,
      category: addToDbCategory.value || null,
      dataset: dataset.value === 'ucf-crime' ? 'ucf' : 'sht'
    }
  }).filter(f => f !== null)
  
  try {
    const response = await filesAPI.addBatch({ files: filesToAdd })
    if (response.data.success) {
      ElMessage.success(`Added ${response.data.added} file(s)${response.data.skipped > 0 ? `, skipped ${response.data.skipped} existing` : ''}`)
      addToDbCategory.value = ''
      loadDbFiles()
      loadDbCategories()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Failed to add to database')
  }
}

const addSingleToDatabase = async () => {
  if (!previewFile.value) return
  
  const file = previewFile.value
  try {
    const response = await filesAPI.add({
      name: file.name,
      original_path: file.fullPath,
      file_type: file.type,
      dataset: dataset.value === 'ucf-crime' ? 'ucf' : 'sht'
    })
    
    if (response.data.success) {
      ElMessage.success('Added to database')
      loadDbFiles()
      loadDbCategories()
    }
  } catch (error) {
    if (error.response?.status === 409) {
      ElMessage.warning('File already in database')
    } else {
      ElMessage.error(error.response?.data?.error || 'Failed to add to database')
    }
  }
}

const copyToDbCategory = async (fileIds, targetCategory) => {
  if (!fileIds.length || !targetCategory) return
  
  try {
    const response = await filesAPI.copyToCategory({
      file_ids: fileIds,
      category: targetCategory
    })
    if (response.data.success) {
      ElMessage.success(response.data.message)
      loadDbFiles()
      loadDbCategories()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Copy failed')
  }
}

const moveToDbCategory = async (fileIds, targetCategory) => {
  if (!fileIds.length || !targetCategory) return
  
  try {
    const response = await filesAPI.moveToCategory({
      file_ids: fileIds,
      category: targetCategory
    })
    if (response.data.success) {
      ElMessage.success(response.data.message)
      loadDbFiles()
      loadDbCategories()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Move failed')
  }
}

const deleteFromDatabase = async (fileId) => {
  try {
    await ElMessageBox.confirm(
      'Remove this record? The file will not be deleted.',
      'Confirm Remove',
      { type: 'warning' }
    )
    
    const response = await filesAPI.delete(fileId)
    if (response.data.success) {
      ElMessage.success('Removed from database')
      loadDbFiles()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || 'Remove failed')
    }
  }
}

// ─── Trash / Recycle Bin ───
const loadTrash = async () => {
  trashLoading.value = true
  try {
    const res = await trashAPI.list()
    trashItems.value = res.data.items || []
    trashTotalSize.value = res.data.total_size || 0
  } catch (e) {
    console.error('Failed to load trash:', e)
  } finally {
    trashLoading.value = false
  }
}

const toggleTrashSelect = (item) => {
  const idx = selectedTrashItems.value.indexOf(item.id)
  if (idx >= 0) {
    selectedTrashItems.value.splice(idx, 1)
  } else {
    selectedTrashItems.value.push(item.id)
  }
}

const selectAllTrash = () => {
  selectedTrashItems.value = trashItems.value.map(i => i.id)
}

const clearTrashSelection = () => {
  selectedTrashItems.value = []
}

const restoreTrashItem = async (item) => {
  if (!requireLogin()) return
  try {
    const res = await trashAPI.restore(item.id)
    if (res.data.success) {
      ElMessage.success(`Restored: ${item.original_name}`)
      loadTrash()
      refreshFiles()
    } else {
      ElMessage.error(res.data.error || 'Restore failed')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || 'Restore failed')
  }
}

const restoreSelectedTrash = async () => {
  if (!requireLogin()) return
  if (!selectedTrashItems.value.length) return
  try {
    const res = await trashAPI.restoreBatch(selectedTrashItems.value)
    ElMessage.success(`Restored ${res.data.restored} item(s)`)
    selectedTrashItems.value = []
    loadTrash()
    refreshFiles()
  } catch (e) {
    ElMessage.error('Batch restore failed')
  }
}

const permanentDeleteTrashItem = async (item) => {
  if (!requireLogin()) return
  try {
    await ElMessageBox.confirm(
      `Permanently delete "${item.original_name}"? Cannot be undone!`,
      'Permanently Delete',
      { type: 'warning', confirmButtonText: 'Permanently Delete', cancelButtonText: 'Cancel' }
    )
    const res = await trashAPI.delete(item.id)
    if (res.data.success) {
      ElMessage.success('Permanently deleted')
      loadTrash()
    } else {
      ElMessage.error(res.data.error || 'Delete failed')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('Delete failed')
  }
}

const permanentDeleteSelected = async () => {
  if (!requireLogin()) return
  if (!selectedTrashItems.value.length) return
  try {
    await ElMessageBox.confirm(
      `Permanently delete ${selectedTrashItems.value.length} item(s)? Cannot be undone!`,
      'Permanently Delete',
      { type: 'warning', confirmButtonText: 'Permanently Delete', cancelButtonText: 'Cancel' }
    )
    const res = await trashAPI.deleteBatch(selectedTrashItems.value)
    ElMessage.success(`Permanently deleted ${res.data.deleted} item(s)`)
    selectedTrashItems.value = []
    loadTrash()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('Batch delete failed')
  }
}

const emptyTrash = async () => {
  if (!requireLogin()) return
  if (!trashItems.value.length) return
  try {
    await ElMessageBox.confirm(
      `Empty trash? All ${trashItems.value.length} item(s) will be permanently deleted!`,
      'Empty Trash',
      { type: 'warning', confirmButtonText: 'Empty', cancelButtonText: 'Cancel' }
    )
    const res = await trashAPI.empty()
    ElMessage.success(`Trash emptied (${res.data.deleted} items)`)
    trashItems.value = []
    trashTotalSize.value = 0
    selectedTrashItems.value = []
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('Empty failed')
  }
}

const formatTrashTime = (timestamp) => {
  if (!timestamp) return ''
  const d = new Date(timestamp * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// formatSize is already defined above

// Watch trash tab
watch(activeCategory, (val) => {
  if (val === 'trash') {
    loadTrash()
  }
})

// Lifecycle
onMounted(async () => {
  try {
    configuredPaths.value = (await filesAPI.paths()).data
  } catch (error) {
    ElMessage.error('Could not load configured storage paths')
  }
  refreshFiles()
  loadDbFiles()
  loadDbCategories()
  loadFolders()
})

// Reload data when component restored from cache
onActivated(() => {
  refreshFiles()
})

// Cancel requests on keep-alive deactivate
onDeactivated(() => {
  refreshVersion++  // Expire all in-flight requests
})

// Cancel in-flight requests on unmount
onUnmounted(() => {
  refreshVersion++  // Expire all in-flight requests
})

// Watch for login state changes - load data when logged in
watch(isLoggedIn, (val) => {
  if (val) {
    refreshFiles()
    loadDbFiles()
    loadDbCategories()
    loadFolders()
  }
})

watch(isAdmin, (val) => {
  if (!val && activeCategory.value === 'log') {
    activeCategory.value = 'all'
  }
  currentPath.value = []
  selectedFiles.value = []
})

// Watch for dataset changes
watch(dataset, () => {
  if (isLoggedIn.value) {
    refreshFiles()
  }
})

// Watch for category changes - reset path
watch(activeCategory, (val) => {
  currentPath.value = []
  selectedFiles.value = []
  if (val === 'log' && isAdmin.value) {
    refreshFiles()
  }
})
</script>

<style scoped>
.file-management-view {
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

.file-manager-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  height: 100%;
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
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  background: var(--primary);
  color: white;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-btn:hover {
  background: var(--primary-dark);
}

.new-folder-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-folder-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.selection-info {
  font-size: 12px;
  color: var(--primary);
  font-weight: normal;
}

.panel-body {
  flex: 1;
  overflow: hidden;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Only make the right-side Preview panel scrollable */
.actions-panel .panel-body {
  overflow-y: auto;
  overflow-x: hidden;
}

/* Category Tabs */
.category-tabs {
  display: flex;
  gap: 2px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.category-tabs::-webkit-scrollbar {
  display: none;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.tab-btn:hover {
  background: rgba(51, 65, 85, 0.5);
}

.tab-btn.active {
  background: var(--primary);
  color: white;
}

.count-badge {
  font-size: 9px;
  padding: 0px 4px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.2);
}

.tab-btn:not(.active) .count-badge {
  background: rgba(100, 116, 139, 0.3);
}

/* File List Container */
.file-list-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px;
}

/* Toolbar */
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
}

.search-input :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
}

.search-input :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 12px;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.icon-btn {
  width: 32px;
  height: 32px;
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

/* File List */
/* Breadcrumb Navigation */
.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 6px;
  margin-bottom: 10px;
}

.breadcrumb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.2);
  color: var(--primary);
  cursor: pointer;
  transition: all 0.2s;
}

.breadcrumb-btn:hover {
  background: rgba(99, 102, 241, 0.3);
}

.breadcrumb-path {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
}

.breadcrumb-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.breadcrumb-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}

.breadcrumb-item.root {
  color: var(--primary);
}

.breadcrumb-item.active {
  color: var(--text-primary);
  font-weight: 500;
  cursor: default;
}

.breadcrumb-separator {
  color: var(--text-muted);
  font-size: 12px;
}

/* Folder Grid */
.folder-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  align-content: start;
}

.folder-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 10px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  position: relative;
}

.folder-item:hover {
  background: rgba(51, 65, 85, 0.5);
  border-color: rgba(99, 102, 241, 0.3);
  transform: translateY(-2px);
}

.folder-icon {
  color: #c4b5fd;
  margin-bottom: 8px;
}

.folder-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  width: 100%;
}

.folder-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.folder-count {
  font-size: 11px;
  color: var(--text-muted);
}

.folder-actions {
  position: absolute;
  bottom: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.folder-item:hover .folder-actions {
  opacity: 1;
}

.folder-action-btn {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.3);
  color: #c7d2fe;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.folder-action-btn:hover {
  background: rgba(99, 102, 241, 0.5);
  color: white;
}

.folder-action-btn.danger {
  background: rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

.folder-action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.5);
  color: white;
}

.rename-btn {
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 3px;
  background: rgba(99, 102, 241, 0.2);
  color: var(--primary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  transition: all 0.2s;
  vertical-align: middle;
}

.rename-btn:hover {
  background: rgba(99, 102, 241, 0.4);
  color: white;
}

.folder-type-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.folder-type-badge.background {
  background: rgba(59, 130, 246, 0.85);
  color: white;
}

.folder-type-badge.motion {
  background: rgba(234, 179, 8, 0.85);
  color: white;
}

.folder-type-badge.mask_pair {
  background: rgba(139, 92, 246, 0.85);
  color: white;
}

.folder-type-badge.video_ref {
  background: rgba(34, 197, 94, 0.85);
  color: white;
}

.folder-type-badge.video_mask {
  background: rgba(168, 85, 247, 0.85);
  color: white;
}

.folder-type-badge.video_gen {
  background: rgba(236, 72, 153, 0.85);
  color: white;
}

.folder-type-badge.feature_vad {
  background: rgba(107, 114, 128, 0.85);
  color: white;
}

.folder-type-badge.model {
  background: rgba(168, 85, 247, 0.85);
  color: white;
}

.file-list {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  align-content: start;
}

.file-item {
  display: flex;
  flex-direction: column;
  padding: 8px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  position: relative;
}

.file-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.file-item.selected {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.15);
}

.file-checkbox {
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 2;
}

.file-checkbox-native {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #6366f1;
}

.file-preview {
  position: relative;
  aspect-ratio: 16/10;
  border-radius: 6px;
  overflow: hidden;
  background: #000;
  margin-bottom: 6px;
}

.file-preview img,
.file-preview video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.file-icon-large {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-darker);
  color: var(--text-muted);
}

.file-type-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.file-type-badge.background {
  background: rgba(59, 130, 246, 0.85);
  color: white;
}

.file-type-badge.motion {
  background: rgba(234, 179, 8, 0.85);
  color: white;
}

.file-type-badge.mask_pair {
  background: rgba(139, 92, 246, 0.85);
  color: white;
}

.file-type-badge.video_ref {
  background: rgba(34, 197, 94, 0.85);
  color: white;
}

.file-type-badge.video_mask {
  background: rgba(168, 85, 247, 0.85);
  color: white;
}

.file-type-badge.video_gen {
  background: rgba(236, 72, 153, 0.85);
  color: white;
}

.file-type-badge.feature {
  background: rgba(107, 114, 128, 0.85);
  color: white;
}

.file-type-badge.model {
  background: rgba(168, 85, 247, 0.85);
  color: white;
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-path {
  font-size: 9px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Preview Section */
.preview-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-content {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  aspect-ratio: 16/9;
}

.preview-content img,
.preview-content video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.feature-preview {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--bg-darker);
  color: var(--text-muted);
}

.feature-label {
  font-size: 14px;
}

.preview-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: var(--bg-darker);
  border-radius: 8px;
}

.detail-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.detail-row .label {
  color: var(--text-muted);
  width: 50px;
  flex-shrink: 0;
}

.detail-row .value {
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-row .value.path {
  font-size: 10px;
  color: var(--text-secondary);
}

.type-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.type-tag.background { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.type-tag.motion { background: rgba(234, 179, 8, 0.2); color: #eab308; }
.type-tag.mask_pair { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
.type-tag.video_ref { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
.type-tag.video_mask { background: rgba(168, 85, 247, 0.2); color: #a855f7; }
.type-tag.video_gen { background: rgba(236, 72, 153, 0.2); color: #ec4899; }
.type-tag.feature { background: rgba(107, 114, 128, 0.2); color: #6b7280; }

/* Actions Section */
.actions-section {
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.section-title {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 12px 0;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.action-label {
  font-size: 11px;
  color: var(--text-secondary);
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
  height: 32px;
}

.action-select :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 12px;
}

.action-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(51, 65, 85, 0.5);
  color: var(--text-primary);
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

.action-btn.full-width {
  width: 100%;
}

.action-btn.danger {
  background: rgba(239, 68, 68, 0.2);
  color: var(--danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.action-btn.danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
}

.action-btn.success {
  background: rgba(16, 185, 129, 0.2);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.action-btn.success:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.3);
}


/* Single File Actions */
.single-file-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.type-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  padding: 6px 8px;
  background: rgba(99, 102, 241, 0.1);
  border-radius: 6px;
  margin-bottom: 4px;
}

.type-hint .el-icon {
  color: var(--primary-light);
}

.action-row-inline {
  display: flex;
  gap: 6px;
}

.action-select-inline {
  flex: 1;
}

.action-select-inline :deep(.el-input__wrapper) {
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid var(--border);
  box-shadow: none;
  height: 32px;
}

.action-select-inline :deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 12px;
}

.action-btn-sm {
  width: 36px;
  height: 32px;
  border: none;
  border-radius: 6px;
  background: rgba(51, 65, 85, 0.5);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.action-btn-sm:hover:not(:disabled) {
  background: rgba(51, 65, 85, 0.8);
}

.action-btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn-sm.primary {
  background: var(--primary);
  color: white;
}

.action-btn-sm.primary:hover:not(:disabled) {
  background: #4f46e5;
}

.selected-summary {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

.type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.type-dot.background { background: #3b82f6; }
.type-dot.motion { background: #eab308; }
.type-dot.mask_pair { background: #8b5cf6; }
.type-dot.video_ref { background: #22c55e; }
.type-dot.video_mask { background: #a855f7; }
.type-dot.video_gen { background: #ec4899; }
.type-dot.feature { background: #6b7280; }

/* Empty State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  color: var(--primary);
  gap: 16px;
}

.loading-state p {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 120px;
  color: var(--text-muted);
  gap: 12px;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}

/* Element Plus Overrides */
:deep(.el-checkbox__inner) {
  background: rgba(30, 41, 59, 0.8);
  border-color: var(--border);
}

:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background: var(--primary);
  border-color: var(--primary);
}

/* ─── Trash / Recycle Bin ─── */
.trash-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.trash-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #94a3b8;
  font-size: 13px;
}

.trash-size {
  color: #64748b;
}

.trash-actions-bar {
  display: flex;
  gap: 4px;
}

.trash-batch-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 8px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.batch-count {
  color: #a5b4fc;
  font-size: 13px;
  margin-right: auto;
}

.trash-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-right: 4px;
}

.trash-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(51, 65, 85, 0.3);
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  position: relative;
}

.trash-item:hover {
  background: rgba(51, 65, 85, 0.5);
}

.trash-item.selected {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.15);
}

.trash-icon {
  color: #64748b;
  flex-shrink: 0;
}

.trash-details {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trash-name {
  color: #e2e8f0;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trash-meta {
  color: #64748b;
  font-size: 11px;
}

.trash-path {
  color: #475569;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trash-item-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.trash-item:hover .trash-item-actions {
  opacity: 1;
}

.trash-footer {
  padding: 12px 0 0;
  border-top: 1px solid rgba(51, 65, 85, 0.5);
  margin-top: 12px;
  flex-shrink: 0;
}

/* ─── Folder Picker Dialog ─── */
.folder-picker-list {
  max-height: 400px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.folder-picker-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  background: rgba(30, 41, 59, 0.5);
  border: 2px solid transparent;
}

.folder-picker-item:hover {
  background: rgba(51, 65, 85, 0.6);
}

.folder-picker-item.selected {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.15);
}

.folder-picker-item .folder-icon {
  font-size: 22px;
  color: #f59e0b;
  flex-shrink: 0;
}

.folder-picker-item .folder-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.folder-picker-item .folder-name {
  font-size: 14px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.folder-picker-item .folder-type-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(100, 116, 139, 0.4);
  color: #94a3b8;
  flex-shrink: 0;
}

.folder-picker-item .folder-count {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
}

.folder-picker-list .empty-hint {
  text-align: center;
  color: #64748b;
  padding: 32px 0;
  font-size: 14px;
}

/* ─── No Permission State ─── */
.no-permission-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
  padding: 60px 20px;
}

.no-permission-state .el-icon {
  color: #475569;
}

.no-permission-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-secondary);
}

.no-permission-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}
</style>
