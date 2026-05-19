// 数据集相关的前端接口封装，负责获取可用题库与数据集详情。

import req from '@/utils/req'

export function listDataset() {
  return req({ url: '/data/set', method: 'get' })
}

export function createDataset(data) {
  return req({ url: '/data/set', method: 'post', data })
}

export function deleteDataset(name) {
  return req({ url: `/data/set/${name}`, method: 'delete' })
}

export function getDatasetDetail(name) {
  return req({ url: `/data/set/${name}`, method: 'get' })
}

export function listDatasetItems(name) {
  return req({ url: `/data/set/${name}/items`, method: 'get' })
}

export function getDatasetItem(name, itemId) {
  return req({ url: `/data/set/${name}/items/${itemId}`, method: 'get' })
}

export function createDatasetItem(name, data) {
  return req({ url: `/data/set/${name}/items`, method: 'post', data })
}

export function updateDatasetItem(name, itemId, data) {
  return req({ url: `/data/set/${name}/items/${itemId}`, method: 'put', data })
}

export function deleteDatasetItem(name, itemId) {
  return req({ url: `/data/set/${name}/items/${itemId}`, method: 'delete' })
}
