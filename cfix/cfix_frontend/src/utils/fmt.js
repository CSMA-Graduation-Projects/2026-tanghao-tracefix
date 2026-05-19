// 格式化工具函数，封装常用文本与数值格式化逻辑。

export function fmtStatusLabel(status) {
  const map = {
    draft: '草稿',
    queued: '排队中',
    generating: '生成中',
    testing: '测试中',
    fixing: '修复中',
    stopping: '停止中',
    running: '运行中',
    pass: '通过',
    fail: '失败',
    stop: '已停止'
  }
  return map[status] || '未开始'
}

export function fmtStatusType(status) {
  const map = {
    draft: 'info',
    queued: 'warning',
    generating: 'warning',
    testing: 'primary',
    fixing: 'danger',
    stopping: 'info',
    running: 'primary',
    pass: 'success',
    fail: 'danger',
    stop: 'info'
  }
  return map[status] || 'info'
}

export function fmtJson(val) {
  if (val === null || val === undefined || val === '') return '-'
  if (typeof val === 'string') return val
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}
