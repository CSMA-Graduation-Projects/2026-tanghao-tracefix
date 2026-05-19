// 前端入口：负责初始化 Vue 应用、全局状态、路由和 Element Plus 组件库。
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

// 批量注册 Element Plus 图标，便于各页面直接按名称使用。
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 统一挂载状态管理、路由与 UI 组件库后再渲染应用。
app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
