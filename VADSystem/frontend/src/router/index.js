import { createRouter, createWebHistory } from 'vue-router'
import MotionView from '../views/MotionView.vue'
import VideoGenView from '../views/VideoGenView.vue'
import DataProcessView from '../views/DataProcessView.vue'
import FileManagementView from '../views/FileManagementView.vue'
import TrainView from '../views/TrainView.vue'
import InferView from '../views/InferView.vue'
import AnalysisView from '../views/AnalysisView.vue'
import MonitorView from '../views/MonitorView.vue'

// Routes requiring authentication
const authRequiredRoutes = ['motion', 'video', 'data', 'files', 'train']

const routes = [
  {
    path: '/',
    redirect: '/infer'
  },
  {
    path: '/motion',
    name: 'motion',
    component: MotionView,
    meta: { requireAuth: true }
  },
  {
    path: '/video',
    name: 'video',
    component: VideoGenView,
    meta: { requireAuth: true }
  },
  {
    path: '/data',
    name: 'data',
    component: DataProcessView,
    meta: { requireAuth: true }
  },
  {
    path: '/files',
    name: 'files',
    component: FileManagementView,
    meta: { requireAuth: true }
  },
  {
    path: '/train',
    name: 'train',
    component: TrainView,
    meta: { requireAuth: true }
  },
  {
    path: '/infer',
    name: 'infer',
    component: InferView
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: MonitorView
  },
  {
    path: '/analysis',
    name: 'analysis',
    component: AnalysisView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
