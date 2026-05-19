<template>
  <el-table v-if="rows.length" :data="rows" size="small" border height="360" style="width: 100%">
    <el-table-column prop="seq_no" label="序号" width="70" />
    <el-table-column prop="node_type" label="类型" width="90" />
    <el-table-column prop="func_name" label="函数" width="120" />
    <el-table-column prop="line_no" label="行号" width="80" />
    <el-table-column prop="log_text" label="日志信息" min-width="220" show-overflow-tooltip />
  </el-table>
  <el-empty v-else description="暂无轨迹数据" :image-size="90" />
</template>

<script setup>
// 轨迹表格组件，负责展示执行 trace 明细。
defineProps({ rows: { type: Array, default: () => [] } })
</script>
