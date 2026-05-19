<template>
  <div class="page-wrap">
    <PageHead title="实验评估" desc="管理批量实验，支持检索、删除、查看结果，并导出实验报告。">
      <el-button @click="loadData" :loading="loading">刷新列表</el-button>
      <el-button type="success" plain :disabled="compareDisabled" @click="openCompare">实验对比（2-3组）</el-button>
      <el-button type="primary" @click="openCreate">新建实验</el-button>
    </PageHead>

    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :md="6">
        <div class="metric-card"><div class="metric-label">实验总数</div><div class="metric-value">{{ statCards.total }}</div></div>
      </el-col>
      <el-col :xs="12" :md="6">
        <div class="metric-card"><div class="metric-label">运行中</div><div class="metric-value">{{ statCards.running }}</div></div>
      </el-col>
      <el-col :xs="12" :md="6">
        <div class="metric-card"><div class="metric-label">已完成</div><div class="metric-value">{{ statCards.finished }}</div></div>
      </el-col>
      <el-col :xs="12" :md="6">
        <div class="metric-card"><div class="metric-label">平均最终通过率</div><div class="metric-value">{{ statCards.avgFinalPass }}</div></div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="16">
        <el-card class="page-card" shadow="never">
          <template #header>
            <div class="card-head">
              <span>实验列表</span>
              <span class="small-tip">优先读取后端 /exp；若后端尚未补齐 start/report/chart，则自动降级为前端原型模式。</span>
            </div>
          </template>

          <div class="toolbar-row toolbar-row-center">
            <el-input v-model="keyword" placeholder="按实验ID / 名称 / 数据集 / 状态查询" clearable class="toolbar-search" @keyup.enter="noopSearch" />
            <el-button type="primary" class="toolbar-search-btn" @click="noopSearch">搜索</el-button>
          </div>

          <el-table ref="expTableRef" :data="filteredRows" row-key="id" border v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="54" reserve-selection />
            <el-table-column type="index" label="序号" width="72" />
            <el-table-column prop="id" label="实验ID" width="96" sortable />
            <el-table-column prop="name" label="实验名称" min-width="220" show-overflow-tooltip />
            <el-table-column label="数据集" width="160">
              <template #default="{ row }">{{ datasetLabel(row.dataset) }}</template>
            </el-table-column>
            <el-table-column label="实验方案" min-width="180">
              <template #default="{ row }">
                <div class="profile-cell">
                  <el-tag size="small" :type="profileTagType(row.profile)">{{ profileShortLabel(row.profile) }}</el-tag>
                  <div class="profile-desc">{{ row.profile?.desc || '-' }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="链路配置" min-width="220">
              <template #default="{ row }">
                <div class="tag-wrap">
                  <el-tag v-for="item in profileFeatureTags(row.profile)" :key="`${row.id}-${item.key}`" size="small" :type="item.enabled ? 'success' : 'info'" effect="plain">
                    {{ item.label }}{{ item.enabled ? '开' : '关' }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="sample_cnt" label="样本数" width="90" />
            <el-table-column prop="max_round" label="最大轮次" width="100" />
            <el-table-column label="状态" width="140">
              <template #default="{ row }">
                <div class="status-wrap">
                  <el-tag :type="fmtStatusType(row.status)">{{ fmtStatusLabel(row.status) }}</el-tag>
                  <el-tag v-if="row.report_source" size="small" effect="plain" class="source-tag">
                    {{ row.report_source === 'server' ? '后端真实' : '本地原型' }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="进度" min-width="180">
              <template #default="{ row }">
                <div class="progress-cell">
                  <el-progress :percentage="Number(row.progress || 0)" :status="row.status === 'fail' ? 'exception' : row.status === 'pass' ? 'success' : ''" />
                  <span class="progress-text">{{ row.progress_text || defaultProgressText(row) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="当前执行" min-width="260">
              <template #default="{ row }">
                <div class="current-cell">
                  <div class="current-main">{{ currentExecText(row) }}</div>
                  <div class="current-link-row" v-if="row.current_task_id || row.current_problem_no">
                    <el-button v-if="row.current_task_id" link type="primary" @click="openTaskFromExp(row.current_task_id)">任务 #{{ row.current_task_id }}</el-button>
                    <el-button v-if="row.current_task_id" link @click="openTaskInsight(row.current_task_id, 'report', row.current_problem_no)">任务报告</el-button>
                    <el-button v-if="row.current_task_id" link @click="openTaskInsight(row.current_task_id, 'version', row.current_problem_no)">版本摘要</el-button>
                    <el-button v-if="row.current_task_id" link @click="openTaskInsight(row.current_task_id, 'cases', row.current_problem_no)">失败样例</el-button>
                    <el-button v-if="row.current_task_id" link @click="openTaskInsight(row.current_task_id, 'trace', row.current_problem_no)">轨迹摘要</el-button>
                    <el-button v-if="row.current_problem_no" link @click="focusProblemFromRow(row)">题号 #{{ row.current_problem_no }}</el-button>
                  </div>
                  <div v-if="lastLogText(row)" class="current-sub">{{ lastLogText(row) }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="结果概览" min-width="210">
              <template #default="{ row }">
                <div v-if="row.report" class="result-brief">
                  <span>初始 {{ pct(row.report.init_pass_rate) }}</span>
                  <span>最终 {{ pct(row.report.final_pass_rate) }}</span>
                  <span>修复贡献 {{ pct(row.report.repair_success_rate) }}</span>
                </div>
                <span v-else class="muted-text">尚无结果</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
                <div class="op-grid">
                  <el-button class="op-btn" type="primary" plain size="small" :disabled="row.status === 'running'" @click="handleStart(row)">批量运行</el-button>
                  <el-button class="op-btn" type="warning" plain size="small" :disabled="row.status !== 'running'" @click="handleStop(row)">停止</el-button>
                  <el-button class="op-btn" type="success" plain size="small" @click="openDetail(row)">查看结果</el-button>
                  <el-button class="op-btn" type="info" plain size="small" :disabled="!row.report" @click="exportReport(row)">导出报告</el-button>
                </div>
                <div class="op-row-bottom">
                  <el-button class="op-btn-delete" type="danger" link @click="removeExp(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loading && !filteredRows.length" description="暂无匹配实验记录" :image-size="88" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card class="page-card" shadow="never">
          <template #header><span>实验统计概览</span></template>

          <div v-if="rows.length" class="status-bars">
            <div v-for="item in statusBarRows" :key="item.key" class="status-bar-item">
              <div class="bar-head">
                <span>{{ item.label }}</span>
                <span>{{ item.count }}</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :class="item.key" :style="{ width: `${item.width}%` }"></div>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无可统计实验" :image-size="80" />

          <div class="metric-block" v-if="datasetStats.length">
            <div class="metric-title">按数据集分布</div>
            <div v-for="item in datasetStats" :key="item.name" class="metric-line">
              <span>{{ item.name }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="createVisible" title="新建实验草稿" width="760px">
      <el-form label-position="top" :model="form">
        <el-form-item label="实验名称">
          <el-input v-model="form.name" placeholder="例如：MBPP 对比实验（Qwen）" clearable />
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="form.dataset" style="width: 100%">
            <el-option v-for="item in datasets" :key="item" :label="datasetLabel(item)" :value="item" />
          </el-select>
          <div class="field-tip" v-if="currentDatasetMeta?.desc">{{ currentDatasetMeta.desc }}</div>
          <div class="field-tip" v-if="currentDatasetMeta?.aliases?.length">
            已去重隐藏旧别名：{{ currentDatasetMeta.aliases.join('、') }}；历史实验记录仍兼容这些名称。
          </div>
        </el-form-item>
        <el-form-item label="实验方案">
          <div class="profile-card-grid">
            <div
              v-for="item in profileOptions"
              :key="item.key"
              class="profile-option-card"
              :class="{ active: form.profile_key === item.key }"
              @click="form.profile_key = item.key"
            >
              <div class="profile-option-head">
                <div class="profile-option-title">{{ item.label }}</div>
                <el-tag size="small" :type="profileTagType(item)">{{ item.short_label || item.label }}</el-tag>
              </div>
              <div class="profile-option-desc">{{ item.desc }}</div>
              <div class="tag-wrap">
                <el-tag v-for="feat in profileFeatureTags(item)" :key="`${item.key}-${feat.key}`" size="small" :type="feat.enabled ? 'success' : 'info'" effect="plain">
                  {{ feat.label }}{{ feat.enabled ? '开' : '关' }}
                </el-tag>
              </div>
            </div>
          </div>
          <div class="field-tip" v-if="selectedProfile">{{ selectedProfile.desc }}</div>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="样本数">
              <el-input-number v-model="form.sample_cnt" :min="1" :max="currentDatasetSize" :step="10" style="width: 100%" />
              <div class="field-tip">当前数据集可用题量：{{ currentDatasetSize }}；超过后会自动按上限截断，不再循环重跑。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大轮次">
              <el-input-number v-model="form.max_round" :min="1" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!canCreate" @click="submitCreate">
          创建实验
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="compareVisible" title="实验对比（2-3组同屏）" width="1180px">
      <template v-if="compareData">
        <div class="compare-top-grid">
          <div v-for="item in compareExperiments" :key="item.id" class="compare-exp-card">
            <div class="compare-exp-title">{{ item.name }}</div>
            <div class="compare-exp-meta">实验 #{{ item.id }} ｜ {{ datasetLabel(item.dataset) }}</div>
            <div class="compare-exp-meta">方案：{{ item.profile?.label || '-' }}</div>
            <div class="tag-wrap compare-tag-wrap">
              <el-tag v-for="feat in profileFeatureTags(item.profile)" :key="`${item.id}-${feat.key}`" size="small" :type="feat.enabled ? 'success' : 'info'" effect="plain">{{ feat.label }}{{ feat.enabled ? '开' : '关' }}</el-tag>
            </div>
          </div>
        </div>

        <el-card shadow="never" class="compare-card compare-summary-shell" v-if="compareSummaryCards.length || compareSummaryVerdict">
          <template #header>
            <div class="compare-card-header">
              <span>结论摘要区</span>
              <span class="compare-card-subtitle">适合直接截图写论文</span>
            </div>
          </template>
          <div class="summary-intro">
            <div class="summary-intro-main">系统会根据当前已运行实验的真实统计结果，自动归纳出便于展示的结论摘要。</div>
            <div class="summary-intro-sub">阅读时建议优先关注数值结果、最佳实验，以及完整链路的稳定性判断。</div>
          </div>
          <div class="summary-layout">
            <div class="summary-card-grid" v-if="compareSummaryCards.length">
              <div v-for="card in compareSummaryCards" :key="card.key" class="summary-card" :class="card.type || 'info'">
                <div class="summary-card-label">{{ card.title }}</div>
                <div class="summary-card-value">{{ card.value_text || '-' }}</div>
                <div class="summary-card-row">
                  <span class="summary-row-label">最佳实验</span>
                  <span class="summary-card-winner">{{ card.winner_label || '-' }}</span>
                </div>
                <div class="summary-card-desc">
                  <span class="summary-row-label">排序</span>
                  <span>{{ normalizeSummaryDesc(card.desc) }}</span>
                </div>
              </div>
            </div>
            <div class="summary-verdict" :class="compareSummaryVerdict?.level || 'info'" v-if="compareSummaryVerdict">
              <div class="summary-verdict-head">
                <span class="summary-verdict-title">{{ compareSummaryVerdict.title || '完整链路稳定性判断' }}</span>
                <el-tag size="small" :type="summaryVerdictTagType(compareSummaryVerdict.level)">{{ compareSummaryVerdict.label || '-' }}</el-tag>
              </div>
              <div class="summary-verdict-text">{{ compareSummaryVerdict.summary || '-' }}</div>
              <ul class="summary-verdict-list" v-if="compareSummaryVerdict.bullets?.length">
                <li v-for="(item, idx) in compareSummaryVerdict.bullets" :key="idx">{{ item }}</li>
              </ul>
            </div>
          </div>
          <div class="summary-note-strip" v-if="compareSummaryNotes.length">
            <div v-for="(note, idx) in compareSummaryNotes" :key="idx" class="summary-note-item">{{ note }}</div>
          </div>
        </el-card>

        <el-card shadow="never" class="compare-card">
          <template #header><span>核心指标对比</span></template>
          <el-table :data="compareMetricRows" border size="small" style="width: 100%">
            <el-table-column prop="metric_label" label="指标" min-width="150" fixed="left" />
            <el-table-column v-for="item in compareExperiments" :key="`metric-${item.id}`" :label="item.name" min-width="180">
              <template #default="{ row }">{{ compareMetricCellText(row, item.id) }}</template>
            </el-table-column>
            <el-table-column label="最佳实验" min-width="180">
              <template #default="{ row }">
                <el-tag size="small" :type="row.best_label === '持平' ? 'info' : 'success'">{{ row.best_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="排序" min-width="220">
              <template #default="{ row }">{{ row.rank_text }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <div class="compare-figure-grid" v-if="compareGroups.length">
          <el-card v-for="group in compareGroups" :key="group.metric_key" shadow="never" class="compare-card">
            <template #header><span>{{ group.metric_label }}</span></template>
            <div class="err-bars">
              <div v-for="item in compareGroupBars(group)" :key="`${group.metric_key}-${item.label}`" class="err-row">
                <span class="err-name">{{ item.label }}</span>
                <div class="err-track"><div class="err-fill paper" :style="{ width: `${item.width}%` }"></div></div>
                <strong>{{ item.text }}</strong>
              </div>
            </div>
          </el-card>
        </div>

        <div class="drawer-tip" v-if="compareData?.compare?.notes?.length">
          <div v-for="(note, idx) in compareData.compare.notes" :key="idx">{{ note }}</div>
        </div>
      </template>
      <el-empty v-else description="请选择 2 到 3 条已运行实验后再进行同屏对比" :image-size="84" />
    </el-dialog>

    <el-drawer v-model="detailVisible" title="实验结果" size="760px">
      <template v-if="detailRow">
        <div class="detail-top">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="实验ID">{{ detailRow.id }}</el-descriptions-item>
            <el-descriptions-item label="实验名称">{{ detailRow.name }}</el-descriptions-item>
            <el-descriptions-item label="数据集">{{ datasetLabel(detailRow.dataset) }}</el-descriptions-item>
            <el-descriptions-item label="样本数">{{ detailRow.sample_cnt ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="最大轮次">{{ detailRow.max_round ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="实验方案">{{ detailRow.profile?.label || '-' }}</el-descriptions-item>
            <el-descriptions-item label="链路配置">{{ profileFeatureSummary(detailRow.profile) }}</el-descriptions-item>
            <el-descriptions-item label="结果来源">
              <el-tag size="small" effect="plain">{{ detailRow.report_source === 'server' ? '后端真实' : '前端原型' }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <div class="drawer-tip">
            <span v-if="detailRow.report_source === 'server'">当前结果来自后端实验接口，可直接用于结果展示与导出。</span>
            <span v-else>当前结果来自前端原型影子层，用于先形成实验页闭环；后端补齐 /exp/{id}/start、/item、/report、/chart 后会自动切换为真实结果。</span>
          </div>
        </div>

        <div class="live-panel">
          <div class="live-head">实验执行进度</div>
          <div class="live-grid">
            <div class="live-item">
              <span class="live-label">当前阶段</span>
              <strong>{{ detailRow.phase || detailRow.status || '-' }}</strong>
            </div>
            <div class="live-item">
              <span class="live-label">当前题号</span>
              <strong>{{ detailRow.current_problem_no ? `#${detailRow.current_problem_no}` : '-' }}</strong>
            </div>
            <div class="live-item">
              <span class="live-label">题目进度</span>
              <strong>{{ currentIndexText(detailRow) }}</strong>
            </div>
            <div class="live-item live-item-wide">
              <span class="live-label">当前题目</span>
              <strong>{{ detailRow.current_problem_title || '-' }}</strong>
            </div>
          </div>
          <div class="log-box">
            <div class="log-head">执行日志</div>
            <div v-if="detailLogs.length" class="log-list">
              <div v-for="(item, idx) in detailLogs" :key="`${item.ts || ''}-${idx}`" class="log-line">
                <span class="log-ts">[{{ item.ts || '--:--:--' }}]</span>
                <span class="log-level" :class="item.level || 'info'">{{ item.level || 'info' }}</span>
                <span class="log-text">{{ item.text }}</span>
                <span class="log-actions" v-if="item.task_id || item.problem_no">
                  <el-button v-if="item.task_id" link type="primary" @click="openTaskFromExp(item.task_id)">task_id=#{{ item.task_id }}</el-button>
                  <el-button v-if="item.task_id" link @click="openTaskInsight(item.task_id, 'report', item.problem_no)">任务报告</el-button>
                  <el-button v-if="item.task_id" link @click="openTaskInsight(item.task_id, 'version', item.problem_no)">版本摘要</el-button>
                  <el-button v-if="item.task_id" link @click="openTaskInsight(item.task_id, 'cases', item.problem_no)">失败样例</el-button>
                  <el-button v-if="item.task_id" link @click="openTaskInsight(item.task_id, 'trace', item.problem_no)">轨迹摘要</el-button>
                  <el-button v-if="item.problem_no" link @click="focusProblemFromLog(item)">题号 #{{ item.problem_no }}</el-button>
                </span>
              </div>
            </div>
            <el-empty v-else description="暂无实验执行日志" :image-size="60" />
          </div>
        </div>

        <el-tabs v-model="detailTab" class="detail-tabs">
          <el-tab-pane label="结果概览" name="overview">
            <template v-if="detailRow.report">
              <div class="report-grid">
                <div class="metric-card compact"><div class="metric-label">初始通过率</div><div class="metric-value">{{ pct(detailRow.report.init_pass_rate) }}</div></div>
                <div class="metric-card compact"><div class="metric-label">最终通过率</div><div class="metric-value">{{ pct(detailRow.report.final_pass_rate) }}</div></div>
                <div class="metric-card compact"><div class="metric-label">修复贡献率</div><div class="metric-value">{{ pct(detailRow.report.repair_success_rate) }}</div></div>
                <div class="metric-card compact"><div class="metric-label">平均轮次</div><div class="metric-value">{{ num1(detailRow.report.avg_round) }}</div></div>
                <div class="metric-card compact"><div class="metric-label">平均耗时</div><div class="metric-value">{{ ms(detailRow.report.avg_time_ms) }}</div></div>
                <div class="metric-card compact"><div class="metric-label">实验样本数</div><div class="metric-value">{{ detailRow.report.sample_cnt || detailRow.sample_cnt || 0 }}</div></div>
                <div class="metric-card compact"><div class="metric-label">修复贡献案例</div><div class="metric-value">{{ typicalCaseStats.repairSuccess }}</div></div>
                <div class="metric-card compact"><div class="metric-label">rollback 生效案例</div><div class="metric-value">{{ typicalCaseStats.rollbackEffective }}</div></div>
              </div>

              <el-card shadow="never" class="paper-card" v-if="detailCh4Metrics.length">
                <template #header><span>第四章统一口径</span></template>
                <div class="paper-grid">
                  <div v-for="item in detailCh4Metrics" :key="item.key" class="paper-metric">
                    <span>{{ item.label }}</span>
                    <strong>{{ item.text }}</strong>
                  </div>
                </div>
                <div v-if="detailCh4Notes.length" class="paper-notes">
                  <div v-for="(note, idx) in detailCh4Notes" :key="idx" class="paper-note">{{ note }}</div>
                </div>
              </el-card>

              <div v-if="detailTypicalCards.length" class="case-pack-grid">
                <el-card v-for="card in detailTypicalCards" :key="card.key" shadow="never" class="case-pack-card">
                  <template #header>
                    <div class="case-pack-head">
                      <span>{{ card.title }}</span>
                      <el-tag size="small" :type="card.tagType">{{ card.problemNoText }}</el-tag>
                    </div>
                  </template>
                  <template v-if="card.item">
                    <div class="case-pack-title">{{ card.item.title }}</div>
                    <div class="case-pack-meta">{{ card.item.reason }}</div>
                    <div class="case-pack-mini">轮次：{{ card.item.round_used }} ｜ 错误：{{ card.item.err_type || '-' }}</div>
                    <div class="case-pack-mini">trace：{{ card.item.latest_trace_sum || '暂无轨迹摘要' }}</div>
                    <div class="case-pack-mini" v-if="card.item.first_failed_case">失败样例：{{ card.item.first_failed_case.err_msg || card.item.first_failed_case.actual_out || '-' }}</div>
                    <div class="case-pack-actions">
                      <el-button size="small" text :disabled="!card.item.task_id" @click="openTaskInsight(card.item.task_id, 'report', card.item.problem_no)">任务报告</el-button>
                      <el-button size="small" text :disabled="!card.item.task_id" @click="openTaskInsight(card.item.task_id, 'cases', card.item.problem_no)">失败样例</el-button>
                      <el-button size="small" text :disabled="!card.item.task_id" @click="openTaskInsight(card.item.task_id, 'trace', card.item.problem_no)">轨迹摘要</el-button>
                    </div>
                  </template>
                  <el-empty v-else description="当前暂无该类型案例" :image-size="60" />
                </el-card>
              </div>
            </template>
            <el-empty v-else description="尚无实验结果" :image-size="84" />
          </el-tab-pane>

          <el-tab-pane label="结果图表" name="charts">
            <template v-if="detailRow.report">
              <div class="chart-grid">
                <el-card shadow="never" class="chart-card">
                  <template #header><span>通过率对比</span></template>
                  <div class="dual-bar-chart">
                    <div class="dual-row">
                      <span>初始</span>
                      <div class="dual-track"><div class="dual-fill init" :style="{ width: `${pctNum(detailRow.report.init_pass_rate)}%` }"></div></div>
                      <strong>{{ pct(detailRow.report.init_pass_rate) }}</strong>
                    </div>
                    <div class="dual-row">
                      <span>最终</span>
                      <div class="dual-track"><div class="dual-fill final" :style="{ width: `${pctNum(detailRow.report.final_pass_rate)}%` }"></div></div>
                      <strong>{{ pct(detailRow.report.final_pass_rate) }}</strong>
                    </div>
                  </div>
                </el-card>

                <el-card shadow="never" class="chart-card">
                  <template #header><span>修复贡献率 / 平均轮次</span></template>
                  <div class="gauge-wrap">
                    <div class="gauge-item">
                      <div class="gauge-label">修复贡献率</div>
                      <div class="gauge-value">{{ pct(detailRow.report.repair_success_rate) }}</div>
                    </div>
                    <div class="gauge-item">
                      <div class="gauge-label">平均轮次</div>
                      <div class="gauge-value">{{ num1(detailRow.report.avg_round) }}/{{ detailRow.max_round }}</div>
                    </div>
                  </div>
                  <div class="mini-track">
                    <div class="mini-fill" :style="{ width: `${Math.min(100, (Number(detailRow.report.avg_round || 0) / Math.max(1, Number(detailRow.max_round || 1))) * 100)}%` }"></div>
                  </div>
                </el-card>

                <el-card shadow="never" class="chart-card span-2">
                  <template #header><span>错误类型分布</span></template>
                  <div v-if="detailErrBars.length" class="err-bars">
                    <div v-for="item in detailErrBars" :key="item.name" class="err-row">
                      <span class="err-name">{{ item.name }}</span>
                      <div class="err-track"><div class="err-fill" :style="{ width: `${item.width}%` }"></div></div>
                      <strong>{{ item.count }}</strong>
                    </div>
                  </div>
                  <el-empty v-else description="暂无错误类型分布" :image-size="70" />
                </el-card>
              </div>

              <div v-if="detailCh4Figures.length" class="paper-fig-grid">
                <el-card v-for="fig in detailCh4Figures" :key="fig.key" shadow="never" class="chart-card">
                  <template #header><span>{{ fig.title }}</span></template>
                  <div v-if="figBarRows(fig).length" class="err-bars">
                    <div v-for="item in figBarRows(fig)" :key="`${fig.key}-${item.label}`" class="err-row">
                      <span class="err-name">{{ item.label }}</span>
                      <div class="err-track"><div class="err-fill paper" :style="{ width: `${item.width}%` }"></div></div>
                      <strong>{{ item.text }}</strong>
                    </div>
                  </div>
                  <el-empty v-else description="暂无图表数据" :image-size="70" />
                </el-card>
              </div>
            </template>
            <el-empty v-else description="尚无图表数据" :image-size="84" />
          </el-tab-pane>

          <el-tab-pane label="实验明细" name="items">
            <el-table ref="detailItemsTableRef" :data="detailItems" border style="width: 100%" :row-class-name="itemRowClassName">
              <el-table-column prop="problem_no" label="题号" width="90">
                <template #default="{ row }">
                  <el-button link @click="focusProblemItem(row.problem_no)">#{{ row.problem_no }}</el-button>
                </template>
              </el-table-column>
              <el-table-column prop="task_id" label="任务ID" width="100">
                <template #default="{ row }">
                  <el-button v-if="row.task_id" link type="primary" @click="openTaskFromExp(row.task_id)">#{{ row.task_id }}</el-button>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="初始结果" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.init_pass ? 'success' : 'info'">{{ row.init_pass ? '通过' : '失败' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="最终结果" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.final_pass ? 'success' : 'danger'">{{ row.final_pass ? '通过' : '失败' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="是否修复成功" width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.repair_ok ? 'success' : 'info'">{{ row.repair_ok ? '是' : '否' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="round_used" label="轮次" width="80" />
              <el-table-column prop="time_ms" label="耗时(ms)" width="100" />
              <el-table-column prop="err_type" label="错误类型" min-width="120" />
              <el-table-column label="典型案例" min-width="180">
                <template #default="{ row }">
                  <div class="tag-wrap" v-if="itemTypicalTags(row).length">
                    <el-tag v-for="tag in itemTypicalTags(row)" :key="`${row.problem_no}-${tag}`" size="small" :type="typicalTagType(tag)">{{ tag }}</el-tag>
                  </div>
                  <el-tooltip v-else content="当前样本不属于修复贡献案例、rollback 生效案例或最终失败案例这三类重点展示样本。" placement="top">
                    <span class="muted-text">非典型样本</span>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="420" fixed="right">
                <template #default="{ row }">
                  <div class="item-actions">
                    <template v-if="row.task_id">
                      <el-button link type="primary" @click="openTaskFromExp(row.task_id)">打开工作台</el-button>
                      <el-button link @click="openTaskInsight(row.task_id, 'report', row.problem_no)">任务报告</el-button>
                      <el-button link @click="openTaskInsight(row.task_id, 'version', row.problem_no)">版本摘要</el-button>
                      <el-button link @click="openTaskInsight(row.task_id, 'cases', row.problem_no)">失败样例</el-button>
                      <el-button link @click="openTaskInsight(row.task_id, 'trace', row.problem_no)">轨迹摘要</el-button>
                    </template>
                    <span v-else class="muted-text">仅定位本表</span>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>

        <div class="drawer-actions">
          <el-button @click="refreshDetail(detailRow)">刷新结果</el-button>
          <el-button :disabled="!detailRow.report" @click="exportTypicalCasePack(detailRow)">导出案例包</el-button>
          <el-button type="primary" :disabled="!detailRow.report" @click="exportReport(detailRow)">导出报告</el-button>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="taskInsightVisible" title="任务洞察" size="760px" direction="ltr" :append-to-body="false">
      <template v-if="taskInsightTaskId">
        <div class="task-insight-head">
          <div>
            <div class="task-insight-title">任务 #{{ taskInsightTaskId }}</div>
            <div class="task-insight-sub">从实验明细直接查看单题任务报告与版本演进摘要，便于把批量实验结果回溯到具体修复过程。</div>
          </div>
          <div class="task-insight-actions">
            <el-button @click="refreshTaskInsight" :loading="taskInsightLoading" :disabled="!taskInsightTaskId">刷新</el-button>
            <el-button @click="exportTaskCaseReport" :disabled="!taskInsightTaskId">导出单题案例报告</el-button>
            <el-button type="primary" plain :disabled="!taskInsightTaskId" @click="openTaskFromExp(taskInsightTaskId)">打开 WorkBench</el-button>
          </div>
        </div>

        <el-tabs v-model="taskInsightTab" class="task-insight-tabs">
          <el-tab-pane label="任务报告" name="report">
            <div v-loading="taskInsightLoading" class="task-insight-grid">
              <div class="metric-card compact"><div class="metric-label">任务标题</div><div class="metric-value metric-small">{{ taskInsight.detail?.title || '-' }}</div></div>
              <div class="metric-card compact"><div class="metric-label">当前状态</div><div class="metric-value metric-small">{{ statusLabel(taskInsight.detail?.status) }}</div></div>
              <div class="metric-card compact"><div class="metric-label">当前轮次</div><div class="metric-value">{{ taskInsight.detail?.cur_round ?? 0 }}</div></div>
              <div class="metric-card compact"><div class="metric-label">最佳版本</div><div class="metric-value">{{ taskInsight.detail?.best_ver_id ?? '-' }}</div></div>
              <div class="metric-card compact"><div class="metric-label">最佳分数</div><div class="metric-value">{{ taskInsight.detail?.best_score ?? 0 }}</div></div>
              <div class="metric-card compact"><div class="metric-label">版本数量</div><div class="metric-value">{{ taskInsight.summary?.ver_cnt ?? taskInsight.versions.length }}</div></div>
              <div class="metric-card compact"><div class="metric-label">运行次数</div><div class="metric-value">{{ taskInsight.runs.length }}</div></div>
              <div class="metric-card compact"><div class="metric-label">测试用例数</div><div class="metric-value">{{ taskInsight.cases.length }}</div></div>
              <div class="metric-card compact"><div class="metric-label">修复计划数</div><div class="metric-value">{{ taskInsight.plans.length }}</div></div>
              <div class="metric-card compact"><div class="metric-label">Lesson 数</div><div class="metric-value">{{ taskInsight.lessons.length }}</div></div>
            </div>

            <div class="insight-block" v-if="taskInsight.detail?.problem_text">
              <div class="insight-block-title">题目描述</div>
              <div class="insight-block-body pre-line">{{ taskInsight.detail.problem_text }}</div>
            </div>

            <div class="insight-block" v-if="taskInsight.latestFb">
              <div class="insight-block-title">最近一次执行反馈</div>
              <div class="mini-grid two">
                <div class="mini-item"><span>运行ID</span><strong>#{{ taskInsight.latestFb.run_id }}</strong></div>
                <div class="mini-item"><span>结果</span><strong>{{ taskInsight.latestFb.result || '-' }}</strong></div>
                <div class="mini-item"><span>通过情况</span><strong>{{ taskInsight.latestFb.pass_cnt ?? 0 }}/{{ taskInsight.latestFb.total_cnt ?? 0 }}</strong></div>
                <div class="mini-item"><span>错误类型</span><strong>{{ taskInsight.latestFb.err_type || '-' }}</strong></div>
                <div class="mini-item wide"><span>错误信息</span><strong>{{ taskInsight.latestFb.err_msg || '-' }}</strong></div>
                <div class="mini-item wide"><span>轨迹摘要</span><strong>{{ taskInsight.latestFb.trace_sum || '-' }}</strong></div>
              </div>
            </div>

            <div class="report-columns">
              <div class="insight-block">
                <div class="insight-block-title">最近修复计划</div>
                <div v-if="latestPlan" class="plan-list">
                  <div class="plan-card">
                    <div class="plan-head">第 {{ latestPlan.round_no || '-' }} 轮</div>
                    <div class="plan-body"><strong>根因：</strong>{{ latestPlan.root_cause || '-' }}</div>
                    <div class="plan-body"><strong>计划：</strong>{{ latestPlan.fix_plan || '-' }}</div>
                    <div class="plan-body"><strong>插桩建议：</strong>{{ latestPlan.inst_sugg || '-' }}</div>
                  </div>
                </div>
                <el-empty v-else description="暂无修复计划" :image-size="60" />
              </div>
              <div class="insight-block">
                <div class="insight-block-title">最近 Lesson</div>
                <div v-if="latestLesson" class="plan-list">
                  <div class="plan-card">
                    <div class="plan-head">第 {{ latestLesson.round_no || '-' }} 轮</div>
                    <div class="plan-body"><strong>失败模式：</strong>{{ latestLesson.bad_pattern || '-' }}</div>
                    <div class="plan-body"><strong>经验总结：</strong>{{ latestLesson.lesson_text || '-' }}</div>
                  </div>
                </div>
                <el-empty v-else description="暂无 Lesson 记录" :image-size="60" />
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="版本演进摘要" name="version">
            <div v-loading="taskInsightLoading">
              <div class="task-insight-grid">
                <div class="metric-card compact"><div class="metric-label">init 版本</div><div class="metric-value">{{ versionStats.init }}</div></div>
                <div class="metric-card compact"><div class="metric-label">repair 版本</div><div class="metric-value">{{ versionStats.repair }}</div></div>
                <div class="metric-card compact"><div class="metric-label">rollback 版本</div><div class="metric-value">{{ versionStats.rollback }}</div></div>
                <div class="metric-card compact"><div class="metric-label">manual 版本</div><div class="metric-value">{{ versionStats.manual }}</div></div>
                <div class="metric-card compact"><div class="metric-label">最新版本</div><div class="metric-value">V{{ latestInsightVersion?.ver_no ?? '-' }}</div></div>
                <div class="metric-card compact"><div class="metric-label">最佳版本</div><div class="metric-value">{{ bestInsightVersion ? `V${bestInsightVersion.ver_no}` : '-' }}</div></div>
              </div>

              <div class="timeline-box" v-if="versionTimeline.length">
                <div v-for="item in versionTimeline" :key="item.id" class="timeline-item" :class="{ best: item.isBest, latest: item.isLatest }">
                  <div class="timeline-main">
                    <div class="timeline-top">
                      <div class="timeline-title">
                        <span class="ver-badge">V{{ item.ver_no }}</span>
                        <el-tag size="small" effect="plain">{{ item.ver_type || '-' }}</el-tag>
                        <el-tag v-if="item.isBest" size="small" type="success">最佳版本</el-tag>
                        <el-tag v-if="item.isLatest" size="small" type="primary">当前最新</el-tag>
                      </div>
                      <div class="timeline-run" v-if="item.run">
                        <span>运行 #{{ item.run.id }}</span>
                        <span>{{ item.run.result || '-' }}</span>
                        <span>{{ item.run.pass_cnt ?? 0 }}/{{ item.run.total_cnt ?? 0 }}</span>
                      </div>
                    </div>
                    <div class="timeline-note">{{ item.note || '无版本备注' }}</div>
                    <div class="timeline-extra">
                      <span v-if="item.run?.err_type">错误：{{ item.run.err_type }}</span>
                      <span v-if="item.run?.trace_sum">轨迹：{{ item.run.trace_sum }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无版本演进信息" :image-size="60" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="失败样例" name="cases">
            <div v-loading="taskInsightLoading">
              <div class="mini-grid two" v-if="taskInsight.latestFailedRun">
                <div class="mini-item"><span>失败运行ID</span><strong>#{{ taskInsight.latestFailedRun.id }}</strong></div>
                <div class="mini-item"><span>运行结果</span><strong>{{ taskInsight.latestFailedRun.result || '-' }}</strong></div>
                <div class="mini-item"><span>通过情况</span><strong>{{ taskInsight.latestFailedFb?.pass_cnt ?? taskInsight.latestFailedRun.pass_cnt ?? 0 }}/{{ taskInsight.latestFailedFb?.total_cnt ?? taskInsight.latestFailedRun.total_cnt ?? 0 }}</strong></div>
                <div class="mini-item"><span>错误类型</span><strong>{{ taskInsight.latestFailedFb?.err_type || taskInsight.latestFailedRun.err_type || '-' }}</strong></div>
                <div class="mini-item wide"><span>错误信息</span><strong>{{ taskInsight.latestFailedFb?.err_msg || taskInsight.latestFailedRun.err_msg || '-' }}</strong></div>
              </div>
              <div class="insight-block" v-if="taskInsight.latestFailedCases.length">
                <div class="insight-block-title">最近一次失败运行的 case 列表</div>
                <el-table :data="taskInsight.latestFailedCases" border size="small" style="width: 100%">
                  <el-table-column label="case_id" prop="case_id" width="90" />
                  <el-table-column label="断言" min-width="260">
                    <template #default="{ row }">
                      <div class="pre-line">{{ row.assert_text || '-' }}</div>
                    </template>
                  </el-table-column>
                  <el-table-column label="实际输出" min-width="180">
                    <template #default="{ row }"><div class="pre-line">{{ row.actual_out || '-' }}</div></template>
                  </el-table-column>
                  <el-table-column label="错误信息" min-width="220">
                    <template #default="{ row }"><div class="pre-line">{{ row.err_msg || '-' }}</div></template>
                  </el-table-column>
                  <el-table-column label="耗时(ms)" prop="time_ms" width="100" />
                </el-table>
              </div>
              <el-empty v-else description="暂无可展示的失败样例；该任务可能尚未出现失败运行，或尚未生成单用例结果。" :image-size="70" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="轨迹摘要" name="trace">
            <div v-loading="taskInsightLoading">
              <div class="insight-block" v-if="taskInsight.latestFb || taskInsight.latestRun">
                <div class="insight-block-title">最近一次运行的轨迹摘要</div>
                <div class="mini-grid two">
                  <div class="mini-item"><span>运行ID</span><strong>#{{ taskInsight.latestRun?.id || taskInsight.latestFb?.run_id || '-' }}</strong></div>
                  <div class="mini-item"><span>结果</span><strong>{{ taskInsight.latestRun?.result || taskInsight.latestFb?.result || '-' }}</strong></div>
                  <div class="mini-item wide"><span>trace_sum</span><strong>{{ taskInsight.latestFb?.trace_sum || taskInsight.latestRun?.trace_sum || '暂无轨迹摘要' }}</strong></div>
                </div>
              </div>
              <div class="insight-block" v-if="taskInsight.latestTrace.length">
                <div class="insight-block-title">关键 trace 条目</div>
                <el-table :data="taskInsight.latestTrace.slice(0, 40)" border size="small" style="width: 100%">
                  <el-table-column prop="seq_no" label="序号" width="80" />
                  <el-table-column prop="node_type" label="类型" width="110" />
                  <el-table-column prop="func_name" label="函数" width="120" />
                  <el-table-column prop="line_no" label="行号" width="90" />
                  <el-table-column label="日志内容" min-width="320">
                    <template #default="{ row }"><div class="pre-line">{{ row.log_text || '-' }}</div></template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="最近一次运行暂无可展示的轨迹条目" :image-size="70" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
// 实验列表页面，负责创建、启动与查看实验任务。
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import PageHead from '@/comps/PageHead.vue'
import { getDatasetDetail, listDataset } from '@/api/data'
import {
  compareExp,
  createExp,
  getExpChart,
  getExpDetail,
  getExpItems,
  getExpReport,
  listExp,
  listExpProfiles,
  startExp,
  stopExp,
  deleteExp
} from '@/api/exp'
import {
  getTaskCases,
  getTaskDetail,
  getTaskLessons,
  getTaskPlans,
  getTaskSummary,
  listTaskVers
} from '@/api/task'
import { getRunCases, getRunDetail, getRunFb, getRunTrace, listTaskRuns } from '@/api/run'
import { fmtStatusLabel, fmtStatusType } from '@/utils/fmt'

const router = useRouter()

const expTableRef = ref(null)
const loading = ref(false)
const creating = ref(false)
const rows = ref([])
const datasets = ref(['custom', 'class_bank', 'file_bank'])
const profileOptions = ref([])
const datasetMetaMap = ref({})
const createVisible = ref(false)
const compareVisible = ref(false)
const compareLoading = ref(false)
const compareData = ref(null)
const compareSelection = ref([])
const detailVisible = ref(false)
const keyword = ref('')
function noopSearch() {
  // 当前搜索为前端即时过滤，保留按钮是为了更符合使用习惯。
}
const detailRow = ref(null)
const detailTab = ref('overview')
const detailItemsTableRef = ref(null)
const activeProblemNo = ref(null)
const taskInsightVisible = ref(false)
const taskInsightLoading = ref(false)
const taskInsightTaskId = ref(null)
const taskInsightTab = ref('report')
const taskInsight = reactive({
  detail: null,
  summary: null,
  versions: [],
  runs: [],
  runDetails: [],
  latestRun: null,
  latestFailedRun: null,
  latestFb: null,
  latestFailedFb: null,
  latestTrace: [],
  latestFailedCases: [],
  cases: [],
  plans: [],
  lessons: []
})

function statusLabel(val) {
  return fmtStatusLabel(val)
}

function fallbackProfiles() {
  return [
    {
      key: 'no_feedback_single',
      label: '无反馈单轮生成',
      short_label: '单轮基线',
      desc: '只生成一次代码并直接测试，用来观察初始通过情况。',
      iterative: false,
      trace_on: false,
      lesson_on: false,
      rollback_on: false,
      features: [
        { key: 'gen_once', label: '单轮生成', enabled: true },
        { key: 'error_feedback', label: '错误反馈修复', enabled: false },
        { key: 'trace', label: 'Trace', enabled: false },
        { key: 'lesson', label: 'Lesson', enabled: false },
        { key: 'rollback', label: 'Rollback', enabled: false }
      ]
    },
    {
      key: 'error_feedback_iter',
      label: '只有错误反馈的多轮修复',
      short_label: '错误反馈多轮',
      desc: '失败后仅使用结构化错误反馈做多轮修复，不启用 Trace、Lesson 和 Rollback。',
      iterative: true,
      trace_on: false,
      lesson_on: false,
      rollback_on: false,
      features: [
        { key: 'gen_once', label: '单轮生成', enabled: true },
        { key: 'error_feedback', label: '错误反馈修复', enabled: true },
        { key: 'trace', label: 'Trace', enabled: false },
        { key: 'lesson', label: 'Lesson', enabled: false },
        { key: 'rollback', label: 'Rollback', enabled: false }
      ]
    },
    {
      key: 'full_chain',
      label: 'trace + lesson + rollback 完整链路',
      short_label: '完整链路',
      desc: '启用 Trace、Lesson 和 Rollback，观察完整机制是否比前两组更稳定。',
      iterative: true,
      trace_on: true,
      lesson_on: true,
      rollback_on: true,
      features: [
        { key: 'gen_once', label: '单轮生成', enabled: true },
        { key: 'error_feedback', label: '错误反馈修复', enabled: true },
        { key: 'trace', label: 'Trace', enabled: true },
        { key: 'lesson', label: 'Lesson', enabled: true },
        { key: 'rollback', label: 'Rollback', enabled: true }
      ]
    }
  ]
}

function getProfile(profileOrKey) {
  const key = typeof profileOrKey === 'string' ? profileOrKey : profileOrKey?.key
  return profileOptions.value.find(item => item.key === key) || profileOrKey || fallbackProfiles().find(item => item.key === key) || fallbackProfiles()[2]
}

function profileShortLabel(profileOrKey) {
  const profile = getProfile(profileOrKey)
  return profile?.short_label || profile?.label || '-'
}

function profileFeatureTags(profileOrKey) {
  const profile = getProfile(profileOrKey)
  if (Array.isArray(profile?.features) && profile.features.length) return profile.features
  return []
}

function profileFeatureSummary(profileOrKey) {
  const tags = profileFeatureTags(profileOrKey)
  if (!tags.length) return '-'
  return tags.map(item => `${item.label}${item.enabled ? '开' : '关'}`).join(' / ')
}

function profileTagType(profileOrKey) {
  const key = getProfile(profileOrKey)?.key
  if (key === 'no_feedback_single') return 'info'
  if (key === 'error_feedback_iter') return 'warning'
  return 'success'
}

const form = reactive({
  name: '',
  dataset: 'custom',
  sample_cnt: 50,
  max_round: 3,
  profile_key: 'full_chain'
})

const shadowKey = 'cfix_exp_shadow'
const runTimers = new Map()
const pollTimers = new Map()

function handleSelectionChange(val) {
  compareSelection.value = Array.isArray(val) ? val : []
}

const compareDisabled = computed(() => compareSelection.value.length < 2 || compareSelection.value.length > 3)
const compareExperiments = computed(() => compareData.value?.experiments || [])
const compareGroups = computed(() => compareData.value?.compare?.groups || [])
const compareMetricRows = computed(() => compareData.value?.metric_rows || [])
const compareSummary = computed(() => compareData.value?.summary || compareData.value?.compare?.summary || null)
const compareSummaryCards = computed(() => compareSummary.value?.cards || [])
const compareSummaryVerdict = computed(() => compareSummary.value?.verdict || null)
const compareSummaryNotes = computed(() => compareSummary.value?.notes || [])

function formatCompareMetric(metricKey, value) {
  if (['final_pass_rate', 'repair_success_rate', 'delta_pass_rate'].includes(metricKey)) {
    return `${(Number(value || 0) * 100).toFixed(2)}%`
  }
  if (metricKey === 'avg_round') return Number(value || 0).toFixed(2)
  return `${Math.round(Number(value || 0))}`
}

function compareMetricCellText(row, expId) {
  const target = (row?.values || []).find(item => Number(item.exp_id) === Number(expId))
  return target?.text || '-'
}

function formatCompareDelta(metricKey, value) {
  const num = Number(value || 0)
  const prefix = num > 0 ? '+' : ''
  if (['final_pass_rate', 'repair_success_rate', 'delta_pass_rate'].includes(metricKey)) {
    return `${prefix}${(num * 100).toFixed(2)}%`
  }
  if (metricKey === 'avg_round') return `${prefix}${num.toFixed(2)}`
  return `${prefix}${Math.round(num)}`
}

function summaryVerdictTagType(level) {
  if (level === 'success') return 'success'
  if (level === 'warning') return 'warning'
  if (level === 'danger') return 'danger'
  return 'info'
}

function normalizeSummaryDesc(text) {
  const value = String(text || '-').trim()
  if (!value) return '-'
  return value.replace(/^排序[:：]\s*/, '') || '-'
}

function compareGroupBars(group) {
  const list = (group?.items || []).map(item => ({
    label: item.label,
    value: Number(item.value || 0),
    text: formatCompareMetric(group.metric_key, item.value)
  }))
  const max = Math.max(...list.map(item => item.value), 1)
  return list.map(item => ({ ...item, width: (item.value / max) * 100 }))
}


function readShadow() {
  try {
    return JSON.parse(localStorage.getItem(shadowKey) || '{}')
  } catch {
    return {}
  }
}

function writeShadow(map) {
  localStorage.setItem(shadowKey, JSON.stringify(map || {}))
}

function stopPolling(expId) {
  if (pollTimers.has(expId)) {
    clearInterval(pollTimers.get(expId))
    pollTimers.delete(expId)
  }
}

function syncPollingTimers() {
  const runningIds = new Set((rows.value || []).filter(item => item.status === 'running' && item.report_source === 'server').map(item => item.id))
  for (const [expId, timer] of pollTimers.entries()) {
    if (!runningIds.has(expId)) {
      clearInterval(timer)
      pollTimers.delete(expId)
    }
  }
  for (const expId of runningIds) {
    if (!pollTimers.has(expId)) {
      startPolling(expId)
    }
  }
}

async function pollServerExp(expId, withAssets = false) {
  try {
    const detailRes = await getExpDetail(expId)
    const oldRow = rows.value.find(item => item.id === expId) || {}
    let next = { ...oldRow, ...(detailRes?.data || {}), report_source: 'server' }

    const needAssets = withAssets || detailVisible.value && detailRow.value?.id === expId || next.status !== 'running'
    if (needAssets) {
      next = await fetchExpAssets(next)
    }

    rows.value = rows.value.map(item => (item.id === expId ? next : item))
    if (detailRow.value?.id === expId) {
      detailRow.value = next
    }

    if (next.status !== 'running') {
      stopPolling(expId)
    }
    return next
  } catch {
    stopPolling(expId)
    return null
  }
}

function startPolling(expId) {
  if (pollTimers.has(expId)) return
  pollServerExp(expId, detailRow.value?.id === expId)
  const timer = setInterval(() => {
    pollServerExp(expId, detailRow.value?.id === expId)
  }, 1500)
  pollTimers.set(expId, timer)
}

function getShadowRow(expId) {
  const shadow = readShadow()
  return shadow[String(expId)] || shadow[expId] || {}
}

function patchShadow(expId, patch) {
  const shadow = readShadow()
  const key = String(expId)
  shadow[key] = {
    ...(shadow[key] || {}),
    ...patch
  }
  writeShadow(shadow)
  return shadow[key]
}

function mergeRows(baseRows) {
  const shadow = readShadow()
  return (Array.isArray(baseRows) ? baseRows : []).map(item => ({
    ...item,
    ...(shadow[String(item.id)] || {})
  }))
}

function datasetBase(name) {
  const map = {
    custom: 0.34,
    mbpp: 0.34,
    humaneval: 0.34,
    class_bank: 0.37,
    class_eval: 0.37,
    file_bank: 0.4,
    file_ultra: 0.4
  }
  return map[name] ?? 0.35
}

function clamp(num, min, max) {
  return Math.min(max, Math.max(min, num))
}

function num1(val) {
  return Number(val || 0).toFixed(1)
}

function ms(val) {
  return `${Math.round(Number(val || 0))}`
}

function pctNum(val) {
  return Math.round(Number(val || 0) * 100)
}

function pct(val) {
  return `${pctNum(val)}%`
}

function defaultProgressText(row) {
  if (row.status === 'draft') return '待启动'
  if (row.status === 'running') return '批量运行中'
  if (row.report) return `最终通过率 ${pct(row.report.final_pass_rate)}`
  return '尚无结果'
}

function currentIndexText(row) {
  const idx = Number(row?.current_index || 0)
  const total = Number(row?.total || row?.sample_cnt || 0)
  if (!total) return '-'
  return `${idx}/${total}`
}

function currentExecText(row) {
  if (!row) return '-'
  if (row.current_problem_no) {
    return `第 ${currentIndexText(row)} 题 · #${row.current_problem_no}`
  }
  if (row.status === 'running') return '运行中，等待当前题信息'
  if (row.status === 'stop') return '实验已停止'
  if (row.status === 'draft') return '尚未开始'
  return '已无进行中的题目'
}

function lastLogText(row) {
  const logs = Array.isArray(row?.logs) ? row.logs : []
  return logs.length ? logs[logs.length - 1]?.text || '' : ''
}

function makeLocalItems(row) {
  const profile = getProfile(row.profile)
  const sampleCnt = Math.max(1, Number(row.sample_cnt || 1))
  const roundCap = profile?.iterative ? Math.max(1, Number(row.max_round || 1)) : 1
  const seedBase = Number(row.id || 1) * 17 + sampleCnt * 3 + roundCap * 11
  const items = []
  let initPassCnt = 0
  let finalPassCnt = 0
  let repairCnt = 0
  const errPool = ['AssertionError', 'TypeError', 'IndexError', 'ValueError', 'WrongAnswer']

  for (let i = 1; i <= sampleCnt; i += 1) {
    const wave = ((seedBase + i * 13) % 100) / 100
    const initThreshold = clamp(datasetBase(row.dataset) + roundCap * 0.015, 0.2, 0.72)
    const boost = profile?.iterative ? clamp(0.08 + roundCap * 0.03 + (((seedBase + i * 7) % 9) / 100), 0.08, 0.28) : 0
    const initPass = wave < initThreshold
    const finalPass = initPass || wave < initThreshold + boost
    const repairOk = Boolean(profile?.iterative) && !initPass && finalPass
    const roundUsed = profile?.iterative ? (finalPass ? 1 + ((seedBase + i) % roundCap) : roundCap) : 0
    const timeMs = 700 + ((seedBase + i * 29) % 1600)
    const errType = finalPass ? '-' : errPool[(seedBase + i) % errPool.length]

    if (initPass) initPassCnt += 1
    if (finalPass) finalPassCnt += 1
    if (repairOk) repairCnt += 1

    items.push({
      problem_no: i,
      task_id: null,
      init_pass: initPass,
      final_pass: finalPass,
      repair_ok: repairOk,
      round_used: roundUsed,
      time_ms: timeMs,
      err_type: errType
    })
  }

  const avgRound = items.reduce((sum, item) => sum + Number(item.round_used || 0), 0) / items.length
  const avgTimeMs = items.reduce((sum, item) => sum + Number(item.time_ms || 0), 0) / items.length
  const report = {
    dataset: row.dataset,
    sample_cnt: sampleCnt,
    init_pass_rate: initPassCnt / sampleCnt,
    final_pass_rate: finalPassCnt / sampleCnt,
    repair_success_rate: repairCnt / sampleCnt,
    avg_round: Number(avgRound.toFixed(2)),
    avg_time_ms: Math.round(avgTimeMs)
  }

  const chart = {
    pass_compare: [
      { label: '初始通过率', value: report.init_pass_rate },
      { label: '最终通过率', value: report.final_pass_rate }
    ],
    repair_success_rate: report.repair_success_rate,
    avg_round: report.avg_round,
    avg_time_ms: report.avg_time_ms,
    error_dist: buildErrDist(items)
  }

  return { items, report, chart }
}

function buildErrDist(items) {
  const map = new Map()
  for (const item of items || []) {
    const key = item.final_pass ? '通过' : (item.err_type || '未知')
    map.set(key, (map.get(key) || 0) + 1)
  }
  const list = [...map.entries()].map(([name, count]) => ({ name, count }))
  const max = Math.max(...list.map(item => item.count), 1)
  return list.map(item => ({ ...item, width: (item.count / max) * 100 }))
}

function fmtMetricText(key, value) {
  const num = Number(value || 0)
  if (['init_pass_rate', 'final_pass_rate', 'repair_success_rate', 'delta_pass_rate'].includes(key)) {
    return `${(num * 100).toFixed(2)}%`
  }
  if (key === 'avg_round') {
    return num.toFixed(2)
  }
  return `${Math.round(num)}`
}

function getCh4FromReport(report) {
  if (report?.ch4?.metrics?.length) return report.ch4
  const initRate = Number(report?.init_pass_rate || 0)
  const finalRate = Number(report?.final_pass_rate || 0)
  const deltaRate = Math.max(0, finalRate - initRate)
  const values = {
    sample_cnt: Number(report?.sample_cnt || 0),
    init_pass_rate: initRate,
    final_pass_rate: finalRate,
    repair_success_rate: Number(report?.repair_success_rate || 0),
    avg_round: Number(report?.avg_round || 0),
    avg_time_ms: Number(report?.avg_time_ms || 0),
    delta_pass_rate: deltaRate
  }
  const order = ['sample_cnt', 'init_pass_rate', 'final_pass_rate', 'repair_success_rate', 'avg_round', 'avg_time_ms', 'delta_pass_rate']
  const labels = {
    sample_cnt: '样本数',
    init_pass_rate: '初始通过率',
    final_pass_rate: '最终通过率',
    repair_success_rate: '修复贡献率',
    avg_round: '平均修复轮次',
    avg_time_ms: '平均耗时(ms)',
    delta_pass_rate: '通过率提升'
  }
  return {
    metric_order: order,
    values,
    metrics: order.map(key => ({ key, label: labels[key], value: values[key], text: fmtMetricText(key, values[key]) })),
    notes: [
      '初始通过率表示仅做单轮生成时的通过情况，可作为单轮生成基线。',
      '最终通过率表示完整实验链路结束后的结果。',
      '修复贡献率表示初始失败但最终通过的样本比例。',
      '通过率提升 = 最终通过率 - 初始通过率。'
    ]
  }
}

function getCh4Chart(row) {
  if (row?.chart?.ch4?.figures?.length) return row.chart.ch4
  const ch4 = getCh4FromReport(row?.report || {})
  const caseDist = row?.report?.case_type_dist || {}
  const caseRows = [
    { label: '修复贡献案例', value: Number(caseDist.repair_success || 0), text: `${Number(caseDist.repair_success || 0)}` },
    { label: 'rollback 生效案例', value: Number(caseDist.rollback_effective || 0), text: `${Number(caseDist.rollback_effective || 0)}` },
    { label: '最终失败案例', value: Number(caseDist.final_failure || 0), text: `${Number(caseDist.final_failure || 0)}` },
    { label: '普通案例', value: Number(caseDist.ordinary || 0), text: `${Number(caseDist.ordinary || 0)}` }
  ]
  const errRows = (row?.chart?.error_dist || buildErrDist(row?.items || [])).map(item => ({
    label: item.name,
    value: Number(item.count || 0),
    text: `${Number(item.count || 0)}`
  }))
  return {
    metric_cards: ch4.metrics,
    figures: [
      {
        key: 'fig_pass',
        title: '初始/最终通过率对比',
        items: [
          { label: '初始通过率', value: ch4.values.init_pass_rate, text: fmtMetricText('init_pass_rate', ch4.values.init_pass_rate) },
          { label: '最终通过率', value: ch4.values.final_pass_rate, text: fmtMetricText('final_pass_rate', ch4.values.final_pass_rate) },
          { label: '通过率提升', value: ch4.values.delta_pass_rate, text: fmtMetricText('delta_pass_rate', ch4.values.delta_pass_rate) }
        ]
      },
      {
        key: 'fig_eff',
        title: '修复效率指标',
        items: [
          { label: '修复贡献率', value: ch4.values.repair_success_rate, text: fmtMetricText('repair_success_rate', ch4.values.repair_success_rate) },
          { label: '平均修复轮次', value: ch4.values.avg_round, text: fmtMetricText('avg_round', ch4.values.avg_round) },
          { label: '平均耗时(ms)', value: ch4.values.avg_time_ms, text: fmtMetricText('avg_time_ms', ch4.values.avg_time_ms) }
        ]
      },
      { key: 'fig_case', title: '典型案例类型分布', items: caseRows },
      { key: 'fig_err', title: '错误类型分布', items: errRows }
    ]
  }
}

function figBarRows(fig) {
  const list = (fig?.items || []).map(item => ({
    label: item.label,
    value: Number(item.value || 0),
    text: item.text || `${item.value || 0}`
  }))
  const max = Math.max(...list.map(item => item.value), 1)
  return list.map(item => ({ ...item, width: (item.value / max) * 100 }))
}

function exportText(filename, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}


function openTaskFromExp(taskId) {
  if (!taskId) {
    ElMessage.warning('当前日志尚未关联到任务ID')
    return
  }
  router.push({ path: '/workbench', query: { taskId } })
}

function itemRowClassName({ row }) {
  const classes = []
  if (Number(activeProblemNo.value) === Number(row?.problem_no)) classes.push('focus-problem-row')
  const tags = itemTypicalTags(row)
  if (tags.some(tag => String(tag || '').includes('最终失败'))) classes.push('exp-item-row-failure')
  else if (tags.some(tag => String(tag || '').includes('rollback'))) classes.push('exp-item-row-rollback')
  else if (tags.some(tag => String(tag || '').includes('修复') || String(tag || '').includes('成功'))) classes.push('exp-item-row-success')
  return classes.join(' ')
}

function focusProblemItem(problemNo) {
  activeProblemNo.value = Number(problemNo || 0) || null
}

async function focusProblemInItems(problemNo) {
  if (!problemNo) return
  activeProblemNo.value = Number(problemNo)
  if (detailRow.value) {
    detailRow.value = { ...detailRow.value, current_problem_no: Number(problemNo) }
  }
  detailTab.value = 'items'
  await nextTick()
  const root = detailItemsTableRef.value?.$el || detailItemsTableRef.value
  const target = root?.querySelector?.('.focus-problem-row')
  target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}

function focusProblemFromRow(row) {
  if (!row?.current_problem_no) {
    ElMessage.warning('当前没有可定位的题号')
    return
  }
  focusProblemInItems(row.current_problem_no)
}

function focusProblemFromLog(log) {
  if (log?.problem_no) {
    focusProblemInItems(log.problem_no)
  }
  if (log?.task_id) {
    openTaskInsight(log.task_id, 'report', log.problem_no)
    return
  }
  if (log?.problem_no) {
    return
  }
  ElMessage.warning('当前日志没有可跳转的 task_id 或题号')
}

function resetTaskInsight() {
  taskInsight.detail = null
  taskInsight.summary = null
  taskInsight.versions = []
  taskInsight.runs = []
  taskInsight.runDetails = []
  taskInsight.latestRun = null
  taskInsight.latestFailedRun = null
  taskInsight.latestFb = null
  taskInsight.latestFailedFb = null
  taskInsight.latestTrace = []
  taskInsight.latestFailedCases = []
  taskInsight.cases = []
  taskInsight.plans = []
  taskInsight.lessons = []
}

async function loadTaskInsight(taskId) {
  if (!taskId) return
  taskInsightLoading.value = true
  try {
    const [detailRes, summaryRes, versionsRes, runsRes, casesRes, plansRes, lessonsRes] = await Promise.allSettled([
      getTaskDetail(taskId),
      getTaskSummary(taskId),
      listTaskVers(taskId),
      listTaskRuns(taskId),
      getTaskCases(taskId),
      getTaskPlans(taskId),
      getTaskLessons(taskId)
    ])

    taskInsight.detail = detailRes.status === 'fulfilled' ? (detailRes.value?.data || null) : null
    taskInsight.summary = summaryRes.status === 'fulfilled' ? (summaryRes.value?.data || null) : null
    taskInsight.versions = versionsRes.status === 'fulfilled' ? (versionsRes.value?.data || []) : []
    taskInsight.runs = runsRes.status === 'fulfilled' ? (runsRes.value?.data || []) : []
    taskInsight.cases = casesRes.status === 'fulfilled' ? (casesRes.value?.data || []) : []
    taskInsight.plans = plansRes.status === 'fulfilled' ? (plansRes.value?.data || []) : []
    taskInsight.lessons = lessonsRes.status === 'fulfilled' ? (lessonsRes.value?.data || []) : []

    if (taskInsight.runs.length) {
      const runDetailRs = await Promise.allSettled(taskInsight.runs.slice(0, 24).map(item => getRunDetail(item.id)))
      taskInsight.runDetails = runDetailRs
        .filter(item => item.status === 'fulfilled')
        .map(item => item.value?.data)
        .filter(Boolean)

      const latestRun = taskInsight.runDetails[0] || null
      const latestRunId = latestRun?.id || taskInsight.runs[0]?.id || null
      const latestFailedBase = taskInsight.runs.find(item => item.result !== 'pass') || null
      const latestFailedRunId = latestFailedBase?.id || null

      taskInsight.latestRun = latestRun
      taskInsight.latestFailedRun = latestFailedRunId
        ? (taskInsight.runDetails.find(item => Number(item?.id) === Number(latestFailedRunId)) || latestFailedBase || null)
        : null

      if (latestRunId) {
        const [fbRes, traceRes] = await Promise.allSettled([
          getRunFb(latestRunId),
          getRunTrace(latestRunId)
        ])
        taskInsight.latestFb = fbRes.status === 'fulfilled' ? (fbRes.value?.data || null) : null
        taskInsight.latestTrace = traceRes.status === 'fulfilled' ? (traceRes.value?.data || []) : []
      } else {
        taskInsight.latestFb = null
        taskInsight.latestTrace = []
      }

      if (latestFailedRunId) {
        const [failedFbRes, failedCasesRes] = await Promise.allSettled([
          getRunFb(latestFailedRunId),
          getRunCases(latestFailedRunId)
        ])
        taskInsight.latestFailedFb = failedFbRes.status === 'fulfilled' ? (failedFbRes.value?.data || null) : null
        const rawCases = failedCasesRes.status === 'fulfilled' ? (failedCasesRes.value?.data || []) : []
        const caseMap = new Map((taskInsight.cases || []).map(item => [Number(item.id), item]))
        taskInsight.latestFailedCases = rawCases.map(item => ({
          ...item,
          assert_text: caseMap.get(Number(item.case_id))?.assert_text || ''
        }))
      } else {
        taskInsight.latestFailedFb = null
        taskInsight.latestFailedCases = []
      }
    } else {
      taskInsight.runDetails = []
      taskInsight.latestRun = null
      taskInsight.latestFailedRun = null
      taskInsight.latestFb = null
      taskInsight.latestFailedFb = null
      taskInsight.latestTrace = []
      taskInsight.latestFailedCases = []
    }
  } catch (error) {
    ElMessage.error(error?.message || '任务洞察加载失败')
  } finally {
    taskInsightLoading.value = false
  }
}

async function openTaskInsight(taskId, tab = 'report', problemNo = null) {
  if (!taskId) {
    ElMessage.warning('当前实验题目尚未关联到任务ID')
    return
  }
  taskInsightTaskId.value = Number(taskId)
  taskInsightTab.value = tab
  if (problemNo) {
    activeProblemNo.value = Number(problemNo)
    if (detailRow.value) {
      detailRow.value = { ...detailRow.value, current_problem_no: Number(problemNo) }
    }
  }
  taskInsightVisible.value = true
  resetTaskInsight()
  await loadTaskInsight(taskInsightTaskId.value)
}

async function refreshTaskInsight() {
  if (!taskInsightTaskId.value) return
  await loadTaskInsight(taskInsightTaskId.value)
  ElMessage.success('任务洞察已刷新')
}

function findRunDetailByVer(verId) {
  return (taskInsight.runDetails || []).find(item => Number(item?.ver_id) === Number(verId)) || null
}

function sortByRoundDesc(list, key = 'round_no') {
  return [...(list || [])].sort((a, b) => Number(b?.[key] || 0) - Number(a?.[key] || 0))
}

function buildTypicalCasePackMarkdown(row) {
  const report = row.report || {}
  const pack = report.typical_cases || {}
  const cases = [
    ['修复贡献案例', pack.success_case],
    ['rollback 生效案例', pack.rollback_case],
    ['最终失败案例', pack.failure_case]
  ]
  const lines = [
    `# 典型案例包：${row.name}`,
    '',
    `- 实验ID：${row.id}`,
    `- 数据集：${row.dataset || '-'}`,
    `- 实验方案：${row.profile?.label || '-'}`,
    `- 样本数：${report.sample_cnt ?? row.sample_cnt ?? 0}`,
    '',
  ]
  for (const [label, item] of cases) {
    lines.push(`## ${label}`)
    lines.push('')
    if (!item) {
      lines.push('- 当前没有筛选出该类型案例。')
      lines.push('')
      continue
    }
    lines.push(`- 题号：#${item.problem_no || '-'}`)
    lines.push(`- 标题：${item.title || '-'}`)
    lines.push(`- 选择原因：${item.reason || '-'}`)
    lines.push(`- 轮次：${item.round_used ?? 0}`)
    lines.push(`- 错误类型：${item.err_type || '-'}`)
    lines.push(`- rollback 次数：${item.rollback_cnt ?? 0}`)
    lines.push(`- 轨迹摘要：${item.latest_trace_sum || '暂无轨迹摘要'}`)
    if (item.first_failed_case) {
      lines.push(`- 首个失败样例：${item.first_failed_case.err_msg || item.first_failed_case.actual_out || '-'}`)
    }
    lines.push('')
  }
  return lines.join('\n')
}

function exportTypicalCasePack(row) {
  if (!row?.report) {
    ElMessage.warning('当前没有可导出的案例包')
    return
  }
  exportText(`exp_${row.id}_case_pack.md`, buildTypicalCasePackMarkdown(row))
  ElMessage.success('典型案例包已导出')
}

function buildReportMarkdown(row) {
  const report = row.report || {}
  const items = row.items || []
  const topItems = items.slice(0, 20)
  const pack = report.typical_cases || {}
  return [
    `# 实验报告：${row.name}`,
    '',
    `- 实验ID：${row.id}`,
    `- 结果来源：${row.report_source === 'server' ? '后端真实' : '前端原型'}`,
    `- 数据集：${row.dataset || '-'}`,
    `- 实验方案：${row.profile?.label || '-'}`,
    `- 样本数：${report.sample_cnt ?? row.sample_cnt ?? 0}`,
    `- 最大轮次：${row.max_round ?? '-'}`,
    `- 当前状态：${fmtStatusLabel(row.status)}`,
    `- 当前阶段：${row.phase || row.status || '-'}`,
    `- 当前题目进度：${currentIndexText(row)}`,
    row.current_problem_no ? `- 当前题号：#${row.current_problem_no}` : `- 当前题号：-`,
    '',
    '## 核心指标',
    '',
    `- 初始通过率：${pct(report.init_pass_rate || 0)}`,
    `- 最终通过率：${pct(report.final_pass_rate || 0)}`,
    `- 修复贡献率：${pct(report.repair_success_rate || 0)}`,
    `- 平均修复轮次：${num1(report.avg_round || 0)}`,
    `- 平均耗时(ms)：${ms(report.avg_time_ms || 0)}`,
    '',
    '## 第四章统一口径',
    '',
    ...getCh4FromReport(report).metrics.map(item => `- ${item.label}：${item.text}`),
    '',
    '## 实验明细（前20条）',
    '',
    '| 题号 | 初始结果 | 最终结果 | 修复贡献 | 轮次 | 耗时(ms) | 错误类型 |',
    '| --- | --- | --- | --- | --- | --- | --- |',
    ...topItems.map(item => `| ${item.problem_no} | ${item.init_pass ? '通过' : '失败'} | ${item.final_pass ? '通过' : '失败'} | ${item.repair_ok ? '是' : '否'} | ${item.round_used} | ${item.time_ms} | ${item.err_type || '-'} |`),
    '',
    '## 典型案例摘要',
    '',
    `- 修复贡献案例：${pack.success_case ? `#${pack.success_case.problem_no} ${pack.success_case.title}` : '暂无'}`,
    `- rollback 生效案例：${pack.rollback_case ? `#${pack.rollback_case.problem_no} ${pack.rollback_case.title}` : '暂无'}`,
    `- 最终失败案例：${pack.failure_case ? `#${pack.failure_case.problem_no} ${pack.failure_case.title}` : '暂无'}`,
    '',
    '## 图表口径说明',
    '',
    ...getCh4FromReport(report).notes.map(item => `- ${item}`),
    '',
    row.report_source === 'server'
      ? '> 当前报告来自后端真实实验接口。'
      : '> 当前报告来自前端原型影子层，仅用于先形成实验页展示闭环。后续后端补齐 /exp/{id}/start、/item、/report、/chart 后会自动切换为真实数据。'
  ].join('\n')
}

function itemTypicalTags(row) {
  if (!row) return []
  const fromServer = Array.isArray(row.typical_tags) ? row.typical_tags.filter(Boolean) : []
  if (fromServer.length) return fromServer
  const tags = []
  if (row.repair_ok) tags.push('修复贡献案例')
  if (Number(row.rollback_cnt || 0) > 0 && row.final_pass) {
    tags.push('rollback 生效案例')
  } else if (Number(row.rollback_cnt || 0) > 0) {
    tags.push('发生 rollback')
  }
  return tags
}

function typicalTagType(tag) {
  const text = String(tag || '')
  if (text.includes('失败')) return 'danger'
  if (text.includes('rollback')) return 'warning'
  if (text.includes('修复') || text.includes('成功')) return 'success'
  return 'info'
}

function buildTaskCaseReportMarkdown() {
  const mdSafe = (val) => String(val ?? '-').replace(/\n/g, '<br>')
  const lines = [
    `# 单题案例报告：任务 #${taskInsightTaskId.value}`,
    '',
    '## 任务摘要',
    '',
    `- 任务标题：${taskInsight.detail?.title || '-'}`,
    `- 当前状态：${statusLabel(taskInsight.detail?.status)}`,
    `- 当前轮次：${taskInsight.detail?.cur_round ?? 0}`,
    `- 最佳版本：${taskInsight.detail?.best_ver_id ?? '-'}`,
    `- 最佳分数：${taskInsight.detail?.best_score ?? 0}`,
    `- 版本数量：${taskInsight.summary?.ver_cnt ?? taskInsight.versions.length}`,
    `- 运行次数：${taskInsight.runs.length}`,
    `- 测试用例数：${taskInsight.cases.length}`,
    '',
    '## 最近反馈',
    '',
    `- 最近运行ID：${taskInsight.latestFb?.run_id ?? '-'}`,
    `- 运行结果：${taskInsight.latestFb?.result || '-'}`,
    `- 通过情况：${taskInsight.latestFb?.pass_cnt ?? 0}/${taskInsight.latestFb?.total_cnt ?? 0}`,
    `- 错误类型：${taskInsight.latestFb?.err_type || '-'}`,
    `- 错误信息：${taskInsight.latestFb?.err_msg || '-'}`,
    `- 轨迹摘要：${taskInsight.latestFb?.trace_sum || '-'}`,
    '',
    '## 最近修复计划',
    '',
    `- 根因：${latestPlan.value?.root_cause || '-'}`,
    `- 计划：${latestPlan.value?.fix_plan || '-'}`,
    `- 插桩建议：${latestPlan.value?.inst_sugg || '-'}`,
    '',
    '## 版本演进摘要',
    '',
    '| 版本 | 类型 | 运行结果 | 通过情况 | 备注 |',
    '| --- | --- | --- | --- | --- |',
    ...versionTimeline.value.map(item => `| V${item.ver_no} | ${item.ver_type || '-'} | ${item.run?.result || '-'} | ${item.run ? `${item.run.pass_cnt ?? 0}/${item.run.total_cnt ?? 0}` : '-'} | ${mdSafe(item.note || '-')} |`),
  ]

  if (taskInsight.latestFailedCases.length) {
    lines.push('', '## 最近失败样例', '', '| case_id | 断言 | 实际输出 | 错误信息 |', '| --- | --- | --- | --- |')
    lines.push(...taskInsight.latestFailedCases.map(item => `| ${item.case_id} | ${mdSafe(item.assert_text)} | ${mdSafe(item.actual_out)} | ${mdSafe(item.err_msg)} |`))
  }

  if (taskInsight.latestTrace.length) {
    lines.push('', '## 关键 Trace 条目（前20条）', '', '| 序号 | 类型 | 函数 | 行号 | 日志 |', '| --- | --- | --- | --- | --- |')
    lines.push(...taskInsight.latestTrace.slice(0, 20).map(item => `| ${item.seq_no ?? '-'} | ${item.node_type || '-'} | ${item.func_name || '-'} | ${item.line_no ?? '-'} | ${mdSafe(item.log_text)} |`))
  }

  return lines.join('\n')
}

function exportTaskCaseReport() {
  if (!taskInsightTaskId.value) {
    ElMessage.warning('当前没有可导出的任务')
    return
  }
  const text = buildTaskCaseReportMarkdown()
  exportText(`task_case_${taskInsightTaskId.value}.md`, text)
  ElMessage.success('单题案例报告已导出')
}

async function loadProfiles() {
  try {
    const res = await listExpProfiles()
    if (Array.isArray(res.data) && res.data.length) {
      profileOptions.value = res.data
    } else {
      profileOptions.value = fallbackProfiles()
    }
  } catch {
    profileOptions.value = fallbackProfiles()
  }
  if (!profileOptions.value.some(item => item.key === form.profile_key)) {
    form.profile_key = profileOptions.value[0]?.key || 'full_chain'
  }
}

async function loadDatasets() {
  try {
    const res = await listDataset()
    if (Array.isArray(res.data) && res.data.length) {
      datasets.value = res.data
      const detailList = await Promise.all(datasets.value.map(async name => {
        try {
          const item = await getDatasetDetail(name)
          return item.data || { name, size: 1, desc: '' }
        } catch {
          return { name, size: 1, desc: '' }
        }
      }))
      datasetMetaMap.value = detailList.reduce((acc, item) => {
        acc[item.name] = item
        return acc
      }, {})
      if (!datasets.value.includes(form.dataset)) {
        form.dataset = datasets.value[0]
      }
      form.sample_cnt = Math.min(Math.max(1, Number(form.sample_cnt || 1)), currentDatasetSize.value)
    }
  } catch {
    // keep defaults
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await listExp()
    rows.value = mergeRows(res.data)
    syncPollingTimers()
  } catch (error) {
    ElMessage.error(error?.message || '实验列表加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.sample_cnt = Math.min(Math.max(1, Number(form.sample_cnt || 1)), currentDatasetSize.value)
  if (!profileOptions.value.length) {
    profileOptions.value = fallbackProfiles()
  }
  if (!profileOptions.value.some(item => item.key === form.profile_key)) {
    form.profile_key = profileOptions.value[0]?.key || 'full_chain'
  }
  createVisible.value = true
}

async function removeExp(row) {
  try {
    await ElMessageBox.confirm(`确认删除实验 #${row.id} 吗？该操作会删除实验明细。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteExp(row.id)
    if (detailRow.value?.id === row.id) {
      detailVisible.value = false
      detailRow.value = null
    }
    if (taskInsightVisible.value) {
      taskInsightVisible.value = false
    }
    await loadData()
    ElMessage.success('实验记录已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '删除实验失败')
    }
  }
}

function resetForm() {
  form.name = ''
  form.dataset = datasets.value[0] || 'custom'
  form.sample_cnt = Math.min(50, currentDatasetSize.value)
  form.max_round = 3
  form.profile_key = profileOptions.value.find(item => item.key === 'full_chain')?.key || profileOptions.value[0]?.key || 'full_chain'
}

const currentDatasetSize = computed(() => {
  const meta = datasetMetaMap.value?.[form.dataset]
  const size = Number(meta?.size || 1)
  return size > 0 ? size : 1
})

const currentDatasetMeta = computed(() => datasetMetaMap.value?.[form.dataset] || null)
const selectedProfile = computed(() => getProfile(form.profile_key))

function datasetLabel(name) {
  const meta = datasetMetaMap.value?.[name]
  if (meta?.display_name) {
    return `${meta.display_name}（${meta.name}）`
  }
  const labelMap = {
    custom: '函数级题库（custom）',
    class_bank: '类文件级题库（class_bank）',
    file_bank: '文件级题库（file_bank）',
    mbpp: '函数级题库（mbpp 旧别名）',
    humaneval: '函数级题库（humaneval 旧别名）',
    class_eval: '类文件级题库（class_eval 旧别名）',
    file_ultra: '文件级题库（file_ultra 旧别名）'
  }
  return labelMap[name] || String(name || '-')
}

watch(() => form.dataset, () => {
  form.sample_cnt = Math.min(Math.max(1, Number(form.sample_cnt || 1)), currentDatasetSize.value)
})

watch(() => form.profile_key, (val) => {
  const profile = getProfile(val)
  if (!profile?.iterative) {
    form.max_round = 1
  } else if (Number(form.max_round || 0) < 2) {
    form.max_round = 3
  }
})

const canCreate = computed(() => Boolean(form.name.trim() && form.dataset && form.profile_key))

async function submitCreate() {
  if (!canCreate.value) {
    ElMessage.warning('请先填写实验名称和数据集')
    return
  }

  creating.value = true
  try {
    const payload = {
      name: form.name.trim(),
      dataset: form.dataset,
      model_id: null,
      sample_cnt: Math.min(currentDatasetSize.value, Math.max(1, Number(form.sample_cnt || 0))),
      max_round: Number(form.max_round || 3),
      profile_key: form.profile_key
    }
    const res = await createExp(payload)
    const id = res.data?.id
    if (id) {
      patchShadow(id, {
        dataset: payload.dataset,
        sample_cnt: payload.sample_cnt,
        max_round: payload.max_round,
        profile: getProfile(payload.profile_key),
        progress: 0,
        progress_text: '待启动',
        note: '已在前端创建实验草稿，可继续进行批量运行、结果图表查看与报告导出。'
      })
    }
    ElMessage.success('实验草稿创建成功')
    createVisible.value = false
    resetForm()
    await loadData()
  } catch (error) {
    ElMessage.error(error?.message || '创建实验失败')
  } finally {
    creating.value = false
  }
}

function openDetail(row) {
  detailRow.value = row
  detailTab.value = 'overview'
  detailVisible.value = true
  if (row?.status === 'running' && row?.report_source === 'server') {
    startPolling(row.id)
  }
}

async function refreshDetail(row) {
  if (!row?.id) return
  const next = await fetchExpAssets(row)
  detailRow.value = next
  rows.value = rows.value.map(item => (item.id === next.id ? next : item))
  if (next.status === 'running' && next.report_source === 'server') {
    startPolling(next.id)
  }
  ElMessage.success('实验结果已刷新')
}

async function fetchExpAssets(row) {
  const expId = row.id
  let useServer = false
  let report = null
  let items = null
  let chart = null

  try {
    const [reportRes, itemsRes, chartRes] = await Promise.all([
      getExpReport(expId),
      getExpItems(expId),
      getExpChart(expId)
    ])
    report = reportRes?.data || null
    items = itemsRes?.data || []
    chart = chartRes?.data || null
    useServer = Boolean(report)
  } catch {
    useServer = false
  }

  if (!useServer) {
    const shadow = getShadowRow(expId)
    report = shadow.report || null
    items = shadow.items || []
    chart = shadow.chart || (items.length ? { error_dist: buildErrDist(items) } : null)
  }

  const shadow = getShadowRow(expId)
  const merged = {
    ...row,
    ...(!useServer ? shadow : {}),
    report: report || row.report || shadow.report || null,
    items: items || row.items || shadow.items || [],
    chart: chart || row.chart || shadow.chart || null,
    report_source: useServer ? 'server' : (row.report_source || shadow.report_source || 'local')
  }

  if (merged.report && !useServer) {
    patchShadow(expId, {
      report: merged.report,
      items: merged.items,
      chart: merged.chart,
      report_source: 'local'
    })
  }

  return merged
}

function simulateLocalRun(row) {
  const expId = row.id
  const total = Math.max(1, Number(row.sample_cnt || 1))
  const baseRow = { ...row, status: 'running', progress: 0, progress_text: '正在批量运行（前端原型模式）...', phase: 'running', current_index: 0, total }
  rows.value = rows.value.map(item => (item.id === expId ? baseRow : item))
  patchShadow(expId, {
    status: 'running',
    progress: 0,
    progress_text: '正在批量运行（前端原型模式）...',
    report_source: 'local',
    phase: 'running',
    current_index: 0,
    total,
    current_problem_no: null,
    current_problem_title: '',
    logs: [{ ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'info', text: '前端原型模式：实验启动', action: 'exp_start' }]
  })

  if (runTimers.has(expId)) {
    clearInterval(runTimers.get(expId))
  }

  let progress = 0
  const timer = setInterval(() => {
    progress += 10
    const currentIndex = Math.min(total, Math.max(1, Math.ceil((progress / 100) * total)))
    const currentNo = currentIndex
    const currentTitle = `原型样本 ${currentNo}`
    if (progress >= 100) {
      clearInterval(timer)
      runTimers.delete(expId)
      const { items, report, chart } = makeLocalItems(baseRow)
      const status = report.final_pass_rate >= 0.6 ? 'pass' : 'fail'
      patchShadow(expId, {
        status,
        progress: 100,
        progress_text: `已完成（最终通过率 ${pct(report.final_pass_rate)}）`,
        report,
        items,
        chart,
        report_source: 'local',
        phase: status,
        current_index: total,
        total,
        current_problem_no: null,
        current_problem_title: '',
        logs: [
          ...(getShadowRow(expId).logs || []),
          { ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'info', text: `前端原型模式：实验结束，最终状态 ${status}`, action: 'exp_done' }
        ].slice(-80),
        note: '当前结果来自前端原型影子层；后端补齐实验接口后会自动切换为真实结果。'
      })
      rows.value = mergeRows(rows.value.map(item => (item.id === expId ? { ...item, status } : item)))
      if (detailRow.value?.id === expId) {
        detailRow.value = {
          ...detailRow.value,
          status,
          progress: 100,
          progress_text: `已完成（最终通过率 ${pct(report.final_pass_rate)}）`,
          report,
          items,
          chart,
          report_source: 'local'
        }
      }
      ElMessage.success('实验批量运行完成（前端原型模式）')
      return
    }

    const progressText = `正在批量运行（${progress}%）`
    const nextLogs = [
      ...(getShadowRow(expId).logs || []),
      { ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'info', text: `正在执行第 ${currentIndex}/${total} 题：#${currentNo}`, problem_no: currentNo, problem_title: currentTitle, current_index: currentIndex, total, action: 'problem_running' }
    ].slice(-80)
    patchShadow(expId, {
      status: 'running',
      progress,
      progress_text: progressText,
      report_source: 'local',
      phase: 'running',
      current_index: currentIndex,
      total,
      current_problem_no: currentNo,
      current_problem_title: currentTitle,
      logs: nextLogs
    })
    rows.value = rows.value.map(item => (item.id === expId ? { ...item, status: 'running', progress, progress_text: progressText, report_source: 'local', phase: 'running', current_index: currentIndex, total, current_problem_no: currentNo, current_problem_title: currentTitle, logs: nextLogs } : item))
    if (detailRow.value?.id === expId) {
      detailRow.value = { ...detailRow.value, status: 'running', progress, progress_text: progressText, report_source: 'local', phase: 'running', current_index: currentIndex, total, current_problem_no: currentNo, current_problem_title: currentTitle, logs: nextLogs }
    }
  }, 260)

  runTimers.set(expId, timer)
}

async function handleStart(row) {
  try {
    await startExp(row.id)
    ElMessage.success('已在后端异步启动实验，正在轮询进度')
    rows.value = rows.value.map(item => (item.id === row.id ? { ...item, status: 'running', progress: Number(item.progress || 0), progress_text: '后端实验已启动...', report_source: 'server', phase: 'queued', logs: [{ ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'info', text: '后端实验已启动，等待首个进度刷新', action: 'exp_start' }] } : item))
    patchShadow(row.id, {
      status: 'running',
      progress: Number(getShadowRow(row.id)?.progress || 0),
      progress_text: '后端实验已启动...',
      report_source: 'server',
      phase: 'queued',
      logs: [{ ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'info', text: '后端实验已启动，等待首个进度刷新', action: 'exp_start' }]
    })
    startPolling(row.id)
    await pollServerExp(row.id, detailRow.value?.id === row.id)
  } catch (error) {
    const status = error?.response?.status
    if (status === 404 || /接口不存在/.test(error?.message || '')) {
      simulateLocalRun(row)
      ElMessage.warning('后端尚未补齐实验启动接口，已切换为前端原型模式继续演示')
      return
    }
    ElMessage.error(error?.message || '启动实验失败')
  }
}

async function handleStop(row) {
  const expId = row.id
  if (runTimers.has(expId)) {
    clearInterval(runTimers.get(expId))
    runTimers.delete(expId)
  }

  try {
    await stopExp(expId)
    stopPolling(expId)
    patchShadow(expId, {
      status: 'stop',
      progress_text: '已停止',
      progress: Number(getShadowRow(expId)?.progress || 0),
      phase: 'stop',
      logs: [
        ...(getShadowRow(expId).logs || []),
        { ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'warning', text: '用户已请求停止实验', action: 'exp_stop' }
      ].slice(-80)
    })
    await loadData()
    if (detailRow.value?.id === expId) {
      await refreshDetail(detailRow.value)
    }
    ElMessage.success('实验已停止')
  } catch (error) {
    const status = error?.response?.status
    if (status === 404 || /接口不存在/.test(error?.message || '')) {
      patchShadow(expId, {
        status: 'stop',
        progress_text: '已停止（前端原型模式）',
        progress: Number(getShadowRow(expId)?.progress || 0),
        report_source: 'local',
        phase: 'stop',
        logs: [
          ...(getShadowRow(expId).logs || []),
          { ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }), level: 'warning', text: '前端原型模式：用户已停止实验', action: 'exp_stop' }
        ].slice(-80)
      })
      rows.value = mergeRows(rows.value.map(item => (item.id === expId ? { ...item, status: 'stop', report_source: 'local' } : item)))
      if (detailRow.value?.id === expId) {
        detailRow.value = { ...detailRow.value, status: 'stop', report_source: 'local' }
      }
      ElMessage.warning('后端尚未补齐停止接口，已在前端原型模式下停止')
      return
    }
    ElMessage.error(error?.message || '停止实验失败')
  }
}

async function openCompare() {
  if (compareSelection.value.length < 2 || compareSelection.value.length > 3) {
    ElMessage.warning('请选择 2 到 3 条实验记录进行对比')
    return
  }
  const selected = compareSelection.value.map(item => rows.value.find(row => Number(row.id) === Number(item.id)) || item).filter(Boolean)
  if (selected.some(item => !item.report)) {
    ElMessage.warning('请先运行实验并生成结果，再进行对比')
    return
  }
  compareLoading.value = true
  try {
    const ids = selected.map(item => item.id)
    const res = await compareExp(ids)
    compareData.value = res.data || null
    compareVisible.value = true
  } catch (error) {
    compareData.value = buildLocalCompare(compareSelection.value)
    compareVisible.value = true
    if (!compareData.value) {
      ElMessage.error(error?.message || '实验对比加载失败')
      return
    }
  } finally {
    compareLoading.value = false
  }
}

function buildCompareRankText(list) {
  if (!Array.isArray(list) || !list.length) return '-'
  const groups = []
  list.forEach(item => {
    const value = Number(item.value || 0)
    const last = groups[groups.length - 1]
    if (last && Math.abs(Number(last.value || 0) - value) < 1e-9) {
      last.labels.push(item.label)
    } else {
      groups.push({ value, labels: [item.label] })
    }
  })
  return groups.map(group => group.labels.join(' = ')).join(' > ')
}

function buildLocalCompareSummary(items) {
  const list = (Array.isArray(items) ? items : []).map(exp => ({
    exp_id: exp.id,
    mode: exp.profile?.key,
    label: exp.name,
    init_pass_rate: Number(exp.report?.init_pass_rate || 0),
    final_pass_rate: Number(exp.report?.final_pass_rate || 0),
    repair_success_rate: Number(exp.report?.repair_success_rate || 0),
    avg_round: Number(exp.report?.avg_round || 0),
    avg_time_ms: Number(exp.report?.avg_time_ms || 0)
  }))
  if (!list.length) return { cards: [], verdict: null, notes: [] }
  const withDelta = list.map(item => ({ ...item, delta_pass_rate: Math.max(0, item.final_pass_rate - item.init_pass_rate) }))
  const rank = (key, prefer = 'high') => [...withDelta].sort((a, b) => prefer === 'high' ? Number(b[key] || 0) - Number(a[key] || 0) : Number(a[key] || 0) - Number(b[key] || 0))
  const bestLabel = rows => {
    if (!rows.length) return '-'
    const best = Number(rows[0]?.[rows.metricKey] || rows[0]?.value || 0)
    const winners = rows.filter(item => Math.abs(Number((rows.metricKey ? item[rows.metricKey] : item.value) || 0) - best) < 1e-9).map(item => item.label)
    return winners.length === rows.length ? '持平' : winners.join(' / ')
  }
  const rankText = (rows, key) => {
    const groups = []
    rows.forEach(item => {
      const value = Number(item[key] || 0)
      const last = groups[groups.length - 1]
      if (last && Math.abs(Number(last.value || 0) - value) < 1e-9) {
        last.labels.push(item.label)
      } else {
        groups.push({ value, labels: [item.label] })
      }
    })
    return groups.map(group => group.labels.join(' = ')).join(' > ')
  }
  const finalRank = rank('final_pass_rate', 'high')
  const roundRank = rank('avg_round', 'low')
  const deltaRank = rank('delta_pass_rate', 'high')
  const cards = [
    {
      key: 'best_final_pass',
      title: '最终通过率最高',
      winner_label: bestLabel(Object.assign(finalRank, { metricKey: 'final_pass_rate' })),
      value_text: formatCompareMetric('final_pass_rate', finalRank[0]?.final_pass_rate || 0),
      desc: `排序：${rankText(finalRank, 'final_pass_rate')}`,
      type: 'success'
    },
    {
      key: 'best_avg_round',
      title: '平均轮次最低',
      winner_label: bestLabel(Object.assign(roundRank, { metricKey: 'avg_round' })),
      value_text: formatCompareMetric('avg_round', roundRank[0]?.avg_round || 0),
      desc: `排序：${rankText(roundRank, 'avg_round')}`,
      type: 'warning'
    },
    {
      key: 'best_delta_pass',
      title: '通过率提升最大',
      winner_label: bestLabel(Object.assign(deltaRank, { metricKey: 'delta_pass_rate' })),
      value_text: formatCompareMetric('delta_pass_rate', deltaRank[0]?.delta_pass_rate || 0),
      desc: `排序：${rankText(deltaRank, 'delta_pass_rate')}`,
      type: 'primary'
    }
  ]

  let verdict = {
    title: '完整链路稳定性判断',
    level: 'info',
    label: '当前未选择完整链路',
    summary: '本次对比结果中未包含完整链路方案，暂时无法判断其稳定性表现。',
    bullets: []
  }
  const full = withDelta.find(item => item.mode === 'full_chain')
  if (full) {
    const others = withDelta.filter(item => item.mode !== 'full_chain')
    const bestOtherFinal = others.length ? Math.max(...others.map(item => Number(item.final_pass_rate || 0))) : Number(full.final_pass_rate || 0)
    const bestOtherRepair = others.length ? Math.max(...others.map(item => Number(item.repair_success_rate || 0))) : Number(full.repair_success_rate || 0)
    const bestOtherRound = others.length ? Math.min(...others.map(item => Number(item.avg_round || 0))) : Number(full.avg_round || 0)
    const betterFinal = Number(full.final_pass_rate || 0) >= bestOtherFinal - 1e-9
    const betterRepair = Number(full.repair_success_rate || 0) >= bestOtherRepair - 1e-9
    const roundPenalty = Number(full.avg_round || 0) - bestOtherRound
    if (betterFinal && betterRepair && roundPenalty <= 0.3) {
      verdict = {
        title: '完整链路稳定性判断',
        level: 'success',
        label: '完整链路更稳',
        summary: '从最终通过率、修复贡献率和平均轮次综合看，完整链路在这组实验里表现出更好的稳定性。',
        bullets: []
      }
    } else if (betterFinal && betterRepair) {
      verdict = {
        title: '完整链路稳定性判断',
        level: 'warning',
        label: '完整链路更偏稳健，但轮次略高',
        summary: '完整链路在最终通过率和修复贡献率上占优，但平均轮次略高，更像是以更多修复成本换取稳定结果。',
        bullets: []
      }
    } else if (betterFinal) {
      verdict = {
        title: '完整链路稳定性判断',
        level: 'info',
        label: '完整链路最终结果更好，但优势有限',
        summary: '完整链路的最终通过率更高，不过在修复贡献率或平均轮次上并没有同时形成明显优势。',
        bullets: []
      }
    } else {
      verdict = {
        title: '完整链路稳定性判断',
        level: 'danger',
        label: '本次对比下未体现明显稳定优势',
        summary: '在当前这组实验中，完整链路没有同时取得更高的最终通过率和更好的修复效率，稳定性优势还不明显。',
        bullets: []
      }
    }
    verdict.bullets = [
      `完整链路最终通过率：${formatCompareMetric('final_pass_rate', full.final_pass_rate)}；其它方案最高：${formatCompareMetric('final_pass_rate', bestOtherFinal)}。`,
      `完整链路修复贡献率：${formatCompareMetric('repair_success_rate', full.repair_success_rate)}；其它方案最高：${formatCompareMetric('repair_success_rate', bestOtherRepair)}。`,
      `完整链路平均轮次：${formatCompareMetric('avg_round', full.avg_round)}；其它方案最低：${formatCompareMetric('avg_round', bestOtherRound)}。`
    ]
  }
  return {
    cards,
    verdict,
    notes: [
      '结论摘要区基于当前已运行实验的真实统计结果自动生成，可直接用于论文截图展示。',
      '完整链路稳定性判断主要参考最终通过率、修复贡献率和平均轮次三项指标。'
    ]
  }
}

function buildLocalCompare(selection) {
  const items = (Array.isArray(selection) ? selection : []).map(item => ({ ...item, profile: getProfile(item.profile) }))
  if (items.length < 2 || items.length > 3) return null
  const metricSpecs = [
    ['final_pass_rate', '最终通过率', 'high'],
    ['repair_success_rate', '修复贡献率', 'high'],
    ['delta_pass_rate', '通过率提升', 'high'],
    ['avg_round', '平均修复轮次', 'low'],
    ['avg_time_ms', '平均耗时(ms)', 'low']
  ]
  const groups = metricSpecs.map(([key, label]) => ({
    metric_key: key,
    metric_label: label,
    items: items.map(exp => {
      const value = key === 'delta_pass_rate'
        ? Number(exp.report?.final_pass_rate || 0) - Number(exp.report?.init_pass_rate || 0)
        : Number(exp.report?.[key] || 0)
      return { exp_id: exp.id, label: exp.name, value, text: formatCompareMetric(key, value) }
    })
  }))
  const metric_rows = metricSpecs.map(([key, label, prefer]) => {
    const values = groups.find(g => g.metric_key === key)?.items || []
    const ordered = [...values].sort((a, b) => prefer === 'high' ? b.value - a.value : a.value - b.value)
    const bestValue = ordered.length ? Number(ordered[0].value || 0) : 0
    const bestNames = ordered.filter(item => Math.abs(Number(item.value || 0) - bestValue) < 1e-9).map(item => item.label)
    const best_label = bestNames.length === values.length ? '持平' : bestNames.join(' / ')
    const rank_text = buildCompareRankText(ordered)
    return { metric_key: key, metric_label: label, prefer, values, best_label, rank_text }
  })
  return {
    experiments: items,
    compare: {
      groups,
      summary: buildLocalCompareSummary(items),
      notes: ['对比结果优先读取后端接口；当前为前端降级计算结果。']
    },
    summary: buildLocalCompareSummary(items),
    metric_rows
  }
}

function exportReport(row) {
  if (!row?.report) {
    ElMessage.warning('当前实验尚无可导出的结果')
    return
  }
  const text = buildReportMarkdown(row)
  exportText(`exp_${row.id}_${row.name || 'report'}.md`, text)
  ElMessage.success('实验报告已导出')
}

const filteredRows = computed(() => {
  const kw = String(keyword.value || '').trim().toLowerCase()
  if (!kw) return rows.value
  return rows.value.filter(item => {
    const text = [item.id, item.name, item.dataset, item.status, fmtStatusLabel(item.status), item.profile?.label, item.profile?.short_label].join(' ').toLowerCase()
    return text.includes(kw)
  })
})

const statCards = computed(() => {
  const list = rows.value || []
  const total = list.length
  const running = list.filter(item => item.status === 'running').length
  const finished = list.filter(item => ['pass', 'fail', 'stop'].includes(item.status)).length
  const reportRows = list.filter(item => item.report)
  const avgFinalPass = reportRows.length
    ? `${Math.round((reportRows.reduce((sum, item) => sum + Number(item.report?.final_pass_rate || 0), 0) / reportRows.length) * 100)}%`
    : '0%'
  return { total, running, finished, avgFinalPass }
})

const statusBarRows = computed(() => {
  const list = rows.value || []
  const counts = {
    draft: list.filter(item => item.status === 'draft').length,
    running: list.filter(item => item.status === 'running').length,
    pass: list.filter(item => item.status === 'pass').length,
    fail: list.filter(item => item.status === 'fail').length,
    stop: list.filter(item => item.status === 'stop').length
  }
  const max = Math.max(...Object.values(counts), 1)
  return [
    { key: 'draft', label: '草稿', count: counts.draft, width: (counts.draft / max) * 100 },
    { key: 'running', label: '运行中', count: counts.running, width: (counts.running / max) * 100 },
    { key: 'pass', label: '通过', count: counts.pass, width: (counts.pass / max) * 100 },
    { key: 'fail', label: '失败', count: counts.fail, width: (counts.fail / max) * 100 },
    { key: 'stop', label: '已停止', count: counts.stop, width: (counts.stop / max) * 100 }
  ]
})

const datasetStats = computed(() => {
  const map = new Map()
  for (const item of rows.value || []) {
    const key = item.dataset || '未知'
    map.set(key, (map.get(key) || 0) + 1)
  }
  return [...map.entries()].map(([name, count]) => ({ name, count }))
})

const detailItems = computed(() => detailRow.value?.items || [])
const detailErrBars = computed(() => detailRow.value?.chart?.error_dist || buildErrDist(detailItems.value))
const detailCh4 = computed(() => getCh4Chart(detailRow.value))
const detailCh4Metrics = computed(() => detailCh4.value?.metric_cards || getCh4FromReport(detailRow.value?.report || {}).metrics || [])
const detailCh4Figures = computed(() => detailCh4.value?.figures || [])
const detailCh4Notes = computed(() => getCh4FromReport(detailRow.value?.report || {}).notes || [])
const typicalCaseStats = computed(() => ({
  repairSuccess: detailItems.value.filter(item => itemTypicalTags(item).includes('修复贡献案例')).length,
  rollbackEffective: detailItems.value.filter(item => itemTypicalTags(item).includes('rollback 生效案例')).length
}))
const detailTypicalCases = computed(() => detailRow.value?.report?.typical_cases || {})
const detailTypicalCards = computed(() => [
  {
    key: 'success_case',
    title: '修复贡献案例',
    tagType: 'success',
    item: detailTypicalCases.value?.success_case || null,
    problemNoText: detailTypicalCases.value?.success_case?.problem_no ? `#${detailTypicalCases.value.success_case.problem_no}` : '暂无'
  },
  {
    key: 'rollback_case',
    title: 'rollback 生效案例',
    tagType: 'warning',
    item: detailTypicalCases.value?.rollback_case || null,
    problemNoText: detailTypicalCases.value?.rollback_case?.problem_no ? `#${detailTypicalCases.value.rollback_case.problem_no}` : '暂无'
  },
  {
    key: 'failure_case',
    title: '最终失败案例',
    tagType: 'danger',
    item: detailTypicalCases.value?.failure_case || null,
    problemNoText: detailTypicalCases.value?.failure_case?.problem_no ? `#${detailTypicalCases.value.failure_case.problem_no}` : '暂无'
  }
])
const detailLogs = computed(() => (Array.isArray(detailRow.value?.logs) ? detailRow.value.logs : []).slice(-50))
const latestInsightVersion = computed(() => {
  const list = taskInsight.versions || []
  return list.length ? list[list.length - 1] : null
})
const bestInsightVersion = computed(() => {
  const bestId = Number(taskInsight.detail?.best_ver_id || 0)
  if (!bestId) return null
  return (taskInsight.versions || []).find(item => Number(item.id) === bestId) || null
})
const versionStats = computed(() => {
  const stats = { init: 0, repair: 0, rollback: 0, manual: 0 }
  for (const item of taskInsight.versions || []) {
    const key = item?.ver_type
    if (Object.prototype.hasOwnProperty.call(stats, key)) stats[key] += 1
  }
  return stats
})
const latestPlan = computed(() => sortByRoundDesc(taskInsight.plans)[0] || null)
const latestLesson = computed(() => sortByRoundDesc(taskInsight.lessons)[0] || null)
const versionTimeline = computed(() => {
  const list = taskInsight.versions || []
  const bestId = Number(taskInsight.detail?.best_ver_id || 0)
  const latestId = Number(latestInsightVersion.value?.id || 0)
  return list.map(item => ({
    ...item,
    run: findRunDetailByVer(item.id),
    isBest: bestId && Number(item.id) === bestId,
    isLatest: latestId && Number(item.id) === latestId
  }))
})

onMounted(async () => {
  await Promise.all([loadProfiles(), loadDatasets(), loadData()])
  syncPollingTimers()
})

onBeforeUnmount(() => {
  for (const timer of runTimers.values()) {
    clearInterval(timer)
  }
  runTimers.clear()
  for (const timer of pollTimers.values()) {
    clearInterval(timer)
  }
  pollTimers.clear()
})
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.page-card { border-radius: 16px; }
.card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.small-tip { font-size: 12px; color: #909399; }
.status-bars { display: flex; flex-direction: column; gap: 12px; }
.status-bar-item { display: flex; flex-direction: column; gap: 6px; }
.bar-head { display: flex; justify-content: space-between; color: #606266; font-size: 13px; }
.bar-track { height: 10px; border-radius: 999px; background: #f2f3f5; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; }
.bar-fill.draft { background: #909399; }
.bar-fill.running { background: #409eff; }
.bar-fill.pass { background: #67c23a; }
.bar-fill.fail { background: #f56c6c; }
.bar-fill.stop { background: #e6a23c; }
.metric-block { margin-top: 18px; border-top: 1px dashed #ebeef5; padding-top: 14px; }
.metric-title { font-size: 13px; font-weight: 700; color: #303133; margin-bottom: 10px; }
.metric-line { display: flex; justify-content: space-between; margin-bottom: 8px; color: #606266; }
.drawer-tip {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f7f9fc;
  color: #606266;
  line-height: 1.8;
}
.metric-card { padding: 14px 16px; border: 1px solid #ebeef5; border-radius: 14px; background: #fff; }
.toolbar-row { display:flex; justify-content:flex-end; margin-bottom:14px; }
.toolbar-row-center { justify-content:center; gap: 10px; }
.toolbar-search { width: 360px; max-width: 100%; }
.toolbar-search-btn { flex-shrink: 0; }
.op-grid { display:grid; grid-template-columns: 1fr 1fr; gap:8px; }
.op-btn { width:100%; margin:0 !important; }
.op-row-bottom { display:flex; justify-content:flex-end; margin-top:6px; }
.op-btn-delete { padding-right: 2px; }
.metric-card.compact { padding: 12px 14px; }
.metric-label { font-size: 12px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 18px; font-weight: 700; color: #303133; }
.status-wrap { display: flex; flex-direction: column; gap: 6px; }
.source-tag { width: fit-content; }
.progress-cell { display: flex; flex-direction: column; gap: 6px; }
.progress-text { font-size: 12px; color: #909399; line-height: 1.4; }
.result-brief { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #606266; }
.muted-text { color: #909399; }
.detail-top { display: flex; flex-direction: column; gap: 14px; }
.detail-tabs { margin-top: 16px; }
.paper-card {
  margin-top: 14px;
  border-radius: 14px;
}
.paper-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.paper-metric {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px dashed #dcdfe6;
  background: #fafbfd;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #606266;
}
.paper-metric strong {
  color: #303133;
}
.paper-notes {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.paper-note {
  color: #606266;
  font-size: 12px;
  line-height: 1.7;
}
.report-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.paper-fig-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.chart-card { border-radius: 14px; }
.chart-card.span-2 { grid-column: span 2; }
.dual-bar-chart { display: flex; flex-direction: column; gap: 14px; }
.dual-row {
  display: grid;
  grid-template-columns: 42px 1fr 56px;
  align-items: center;
  gap: 10px;
}
.dual-track, .err-track, .mini-track {
  height: 12px;
  border-radius: 999px;
  background: #f2f3f5;
  overflow: hidden;
}
.dual-fill, .err-fill, .mini-fill {
  height: 100%;
  border-radius: 999px;
}
.dual-fill.init { background: #909399; }
.dual-fill.final, .mini-fill { background: #67c23a; }
.gauge-wrap {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.gauge-item {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 14px;
  background: #fafafa;
}
.gauge-label { font-size: 12px; color: #909399; margin-bottom: 8px; }
.gauge-value { font-size: 20px; font-weight: 700; color: #303133; }
.err-bars { display: flex; flex-direction: column; gap: 12px; }
.err-row {
  display: grid;
  grid-template-columns: 90px 1fr 50px;
  align-items: center;
  gap: 10px;
}
.err-name {
  color: #606266;
  font-size: 13px;
}
.err-fill { background: #409eff; }
.drawer-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 16px; }

.tag-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
.item-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.pre-line { white-space: pre-wrap; word-break: break-word; }
.report-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.insight-block-title { font-weight: 700; color: #303133; margin-bottom: 10px; }
.insight-block-body { color: #606266; line-height: 1.8; }
.mini-grid { display: grid; gap: 10px; }
.mini-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.mini-item { border: 1px solid #ebeef5; border-radius: 10px; padding: 10px 12px; background: #fafafa; display: flex; flex-direction: column; gap: 6px; }
.mini-item.wide { grid-column: 1 / -1; }
.plan-list { display: flex; flex-direction: column; gap: 10px; }
.plan-card { border: 1px solid #ebeef5; border-radius: 12px; padding: 12px; background: #fafafa; }
.plan-head { font-weight: 700; color: #303133; margin-bottom: 8px; }
.plan-body { color: #606266; line-height: 1.8; }
.timeline-box { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
.timeline-item { border: 1px solid #ebeef5; border-radius: 14px; padding: 12px; background: #fff; }
.timeline-item.best { border-color: #67c23a; background: #f6fff2; }
.timeline-item.latest { box-shadow: inset 0 0 0 1px #409eff; }
.timeline-top { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.timeline-title { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.ver-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 42px; height: 24px; padding: 0 8px; border-radius: 999px; background: #f2f3f5; font-weight: 700; color: #303133; }
.timeline-run { display: flex; flex-wrap: wrap; gap: 10px; color: #909399; font-size: 12px; }
.timeline-note { margin-top: 8px; color: #606266; }
.timeline-extra { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; color: #909399; font-size: 12px; }

@media (max-width: 900px) {
  .report-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }
  .paper-grid {
    grid-template-columns: 1fr;
  }
  .paper-fig-grid {
    grid-template-columns: 1fr;
  }
  .chart-card.span-2 { grid-column: span 1; }
}

.current-cell { display: flex; flex-direction: column; gap: 4px; }
.current-main { font-size: 13px; color: #303133; }
.current-sub { font-size: 12px; color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.live-panel { margin: 16px 0 18px; padding: 14px; border: 1px solid #ebeef5; border-radius: 14px; background: #fafafa; }
.live-head { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #303133; }
.live-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.live-item { padding: 10px 12px; border-radius: 10px; background: #fff; border: 1px solid #ebeef5; display: flex; flex-direction: column; gap: 4px; }
.live-item-wide { grid-column: 1 / -1; }
.live-label { font-size: 12px; color: #909399; }
.log-box { border: 1px solid #ebeef5; border-radius: 12px; background: #fff; padding: 10px 12px; }
.log-head { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #606266; }
.log-list { max-height: 240px; overflow: auto; display: flex; flex-direction: column; gap: 8px; }
.log-line { font-size: 12px; line-height: 1.6; color: #303133; word-break: break-all; }
.log-ts { color: #909399; margin-right: 6px; }
.log-level { display: inline-block; min-width: 40px; margin-right: 6px; font-weight: 600; }
.log-level.info { color: #409eff; }
.log-level.warning { color: #e6a23c; }
.log-level.error { color: #f56c6c; }
@media (max-width: 768px) { .live-grid { grid-template-columns: 1fr; } }

.current-link-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:4px; }
.log-actions { display:inline-flex; flex-wrap:wrap; gap:8px; margin-left:8px; }
:deep(.focus-problem-row) > td { background: #fff8e6 !important; }
:deep(.exp-item-row-success) > td { background: #f0f9eb !important; }
:deep(.exp-item-row-rollback) > td { background: #fff7e6 !important; }
:deep(.exp-item-row-failure) > td { background: #fef0f0 !important; }
.task-insight-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.task-insight-title { font-size: 16px; font-weight: 700; color: #303133; }
.task-insight-sub { margin-top: 6px; color: #909399; line-height: 1.7; }
.task-insight-actions { display: flex; gap: 8px; }
.task-insight-tabs { margin-top: 8px; }
.task-insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.metric-small { font-size: 14px; line-height: 1.5; }
.insight-block {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  background: #fff;
}
.insight-block-title { font-size: 14px; font-weight: 700; color: #303133; margin-bottom: 10px; }
.insight-block-body { color: #606266; line-height: 1.8; }
.pre-line { white-space: pre-line; }
.mini-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.mini-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f7f9fc;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mini-item span { font-size: 12px; color: #909399; }
.mini-item strong { color: #303133; line-height: 1.6; }
.mini-item.wide { grid-column: 1 / -1; }
.report-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.plan-list { display: flex; flex-direction: column; gap: 10px; }
.plan-card { padding: 12px; border-radius: 12px; background: #f7f9fc; }
.plan-head { font-size: 13px; font-weight: 700; color: #303133; margin-bottom: 8px; }
.plan-body { color: #606266; line-height: 1.8; margin-top: 4px; }
.timeline-box { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.timeline-item {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
}
.timeline-item.best { border-color: #95d475; background: #f6ffed; }
.timeline-item.latest { box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.18) inset; }
.timeline-top { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.timeline-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ver-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 700;
}
.timeline-run { display: flex; gap: 12px; color: #606266; font-size: 13px; flex-wrap: wrap; }
.timeline-note { margin-top: 10px; color: #303133; line-height: 1.7; }
.timeline-extra { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; color: #909399; font-size: 12px; }
.item-actions { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
@media (max-width: 900px) {
  .task-insight-head,
  .report-columns {
    grid-template-columns: 1fr;
    display: block;
  }
  .task-insight-grid,
  .mini-grid {
    grid-template-columns: 1fr;
  }
  .task-insight-actions { margin-top: 12px; }
}

.case-pack-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.case-pack-card {
  border-radius: 12px;
}
.case-pack-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.case-pack-title {
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 6px;
}
.case-pack-meta {
  color: #4b5563;
  line-height: 1.6;
  margin-bottom: 8px;
}
.case-pack-mini {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 4px;
}
.case-pack-actions {
  margin-top: 10px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
@media (max-width: 1200px) {
  .case-pack-grid {
    grid-template-columns: 1fr;
  }
}


.profile-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.profile-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.profile-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  width: 100%;
}
.profile-option-card {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
  cursor: pointer;
  transition: all .2s ease;
}
.profile-option-card:hover {
  border-color: #bfdcff;
  box-shadow: 0 6px 18px rgba(64, 158, 255, 0.08);
}
.profile-option-card.active {
  border-color: #409eff;
  background: #f5f9ff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.15) inset;
}
.profile-option-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.profile-option-title {
  font-weight: 700;
  color: #303133;
}

.compare-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.compare-card-subtitle {
  color: #909399;
  font-size: 12px;
  font-weight: 500;
}
.compare-summary-shell {
  margin-bottom: 14px;
}
.summary-intro {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #ebeef5;
  background: linear-gradient(135deg, #f8fbff 0%, #f5f7fa 100%);
}
.summary-intro-main {
  color: #303133;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.7;
  margin-bottom: 4px;
}
.summary-intro-sub {
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}
.summary-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(320px, 1fr);
  gap: 14px;
  align-items: stretch;
}
.summary-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 220px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #ebeef5;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(17, 24, 39, 0.06);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.summary-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 4px;
  background: #c0c4cc;
}
.summary-card.success::before {
  background: linear-gradient(90deg, #67c23a 0%, #95d475 100%);
}
.summary-card.warning::before {
  background: linear-gradient(90deg, #e6a23c 0%, #f3d19e 100%);
}
.summary-card.primary::before {
  background: linear-gradient(90deg, #409eff 0%, #79bbff 100%);
}
.summary-card.info::before {
  background: linear-gradient(90deg, #909399 0%, #c8c9cc 100%);
}
.summary-card-label {
  color: #909399;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.6;
  letter-spacing: 0.2px;
}
.summary-card-value {
  color: #1f2d3d;
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
}
.summary-card.success .summary-card-value {
  color: #1d7a46;
}
.summary-card.warning .summary-card-value {
  color: #b88230;
}
.summary-card.primary .summary-card-value {
  color: #1f6fd8;
}
.summary-card-row,
.summary-card-desc {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}
.summary-card-row {
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
}
.summary-card-winner {
  color: #303133;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.7;
}
.summary-row-label {
  color: #909399;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.8;
}
.summary-card-desc {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #f2f3f5;
  color: #606266;
  font-size: 13px;
  line-height: 1.8;
}
.summary-verdict {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #ebeef5;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.summary-verdict.success {
  border-color: #d9ecdb;
  background: linear-gradient(180deg, #f7fcf8 0%, #eff8f2 100%);
}
.summary-verdict.warning {
  border-color: #f3e1c1;
  background: linear-gradient(180deg, #fffaf2 0%, #fdf4e6 100%);
}
.summary-verdict.danger {
  border-color: #f5c2c7;
  background: linear-gradient(180deg, #fff7f7 0%, #fdf0f0 100%);
}
.summary-verdict.info {
  border-color: #d9ecff;
  background: linear-gradient(180deg, #f7fbff 0%, #edf5ff 100%);
}
.summary-verdict-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.summary-verdict-title {
  color: #303133;
  font-size: 16px;
  font-weight: 700;
}
.summary-verdict-text {
  color: #303133;
  font-size: 14px;
  line-height: 1.85;
}
.summary-verdict-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}
.summary-verdict-list li {
  position: relative;
  padding: 10px 12px 10px 24px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(235, 238, 245, 0.9);
  color: #606266;
  font-size: 13px;
  line-height: 1.75;
}
.summary-verdict-list li::before {
  content: '';
  position: absolute;
  left: 10px;
  top: 18px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #409eff;
}
.summary-note-strip {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}
.summary-note-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f5f7fa;
  color: #606266;
  font-size: 13px;
  line-height: 1.75;
}
.profile-option-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
  min-height: 46px;
  margin-bottom: 10px;
}
.compare-top-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.compare-exp-card,
.compare-card {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  background: #fff;
}
.compare-exp-card {
  padding: 14px;
}
.compare-exp-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 8px;
}
.compare-exp-meta {
  color: #606266;
  line-height: 1.7;
  margin-bottom: 4px;
}
.compare-tag-wrap {
  margin-top: 10px;
}
.compare-figure-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 1100px) {
  .summary-layout {
    grid-template-columns: 1fr;
  }
  .summary-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 900px) {
  .profile-card-grid,
  .compare-top-grid,
  .compare-figure-grid,
  .summary-card-grid {
    grid-template-columns: 1fr;
  }
  .compare-card-header,
  .summary-verdict-head {
    align-items: flex-start;
    flex-direction: column;
  }
}

</style>
