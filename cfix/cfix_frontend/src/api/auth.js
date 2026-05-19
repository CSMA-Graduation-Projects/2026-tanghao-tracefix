// 认证相关的前端接口封装，统一处理登录态请求。

import req from '@/utils/req'

/**
 * 登录
 * 当前后端支持：用户不存在时自动注册并登录
 */
export function login(data) {
  return req({
    url: '/auth/login',
    method: 'post',
    data
  })
}

/**
 * 获取当前用户信息
 */
export function getMe() {
  return req({
    url: '/auth/me',
    method: 'get'
  })
}

/**
 * 退出登录
 */
export function logout() {
  return req({
    url: '/auth/logout',
    method: 'post'
  })
}