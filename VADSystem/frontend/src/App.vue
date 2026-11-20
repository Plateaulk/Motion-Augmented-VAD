<template>
  <div class="app-wrapper">
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="28"><VideoCamera /></el-icon>
        </div>
        <div class="logo-text">
          <span class="logo-title">VAD System</span>
          <span class="logo-subtitle">Video Anomaly Detection</span>
        </div>
      </div>
      
      <nav class="nav-menu">
        <a
          v-for="item in allMenuItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
          @click.prevent="handleNavClick(item)"
        >
          <el-icon :size="20"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </a>
      </nav>
      
      <div class="sidebar-footer">
      </div>
    </aside>
    
    <main class="main-content">
      <header class="page-header">
        <h1 class="page-title">{{ currentPageTitle }}</h1>
        <div class="header-right">
          <div class="dataset-switcher">
            <button
              :class="['ds-btn', { active: !isUCF }]"
              @click="switchDataset(false)"
            >
              <span class="ds-dot sht"></span>
              SHT
            </button>
            <button
              :class="['ds-btn', { active: isUCF }]"
              @click="switchDataset(true)"
            >
              <span class="ds-dot ucf"></span>
              UCF
            </button>
          </div>
          <div class="auth-buttons" v-if="!currentUser">
            <button class="auth-btn login" @click="showLogin = true">
              <el-icon><User /></el-icon>
              <span>Login</span>
            </button>
            <button class="auth-btn register" @click="showRegister = true">
              <el-icon><Plus /></el-icon>
              <span>Register</span>
            </button>
          </div>
          <div class="user-info" v-else>
            <el-dropdown trigger="click" @command="handleUserCommand">
              <button class="user-btn">
                <el-icon><User /></el-icon>
                <span>{{ currentUser.username }}</span>
                <el-icon class="arrow"><ArrowDown /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item disabled>
                    <span class="user-email">{{ currentUser.email }}</span>
                  </el-dropdown-item>
                  <el-dropdown-item divided command="password">Change Password</el-dropdown-item>
                  <el-dropdown-item command="logout">Logout</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </header>
      
      <div class="page-content">
        <router-view :key="currentDataset" />
      </div>
    </main>
    
    <!-- Login Dialog -->
    <el-dialog v-model="showLogin" title="Login" width="400px" :close-on-click-modal="false">
      <el-form :model="loginForm" label-position="top">
        <el-form-item label="Username/Email">
          <el-input v-model="loginForm.username" placeholder="Enter username or email" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input v-model="loginForm.password" type="password" placeholder="Enter password" show-password @keyup.enter="handleLogin" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showLogin = false">Cancel</el-button>
          <el-button type="primary" @click="handleLogin" :loading="loginLoading">Login</el-button>
        </div>
        <div class="dialog-link">
          No account? <a href="#" @click.prevent="switchToRegister">Register now</a>
        </div>
      </template>
    </el-dialog>
    
    <!-- Register Dialog -->
    <el-dialog v-model="showRegister" title="Register" width="400px" :close-on-click-modal="false">
      <el-form :model="registerForm" label-position="top">
        <el-form-item label="Username">
          <el-input v-model="registerForm.username" placeholder="Enter username (min 3 chars)" />
        </el-form-item>
        <el-form-item label="Email">
          <el-input v-model="registerForm.email" placeholder="Enter email" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input v-model="registerForm.password" type="password" placeholder="Enter password (min 6 chars)" show-password />
        </el-form-item>
        <el-form-item label="Confirm Password">
          <el-input v-model="registerForm.confirmPassword" type="password" placeholder="Re-enter password" show-password @keyup.enter="handleRegister" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showRegister = false">Cancel</el-button>
          <el-button type="primary" @click="handleRegister" :loading="registerLoading">Register</el-button>
        </div>
        <div class="dialog-link">
          Have an account? <a href="#" @click.prevent="switchToLogin">Login now</a>
        </div>
      </template>
    </el-dialog>
    
    <!-- Change Password Dialog -->
    <el-dialog v-model="showPasswordDialog" title="Change Password" width="400px" :close-on-click-modal="false">
      <el-form :model="passwordForm" label-position="top">
        <el-form-item label="Old Password">
          <el-input v-model="passwordForm.oldPassword" type="password" placeholder="Enter old password" show-password />
        </el-form-item>
        <el-form-item label="New Password">
          <el-input v-model="passwordForm.newPassword" type="password" placeholder="Enter new password (min 6 chars)" show-password />
        </el-form-item>
        <el-form-item label="Confirm New Password">
          <el-input v-model="passwordForm.confirmPassword" type="password" placeholder="Re-enter new password" show-password @keyup.enter="handleChangePassword" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">Cancel</el-button>
        <el-button type="primary" @click="handleChangePassword" :loading="passwordLoading">Confirm</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, provide, onMounted, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI, inferAPI, monitorAPI } from './api'

const route = useRoute()
const router = useRouter()
const isUCF = ref(false)
const showLogin = ref(false)
const showRegister = ref(false)
const showPasswordDialog = ref(false)

// User state
const currentUser = ref(null)
const loginLoading = ref(false)
const registerLoading = ref(false)
const passwordLoading = ref(false)

// Forms
const loginForm = reactive({
  username: '',
  password: ''
})

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// Menu items, requireAuth = login required
const allMenuItems = [
  { path: '/motion', label: 'Mask Generator', icon: 'Brush', requireAuth: true },
  { path: '/video', label: 'Video Generator', icon: 'Film', requireAuth: true },
  { path: '/data', label: 'Data Process', icon: 'Cpu', requireAuth: true },
  { path: '/files', label: 'Manage Files', icon: 'FolderOpened', requireAuth: true },
  { path: '/train', label: 'Training', icon: 'SetUp', requireAuth: true },
  { path: '/infer', label: 'Inference', icon: 'Aim', requireAuth: false },
  { path: '/monitor', label: 'Monitor', icon: 'Monitor', requireAuth: false },
  { path: '/analysis', label: 'Analysis', icon: 'TrendCharts', requireAuth: false }
]

const isLoggedIn = computed(() => !!currentUser.value)

const currentPageTitle = computed(() => {
  const item = allMenuItems.find(m => m.path === route.path)
  return item?.label || 'VAD System'
})

const currentDataset = computed(() => isUCF.value ? 'ucf-crime' : 'shanghaitech')

const switchDataset = (toUCF) => {
  isUCF.value = toUCF
}

const monitorPreloadCache = new Set()
let monitorPreloadTimer = null

const selectMonitorModel = (modelList, datasetName) => {
  const candidates = modelList.filter(m => m.dataset === datasetName && m.available !== false)
  const synth = candidates.find(m => m.synthetic)
  return synth?.id || candidates[0]?.id || ''
}

const preloadMonitorForDataset = async (datasetName = currentDataset.value) => {
  let cacheKey = ''
  try {
    const res = await inferAPI.models()
    const modelId = selectMonitorModel(res.data.models || [], datasetName)
    if (!modelId) return

    cacheKey = `${datasetName}:${modelId}`
    if (monitorPreloadCache.has(cacheKey)) return
    monitorPreloadCache.add(cacheKey)

    await monitorAPI.preload({ model_id: modelId })
  } catch (error) {
    if (cacheKey) monitorPreloadCache.delete(cacheKey)
    console.warn('Monitor preload skipped:', error)
  }
}

const scheduleMonitorPreload = () => {
  if (monitorPreloadTimer) clearTimeout(monitorPreloadTimer)
  monitorPreloadTimer = setTimeout(() => {
    preloadMonitorForDataset()
  }, 600)
}

// Auth methods
const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('Enter username and password')
    return
  }
  
  loginLoading.value = true
  try {
    const response = await authAPI.login({
      username: loginForm.username,
      password: loginForm.password
    })
    
    if (response.data.success) {
      localStorage.setItem('auth_token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      currentUser.value = response.data.user
      showLogin.value = false
      loginForm.username = ''
      loginForm.password = ''
      ElMessage.success('Login successful')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Login failed')
  } finally {
    loginLoading.value = false
  }
}

const handleRegister = async () => {
  if (!registerForm.username || !registerForm.email || !registerForm.password) {
    ElMessage.warning('Please fill all required fields')
    return
  }
  
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning('Passwords do not match')
    return
  }
  
  registerLoading.value = true
  try {
    const response = await authAPI.register({
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password
    })
    
    if (response.data.success) {
      localStorage.setItem('auth_token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      currentUser.value = response.data.user
      showRegister.value = false
      registerForm.username = ''
      registerForm.email = ''
      registerForm.password = ''
      registerForm.confirmPassword = ''
      ElMessage.success('Registration successful')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Registration failed')
  } finally {
    registerLoading.value = false
  }
}

const handleChangePassword = async () => {
  if (!passwordForm.oldPassword || !passwordForm.newPassword) {
    ElMessage.warning('Please fill all required fields')
    return
  }
  
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.warning('New passwords do not match')
    return
  }
  
  passwordLoading.value = true
  try {
    const response = await authAPI.changePassword({
      old_password: passwordForm.oldPassword,
      new_password: passwordForm.newPassword
    })
    
    if (response.data.success) {
      showPasswordDialog.value = false
      passwordForm.oldPassword = ''
      passwordForm.newPassword = ''
      passwordForm.confirmPassword = ''
      ElMessage.success('Password changed')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || 'Password change failed')
  } finally {
    passwordLoading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user')
  currentUser.value = null
  ElMessage.success('Logged out')
}

const handleUserCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'password') {
    showPasswordDialog.value = true
  }
}

const switchToRegister = () => {
  showLogin.value = false
  showRegister.value = true
}

const switchToLogin = () => {
  showRegister.value = false
  showLogin.value = true
}

// Check for existing session on mount
onMounted(() => {
  const token = localStorage.getItem('auth_token')
  const user = localStorage.getItem('user')
  if (token && user) {
    try {
      currentUser.value = JSON.parse(user)
    } catch (e) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
    }
  }
  scheduleMonitorPreload()
})

watch(currentDataset, () => {
  scheduleMonitorPreload()
})

// requireLogin: called by child components, shows login dialog if not logged in
const requireLogin = () => {
  if (isLoggedIn.value) return true
  showLogin.value = true
  return false
}

// Navigation click handler: always allow navigation, login is enforced per-action inside each view
const handleNavClick = (item) => {
  router.push(item.path)
}

provide('dataset', currentDataset)
provide('isUCF', isUCF)
provide('currentUser', currentUser)
provide('isLoggedIn', isLoggedIn)
provide('requireLogin', requireLogin)
</script>

<style>
:root {
  --primary: #6366f1;
  --primary-light: #818cf8;
  --primary-dark: #4f46e5;
  --bg-dark: #0f172a;
  --bg-card: #1e293b;
  --bg-hover: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border-color: #334155;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --radius: 12px;
  --radius-sm: 8px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  color: var(--text-primary);
  min-height: 100vh;
}

.app-wrapper {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  position: fixed;
  height: 100vh;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  height: 72px;
  border-bottom: 1px solid var(--border-color);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.logo-subtitle {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  margin-top: 4px;
}

.nav-menu {
  flex: 1;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}


.sidebar-footer {
  padding: 0;
}


.main-content {
  flex: 1;
  margin-left: 220px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 28px;
  height: 72px;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 50;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--text-primary) 0%, var(--primary-light) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.dataset-switcher {
  display: flex;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 24px;
  padding: 4px;
  border: 1px solid var(--border-color);
}

.ds-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 20px;
  transition: all 0.2s ease;
}

.ds-btn:hover {
  color: var(--text-primary);
}

.ds-btn.active {
  background: var(--primary);
  color: white;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}

.ds-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.ds-dot.sht {
  background: #10b981;
}

.ds-dot.ucf {
  background: #f59e0b;
}

.auth-buttons {
  display: flex;
  gap: 8px;
}

.auth-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.auth-btn.login {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: var(--primary-light);
}

.auth-btn.login:hover {
  background: rgba(99, 102, 241, 0.25);
  border-color: rgba(99, 102, 241, 0.5);
}

.auth-btn.register {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
}

.auth-btn.register:hover {
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  transform: translateY(-1px);
}

.user-info {
  display: flex;
  align-items: center;
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: none;
  border-radius: 20px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: var(--primary-light);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-btn:hover {
  background: rgba(99, 102, 241, 0.25);
  border-color: rgba(99, 102, 241, 0.5);
}

.user-btn .arrow {
  font-size: 12px;
  margin-left: 4px;
}

.user-email {
  font-size: 12px;
  color: var(--text-muted);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.dialog-link {
  text-align: center;
  margin-top: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.dialog-link a {
  color: var(--primary-light);
  text-decoration: none;
}

.dialog-link a:hover {
  text-decoration: underline;
}

.page-content {
  flex: 1;
  padding: 20px 28px;
}

/* Element Plus overrides */
.el-card {
  background: rgba(30, 41, 59, 0.8) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: var(--radius) !important;
  backdrop-filter: blur(10px);
}

.el-card__header {
  border-bottom: 1px solid var(--border-color) !important;
  padding: 16px 20px !important;
}

.el-card__body {
  padding: 20px !important;
}

.el-input__wrapper,
.el-textarea__inner,
.el-select__wrapper {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
  box-shadow: none !important;
}

.el-input__inner,
.el-textarea__inner {
  color: var(--text-primary) !important;
}

.el-input__inner::placeholder,
.el-textarea__inner::placeholder {
  color: var(--text-muted) !important;
}

.el-form-item__label {
  color: var(--text-secondary) !important;
}

.el-button--primary {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
  border: none !important;
}

.el-table {
  background: transparent !important;
  color: var(--text-primary) !important;
}

.el-table tr,
.el-table th.el-table__cell {
  background: transparent !important;
}

.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background: rgba(51, 65, 85, 0.3) !important;
}

.el-table td.el-table__cell,
.el-table th.el-table__cell.is-leaf {
  border-bottom: 1px solid var(--border-color) !important;
}

.el-progress__text {
  color: var(--text-primary) !important;
}

.el-dialog {
  background: var(--bg-card) !important;
  border-radius: var(--radius) !important;
}

.el-dialog__header {
  border-bottom: 1px solid var(--border-color);
}

.el-dialog__body {
  padding-top: 24px !important;
}

.el-dialog__footer {
  padding-top: 8px !important;
}

.el-dialog__title {
  color: var(--text-primary) !important;
}

.el-empty__description {
  color: var(--text-muted) !important;
}

.el-tabs__item {
  color: var(--text-secondary) !important;
}

.el-tabs__item.is-active {
  color: var(--primary-light) !important;
}

.el-tabs__active-bar {
  background: var(--primary) !important;
}

.el-select-dropdown {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
}

.el-select-dropdown__item {
  color: var(--text-primary) !important;
}

.el-select-dropdown__item.hover,
.el-select-dropdown__item:hover {
  background: rgba(99, 102, 241, 0.15) !important;
  color: var(--primary-light) !important;
}

.el-select-dropdown__item.is-hovering {
  background: rgba(99, 102, 241, 0.15) !important;
  color: var(--primary-light) !important;
}

.el-select-dropdown__item.selected,
.el-select-dropdown__item.is-selected {
  background: rgba(99, 102, 241, 0.25) !important;
  color: var(--primary-light) !important;
  font-weight: 600;
}

.el-select-dropdown__item.is-disabled {
  color: var(--text-muted) !important;
  background: transparent !important;
}

/* Option group header */
.el-select-group__title {
  color: var(--text-muted) !important;
}

.el-popper.is-light {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-color) !important;
}

.el-popper.is-light .el-popper__arrow::before {
  background: var(--bg-card) !important;
  border-color: var(--border-color) !important;
}

/* Cascader, tree, menu hover - unified light-blue hover */
.el-cascader-menu .el-cascader-node:hover,
.el-cascader-menu .el-cascader-node.in-active-path,
.el-cascader-menu .el-cascader-node.is-active {
  background: rgba(99, 102, 241, 0.15) !important;
}

.el-tree-node__content:hover {
  background: rgba(99, 102, 241, 0.12) !important;
}

.el-menu-item:hover,
.el-sub-menu__title:hover {
  background: rgba(99, 102, 241, 0.12) !important;
}

/* Dropdown menu items */
.el-dropdown-menu__item:not(.is-disabled):hover,
.el-dropdown-menu__item:not(.is-disabled):focus {
  background: rgba(99, 102, 241, 0.15) !important;
  color: var(--primary-light) !important;
}

/* Autocomplete suggestions */
.el-autocomplete-suggestion li:hover {
  background: rgba(99, 102, 241, 0.15) !important;
}
</style>
