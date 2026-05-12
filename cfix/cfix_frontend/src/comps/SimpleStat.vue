<template>
  <div class="stat-grid">
    <div class="item" v-for="item in items" :key="item.label">
      <div class="label">{{ item.label }}</div>
      <div class="value">{{ item.value }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
</script>

<style scoped>
.stat-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(120px,1fr)); gap:12px; }
.item { padding:12px 14px; background:#fafafa; border:1px solid #ebeef5; border-radius:12px; }
.label { font-size:12px; color:#909399; margin-bottom:8px; }
.value { font-size:15px; font-weight:700; color:#303133; }
</style>
