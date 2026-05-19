// 模型配置相关的前端接口封装，负责模型列表和参数管理。

import req from '@/utils/req'

export function getModelConfig() {
  return req({
    url: '/model/config',
    method: 'get'
  })
}

export function saveModelConfig(data) {
  return req({
    url: '/model/config',
    method: 'put',
    data
  })
}