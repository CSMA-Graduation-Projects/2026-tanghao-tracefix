import { ElMessage } from 'element-plus'

export async function copyText(text) {
  if (!text) {
    ElMessage.warning('没有可复制的内容')
    return false
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功')
    return true
  } catch {
    ElMessage.error('复制失败，请手动复制')
    return false
  }
}
