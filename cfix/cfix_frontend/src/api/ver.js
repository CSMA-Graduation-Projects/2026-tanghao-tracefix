// 代码版本相关的前端接口封装，负责查看版本、差异和回滚。

import req from '@/utils/req'

/**
 * 获取版本基础信息
 */
export function getVerInfo(verId) {
  return req({
    url: `/ver/${verId}`,
    method: 'get'
  })
}

/**
 * 获取版本代码内容
 */
export function getVerCode(verId) {
  return req({
    url: `/ver/${verId}/code`,
    method: 'get'
  })
}

/**
 * 获取两个版本的 diff
 * 参数顺序：fromVerId -> toVerId
 */
export function getVerDiff(fromVerId, toVerId, opts = {}) {
  return req({
    url: `/ver/${fromVerId}/diff/${toVerId}`,
    method: 'get',
    silentError: Boolean(opts.silentError)
  })
}

/**
 * 手动把指定历史版本回退成一个新的 rollback 基线版本
 */
export function rollbackVersion(verId) {
  return req({
    url: `/ver/${verId}/rollback`,
    method: 'post'
  })
}
