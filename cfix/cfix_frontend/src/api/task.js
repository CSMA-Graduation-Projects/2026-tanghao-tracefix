// 任务链路相关的前端接口封装，负责创建任务、运行和自动修复。

import req from '@/utils/req'

/**
 * 获取任务列表
 * 可用于历史任务列表、任务抽屉
 */
export function listTask(params = {}) {
  return req({
    url: '/task',
    method: 'get',
    params
  })
}

/**
 * 创建任务
 */
export function createTask(data) {
  return req({
    url: '/task',
    method: 'post',
    data
  })
}

/**
 * 获取任务详情
 */
export function getTaskDetail(taskId, config = {}) {
  return req({
    url: `/task/${taskId}`,
    method: 'get',
    ...config
  })
}


/**
 * 更新任务元信息
 */
export function updateTask(taskId, data) {
  return req({
    url: `/task/${taskId}`,
    method: 'put',
    data
  })
}

/**
 * 删除任务
 * 当前前端未使用，保留给后续扩展
 */
export function deleteTask(taskId) {
  return req({
    url: `/task/${taskId}`,
    method: 'delete'
  })
}

/**
 * 生成初始代码
 */
export function genTask(taskId, data = {}) {
  return req({
    url: `/task/${taskId}/gen`,
    method: 'post',
    data
  })
}

/**
 * 执行当前最新版本
 */
export function runTask(taskId, data = {}) {
  return req({
    url: `/task/${taskId}/run`,
    method: 'post',
    data
  })
}

/**
 * 自动多轮修复
 */
export function autoFixTask(taskId, data) {
  return req({
    url: `/task/${taskId}/auto`,
    method: 'post',
    data
  })
}

/**
 * 中止当前任务（当前轮结束后停止）
 */
export function stopTask(taskId) {
  return req({
    url: `/task/${taskId}/stop`,
    method: 'post'
  })
}

/**
 * 获取任务当前状态
 */
export function getTaskStatus(taskId) {
  return req({
    url: `/task/${taskId}/status`,
    method: 'get'
  })
}

/**
 * 获取任务摘要
 */
export function getTaskSummary(taskId) {
  return req({
    url: `/task/${taskId}/summary`,
    method: 'get'
  })
}

/**
 * 获取任务版本列表
 */
export function listTaskVers(taskId) {
  return req({
    url: `/task/${taskId}/ver`,
    method: 'get'
  })
}

/**
 * 获取任务测试用例列表
 * 对应后端：GET /task/{id}/case
 */
export function getTaskCases(taskId) {
  return req({
    url: `/task/${taskId}/case`,
    method: 'get'
  })
}


/**
 * 替换任务当前测试用例
 */
export function updateTaskCases(taskId, data) {
  return req({
    url: `/task/${taskId}/case`,
    method: 'put',
    data
  })
}

/**
 * 获取任务修复计划列表
 * 对应后端：GET /task/{id}/plan
 */
export function getTaskPlans(taskId) {
  return req({
    url: `/task/${taskId}/plan`,
    method: 'get'
  })
}

/**
 * 获取任务 Lesson 列表
 * 对应后端：GET /task/{id}/lesson
 */
export function getTaskLessons(taskId) {
  return req({
    url: `/task/${taskId}/lesson`,
    method: 'get'
  })
}

/**
 * AI 生成测试用例
 */
export function genTaskCases(data) {
  return req({
    url: `/task/case/gen`,
    method: 'post',
    data
  })
}
