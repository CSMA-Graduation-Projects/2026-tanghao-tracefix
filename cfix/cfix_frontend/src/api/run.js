import req from '@/utils/req'

/**
 * 获取某个任务的全部运行记录
 */
export function listTaskRuns(taskId) {
  return req({
    url: `/run/task/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取单次运行完整详情
 * 更偏调试用途
 */
export function getRunDetail(runId) {
  return req({
    url: `/run/${runId}`,
    method: 'get'
  })
}

/**
 * 获取结构化执行反馈
 * WorkBench 右侧反馈区主接口
 */
export function getRunFb(runId) {
  return req({
    url: `/run/${runId}/fb`,
    method: 'get'
  })
}

/**
 * 获取运行轨迹
 */
export function getRunTrace(runId) {
  return req({
    url: `/run/${runId}/trace`,
    method: 'get'
  })
}

/**
 * 获取单用例执行结果
 * 对应后端：GET /run/{id}/cases
 */
export function getRunCases(runId) {
  return req({
    url: `/run/${runId}/cases`,
    method: 'get'
  })
}