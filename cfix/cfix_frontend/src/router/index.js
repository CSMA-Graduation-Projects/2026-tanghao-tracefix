// 路由配置入口，负责页面路由声明与登录鉴权守卫。

import { createRouter, createWebHashHistory } from 'vue-router'

const Login = () => import('@/views/login/Login.vue')
const MainLay = () => import('@/layout/MainLay.vue')
const WorkBench = () => import('@/views/work/WorkBench.vue')
const HistList = () => import('@/views/hist/HistList.vue')
const DataSet = () => import('@/views/data/DataSet.vue')
const ExpList = () => import('@/views/exp/ExpList.vue')
const SysSet = () => import('@/views/set/SysSet.vue')

// 工作台与其余业务页统一挂在主布局下，登录页单独暴露为公开路由。
const routes = [
  { path: '/', redirect: '/workbench' },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    component: MainLay,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'workbench',
        name: 'WorkBench',
        component: WorkBench,
        meta: { title: '代码自修复工作台', requiresAuth: true, keepAlive: true }
      },
      {
        path: 'history',
        name: 'History',
        component: HistList,
        meta: { title: '历史任务', requiresAuth: true }
      },
      {
        path: 'dataset',
        name: 'DataSet',
        component: DataSet,
        meta: { title: '数据集', requiresAuth: true }
      },
      {
        path: 'experiment',
        name: 'Experiment',
        component: ExpList,
        meta: { title: '实验评估', requiresAuth: true }
      },
      {
        path: 'setting',
        name: 'SysSet',
        component: SysSet,
        meta: { title: '系统设置', requiresAuth: true }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/workbench' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  document.title = to.meta?.title ? `${to.meta.title} - 自修复系统` : '自修复系统'

  // 公开页面允许直接访问，但已登录用户无需回到登录页。
  if (to.meta?.public) {
    if (to.path === '/login' && token) {
      next('/workbench')
      return
    }
    next()
    return
  }

  // 受保护页面缺少 token 时统一回跳登录页，并带上原始目标地址。
  if (to.meta?.requiresAuth && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  next()
})

export default router
