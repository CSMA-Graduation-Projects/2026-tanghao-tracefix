import axios from 'axios'
import { ElMessage } from 'element-plus'

const baseURL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

const req = axios.create({
  baseURL,
  timeout: 1800000
})

req.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    const tokenType = localStorage.getItem('token_type') || 'bearer'

    if (token) {
      config.headers.Authorization = `${tokenType} ${token}`
    }

    if (!config.headers['Content-Type']) {
      config.headers['Content-Type'] = 'application/json'
    }

    return config
  },
  error => Promise.reject(error)
)

req.interceptors.response.use(
  response => {
    const res = response.data

    /**
     * 统一兼容后端标准格式：
     * {
     *   code: 200,
     *   msg: 'ok',
     *   data: ...
     * }
     */
    if (typeof res === 'object' && res !== null && 'code' in res) {
      if (res.code === 200) {
        return res
      }

      ElMessage.error(res.msg || '请求失败')
      return Promise.reject(new Error(res.msg || '请求失败'))
    }

    /**
     * 兼容极少数非统一格式返回
     */
    return res
  },
  error => {
    const status = error?.response?.status
    const silent = Boolean(error?.config?.silentError)
    const detail =
      error?.response?.data?.msg ||
      error?.response?.data?.detail ||
      error?.message ||
      '网络异常，请稍后重试'

    if (error && typeof error === 'object' && detail) {
      error.message = detail
    }

    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('token_type')
      localStorage.removeItem('username')

      if (!silent) ElMessage.error('登录状态已失效，请重新登录')

      if (!location.pathname.includes('/login')) {
        location.href = '/login'
      }
      return Promise.reject(error)
    }

    if (status === 403) {
      if (!silent) ElMessage.error('无权限访问该接口')
      return Promise.reject(error)
    }

    if (status === 404) {
      if (!silent) ElMessage.error(detail || '接口不存在')
      return Promise.reject(error)
    }

    if (status === 500) {
      if (!silent) ElMessage.error(detail || '服务器异常')
      return Promise.reject(error)
    }

    if (!silent) ElMessage.error(detail)
    return Promise.reject(error)
  }
)

export default req