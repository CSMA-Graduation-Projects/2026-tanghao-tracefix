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