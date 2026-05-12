<template>
  <el-card class="page-head" shadow="never">
    <div class="head-main">
      <div>
        <div class="title">{{ title }}</div>
        <div v-if="desc" class="desc">{{ desc }}</div>
      </div>
      <div class="extra">
        <slot />
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  desc: { type: String, default: '' }
})
</script>

<style scoped>
.page-head { border-radius: 16px; margin-bottom: 16px; }
.head-main { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
.title { font-size:22px; font-weight:700; color:#303133; }
.desc { font-size:13px; color:#909399; margin-top:6px; line-height:1.6; }
.extra { display:flex; align-items:center; gap:10px; }
</style>
