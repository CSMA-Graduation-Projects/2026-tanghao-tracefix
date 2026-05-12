<template>
  <div class="main-lay">
    <el-container class="main-wrap">
      <el-header class="top-header">
        <div class="header-left" @click="go('/workbench')">
          <div class="logo-box">CFIX</div>
          <div class="sys-info">
            <div class="sys-title">代码生成与自修复系统</div>
            <div class="sys-subtitle">基于代码执行反馈的研究原型平台</div>
          </div>
        </div>

        <div class="header-center">
          <div
            v-for="item in navs"
            :key="item.path"
            class="nav-item"
            :class="{ active: route.path === item.path }"
            @click="go(item.path)"
          >
            {{ item.label }}
          </div>
        </div>

        <div class="header-right">
          <div class="user-box">
            <el-avatar :size="34">{{ userInitial }}</el-avatar>
            <div class="user-meta">
              <div class="user-name">{{ username }}</div>
              <div class="user-role">{{ roleText }}</div>
            </div>
          </div>

          <el-button plain @click="go('/workbench')">返回工作台</el-button>
          <el-button type="danger" :loading="logoutLoading" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="page-main">
        <router-view v-slot="{ Component, route: currentRoute }">
          <keep-alive include="WorkBench">
            <component v-if="currentRoute.meta?.keepAlive" :is="Component" />
          </keep-alive>
          <component v-if="!currentRoute.meta?.keepAlive" :is="Component" />
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logout } from '@/api/auth'
import { useTaskUiStore, useUserStore } from '@/store'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const taskUiStore = useTaskUiStore()
const logoutLoading = ref(false)

const navs = [
  { path: '/workbench', label: '工作台' },
  { path: '/history', label: '历史任务' },
  { path: '/dataset', label: '数据集' },
  { path: '/experiment', label: '实验评估' },
  { path: '/setting', label: '系统设置' }
]

const username = computed(() => userStore.username || localStorage.getItem('username') || '未命名用户')
const userInitial = computed(() => (username.value || 'U').slice(0, 1).toUpperCase())
const roleText = computed(() => (userStore.role ? `角色：${userStore.role}` : '当前登录用户'))

function go(path) {
  if (route.path !== path) router.push(path)
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出当前登录状态吗？', '退出提示', {
      confirmButtonText: '确认退出',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  logoutLoading.value = true
  try {
    try {
      await logout()
    } catch {}
    taskUiStore.clearAll()
    userStore.clearLogin()
    ElMessage.success('已退出登录')
    router.replace('/login')
  } finally {
    logoutLoading.value = false
  }
}

onMounted(() => {
  if (userStore.token) {
    userStore.fetchProfile().catch(() => {})
  }
})
</script>

<style scoped>
.main-lay { min-height: 100vh; background: #f5f7fa; }
.main-wrap { min-height: 100vh; }
.top-header {
  height: 72px; padding: 0 18px; border-bottom: 1px solid #ebeef5; background: rgba(255,255,255,.96);
  backdrop-filter: blur(8px); display: grid; grid-template-columns: 320px 1fr auto; align-items: center;
  gap: 18px; position: sticky; top: 0; z-index: 20;
}
.header-left { display:flex; align-items:center; gap:12px; cursor:pointer; min-width:0; }
.logo-box { width:44px; height:44px; border-radius:14px; background:linear-gradient(135deg,#409eff,#67c23a); color:#fff; font-weight:700; display:flex; align-items:center; justify-content:center; }
.sys-title { font-size:16px; font-weight:700; color:#303133; }
.sys-subtitle { font-size:12px; color:#909399; margin-top:2px; }
.header-center { display:flex; align-items:center; gap:10px; }
.nav-item { height:38px; padding:0 16px; border-radius:10px; display:flex; align-items:center; cursor:pointer; color:#606266; transition:.2s; }
.nav-item:hover { background:#f0f7ff; color:#409eff; }
.nav-item.active { background:#ecf5ff; color:#409eff; font-weight:600; }
.header-right { display:flex; align-items:center; gap:12px; }
.user-box { display:flex; align-items:center; gap:10px; padding:6px 10px; border-radius:12px; background:#f7f9fc; border:1px solid #ebeef5; }
.user-name { font-size:14px; font-weight:600; color:#303133; }
.user-role { font-size:12px; color:#909399; }
.page-main { padding:0; }
@media (max-width: 1280px) {
  .top-header { grid-template-columns: 280px 1fr; height:auto; padding:12px 16px; }
  .header-right { grid-column: 1 / span 2; justify-content:flex-end; }
}
@media (max-width: 900px) {
  .top-header { grid-template-columns:1fr; }
  .header-center, .header-right { flex-wrap:wrap; }
  .header-right { justify-content:flex-start; }
}
</style>
