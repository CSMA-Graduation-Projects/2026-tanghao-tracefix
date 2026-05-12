<template>
  <div v-if="feedback" class="feedback-box">
    <div class="line"><span>运行结果</span><el-tag :type="feedback.result === 'pass' ? 'success' : 'danger'">{{ feedback.result || '-' }}</el-tag></div>
    <div class="line"><span>错误类型</span><strong>{{ feedback.err_type || '暂无' }}</strong></div>
    <div class="line"><span>报错行号</span><strong>{{ feedback.line_no ?? '暂无' }}</strong></div>
    <div class="line"><span>通过用例</span><strong>{{ feedback.pass_cnt ?? 0 }} / {{ feedback.total_cnt ?? 0 }}</strong></div>
    <div class="line"><span>耗时</span><strong>{{ feedback.time_ms ?? 0 }} ms</strong></div>
    <div class="block"><div class="block-title">错误提示</div><div class="block-body">{{ feedback.err_msg || '暂无错误提示' }}</div></div>
    <div class="block"><div class="block-title">轨迹摘要</div><div class="block-body">{{ feedback.trace_sum || '暂无轨迹摘要' }}</div></div>
  </div>
  <el-empty v-else description="暂无执行反馈" :image-size="80" />
</template>

<script setup>
defineProps({
  feedback: { type: Object, default: null }
})
</script>

<style scoped>
.feedback-box { display:flex; flex-direction:column; gap:10px; }
.line { display:flex; justify-content:space-between; align-items:center; padding:10px 12px; border:1px solid #ebeef5; border-radius:10px; background:#fafafa; gap:12px; }
.line span { color:#606266; font-size:13px; }
.line strong { color:#303133; font-size:13px; word-break:break-all; text-align:right; }
.block { border:1px solid #ebeef5; border-radius:10px; overflow:hidden; }
.block-title { padding:10px 12px; background:#f5f7fa; font-size:13px; font-weight:600; }
.block-body { padding:12px; font-size:13px; color:#606266; line-height:1.7; white-space:pre-wrap; word-break:break-word; }
</style>
