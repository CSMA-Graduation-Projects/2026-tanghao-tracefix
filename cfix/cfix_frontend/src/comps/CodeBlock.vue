<template>
  <div class="code-wrap">
    <div class="code-head">
      <span>{{ title }}</span>
      <div class="code-tools">
        <slot name="tools" />
      </div>
    </div>
    <pre class="code-body">{{ content || emptyText }}</pre>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  content: { type: String, default: '' },
  emptyText: { type: String, default: '暂无内容' }
})
</script>

<style scoped>
.code-wrap { border:1px solid #1e293b; border-radius:14px; overflow:hidden; background:#0f172a; }
.code-head { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; color:#cbd5e1; background:#111827; border-bottom:1px solid #1f2937; }
.code-body { margin:0; min-height:280px; max-height:520px; overflow:auto; padding:16px; color:#e5e7eb; font-size:13px; line-height:1.65; white-space:pre-wrap; word-break:break-word; }
.code-tools { display:flex; gap:10px; }
</style>
