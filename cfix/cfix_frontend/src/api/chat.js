import req from '@/utils/req'

/**
 * 获取会话列表
 */
export function listSess() {
  return req({
    url: '/chat/sess',
    method: 'get'
  })
}

/**
 * 新建会话
 */
export function createSess(data) {
  return req({
    url: '/chat/sess',
    method: 'post',
    data
  })
}

/**
 * 获取会话消息列表
 */
export function listMsg(sessId) {
  return req({
    url: `/chat/sess/${sessId}/msg`,
    method: 'get'
  })
}

/**
 * 追加消息
 */
export function addMsg(sessId, data) {
  return req({
    url: `/chat/sess/${sessId}/msg`,
    method: 'post',
    data
  })
}

/**
 * 从会话转任务
 */
export function chatToTask(sessId, data) {
  return req({
    url: `/chat/sess/${sessId}/to-task`,
    method: 'post',
    data
  })
}

/**
 * 修改会话标题
 */
export function updateSess(sessId, data) {
  return req({
    url: `/chat/sess/${sessId}`,
    method: 'put',
    data
  })
}
