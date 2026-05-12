<template>
  <div class="page-wrap">
    <PageHead title="历史任务" desc="查看历史任务概览，并可快速预览、检索、排序或回到工作台继续联调。">
      <el-button @click="loadData" :loading="loading">刷新列表</el-button>
    </PageHead>

    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :md="6"><div class="metric-card metric-card-total"><div class="metric-label">任务总数</div><div class="metric-value">{{ stats.total }}</div></div></el-col>
      <el-col :xs="12" :md="6"><div class="metric-card metric-card-pass"><div class="metric-label">通过任务</div><div class="metric-value">{{ stats.pass }}</div></div></el-col>
      <el-col :xs="12" :md="6"><div class="metric-card metric-card-fail"><div class="metric-label">失败任务</div><div class="metric-value">{{ stats.fail }}</div></div></el-col>
      <el-col :xs="12" :md="6"><div class="metric-card metric-card-rollback"><div class="metric-label">发生回退</div><div class="metric-value">{{ stats.rollback }}</div></div></el-col>
    </el-row>

    <el-card class="page-card" shadow="never">
      <div class="toolbar-row toolbar-row-center">
        <el-input v-model="keyword" placeholder="按任务ID / 标题 / 状态查询" clearable class="toolbar-search" @keyup.enter="noopSearch" />
        <el-button type="primary" class="toolbar-search-btn" @click="noopSearch">搜索</el-button>
      </div>
      <el-table :data="filteredRows" border v-loading="loading" style="width: 100%">
        <el-table-column type="index" label="序号" width="72" />
        <el-table-column prop="id" label="任务ID" width="110" sortable />
        <el-table-column prop="title" label="任务标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="fmtStatusType(displayStatus(row.id, row.status))">{{ fmtStatusLabel(displayStatus(row.id, row.status)) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cur_round" label="当前轮次" width="100" sortable />
        <el-table-column prop="best_score" label="最佳分数" width="100" sortable />
        <el-table-column prop="ver_cnt" label="版本数" width="92" sortable />
        <el-table-column prop="run_cnt" label="运行数" width="92" sortable />
        <el-table-column label="最近动作" min-width="160">
          <template #default="{ row }">
            <span>{{ row.latest_action_text || '暂无' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="回退" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.has_rollback" type="danger" effect="plain">有</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openTask(row)">继续打开</el-button>
            <el-button link @click="previewTask(row)">只读预览</el-button>
            <el-button type="danger" link @click="removeTask(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && !filteredRows.length" description="暂无匹配任务" :image-size="88" />
    </el-card>

    <el-drawer v-model="previewVisible" title="任务预览" size="560px">
      <template v-if="previewRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="任务ID">{{ previewRow.id }}</el-descriptions-item>
          <el-descriptions-item label="任务标题">{{ previewRow.title }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="fmtStatusType(displayStatus(previewRow.id, previewRow.status))">{{ fmtStatusLabel(displayStatus(previewRow.id, previewRow.status)) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前轮次">{{ previewRow.cur_round ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="最佳版本">{{ previewRow.best_ver_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="最佳分数">{{ previewRow.best_score ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="版本数">{{ previewRow.ver_cnt ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="运行数">{{ previewRow.run_cnt ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="最近动作">{{ previewRow.latest_action_text || '-' }}</el-descriptions-item>
          <el-descriptions-item label="题目描述">{{ previewRow.problem_text || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="preview-extra">
          <div class="extra-title">版本概览</div>
          <div class="chip-wrap" v-if="previewRow.version_brief?.length">
            <el-tag v-for="item in previewRow.version_brief" :key="item.id" effect="plain">
              V{{ item.ver_no }} · {{ item.ver_type }}
            </el-tag>
          </div>
          <el-empty v-else description="暂无版本信息" :image-size="70" />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/comps/PageHead.vue'
import { listTask, getTaskDetail, getTaskSummary, listTaskVers, deleteTask } from '@/api/task'
import { listTaskRuns } from '@/api/run'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskUiStore } from '@/store'
import { fmtStatusLabel, fmtStatusType } from '@/utils/fmt'

const router = useRouter()
const taskUiStore = useTaskUiStore()
const loading = ref(false)
const rows = ref([])
const previewVisible = ref(false)
const previewRow = ref(null)
const keyword = ref('')

function displayStatus(taskId, baseStatus) {
  return taskUiStore.taskStatusById(taskId, baseStatus)
}

function latestActionText(versions = [], runs = []) {
  const latestVer = [...versions].sort((a, b) => Number(b.ver_no || 0) - Number(a.ver_no || 0))[0]
  const latestRun = [...runs].sort((a, b) => Number(b.round_no || 0) - Number(a.round_no || 0))[0]
  const verText = latestVer ? `最新版本：${latestVer.ver_type}` : '无版本'
  const runText = latestRun ? `最近运行：${latestRun.result}` : '无运行'
  return `${verText} / ${runText}`
}

async function loadData() {
  loading.value = true
  try {
    const res = await listTask()
    const baseRows = Array.isArray(res.data) ? res.data : []

    const detailRows = await Promise.all(
      baseRows.map(async item => {
        const [detailRes, summaryRes, verRes, runRes] = await Promise.all([
          getTaskDetail(item.id).catch(() => ({ data: null })),
          getTaskSummary(item.id).catch(() => ({ data: null })),
          listTaskVers(item.id).catch(() => ({ data: [] })),
          listTaskRuns(item.id).catch(() => ({ data: [] }))
        ])

        const detail = detailRes.data || {}
        const versions = Array.isArray(verRes.data) ? verRes.data : []
        const runs = Array.isArray(runRes.data) ? runRes.data : []
        const summary = summaryRes.data || {}

        return {
          ...item,
          problem_text: detail.problem_text || '',
          best_ver_id: detail.best_ver_id ?? null,
          best_score: detail.best_score ?? summary.best_score ?? 0,
          ver_cnt: summary.ver_cnt ?? versions.length,
          run_cnt: runs.length,
          has_rollback: versions.some(v => v.ver_type === 'rollback'),
          latest_action_text: latestActionText(versions, runs),
          version_brief: versions.map(v => ({ id: v.id, ver_no: v.ver_no, ver_type: v.ver_type }))
        }
      })
    )

    rows.value = detailRows
  } finally {
    loading.value = false
  }
}

function openTask(row) {
  router.push({ path: '/workbench', query: { taskId: row.id } })
}

function previewTask(row) {
  previewRow.value = row
  previewVisible.value = true
}

async function removeTask(row) {
  try {
    await ElMessageBox.confirm(`确认删除任务 #${row.id} 吗？该操作会删除该任务的版本、运行和案例记录。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteTask(row.id)
    if (previewRow.value?.id === row.id) {
      previewVisible.value = false
      previewRow.value = null
    }
    await loadData()
    ElMessage.success('历史任务已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '删除历史任务失败')
    }
  }
}

const filteredRows = computed(() => {
  const kw = String(keyword.value || '').trim().toLowerCase()
  if (!kw) return rows.value
  return rows.value.filter(item => {
    const text = [item.id, item.title, item.status, fmtStatusLabel(item.status)].join(' ').toLowerCase()
    return text.includes(kw)
  })
})

const stats = computed(() => ({
  total: rows.value.length,
  pass: rows.value.filter(item => item.status === 'pass').length,
  fail: rows.value.filter(item => item.status === 'fail').length,
  rollback: rows.value.filter(item => item.has_rollback).length
}))

function noopSearch() {
  // 当前搜索为前端即时过滤，保留按钮是为了更符合使用习惯。
}

onMounted(loadData)
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.page-card { border-radius: 16px; }
.preview-extra { margin-top: 16px; }
.extra-title { margin-bottom: 10px; font-size: 13px; font-weight: 700; color: #303133; }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
.metric-card { padding: 14px 16px; border: 1px solid #ebeef5; border-radius: 14px; background: #fff; }
.metric-card-total { background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%); border-color: #dbeafe; }
.metric-card-pass { background: linear-gradient(180deg, #f0fdf4 0%, #ecfdf3 100%); border-color: #bbf7d0; }
.metric-card-fail { background: linear-gradient(180deg, #fef2f2 0%, #fff1f2 100%); border-color: #fecaca; }
.metric-card-rollback { background: linear-gradient(180deg, #fff7ed 0%, #fff1e6 100%); border-color: #fed7aa; }
.toolbar-row { display:flex; justify-content:flex-end; margin-bottom:14px; }
.toolbar-row-center { justify-content:center; gap: 10px; }
.toolbar-search { width: 360px; max-width: 100%; }
.toolbar-search-btn { flex-shrink: 0; }
.metric-label { font-size: 12px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 18px; font-weight: 700; color: #303133; }
</style>
