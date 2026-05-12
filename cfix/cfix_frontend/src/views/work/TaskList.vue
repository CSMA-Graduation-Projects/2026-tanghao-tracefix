<template>
  <div class="page-wrap">
    <PageHead title="任务列表" desc="这一页可作为后续独立任务管理页，目前建议优先使用历史任务页。" />
    <el-alert type="info" :closable="false" title="当前阶段已将任务列表能力整合进 WorkBench 左侧和历史任务页中。" />
  </div>
</template>

<script setup>
import PageHead from '@/comps/PageHead.vue'
</script>
