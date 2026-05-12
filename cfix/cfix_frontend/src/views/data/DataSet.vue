<template>
  <div class="page-wrap dataset-page">
    <PageHead title="数据集" desc="管理实验题库与数据集任务，支持查看任务内容、加入工作台以及对自定义数据集进行增删改。">
      <div class="head-actions">
        <el-button type="primary" @click="openCreateDatasetDialog">添加数据集</el-button>
        <el-button type="danger" plain :disabled="!selectedMeta || selectedMeta?.builtin" @click="handleDeleteDataset">删除数据集</el-button>
        <el-button @click="loadAll">刷新</el-button>
      </div>
    </PageHead>

    <div class="dataset-layout">
      <el-card class="page-card dataset-side" shadow="never">
        <template #header>
          <div class="card-head">
            <span>数据集列表</span>
            <el-tag size="small" type="info">{{ datasetRows.length }}</el-tag>
          </div>
        </template>

        <div class="dataset-side-scroll">
          <div
            v-for="item in datasetRows"
            :key="item.name"
            class="dataset-list-item"
            :class="{ active: selectedDatasetName === item.name }"
            @click="handleSelectDataset(item)"
          >
            <div class="dataset-title-row">
              <div class="dataset-title">{{ item.display_name || item.name }}</div>
              <div class="dataset-tags">
                <el-tag v-if="item.builtin" size="small" type="info" effect="plain">内置</el-tag>
                <el-tag v-else size="small" type="success" effect="plain">自定义</el-tag>
              </div>
            </div>
            <div class="dataset-name">{{ item.name }}</div>
            <div class="dataset-desc">{{ item.desc || '暂无说明' }}</div>
            <div class="dataset-meta-row">
              <span>任务数：{{ item.size ?? 0 }}</span>
              <span v-if="item.aliases?.length">别名：{{ item.aliases.join(' / ') }}</span>
            </div>
          </div>

          <el-empty v-if="!datasetRows.length" description="暂无数据集" :image-size="88" />
        </div>
      </el-card>

      <div class="dataset-main">
        <el-card class="page-card" shadow="never">
          <template #header>
            <div class="card-head dataset-main-head">
              <div>
                <div class="main-title">{{ selectedMeta?.display_name || '请选择数据集' }}</div>
                <div class="main-subtitle">
                  <template v-if="selectedMeta">
                    <span>{{ selectedMeta.name }}</span>
                    <span>·</span>
                    <span>{{ selectedMeta.builtin ? '内置数据集' : '自定义数据集' }}</span>
                    <span>·</span>
                    <span>任务数 {{ selectedMeta.size ?? 0 }}</span>
                  </template>
                  <template v-else>
                    点击左侧任意数据集查看其中的测试任务列表。
                  </template>
                </div>
              </div>
              <div class="dataset-main-actions" v-if="selectedMeta">
                <el-button type="success" plain :disabled="selectedMeta?.builtin" @click="openCreateItemDialog">添加测试任务</el-button>
                <el-button @click="loadSelectedDataset">刷新任务列表</el-button>
              </div>
            </div>
          </template>

          <template v-if="selectedMeta">
            <div class="dataset-summary-grid">
              <div class="summary-card">
                <span class="summary-label">数据集标识</span>
                <span class="summary-value">{{ selectedMeta.name }}</span>
              </div>
              <div class="summary-card">
                <span class="summary-label">数据集说明</span>
                <span class="summary-value multi">{{ selectedMeta.desc || '暂无说明' }}</span>
              </div>
              <div class="summary-card">
                <span class="summary-label">别名兼容</span>
                <span class="summary-value multi">{{ selectedMeta.aliases?.length ? selectedMeta.aliases.join('、') : '无' }}</span>
              </div>
            </div>

            <el-table
              v-if="datasetItems.length"
              :data="datasetItems"
              size="small"
              border
              style="width: 100%"
              height="460"
            >
              <el-table-column type="index" label="序号" width="66" />
              <el-table-column prop="title" label="任务标题" min-width="220" show-overflow-tooltip />
              <el-table-column prop="scene" label="场景" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="sceneTagType(row.scene)">{{ row.scene }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="测试用例数" width="100">
                <template #default="{ row }">{{ row.case_count ?? row.cases?.length ?? 0 }}</template>
              </el-table-column>
              <el-table-column label="操作" width="370" fixed="right">
                <template #default="{ row }">
                  <div class="row-actions">
                    <el-button type="primary" plain size="small" @click="openViewDialog(row)">查看测试任务</el-button>
                    <el-button type="success" plain size="small" @click="addItemToWorkbench(row)">添加到工作台</el-button>
                    <el-button type="warning" plain size="small" @click="openEditItemDialog(row)">修改</el-button>
                    <el-button type="danger" plain size="small" @click="handleDeleteItem(row)">删除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="当前数据集暂无测试任务" :image-size="88" />
          </template>
          <el-empty v-else description="请选择左侧数据集" :image-size="88" />
        </el-card>
      </div>
    </div>

    <el-dialog v-model="datasetDialog.visible" title="添加数据集" width="560px" destroy-on-close>
      <el-form :model="datasetDialog.form" label-width="92px">
        <el-form-item label="数据集标识">
          <el-input v-model="datasetDialog.form.name" placeholder="如 custom_lab，仅支持小写字母、数字、下划线" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="datasetDialog.form.display_name" placeholder="如 自定义实验题库" />
        </el-form-item>
        <el-form-item label="数据集说明">
          <el-input v-model="datasetDialog.form.desc" type="textarea" :rows="4" placeholder="用于说明该数据集的用途、来源或题型范围。" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="datasetDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="datasetDialog.loading" @click="submitCreateDataset">确定添加</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="viewDialog.visible"
      :title="viewDialog.item?.title || '查看测试任务'"
      width="920px"
      top="5vh"
      class="task-view-dialog"
      destroy-on-close
    >
      <template v-if="viewDialog.item">
        <div class="task-view-dialog-scroll">
          <div class="task-view-grid">
          <div class="task-view-block">
            <div class="task-view-label">所属数据集</div>
            <div class="task-view-body short">{{ selectedMeta?.display_name || selectedMeta?.name }}</div>
          </div>
          <div class="task-view-block">
            <div class="task-view-label">任务场景</div>
            <div class="task-view-body short">{{ viewDialog.item.scene }}</div>
          </div>
          <div class="task-view-block span-all">
            <div class="task-view-label">题目描述</div>
            <div class="task-view-body desc-scroll">{{ viewDialog.item.problem_text }}</div>
          </div>
          <div class="task-view-block span-all">
            <div class="task-view-label">测试用例列表</div>
            <div class="task-view-body case-list-body">
              <div v-for="(item, index) in viewDialog.item.cases || []" :key="`${item.sort_no}-${index}`" class="case-view-card">
                <div class="case-view-head">
                  <span>用例 {{ item.sort_no || index + 1 }}</span>
                  <div class="case-view-head-right">
                    <el-tag size="small" :type="caseTypeTag(item.src_type)">{{ item.src_type || 'dataset' }}</el-tag>
                    <el-button link type="primary" size="small" @click="toggleCaseExpand(index)">
                      {{ isCaseExpanded(index) ? '收起' : '展开' }}
                    </el-button>
                  </div>
                </div>
                <pre v-if="isCaseExpanded(index)" class="case-view-pre">{{ item.assert_text }}</pre>
                <div v-else class="case-view-preview">{{ toCasePreview(item.assert_text) }}</div>
              </div>
              <el-empty v-if="!(viewDialog.item.cases || []).length" description="暂无测试用例" :image-size="72" />
            </div>
          </div>
        </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="itemDialog.visible"
      :title="itemDialog.mode === 'create' ? '添加测试任务' : '修改测试任务'"
      width="980px"
      destroy-on-close
    >
      <el-form :model="itemDialog.form" label-width="92px">
        <el-form-item label="任务标题">
          <el-input v-model="itemDialog.form.title" placeholder="请输入测试任务标题" />
        </el-form-item>
        <el-form-item label="任务场景">
          <el-select v-model="itemDialog.form.scene" style="width: 180px">
            <el-option label="func" value="func" />
            <el-option label="class" value="class" />
            <el-option label="file" value="file" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目描述">
          <el-input v-model="itemDialog.form.problem_text" type="textarea" :rows="6" placeholder="请输入题目描述" />
        </el-form-item>
        <el-form-item label="测试用例">
          <div class="edit-case-wrap">
            <div class="edit-case-toolbar">
              <el-button type="primary" plain size="small" @click="appendCaseRow">新增用例</el-button>
              <span class="edit-case-tip">每条用例可填写完整测试块内容，支持多行。</span>
            </div>
            <div class="edit-case-list">
              <div v-for="(item, index) in itemDialog.form.cases" :key="`edit-case-${index}`" class="edit-case-card">
                <div class="edit-case-head">
                  <span>用例 {{ index + 1 }}</span>
                  <div class="edit-case-head-actions">
                    <el-select v-model="item.src_type" size="small" style="width: 120px">
                      <el-option label="dataset" value="dataset" />
                      <el-option label="setup" value="setup" />
                      <el-option label="block" value="block" />
                    </el-select>
                    <el-button type="danger" plain size="small" @click="removeCaseRow(index)">删除</el-button>
                  </div>
                </div>
                <div class="edit-case-inline">
                  <el-input-number v-model="item.weight" :min="0.1" :step="0.1" size="small" />
                  <span class="edit-inline-tip">权重</span>
                </div>
                <el-input v-model="item.assert_text" type="textarea" :rows="4" placeholder="请输入完整测试块或断言内容" />
              </div>
              <el-empty v-if="!itemDialog.form.cases.length" description="请至少添加一条测试用例" :image-size="80" />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="itemDialog.loading" @click="submitItemDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import PageHead from '@/comps/PageHead.vue'
import {
  createDataset,
  createDatasetItem,
  deleteDataset,
  deleteDatasetItem,
  getDatasetDetail,
  listDataset,
  listDatasetItems,
  updateDatasetItem
} from '@/api/data'
import { createTask } from '@/api/task'

const router = useRouter()

const datasetRows = ref([])
const selectedDatasetName = ref('')
const selectedMeta = ref(null)
const datasetItems = ref([])
const pageLoading = ref(false)

const datasetDialog = reactive({
  visible: false,
  loading: false,
  form: {
    name: '',
    display_name: '',
    desc: ''
  }
})

const viewDialog = reactive({
  visible: false,
  item: null,
  expandedCaseKeys: []
})

const itemDialog = reactive({
  visible: false,
  loading: false,
  mode: 'create',
  itemId: '',
  form: buildEmptyItemForm()
})

function buildEmptyItemForm() {
  return {
    title: '',
    scene: 'func',
    problem_text: '',
    cases: [buildEmptyCaseRow(1)]
  }
}

function buildEmptyCaseRow(sortNo = 1) {
  return {
    src_type: 'dataset',
    case_in: null,
    expect_out: null,
    assert_text: '',
    weight: 1,
    sort_no: sortNo
  }
}

function sceneTagType(scene) {
  if (scene === 'file') return 'danger'
  if (scene === 'class') return 'warning'
  return 'success'
}

function caseTypeTag(srcType) {
  if (srcType === 'setup') return 'warning'
  if (srcType === 'block') return 'info'
  return 'success'
}

async function loadDatasetList() {
  const res = await listDataset()
  const names = Array.isArray(res.data) ? res.data : []
  const detailRows = await Promise.all(names.map(async (name) => {
    try {
      const rs = await getDatasetDetail(name)
      return rs.data || { name }
    } catch {
      return { name, display_name: name, desc: '', size: 0, aliases: [], builtin: false }
    }
  }))
  datasetRows.value = detailRows
  if (!selectedDatasetName.value && detailRows.length) {
    selectedDatasetName.value = detailRows[0].name
  }
}

async function loadSelectedDataset() {
  if (!selectedDatasetName.value) {
    selectedMeta.value = null
    datasetItems.value = []
    return
  }
  const [metaRes, itemRes] = await Promise.all([
    getDatasetDetail(selectedDatasetName.value),
    listDatasetItems(selectedDatasetName.value)
  ])
  selectedMeta.value = metaRes.data || null
  datasetItems.value = Array.isArray(itemRes.data) ? itemRes.data : []
}

async function loadAll() {
  pageLoading.value = true
  try {
    await loadDatasetList()
    if (selectedDatasetName.value) {
      await loadSelectedDataset()
    }
  } catch (error) {
    ElMessage.error(error?.message || '数据集加载失败')
  } finally {
    pageLoading.value = false
  }
}

function handleSelectDataset(item) {
  selectedDatasetName.value = item.name
  selectedMeta.value = item
  loadSelectedDataset()
}

function openCreateDatasetDialog() {
  datasetDialog.form = { name: '', display_name: '', desc: '' }
  datasetDialog.visible = true
}

async function submitCreateDataset() {
  if (!datasetDialog.form.name.trim()) {
    ElMessage.warning('请先填写数据集标识')
    return
  }
  if (!datasetDialog.form.display_name.trim()) {
    ElMessage.warning('请先填写显示名称')
    return
  }
  datasetDialog.loading = true
  try {
    const res = await createDataset({ ...datasetDialog.form })
    datasetDialog.visible = false
    selectedDatasetName.value = res.data?.name || datasetDialog.form.name
    await loadAll()
    ElMessage.success('数据集已添加')
  } catch (error) {
    ElMessage.error(error?.message || '添加数据集失败')
  } finally {
    datasetDialog.loading = false
  }
}

async function handleDeleteDataset() {
  if (!selectedMeta.value) {
    ElMessage.warning('请先选择数据集')
    return
  }
  if (selectedMeta.value.builtin) {
    ElMessage.warning('内置数据集不支持删除')
    return
  }
  await ElMessageBox.confirm(`确定删除数据集“${selectedMeta.value.display_name || selectedMeta.value.name}”吗？`, '删除确认', {
    type: 'warning'
  })
  try {
    await deleteDataset(selectedMeta.value.name)
    ElMessage.success('数据集已删除')
    selectedDatasetName.value = ''
    selectedMeta.value = null
    datasetItems.value = []
    await loadAll()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '删除数据集失败')
    }
  }
}

function openViewDialog(row) {
  viewDialog.item = JSON.parse(JSON.stringify(row))
  viewDialog.expandedCaseKeys = []
  viewDialog.visible = true
}

function toggleCaseExpand(index) {
  const pos = viewDialog.expandedCaseKeys.indexOf(index)
  if (pos >= 0) {
    viewDialog.expandedCaseKeys.splice(pos, 1)
    return
  }
  viewDialog.expandedCaseKeys.push(index)
}

function isCaseExpanded(index) {
  return viewDialog.expandedCaseKeys.includes(index)
}

function toCasePreview(text = '') {
  const flat = String(text || '').replace(/\s+/g, ' ').trim()
  return flat.length > 80 ? `${flat.slice(0, 80)}...` : (flat || '空内容')
}

function normalizeCasesForForm(cases = []) {
  if (!Array.isArray(cases) || !cases.length) {
    return [buildEmptyCaseRow(1)]
  }
  return cases.map((item, index) => ({
    src_type: item.src_type || 'dataset',
    case_in: item.case_in ?? null,
    expect_out: item.expect_out ?? null,
    assert_text: item.assert_text || '',
    weight: Number(item.weight || 1),
    sort_no: item.sort_no || index + 1
  }))
}

function openCreateItemDialog() {
  if (!selectedMeta.value) {
    ElMessage.warning('请先选择一个数据集')
    return
  }
  itemDialog.mode = 'create'
  itemDialog.itemId = ''
  itemDialog.form = buildEmptyItemForm()
  itemDialog.visible = true
}

function openEditItemDialog(row) {
  itemDialog.mode = 'edit'
  itemDialog.itemId = row.id
  itemDialog.form = {
    title: row.title || '',
    scene: row.scene || 'func',
    problem_text: row.problem_text || '',
    cases: normalizeCasesForForm(row.cases)
  }
  itemDialog.visible = true
}

function appendCaseRow() {
  itemDialog.form.cases.push(buildEmptyCaseRow(itemDialog.form.cases.length + 1))
}

function removeCaseRow(index) {
  itemDialog.form.cases.splice(index, 1)
  if (!itemDialog.form.cases.length) {
    itemDialog.form.cases.push(buildEmptyCaseRow(1))
  }
  itemDialog.form.cases.forEach((item, idx) => {
    item.sort_no = idx + 1
  })
}

function buildItemPayload() {
  const title = itemDialog.form.title.trim()
  const problemText = itemDialog.form.problem_text.trim()
  if (!title) {
    throw new Error('任务标题不能为空')
  }
  if (!problemText) {
    throw new Error('题目描述不能为空')
  }
  const cases = itemDialog.form.cases
    .map((item, index) => ({
      src_type: item.src_type || 'dataset',
      case_in: item.case_in ?? null,
      expect_out: item.expect_out ?? null,
      assert_text: (item.assert_text || '').trim(),
      weight: Number(item.weight || 1),
      sort_no: index + 1
    }))
    .filter(item => item.assert_text)
  if (!cases.length) {
    throw new Error('至少保留一条测试用例')
  }
  return {
    title,
    scene: itemDialog.form.scene || 'func',
    problem_text: problemText,
    cases
  }
}

async function submitItemDialog() {
  if (!selectedMeta.value) {
    ElMessage.warning('请先选择一个数据集')
    return
  }
  let payload
  try {
    payload = buildItemPayload()
  } catch (error) {
    ElMessage.warning(error.message)
    return
  }
  itemDialog.loading = true
  try {
    if (itemDialog.mode === 'create') {
      await createDatasetItem(selectedMeta.value.name, payload)
      ElMessage.success('测试任务已添加')
    } else {
      await updateDatasetItem(selectedMeta.value.name, itemDialog.itemId, payload)
      ElMessage.success('测试任务已更新')
    }
    itemDialog.visible = false
    await loadSelectedDataset()
    await loadDatasetList()
  } catch (error) {
    ElMessage.error(error?.message || '保存测试任务失败')
  } finally {
    itemDialog.loading = false
  }
}

async function handleDeleteItem(row) {
  if (!selectedMeta.value) return
  await ElMessageBox.confirm(`确定删除测试任务“${row.title}”吗？`, '删除确认', { type: 'warning' })
  try {
    await deleteDatasetItem(selectedMeta.value.name, row.id)
    ElMessage.success('测试任务已删除')
    await loadSelectedDataset()
    await loadDatasetList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '删除测试任务失败')
    }
  }
}

async function addItemToWorkbench(row) {
  try {
    const payload = {
      title: row.title,
      scene: row.scene,
      dataset: selectedMeta.value?.name || 'custom',
      problem_text: row.problem_text,
      max_round: 3,
      is_trace_on: true,
      is_lesson_on: true,
      cases: (row.cases || []).map((item, index) => ({
        src_type: item.src_type || 'dataset',
        case_in: item.case_in ?? null,
        expect_out: item.expect_out ?? null,
        assert_text: item.assert_text,
        weight: Number(item.weight || 1),
        sort_no: item.sort_no || index + 1
      }))
    }
    const res = await createTask(payload)
    const taskId = res.data?.id
    if (!taskId) {
      throw new Error('任务创建失败')
    }
    ElMessage.success('已添加到工作台')
    router.push({ name: 'WorkBench', query: { taskId } })
  } catch (error) {
    ElMessage.error(error?.message || '添加到工作台失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.dataset-page {
  min-height: 100%;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dataset-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.dataset-side {
  min-height: calc(100vh - 210px);
}

.dataset-side-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  padding-right: 4px;
}

.dataset-list-item {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
  background: #fff;
  transition: all 0.2s ease;
}

.dataset-list-item:hover {
  border-color: #c6e2ff;
  background: #f7fbff;
}

.dataset-list-item.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 8px 22px rgba(64, 158, 255, 0.12);
}

.dataset-title-row,
.card-head,
.dataset-main-head,
.edit-case-head,
.case-view-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.dataset-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}

.dataset-name {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.dataset-desc {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dataset-meta-row {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

.main-title {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.main-subtitle {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: #909399;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.dataset-main-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dataset-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.summary-card {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 14px;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-label {
  font-size: 12px;
  color: #909399;
}

.summary-value {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  word-break: break-word;
}

.summary-value.multi {
  font-weight: 500;
  line-height: 1.7;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-view-dialog-scroll {
  height: 100%;
  overflow-y: auto;
  padding-right: 4px;
}

.task-view-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.task-view-block {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
}

.task-view-block.span-all {
  grid-column: 1 / -1;
}

.task-view-label {
  padding: 12px 14px;
  background: #f5f7fa;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

.task-view-body {
  padding: 14px;
  color: #606266;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.task-view-body.short {
  min-height: 52px;
}

.task-view-body.desc-scroll {
  height: 220px;
  overflow-y: auto;
}

.case-list-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.case-view-card {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
}

.case-view-head {
  padding: 10px 12px;
  background: #fafafa;
  font-size: 13px;
  color: #303133;
  font-weight: 600;
}

.case-view-head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.case-view-preview {
  padding: 12px;
  font-size: 12px;
  line-height: 1.7;
  color: #606266;
  word-break: break-word;
}

.case-view-pre {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  border-top: 1px solid #ebeef5;
}

.edit-case-wrap {
  width: 100%;
}

.edit-case-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.edit-case-tip,
.edit-inline-tip {
  font-size: 12px;
  color: #909399;
}

.edit-case-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}

.edit-case-card {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 12px;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.edit-case-head-actions,
.edit-case-inline {
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.task-view-dialog .el-dialog) {
  height: min(84vh, 760px);
  display: flex;
  flex-direction: column;
}

:deep(.task-view-dialog .el-dialog__body) {
  flex: 1;
  overflow: hidden;
  padding-top: 12px;
}

@media (max-width: 1200px) {
  .dataset-layout {
    grid-template-columns: 1fr;
  }

  .dataset-side {
    min-height: 0;
  }

  .dataset-side-scroll {
    max-height: 360px;
  }

  .dataset-summary-grid,
  .task-view-grid {
    grid-template-columns: 1fr;
  }
}

</style>
