<template>
  <div class="workbench-page">
    <el-card class="top-card" shadow="never">
      <div class="top-bar">
        <div class="top-left">
          <div class="page-title">代码自修复工作台</div>
          <div class="page-subtitle">
            面向“生成 - 执行 - 反馈 - 修复”的闭环调试页面
          </div>
        </div>

        <div class="top-right">
          <el-tag :type="statusTagType(effectiveTaskStatus)" size="large">
            {{ statusLabel(effectiveTaskStatus) }}
          </el-tag>
          <el-button @click="refreshAll" :disabled="!taskInfo?.id">刷新当前任务</el-button>
          <el-button
            type="danger"
            plain
            :loading="isCurrentTaskStopping"
            :disabled="!canStopCurrentTask"
            @click="handleStopTask"
          >
            中止任务
          </el-button>
          <el-button @click="exitCurrentTask" :disabled="!taskInfo?.id">退出当前任务</el-button>
          <el-button type="primary" plain @click="exportTaskReport" :disabled="!taskInfo?.id">导出任务报告</el-button>
        </div>
      </div>

      <div class="summary-row" v-if="taskInfo">
        <div class="summary-item">
          <span class="summary-label">任务ID</span>
          <span class="summary-value">{{ taskInfo.id }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">标题</span>
          <span class="summary-value">{{ taskInfo.title || '-' }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">当前轮次</span>
          <span class="summary-value">{{ taskInfo.cur_round ?? 0 }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">最佳版本</span>
          <span class="summary-value">{{ taskInfo.best_ver_id ?? '-' }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">最佳分数</span>
          <span class="summary-value">{{ taskInfo.best_score ?? 0 }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Trace 开关</span>
          <span class="summary-value">{{ boolText(taskInfo?.is_trace_on) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Lesson 开关</span>
          <span class="summary-value">{{ boolText(taskInfo?.is_lesson_on) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">版本数量</span>
          <span class="summary-value">{{ summaryInfo?.ver_cnt ?? versions.length }}</span>
        </div>
      </div>

      <div class="flag-feedback" v-if="taskInfo || autoMeta">
        <div class="flag-chip">
          <span class="chip-label">当前 stop_on_pass</span>
          <span class="chip-value">{{ boolText(autoMeta?.stop_on_pass ?? form.stopOnPass) }}</span>
        </div>
        <div class="flag-chip">
          <span class="chip-label">停止原因</span>
          <span class="chip-value">{{ stopReasonLabel(autoMeta?.stopped_reason) }}</span>
        </div>
        <div class="flag-chip">
          <span class="chip-label">最近动作</span>
          <span class="chip-value">{{ autoActionLabel(autoMeta?.last_action) }}</span>
        </div>
        <div class="flag-chip wide" v-if="autoMeta?.last_action_reason">
          <span class="chip-label">动作说明</span>
          <span class="chip-value">{{ autoMeta.last_action_reason }}</span>
        </div>
        <div class="flag-chip" v-if="autoMeta?.rollback_ver_id">
          <span class="chip-label">回退版本</span>
          <span class="chip-value">#{{ autoMeta.rollback_ver_id }}</span>
        </div>
      </div>

      <div v-if="rollbackRunMeta.pending" class="rollback-run-banner pending">
        <div class="rollback-run-main">
          <div class="rollback-run-title">回退已完成，等待基于新 rollback 版本重新运行</div>
          <div class="rollback-run-desc">
            当前最新代码已经切到 rollback 版本
            <strong>V{{ rollbackRunMeta.rollbackVerNo || '-' }}</strong>
            / #{{ rollbackRunMeta.rollbackVerId || '-' }}，右侧反馈仍可能停留在回退前的旧运行结果。
          </div>
        </div>
        <el-button
          type="primary"
          :loading="loading.rerunRollback"
          :disabled="!taskInfo?.id || !rollbackRunMeta.rollbackVerId"
          @click="handleRunRollbackVersion"
        >
          一键重新运行测试
        </el-button>
      </div>

      <div v-else-if="rollbackRunMeta.lastRunId" class="rollback-run-banner success">
        <div class="rollback-run-main">
          <div class="rollback-run-title">rollback 版本已完成复测</div>
          <div class="rollback-run-desc">
            最近一次基于 rollback 版本的运行：#{{ rollbackRunMeta.lastRunId }}，结果：
            <strong>{{ rollbackRunMeta.lastRunResult || '-' }}</strong>
          </div>
        </div>
        <el-button
          text
          :loading="loading.rerunRollback"
          :disabled="!taskInfo?.id"
          @click="handleRunRollbackVersion"
        >
          再次运行当前 rollback 版本
        </el-button>
      </div>
    </el-card>

    <div class="main-grid">
      <!-- 左栏 -->
      <div class="left-panel">
        <el-card class="panel-card input-panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>任务输入区</span>
              <el-button text @click="resetForm">重置</el-button>
            </div>
          </template>

          <el-form label-position="top" :model="form">
            <div class="field-head">
              <span>当前会话：{{ currentSessTitle }}</span>
            </div>
            <el-form-item label="">
              <div class="sess-row">
                <el-select
                  v-model="form.sessId"
                  placeholder="请选择会话"
                  style="flex: 1"
                  :disabled="sessLoading"
                  filterable
                >
                  <el-option
                    v-for="item in sessList"
                    :key="item.id"
                    :label="item.title || `会话 ${item.id}`"
                    :value="item.id"
                  />
                </el-select>
                <el-button @click="handleCreateSess" :loading="sessCreating">新建会话</el-button>
                <el-button plain @click="handleRenameSess" :disabled="!form.sessId || sessCreating || sessLoading">修改名称</el-button>
              </div>
            </el-form-item>

            <el-form-item label="任务标题">
              <el-input v-model="form.title" placeholder="例如：加法函数失败测试" clearable />
            </el-form-item>

            <el-form-item label="数据集">
              <el-select v-model="form.dataset" style="width: 100%">
                <el-option
                  v-for="item in datasetOptions"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>

            <div class="inline-grid">
              <el-form-item label="语言">
                <el-select v-model="form.lang" style="width: 100%">
                  <el-option label="python" value="python" />
                </el-select>
              </el-form-item>

              <el-form-item label="场景">
                <el-select v-model="form.scene" style="width: 100%">
                  <el-option label="func" value="func" />
                  <el-option label="class" value="class" />
                  <el-option label="file" value="file" />
                </el-select>
              </el-form-item>
            </div>

            <div class="inline-grid">
              <el-form-item label="最大轮次">
                <el-input-number
                  v-model="form.maxRound"
                  :min="1"
                  :max="10"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>

              <div class="switch-group switch-group-3">
                <el-form-item label="开启 Trace">
                  <el-switch v-model="form.isTraceOn" />
                </el-form-item>
                <el-form-item label="开启 Lesson">
                  <el-switch v-model="form.isLessonOn" />
                </el-form-item>
                <el-form-item label="通过即停止">
                  <el-switch v-model="form.stopOnPass" />
                </el-form-item>
              </div>
            </div>

            <el-form-item label="">
              <div class="full-field">
                <div class="field-head">
                  <span>题目描述</span>
                  <el-button size="small" @click="applyProblemTemplate">模板添加</el-button>
                </div>
                <el-input
                  v-model="form.problemText"
                  type="textarea"
                  :rows="8"
                  placeholder="请输入自然语言问题描述，例如：请实现 solve(a, b)，返回两个整数之和。"
                />
              </div>
            </el-form-item>

            <el-form-item label="">
              <div class="full-field">
                <div class="field-head field-head-between">
                  <span>测试用例（空行分隔测试块；不含 assert 的块会作为共享准备块）</span>
                  <div class="field-head-actions">
                    <el-checkbox v-model="form.autoGenCases">AI 生成测试块</el-checkbox>
                    <el-select v-model="form.caseCfg.preset" style="width: 120px" :disabled="!form.autoGenCases">
                      <el-option label="标准覆盖" value="standard" />
                      <el-option label="高覆盖" value="high" />
                      <el-option label="极限压力" value="ultra" />
                    </el-select>
                    <el-select v-model="form.caseCfg.focus" style="width: 120px" :disabled="!form.autoGenCases">
                      <el-option label="均衡覆盖" value="balanced" />
                      <el-option label="边界优先" value="boundary" />
                      <el-option label="异常优先" value="exception" />
                      <el-option label="状态联动" value="stateful" />
                    </el-select>
                    <el-input-number v-model="form.caseCfg.count" :min="4" :max="30" controls-position="right" style="width: 120px" :disabled="!form.autoGenCases" />
                  </div>
                </div>
                <el-input
                  v-model="form.caseCfg.hint"
                  class="case-hint-input"
                  clearable
                  :disabled="!form.autoGenCases"
                  placeholder="可选：补充对测试块的要求，例如更多异常输入、更多跨 API 联动。"
                />
                <el-input
                  v-model="form.casesText"
                  type="textarea"
                  :rows="8"
                  placeholder="示例（空行分隔）：&#10;def assert_raises(exc_type, fn, *args, **kwargs):&#10;    ...&#10;&#10;rt = RouterTable()&#10;rt.add('/', 'root')&#10;assert rt.resolve('/').handler == 'root'"
                />
                <el-alert
                  v-if="legacyCaseWarning"
                  class="legacy-case-alert"
                  type="error"
                  :closable="false"
                  show-icon
                  :title="legacyCaseWarning"
                />
                <el-alert
                  v-else-if="isEndedTask"
                  class="legacy-case-alert"
                  type="info"
                  :closable="false"
                  show-icon
                  title="当前任务已结束，但仍可继续点击“运行测试”或“自动修复”进行重新验证与续修；任务状态会按最新结果刷新。"
                />
              </div>
            </el-form-item>

            <div class="action-grid">
              <div class="action-cell">
                <el-button
                  type="primary"
                  :loading="loading.createTask"
                  @click="onCreateTask"
                  :disabled="!canCreateTask"
                >
                  创建任务
                </el-button>
              </div>

              <div class="action-cell">
                <el-button
                  type="success"
                  :loading="isCurrentTaskGenerating"
                  @click="onGenCode"
                  :disabled="!taskInfo?.id"
                >
                  {{ genActionText }}
                </el-button>
              </div>

              <div class="action-cell">
                <el-button
                  type="warning"
                  :loading="isCurrentTaskTesting"
                  @click="onRunTask"
                  :disabled="!canRunCurrentTask"
                >
                  {{ runButtonText }}
                </el-button>
              </div>

              <div class="action-cell">
                <el-button
                  type="danger"
                  :loading="isCurrentTaskFixing"
                  @click="onAutoFix"
                  :disabled="!canAutoFixCurrentTask"
                >
                  {{ autoActionText }}
                </el-button>
              </div>

              <div class="action-cell action-grid-spacer" aria-hidden="true"></div>

              <div class="action-cell action-save-cell">
                <el-button
                  class="action-save-btn"
                  type="info"
                  plain
                  :loading="loading.saveTask"
                  @click="onSaveTaskEdits"
                  :disabled="!canSaveTaskEdits"
                >
                  保存修改
                </el-button>
              </div>
            </div>

            <div class="local-flag-tip">
              当前提交值：Trace {{ boolText(form.isTraceOn) }} / Lesson {{ boolText(form.isLessonOn) }} / stop_on_pass {{ boolText(form.stopOnPass) }}
            </div>
            <div class="draft-tip" v-if="taskInfo?.id">
              <template v-if="hasPendingTaskEdits">
                当前表单存在未保存修改。点击“保存修改”才会覆盖当前任务；直接点击“创建任务”会按当前表单新建一个任务，不会自动覆盖原任务。
              </template>
              <template v-else>
                当前表单与已保存任务一致。
              </template>
            </div>
          </el-form>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>任务测试用例</span>
              <span class="small-tip">后端已接 /task/{id}/case</span>
            </div>
          </template>

          <div class="fixed-scroll-body fixed-body-case">
            <el-table v-if="taskCases.length" :data="taskCases" size="small" border style="width: 100%" height="300">
            <el-table-column prop="sort_no" label="序号" width="70" />
            <el-table-column label="类型" width="96">
              <template #default="{ row }">
                <el-tag size="small" :type="row.src_type === 'setup' ? 'warning' : 'success'">{{ caseTypeLabel(row.src_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="测试块" min-width="260">
              <template #default="{ row }">
                <el-popover placement="top-start" trigger="hover" width="480">
                  <pre class="case-pop-text">{{ row.assert_text }}</pre>
                  <template #reference>
                    <div class="case-cell">{{ toCasePreview(row.assert_text) }}</div>
                  </template>
                </el-popover>
              </template>
            </el-table-column>
            <el-table-column prop="weight" label="权重" width="80" />
          </el-table>
            <el-empty v-else description="暂无测试用例" :image-size="80" />
          </div>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>历史任务</span>
              <el-button text @click="loadTaskList">刷新</el-button>
            </div>
          </template>

          <el-scrollbar max-height="360px">
            <div v-if="taskList.length" class="history-list">
              <div
                v-for="item in taskList"
                :key="item.id"
                class="history-item"
                :class="{ active: activeTaskId === item.id }"
                @click="selectHistoryTask(item)"
              >
                <div class="history-main">
                  <div class="history-title">{{ item.title || `任务 ${item.id}` }}</div>
                  <div class="history-meta">
                    <el-tag size="small" :type="statusTagType(uiTaskStatus(item.id, item.status))">
                      {{ statusLabel(uiTaskStatus(item.id, item.status)) }}
                    </el-tag>
                    <span>轮次：{{ item.cur_round ?? 0 }}</span>
                  </div>
                </div>
                <div class="history-id">#{{ item.id }}</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史任务" :image-size="80" />
          </el-scrollbar>
        </el-card>
      </div>

      <!-- 中栏 -->
      <div class="middle-panel">
        <el-card class="panel-card fill-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>代码演进区</span>
              <div class="header-tools">
                <el-select
                  v-model="currentVerId"
                  placeholder="当前版本"
                  style="width: 150px"
                  @change="handleSelectCurrentVersion"
                  :disabled="!versions.length"
                >
                  <el-option
                    v-for="item in versions"
                    :key="item.id"
                    :label="`V${item.ver_no} (${item.ver_type})`"
                    :value="item.id"
                  />
                </el-select>

                <el-select
                  v-model="compareVerId"
                  placeholder="对比版本"
                  style="width: 150px"
                  @change="loadDiffIfNeed"
                  :disabled="versions.length < 2"
                >
                  <el-option
                    v-for="item in versions"
                    :key="item.id"
                    :label="`V${item.ver_no} (${item.ver_type})`"
                    :value="item.id"
                  />
                </el-select>

                <el-button text @click="copyCurrentCode" :disabled="!curCode">
                  复制当前代码
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="codeFocusMeta.title" class="code-focus-tip">
            <div class="code-focus-main">
              <div class="code-focus-title">{{ codeFocusMeta.title }}</div>
              <div class="code-focus-desc">{{ codeFocusMeta.desc }}</div>
            </div>
            <div class="code-focus-actions">
              <el-button size="small" text @click="codeTab = 'current'">查看当前代码</el-button>
              <el-button
                size="small"
                text
                :disabled="!diffText"
                @click="codeTab = 'diff'"
              >
                查看 Diff
              </el-button>
            </div>
          </div>

          <div v-if="codeTab === 'diff' && diffCompareMeta.show" class="diff-compare-tip">
            <div class="diff-compare-head">
              <div class="diff-compare-title">{{ diffCompareMeta.title }}</div>
              <div class="diff-compare-desc">{{ diffCompareMeta.desc }}</div>
            </div>
            <div class="diff-compare-grid">
              <div class="diff-compare-card from">
                <div class="diff-card-label">对比基线版本</div>
                <div class="diff-card-main">
                  <span class="diff-card-ver">{{ diffCompareMeta.from.short }}</span>
                  <el-tag size="small" effect="plain">{{ diffCompareMeta.from.type }}</el-tag>
                </div>
                <div class="diff-card-note">{{ diffCompareMeta.from.note }}</div>
              </div>
              <div class="diff-compare-arrow">→</div>
              <div class="diff-compare-card to">
                <div class="diff-card-label">当前目标版本</div>
                <div class="diff-card-main">
                  <span class="diff-card-ver">{{ diffCompareMeta.to.short }}</span>
                  <el-tag size="small" effect="plain" type="success">{{ diffCompareMeta.to.type }}</el-tag>
                </div>
                <div class="diff-card-note">{{ diffCompareMeta.to.note }}</div>
              </div>
            </div>
          </div>

          <el-tabs v-model="codeTab" class="code-tabs">
            <el-tab-pane label="原始代码" name="init">
              <div class="code-panel">
                <pre class="code-block"><template v-if="initCode"><span v-for="(line, idx) in initCodeLines" :key="`init-${idx}`" class="code-line">{{ line }}
</span></template><template v-else>{{ emptyCodeText }}</template></pre>
              </div>
            </el-tab-pane>

            <el-tab-pane label="当前代码" name="current">
              <div class="code-panel">
                <pre class="code-block"><template v-if="curCode"><span v-for="(row, idx) in currentCodeRows" :key="`cur-${idx}`" class="code-line" :class="{ 'code-line-added': row.changed }">{{ row.text }}
</span></template><template v-else>{{ emptyCodeText }}</template></pre>
              </div>
            </el-tab-pane>

            <el-tab-pane label="最佳代码" name="best">
              <div class="code-panel">
                <pre class="code-block"><template v-if="bestCode"><span v-for="(row, idx) in bestCodeRows" :key="`best-${idx}`" class="code-line" :class="{ 'code-line-added': row.changed }">{{ row.text }}
</span></template><template v-else>{{ emptyCodeText }}</template></pre>
              </div>
            </el-tab-pane>

            <el-tab-pane label="Diff 对比" name="diff">
              <div class="code-panel">
                <pre class="code-block diff-block"><template v-if="diffText"><span v-for="(row, idx) in diffRows" :key="`diff-${idx}`" class="code-line" :class="row.cls">{{ row.text }}
</span></template><template v-else>{{ emptyDiffText }}</template></pre>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>版本时间线</span>
              <span class="small-tip">点击版本切换当前代码，可对历史版本执行手动回退</span>
            </div>
          </template>

          <el-scrollbar max-height="260px">
            <el-timeline v-if="versions.length">
              <el-timeline-item
                v-for="item in versions"
                :key="item.id"
                :timestamp="`版本号 V${item.ver_no}`"
                placement="top"
                :type="timelineType(item.ver_type)"
              >
                <div class="timeline-box" :class="{ active: selectedTimelineVerId === item.id }" :data-ver-id="item.id" @click="switchToVersion(item)">
                  <div class="timeline-title">
                    <span>{{ item.note || '版本备注为空' }}</span>
                    <div class="timeline-tags">
                      <el-tag size="small" effect="plain">{{ item.ver_type }}</el-tag>
                      <el-tag
                        v-if="latestVerId === item.id"
                        size="small"
                        type="info"
                        effect="plain"
                      >
                        当前最新
                      </el-tag>
                    </div>
                  </div>
                  <div class="timeline-desc timeline-desc-column">
                    <div>
                      版本ID：{{ item.id }}
                      <span v-if="taskInfo?.best_ver_id === item.id" class="best-mark">（当前最佳）</span>
                    </div>

                    <div
                      v-if="isAutoActionVersion(item)"
                      class="auto-action-timeline-mark"
                      :class="`action-${autoActionMeta.action || 'plain'}`"
                    >
                      <div class="auto-action-timeline-title">
                        {{ autoActionTimelineTitle(item) }}
                      </div>
                      <div class="auto-action-timeline-desc">
                        {{ autoActionTimelineDesc(item) }}
                      </div>
                    </div>

                    <div
                      v-if="isRollbackVersion(item)"
                      class="rollback-timeline-mark"
                      :class="{
                        pending: rollbackRetestState(item) === 'pending',
                        success: rollbackRetestState(item) === 'done'
                      }"
                    >
                      <div class="rollback-timeline-title">
                        {{ rollbackRetestTitle(item) }}
                      </div>
                      <div class="rollback-timeline-desc">
                        {{ rollbackRetestDesc(item) }}
                      </div>
                    </div>

                    <div class="timeline-actions">
                      <el-button size="small" text @click.stop="switchToVersion(item)">
                        查看代码
                      </el-button>
                      <el-button
                        size="small"
                        type="danger"
                        plain
                        @click.stop="handleManualRollback(item)"
                        :disabled="loading.rollback || latestVerId === item.id"
                      >
                        回退为最新基线
                      </el-button>
                    </div>
                  </div>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无版本记录" :image-size="80" />
          </el-scrollbar>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>修复计划与历史 Lesson</span>
              <span class="small-tip">对应 /task/{id}/plan 与 /task/{id}/lesson</span>
            </div>
          </template>

          <el-tabs v-model="detailTab" class="detail-tabs">
            <el-tab-pane label="修复计划" name="plan">
              <el-table
                v-if="planList.length"
                :data="planList"
                size="small"
                border
                style="width: 100%"
                height="300"
                @row-click="openPlanDrawer"
              >
                <el-table-column prop="round_no" label="轮次" width="70" />
                <el-table-column prop="root_cause" label="根因分析" min-width="180" show-overflow-tooltip />
                <el-table-column prop="fix_plan" label="修复策略" min-width="200" show-overflow-tooltip />
                <el-table-column prop="inst_sugg" label="插桩建议" min-width="160" show-overflow-tooltip />
                <el-table-column label="操作" width="90">
                  <template #default="{ row }">
                    <el-button type="primary" link @click.stop="openPlanDrawer(row)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="暂无修复计划" :image-size="80" />
            </el-tab-pane>

            <el-tab-pane label="Lesson 记录" name="lesson">
              <el-table
                v-if="lessonList.length"
                :data="lessonList"
                size="small"
                border
                style="width: 100%"
                height="300"
                @row-click="openLessonDrawer"
              >
                <el-table-column prop="round_no" label="轮次" width="70" />
                <el-table-column prop="bad_pattern" label="错误模式" min-width="160" show-overflow-tooltip />
                <el-table-column prop="lesson_text" label="经验摘要" min-width="260" show-overflow-tooltip />
                <el-table-column label="操作" width="90">
                  <template #default="{ row }">
                    <el-button type="primary" link @click.stop="openLessonDrawer(row)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="暂无 Lesson 记录" :image-size="80" />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </div>

      <!-- 右栏 -->
      <div class="right-panel">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>执行反馈区</span>
              <el-button text @click="refreshRunPanel" :disabled="!currentRunId">刷新反馈</el-button>
            </div>
          </template>

          <div class="fixed-scroll-body fixed-body-feedback">
            <div v-if="feedback" class="feedback-box">
            <div v-if="rollbackRunMeta.pending" class="feedback-stale-tip">
              当前代码已经回退到 rollback 版本 V{{ rollbackRunMeta.rollbackVerNo || '-' }}，但这里展示的反馈仍可能来自回退前的旧运行。
              点击上方“ 一键重新运行测试 ”后，会自动刷新新的运行反馈、失败样例和轨迹。
            </div>

            <div class="feedback-line">
              <span class="feedback-label">运行ID</span>
              <span class="feedback-value">{{ feedback.run_id }}</span>
            </div>
            <div class="feedback-line">
              <span class="feedback-label">运行结果</span>
              <el-tag :type="feedback.result === 'pass' ? 'success' : 'danger'">
                {{ feedback.result || '-' }}
              </el-tag>
            </div>
            <div class="feedback-line">
              <span class="feedback-label">错误类型</span>
              <span class="feedback-value">{{ feedback.err_type || '暂无' }}</span>
            </div>
            <div class="feedback-line">
              <span class="feedback-label">报错行号</span>
              <span class="feedback-value">{{ feedback.line_no ?? '暂无' }}</span>
            </div>
            <div class="feedback-line">
              <span class="feedback-label">通过用例</span>
              <span class="feedback-value">{{ feedback.pass_cnt ?? 0 }} / {{ feedback.total_cnt ?? 0 }}</span>
            </div>
            <div class="feedback-line">
              <span class="feedback-label">耗时</span>
              <span class="feedback-value">{{ feedback.time_ms ?? 0 }} ms</span>
            </div>

            <div class="feedback-block">
              <div class="feedback-block-title">错误提示</div>
              <div class="feedback-block-body">{{ feedback.err_msg || '暂无错误提示' }}</div>
            </div>

            <div class="feedback-block">
              <div class="feedback-block-title">轨迹摘要</div>
              <div class="feedback-block-body">{{ feedback.trace_sum || '暂无轨迹摘要' }}</div>
            </div>

            <div class="feedback-block" v-if="autoMeta">
              <div class="feedback-block-title">自动修复开关反馈</div>
              <div class="feedback-block-body compact-lines">
                <div>trace_on：{{ boolText(autoMeta.trace_on) }}</div>
                <div>lesson_on：{{ boolText(autoMeta.lesson_on) }}</div>
                <div>stop_on_pass：{{ boolText(autoMeta.stop_on_pass) }}</div>
                <div>stopped_reason：{{ stopReasonLabel(autoMeta.stopped_reason) }}</div>
                <div>last_action：{{ autoActionLabel(autoMeta.last_action) }}</div>
                <div v-if="autoMeta.last_action_reason">action_reason：{{ autoMeta.last_action_reason }}</div>
                <div v-if="autoMeta.rollback_ver_id">rollback_ver_id：{{ autoMeta.rollback_ver_id }}</div>
              </div>
            </div>
          </div>

            <el-empty v-else description="暂无执行反馈" :image-size="80" />
          </div>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>失败样例 / 单用例结果</span>
              <span class="small-tip">对应 /run/{id}/cases</span>
            </div>
          </template>

          <div class="fixed-scroll-body fixed-body-case-result">
            <el-table
              v-if="runCaseView.length"
              :data="runCaseView"
              size="small"
              border
              style="width: 100%"
              height="300"
            >
            <el-table-column prop="sort_no" label="序号" width="66" />
            <el-table-column prop="case_id" label="用例ID" width="86" />
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag :type="row.result === 'pass' ? 'success' : 'danger'" size="small">
                  {{ row.result }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="96">
              <template #default="{ row }">
                <el-tag size="small" :type="row.case_src_type === 'setup' ? 'warning' : 'success'">{{ row.case_type_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="测试块" min-width="220">
              <template #default="{ row }">
                <el-popover placement="top-start" trigger="hover" width="480">
                  <pre class="case-pop-text">{{ row.assert_text }}</pre>
                  <template #reference>
                    <div class="case-cell">{{ row.case_preview }}</div>
                  </template>
                </el-popover>
              </template>
            </el-table-column>
            <el-table-column label="实际输出" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.actual_out_text }}
              </template>
            </el-table-column>
            <el-table-column prop="err_msg" label="错误信息" min-width="180" show-overflow-tooltip />
            <el-table-column prop="time_ms" label="耗时(ms)" width="90" />
          </el-table>
            <el-empty v-else description="暂无单用例结果" :image-size="80" />
          </div>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>自动修复动作统计</span>
              <span class="small-tip">仅统计自动修复轮次，不含手动 rollback 复测</span>
            </div>
          </template>

          <div class="action-stat-body">
            <div v-if="actionStats.total" class="action-stat-box">
            <div class="action-stat-head">
              <div class="action-stat-kpi accept">
                <span class="kpi-label">accept</span>
                <span class="kpi-value">{{ actionStats.accept }}</span>
              </div>
              <div class="action-stat-kpi continue">
                <span class="kpi-label">continue</span>
                <span class="kpi-value">{{ actionStats.continue }}</span>
              </div>
              <div class="action-stat-kpi rollback">
                <span class="kpi-label">rollback</span>
                <span class="kpi-value">{{ actionStats.rollback }}</span>
              </div>
            </div>

            <div class="action-combo-box" v-if="actionComboChart.show">
              <div class="action-combo-head">
                <div class="action-combo-title">动作统计 + 通过用例变化</div>
                <div class="action-combo-legend">
                  <span class="legend-item click-tip">点击某轮可同步定位运行记录与版本时间线</span>
                  <span class="legend-item"><i class="legend-dot pass"></i>柱：本轮通过用例数</span>
                  <span class="legend-item"><i class="legend-dot best"></i>线：历史最佳通过数</span>
                </div>
              </div>

              <div class="action-combo-chart-wrap">
                <svg
                  class="action-combo-chart"
                  :viewBox="`0 0 ${actionComboChart.width} ${actionComboChart.height}`"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label="自动修复动作统计与通过用例变化图"
                >
                  <line
                    v-for="tick in actionComboChart.yTicks"
                    :key="`y-${tick.value}`"
                    :x1="actionComboChart.padLeft"
                    :x2="actionComboChart.width - actionComboChart.padRight"
                    :y1="tick.y"
                    :y2="tick.y"
                    class="combo-grid-line"
                  />

                  <text
                    v-for="tick in actionComboChart.yTicks"
                    :key="`yt-${tick.value}`"
                    :x="actionComboChart.padLeft - 10"
                    :y="tick.y + 4"
                    text-anchor="end"
                    class="combo-axis-text"
                  >
                    {{ tick.value }}
                  </text>

                  <g
                    v-for="item in actionComboChart.items"
                    :key="`bar-${item.runId}`"
                    class="combo-item-group"
                    :class="{ selected: selectedActionRunId === item.runId }"
                    @click="handleSelectActionRound(item)"
                  >
                    <title>{{ comboItemTitle(item) }}</title>
                    <rect
                      :x="item.hitX"
                      :y="actionComboChart.padTop"
                      :width="item.hitWidth"
                      :height="actionComboChart.height - actionComboChart.padTop - actionComboChart.padBottom + 42"
                      rx="10"
                      class="combo-hit-area"
                    />
                    <rect
                      :x="item.barX"
                      :y="item.barY"
                      :width="item.barWidth"
                      :height="item.barHeight"
                      :rx="6"
                      :class="`combo-bar combo-${item.action}`"
                    />
                    <text
                      :x="item.centerX"
                      :y="item.barY - 8"
                      text-anchor="middle"
                      class="combo-bar-text"
                    >
                      {{ item.passCnt }}/{{ item.totalCnt }}
                    </text>
                    <text
                      :x="item.centerX"
                      :y="actionComboChart.height - actionComboChart.padBottom + 18"
                      text-anchor="middle"
                      class="combo-axis-text"
                    >
                      R{{ item.roundNo }}
                    </text>
                    <text
                      :x="item.centerX"
                      :y="actionComboChart.height - actionComboChart.padBottom + 34"
                      text-anchor="middle"
                      :class="`combo-action-text action-${item.action}`"
                    >
                      {{ item.action }}
                    </text>
                  </g>

                  <polyline
                    v-if="actionComboChart.linePoints"
                    :points="actionComboChart.linePoints"
                    class="combo-best-line"
                  />

                  <g
                    v-for="item in actionComboChart.items"
                    :key="`pt-${item.runId}`"
                    class="combo-point-group"
                    :class="{ selected: selectedActionRunId === item.runId }"
                  >
                    <circle
                      :cx="item.centerX"
                      :cy="item.bestY"
                      r="4.5"
                      class="combo-best-dot"
                    />
                    <text
                      :x="item.centerX"
                      :y="item.bestY - 10"
                      text-anchor="middle"
                      class="combo-best-text"
                    >
                      {{ item.bestCnt }}
                    </text>
                  </g>
                </svg>
              </div>
            </div>

            <div class="action-mini-chart">
              <div
                v-for="item in actionBarRows"
                :key="item.key"
                class="action-bar-row"
              >
                <div class="action-bar-label">{{ item.label }}</div>
                <div class="action-bar-track">
                  <div
                    class="action-bar-fill"
                    :class="`bar-${item.key}`"
                    :style="{ width: `${item.width}%` }"
                  />
                </div>
                <div class="action-bar-value">{{ item.count }}</div>
              </div>
            </div>

            <div class="action-round-list">
              <div
                v-for="item in actionStats.rounds"
                :key="`${item.roundNo}-${item.runId}`"
                class="action-round-chip"
                :class="`chip-${item.action}`"
              >
                <span>R{{ item.roundNo }} · {{ item.action }}</span>
                <span>#{{ item.runId }} · {{ item.passCnt }}/{{ item.totalCnt }}</span>
              </div>
            </div>
          </div>

            <el-empty v-else description="暂无自动修复动作统计" :image-size="80" />
          </div>
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>运行记录</span>
              <span class="small-tip">点击记录切换反馈展示</span>
            </div>
          </template>

          <div class="fixed-scroll-body fixed-body-run">
            <el-table
              v-if="runs.length"
              :data="runs"
              size="small"
              border
              style="width: 100%"
              height="280"
              :row-class-name="runRowClassName"
              @row-click="handleSelectRun"
            >
            <el-table-column prop="id" label="运行ID" width="88">
              <template #default="{ row }">
                <div class="run-id-cell">
                  <span>#{{ row.id }}</span>
                  <el-tag
                    v-if="isRollbackRetestRun(row)"
                    size="small"
                    :type="rollbackRunMeta.source === 'auto' ? 'danger' : 'warning'"
                    effect="dark"
                  >
                    {{ rollbackRunTagText(row) }}
                  </el-tag>
                  <el-tag
                    v-if="isAutoActionRun(row)"
                    size="small"
                    :type="autoActionTagType(autoActionMeta.action)"
                    effect="plain"
                  >
                    {{ autoActionTagText(autoActionMeta.action) }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="round_no" label="轮次" width="72" />
            <el-table-column label="结果" min-width="90">
              <template #default="{ row }">
                <el-tag :type="row.result === 'pass' ? 'success' : 'danger'" size="small">
                  {{ row.result || '-' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="特殊标记" min-width="116">
              <template #default="{ row }">
                <div class="run-mark-stack" v-if="isRollbackRetestRun(row) || isAutoActionRun(row)">
                  <el-tag
                    v-if="isRollbackRetestRun(row)"
                    size="small"
                    :type="row.result === 'pass' ? 'success' : 'warning'"
                    effect="plain"
                  >
                    {{ rollbackRunMarkText(row) }}
                  </el-tag>
                  <el-tag
                    v-if="isAutoActionRun(row)"
                    size="small"
                    :type="autoActionTagType(autoActionMeta.action)"
                    effect="plain"
                  >
                    {{ autoActionRunMarkText(row) }}
                  </el-tag>
                </div>
                <span v-else class="run-mark-empty">-</span>
              </template>
            </el-table-column>
          </el-table>

            <el-empty v-else description="暂无运行记录" :image-size="80" />
          </div>
        </el-card>

        <el-card class="panel-card fill-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>运行轨迹</span>
              <span class="small-tip">当前后端若未插桩，可能为空</span>
            </div>
          </template>

          <div class="fixed-scroll-body fixed-body-trace">
            <el-table
              v-if="traceList.length"
              :data="traceList"
              size="small"
              border
              height="300"
              style="width: 100%"
            >
            <el-table-column prop="seq_no" label="序号" width="70" />
            <el-table-column prop="node_type" label="类型" width="90" />
            <el-table-column prop="func_name" label="函数" width="120" />
            <el-table-column prop="line_no" label="行号" width="80" />
            <el-table-column prop="log_text" label="日志信息" min-width="220" show-overflow-tooltip />
          </el-table>

            <el-empty v-else description="暂无轨迹数据" :image-size="90" />
          </div>
        </el-card>
      </div>
    </div>

    <el-drawer v-model="planDrawer.visible" title="修复计划详情" size="520px">
      <template v-if="planDrawer.item">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="轮次">{{ planDrawer.item.round_no ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="运行ID">{{ planDrawer.item.run_id ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <div class="detail-head">
            <span>根因分析</span>
            <el-button text size="small" @click="copyPlanDetail('root_cause')">复制</el-button>
          </div>
          <pre class="detail-pre">{{ planDrawer.item.root_cause || '暂无内容' }}</pre>
        </div>

        <div class="detail-section">
          <div class="detail-head">
            <span>修复策略</span>
            <el-button text size="small" @click="copyPlanDetail('fix_plan')">复制</el-button>
          </div>
          <pre class="detail-pre">{{ planDrawer.item.fix_plan || '暂无内容' }}</pre>
        </div>

        <div class="detail-section">
          <div class="detail-head">
            <span>插桩建议</span>
            <el-button text size="small" @click="copyPlanDetail('inst_sugg')">复制</el-button>
          </div>
          <pre class="detail-pre">{{ planDrawer.item.inst_sugg || '暂无内容' }}</pre>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="lessonDrawer.visible" title="Lesson 详情" size="520px">
      <template v-if="lessonDrawer.item">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="轮次">{{ lessonDrawer.item.round_no ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源运行ID">{{ lessonDrawer.item.from_run_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源计划ID">{{ lessonDrawer.item.from_plan_id ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <div class="detail-head">
            <span>错误模式</span>
            <el-button text size="small" @click="copyLessonDetail('bad_pattern')">复制</el-button>
          </div>
          <pre class="detail-pre">{{ lessonDrawer.item.bad_pattern || '暂无内容' }}</pre>
        </div>

        <div class="detail-section">
          <div class="detail-head">
            <span>经验摘要</span>
            <el-button text size="small" @click="copyLessonDetail('lesson_text')">复制</el-button>
          </div>
          <pre class="detail-pre">{{ lessonDrawer.item.lesson_text || '暂无内容' }}</pre>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
// 工作台页面，负责发起生成、运行、修复和结果查看。
defineOptions({ name: 'WorkBench' })
import { computed, nextTick, onActivated, onMounted, onDeactivated, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskUiStore } from '@/store'
import { copyText } from '@/utils/copy'
import { listSess, createSess, updateSess } from '@/api/chat'
import {
  createTask,
  updateTask,
  getTaskDetail,
  genTask,
  runTask,
  autoFixTask,
  getTaskStatus,
  stopTask,
  getTaskSummary,
  listTaskVers,
  listTask,
  getTaskCases,
  updateTaskCases,
  getTaskPlans,
  getTaskLessons,
  genTaskCases
} from '@/api/task'
import {
  listTaskRuns,
  getRunFb,
  getRunTrace,
  getRunCases,
  getRunDetail
} from '@/api/run'
import { getVerCode, getVerDiff, rollbackVersion } from '@/api/ver'
import { listDataset } from '@/api/data'

const route = useRoute()
const router = useRouter()
const taskUiStore = useTaskUiStore()

function getLocalBool(key, def = true) {
  const val = localStorage.getItem(key)
  if (val === null) return def
  return val !== '0' && val !== 'false'
}

const defaultForm = () => ({
  sessId: null,
  title: '',
  problemText: '',
  dataset: 'custom',
  lang: 'python',
  scene: 'func',
  maxRound: Number(localStorage.getItem('cfix_max_round') || 3),
  isTraceOn: getLocalBool('cfix_trace_on', true),
  isLessonOn: getLocalBool('cfix_lesson_on', true),
  stopOnPass: getLocalBool('cfix_stop_on_pass', true),
  casesText: '',
  autoGenCases: false,
  caseCfg: {
    preset: 'high',
    focus: 'balanced',
    count: 8,
    hint: ''
  }
})

const form = reactive(defaultForm())

const datasetOptions = ref(['custom', 'mbpp', 'humaneval', 'class_bank', 'class_eval', 'file_bank', 'file_ultra'])
const sessList = ref([])
const taskList = ref([])

const taskInfo = ref(null)
const summaryInfo = ref(null)
const versions = ref([])
const runs = ref([])
const autoMeta = ref(null)
const autoActionMeta = ref({
  action: null,
  reason: '',
  verId: null,
  verNo: null,
  runId: null,
  runResult: null
})
const actionStats = ref({
  accept: 0,
  continue: 0,
  rollback: 0,
  total: 0,
  maxCount: 0,
  rounds: []
})
const rollbackRunMeta = ref({
  pending: false,
  source: null,
  rollbackVerId: null,
  rollbackVerNo: null,
  fromVerId: null,
  lastRunId: null,
  lastRunResult: null
})
const feedback = ref(null)
const traceList = ref([])
const selectedTimelineVerId = ref(null)
const selectedActionRunId = ref(null)
const taskCases = ref([])
const runCaseList = ref([])
const planList = ref([])
const lessonList = ref([])

const planDrawer = reactive({
  visible: false,
  item: null
})
const lessonDrawer = reactive({
  visible: false,
  item: null
})

const currentVerId = ref(null)
const compareVerId = ref(null)
const bestVerId = ref(null)
const currentRunId = ref(null)
const activeTaskId = ref(null)


const WORKBENCH_SNAPSHOT_KEY = 'cfix_workbench_snapshot_v2'

const initCode = ref('')
const curCode = ref('')
const bestCode = ref('')
const diffText = ref('')

const codeTab = ref('current')
const detailTab = ref('plan')
const codeFocusMeta = ref({
  source: null,
  title: '',
  desc: ''
})

const sessLoading = ref(false)
const sessCreating = ref(false)

const loading = reactive({
  page: false,
  createTask: false,
  gen: false,
  run: false,
  auto: false,
  stop: false,
  rollback: false,
  rerunRollback: false,
  genCases: false
})

const emptyCodeText = '暂无代码内容'
const emptyDiffText = '暂无 diff 内容'


const initCodeLines = computed(() => splitCodeLines(initCode.value))
const currentCodeRows = computed(() => markChangedLines(initCode.value, curCode.value))
const bestCodeRows = computed(() => markChangedLines(initCode.value, bestCode.value))
const diffRows = computed(() => splitDiffRows(diffText.value))

const currentSessTitle = computed(() => {
  const row = (sessList.value || []).find(item => Number(item.id) === Number(form.sessId))
  return row?.title || (form.sessId ? `会话 #${form.sessId}` : '未选择会话')
})

const canCreateTask = computed(() => {
  return Boolean(form.title?.trim() && form.problemText?.trim() && form.sessId)
})

function serializeTaskDraftValue() {
  return JSON.stringify({
    title: String(form.title || '').trim(),
    dataset: form.dataset || 'custom',
    lang: form.lang || 'python',
    scene: form.scene || 'func',
    problemText: String(form.problemText || '').trim(),
    maxRound: Number(form.maxRound || 3),
    isTraceOn: Boolean(form.isTraceOn),
    isLessonOn: Boolean(form.isLessonOn),
    casesText: String(form.casesText || '').replace(/\r\n/g, '\n').trim()
  })
}

const hasPendingTaskEdits = computed(() => {
  if (!taskInfo.value?.id) return false
  return savedTaskDraftRef.value !== serializeTaskDraftValue()
})

const canSaveTaskEdits = computed(() => Boolean(taskInfo.value?.id && hasPendingTaskEdits.value))

const latestVerId = computed(() => {
  if (!versions.value.length) return null
  return versions.value[versions.value.length - 1]?.id || null
})

const actionBarRows = computed(() => {
  const maxCount = Math.max(actionStats.value.maxCount || 0, 1)
  return [
    { key: 'accept', label: 'accept', count: actionStats.value.accept || 0, width: ((actionStats.value.accept || 0) / maxCount) * 100 },
    { key: 'continue', label: 'continue', count: actionStats.value.continue || 0, width: ((actionStats.value.continue || 0) / maxCount) * 100 },
    { key: 'rollback', label: 'rollback', count: actionStats.value.rollback || 0, width: ((actionStats.value.rollback || 0) / maxCount) * 100 }
  ]
})

const runCaseView = computed(() => {
  const caseMap = new Map((taskCases.value || []).map(item => [item.id, item]))
  return (runCaseList.value || []).map(item => {
    const meta = caseMap.get(item.case_id) || {}
    let actualOutText = '-'
    const actual = item.actual_out
    if (actual !== null && actual !== undefined && actual !== '') {
      if (typeof actual === 'string') actualOutText = actual
      else {
        try {
          actualOutText = JSON.stringify(actual)
        } catch {
          actualOutText = String(actual)
        }
      }
    }
    const rawText = meta.assert_text || '-'
    return {
      ...item,
      sort_no: meta.sort_no ?? '-',
      assert_text: rawText,
      case_preview: toCasePreview(rawText),
      case_src_type: meta.src_type || 'custom',
      case_type_label: caseTypeLabel(meta.src_type),
      actual_out_text: actualOutText
    }
  })
})


function syncFormFromTask(row) {
  if (!row) return
  if (row.sess_id !== undefined && row.sess_id !== null) {
    form.sessId = row.sess_id
  }
  form.title = row.title || ''
  form.dataset = row.dataset || 'custom'
  form.lang = row.lang || 'python'
  form.scene = row.scene || 'func'
  form.problemText = row.problem_text || ''
  form.maxRound = Number(row.max_round || 3)
  if (typeof row.is_trace_on === 'boolean') form.isTraceOn = row.is_trace_on
  if (typeof row.is_lesson_on === 'boolean') form.isLessonOn = row.is_lesson_on
}

function syncCasesTextFromTaskCases() {
  const rows = Array.isArray(taskCases.value) ? taskCases.value : []
  form.casesText = rows
    .slice()
    .sort((a, b) => (a.sort_no || 0) - (b.sort_no || 0))
    .map(item => (item.assert_text || '').trim())
    .filter(Boolean)
    .join('\n\n')
}

function hasAssertLine(text) {
  return (text || '').split('\n').some(line => {
    const s = line.trim()
    return s.startsWith('assert ') || s.startsWith('assert_raises(')
  })
}

function toCasePreview(text, maxLen = 120) {
  const one = String(text || '').replace(/\r\n/g, '\n').replace(/\n+/g, ' ↵ ').trim()
  if (one.length <= maxLen) return one || '-'
  return `${one.slice(0, maxLen)}...`
}

function caseTypeLabel(srcType) {
  if (srcType === 'setup') return '共享准备'
  if (String(srcType || '').includes('block')) return '测试块'
  return '单行'
}

const legacyCaseWarning = computed(() => {
  if (!taskInfo.value?.id) return ''
  if (!['file', 'class'].includes(String(taskInfo.value?.scene || form.scene || ''))) return ''
  const rows = Array.isArray(taskCases.value) ? taskCases.value : []
  if (!rows.length) return ''
  const srcs = new Set(rows.map(item => String(item.src_type || '').trim().toLowerCase()))
  const hasBlock = [...srcs].some(src => src === 'setup' || src.includes('block'))
  if (hasBlock) return ''
  return '当前任务仍是旧版逐行测试用例（legacy_line）。file/class 场景下这会把多行测试块拆坏，导致反馈被语法与上下文噪声污染。请复制题目与测试块后重新创建一个新任务再运行。'
})

const isEndedTask = computed(() => ['pass', 'fail', 'stop'].includes(String(taskInfo.value?.status || '')))
const canRunCurrentTask = computed(() => Boolean(taskInfo.value?.id && currentVerId.value) && !legacyCaseWarning.value)
const canAutoFixCurrentTask = computed(() => Boolean(taskInfo.value?.id && versions.value.length) && !legacyCaseWarning.value)
const runActionText = computed(() => (isEndedTask.value ? '重新运行测试' : '运行测试'))
const currentTaskId = computed(() => Number(taskInfo.value?.id || activeTaskId.value || 0) || null)
const currentTaskAction = computed(() => taskUiStore.taskActionById(currentTaskId.value))
const isCurrentTaskGenerating = computed(() => currentTaskAction.value === 'generating')
const isCurrentTaskTesting = computed(() => currentTaskAction.value === 'testing')
const isCurrentTaskFixing = computed(() => currentTaskAction.value === 'fixing')
const isCurrentTaskStopping = computed(() => currentTaskAction.value === 'stopping')
const effectiveTaskStatus = computed(() => uiTaskStatus(taskInfo.value?.id, taskInfo.value?.status))
const canStopCurrentTask = computed(() => {
  const status = String(effectiveTaskStatus.value || '')
  return Boolean(taskInfo.value?.id && ['running', 'testing', 'fixing', 'stopping'].includes(status))
})
const genActionText = computed(() => (isCurrentTaskGenerating.value ? '生成中' : '生成初始代码'))
const runButtonText = computed(() => (isCurrentTaskTesting.value ? '测试中' : runActionText.value))
const autoActionText = computed(() => (isCurrentTaskFixing.value ? '修复中' : '自动修复'))

function uiTaskStatus(taskId, baseStatus) {
  return taskUiStore.taskStatusById(taskId, baseStatus || 'draft')
}

function isViewingTask(taskId) {
  return Number(activeTaskId.value || taskInfo.value?.id || 0) === Number(taskId || 0)
}

function markTaskAction(taskId, action) {
  taskUiStore.setTaskAction(taskId, action)
}

function clearTaskAction(taskId, action = '') {
  taskUiStore.clearTaskAction(taskId, action)
}

function snapshotFormValue() {
  return {
    ...JSON.parse(JSON.stringify(form)),
    caseCfg: { ...JSON.parse(JSON.stringify(form.caseCfg || {})) }
  }
}

const snapshotSuspend = ref(true)
const savedTaskDraftRef = ref('')

function persistWorkbenchSnapshot() {
  if (snapshotSuspend.value) return
  const payload = {
    activeTaskId: activeTaskId.value,
    currentVerId: currentVerId.value,
    compareVerId: compareVerId.value,
    currentRunId: currentRunId.value,
    codeTab: codeTab.value,
    detailTab: detailTab.value,
    form: snapshotFormValue()
  }
  sessionStorage.setItem(WORKBENCH_SNAPSHOT_KEY, JSON.stringify(payload))
}

function clearWorkbenchSnapshot() {
  sessionStorage.removeItem(WORKBENCH_SNAPSHOT_KEY)
}

function refreshSavedTaskDraft() {
  savedTaskDraftRef.value = serializeTaskDraftValue()
}

async function saveTaskDraftToServer({ showSuccess = true } = {}) {
  if (!taskInfo.value?.id) {
    throw new Error('当前没有可保存的任务')
  }
  await updateTask(taskInfo.value.id, {
    sess_id: form.sessId,
    title: form.title,
    dataset: form.dataset,
    lang: form.lang,
    scene: form.scene,
    problem_text: form.problemText,
    max_round: form.maxRound,
    is_trace_on: form.isTraceOn,
    is_lesson_on: form.isLessonOn
  })
  await updateTaskCases(taskInfo.value.id, {
    cases: buildCases(form.casesText, form.scene)
  })
  await refreshTaskInfo()
  await refreshCasesPlansLessons()
  refreshSavedTaskDraft()
  if (showSuccess) {
    ElMessage.success('当前任务修改已保存')
  }
}

async function confirmSaveBeforeAction(actionLabel) {
  if (!taskInfo.value?.id || !hasPendingTaskEdits.value) return true
  try {
    await ElMessageBox.confirm(
      `检测到当前表单存在未保存修改。若继续${actionLabel}，系统会先把这些修改保存到当前任务。若你想保留原任务并基于当前草稿创建新任务，请取消后点击“创建任务”。`,
      '未保存修改',
      {
        type: 'warning',
        confirmButtonText: '保存后继续',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return false
  }
  loading.saveTask = true
  try {
    await saveTaskDraftToServer({ showSuccess: false })
    ElMessage.success(`已保存当前任务，并继续${actionLabel}`)
    return true
  } catch (error) {
    ElMessage.error(error?.message || '保存当前任务失败')
    return false
  } finally {
    loading.saveTask = false
  }
}


async function restoreWorkbenchSnapshot() {
  const raw = sessionStorage.getItem(WORKBENCH_SNAPSHOT_KEY)
  if (!raw) return false
  try {
    const snap = JSON.parse(raw)
    if (snap?.form) {
      const defaults = defaultForm()
      Object.assign(form, defaults, snap.form)
      form.caseCfg = { ...defaults.caseCfg, ...(snap.form.caseCfg || {}) }
    }
    const snapTaskId = Number(snap?.activeTaskId || 0)
    if (snapTaskId) {
      await loadTaskAll(snapTaskId)
      if (snap.currentVerId && versions.value.some(v => Number(v.id) === Number(snap.currentVerId))) {
        currentVerId.value = Number(snap.currentVerId)
        await loadCurrentCode(currentVerId.value)
      }
      if (snap.compareVerId && versions.value.some(v => Number(v.id) === Number(snap.compareVerId))) {
        compareVerId.value = Number(snap.compareVerId)
        await loadDiffIfNeed()
      }
      if (snap.currentRunId && runs.value.some(r => Number(r.id) === Number(snap.currentRunId))) {
        currentRunId.value = Number(snap.currentRunId)
        await loadRunPanel(currentRunId.value)
      } else if (currentVerId.value) {
        await syncRunPanelByVersion(currentVerId.value)
      }
      codeTab.value = snap.codeTab || codeTab.value
      detailTab.value = snap.detailTab || detailTab.value
      return true
    }
    return true
  } catch {
    clearWorkbenchSnapshot()
    return false
  }
}

async function syncRunPanelByVersion(verId) {
  if (!verId) {
    feedback.value = null
    traceList.value = []
    runCaseList.value = []
    currentRunId.value = null
    return
  }
  const relatedRuns = (runs.value || []).filter(item => Number(item.ver_id) === Number(verId))
  if (!relatedRuns.length) {
    feedback.value = null
    traceList.value = []
    runCaseList.value = []
    currentRunId.value = null
    return
  }
  const targetRun = relatedRuns[0]
  currentRunId.value = targetRun.id
  selectedActionRunId.value = targetRun.id
  await loadRunPanel(targetRun.id)
}

const diffCompareMeta = computed(() => {
  const from = getVersionById(compareVerId.value)
  const to = getVersionById(currentVerId.value)

  if (!from || !to || from.id === to.id) {
    return { show: false }
  }

  const explain = codeFocusMeta.value?.source && codeTab.value === 'diff'
    ? codeFocusMeta.value.desc
    : '当前 Diff 视图正在对比“对比基线版本”和“当前目标版本”，用来说明这一轮代码相对基线具体改了什么。'

  return {
    show: true,
    title: `当前 Diff 对比：V${from.ver_no ?? '?'} → V${to.ver_no ?? '?'}`,
    desc: explain,
    from: {
      id: from.id,
      verNo: from.ver_no,
      type: from.ver_type || 'unknown',
      short: versionShortText(from),
      note: versionNoteText(from)
    },
    to: {
      id: to.id,
      verNo: to.ver_no,
      type: to.ver_type || 'unknown',
      short: versionShortText(to),
      note: versionNoteText(to)
    }
  }
})

const actionComboChart = computed(() => {
  const rounds = Array.isArray(actionStats.value.rounds) ? [...actionStats.value.rounds] : []
  if (!rounds.length) {
    return {
      show: false,
      width: 640,
      height: 260,
      padLeft: 42,
      padRight: 18,
      padTop: 22,
      padBottom: 56,
      yTicks: [],
      items: [],
      linePoints: ''
    }
  }

  rounds.sort((a, b) => Number(a.roundNo || 0) - Number(b.roundNo || 0))

  const padLeft = 42
  const padRight = 18
  const padTop = 22
  const padBottom = 56
  const stepX = 88
  const width = Math.max(640, padLeft + padRight + rounds.length * stepX)
  const height = 260
  const maxPass = Math.max(...rounds.map(item => Number(item.totalCnt || item.passCnt || 0)), 1)
  const usableHeight = height - padTop - padBottom

  const toY = (val) => {
    const safe = Number(val || 0)
    return padTop + usableHeight - (safe / maxPass) * usableHeight
  }

  let bestSoFar = 0
  const items = rounds.map((item, idx) => {
    const passCnt = Number(item.passCnt || 0)
    const totalCnt = Number(item.totalCnt || 0)
    bestSoFar = Math.max(bestSoFar, passCnt)
    const centerX = padLeft + idx * stepX + stepX / 2
    const barWidth = 30
    const barX = centerX - barWidth / 2
    const barY = toY(passCnt)
    const baseY = height - padBottom
    const barHeight = Math.max(0, baseY - barY)
    return {
      ...item,
      passCnt,
      totalCnt,
      bestCnt: bestSoFar,
      centerX,
      barWidth,
      barX,
      barY,
      barHeight,
      bestY: toY(bestSoFar),
      hitX: centerX - stepX / 2 + 6,
      hitWidth: Math.max(stepX - 12, 32)
    }
  })

  const tickCount = Math.min(maxPass, 4)
  const yTicks = []
  for (let i = 0; i <= tickCount; i += 1) {
    const value = Math.round((maxPass * i) / tickCount)
    yTicks.push({ value, y: toY(value) })
  }

  return {
    show: true,
    width,
    height,
    padLeft,
    padRight,
    padTop,
    padBottom,
    yTicks,
    items,
    linePoints: items.map(item => `${item.centerX},${item.bestY}`).join(' ')
  }
})

function statusLabel(status) {
  const map = {
    draft: '草稿',
    queued: '排队中',
    generating: '生成中',
    testing: '测试中',
    fixing: '修复中',
    stopping: '停止中',
    running: '运行中',
    pass: '通过',
    fail: '失败',
    stop: '已停止'
  }
  return map[status] || '未开始'
}

function statusTagType(status) {
  const map = {
    draft: 'info',
    queued: 'warning',
    generating: 'warning',
    testing: 'primary',
    fixing: 'danger',
    stopping: 'info',
    running: 'primary',
    pass: 'success',
    fail: 'danger',
    stop: 'info'
  }
  return map[status] || 'info'
}

function timelineType(verType) {
  const map = {
    init: 'primary',
    repair: 'warning',
    rollback: 'danger',
    manual: 'success'
  }
  return map[verType] || 'info'
}

function boolText(value) {
  if (value === true) return '开启'
  if (value === false) return '关闭'
  return '未返回'
}

function stopReasonLabel(reason) {
  const map = {
    pass_and_stop_on_pass: '通过后立即停止',
    pass_reached_but_continue_return: '通过后跳出循环并统一返回',
    max_round_reached: '达到最大轮次',
    stop_requested: '用户手动中止',
    repair_generation_failed: '修复代理生成失败'
  }
  return map[reason] || (reason || '尚未触发自动修复')
}

function autoActionLabel(action) {
  const map = {
    accept: '接纳当前版本',
    continue: '继续尝试',
    rollback: '回退到最佳基线',
    stop: '用户手动中止',
    repair_error: '修复代理失败'
  }
  return map[action] || (action || '暂无')
}

function isRollbackVersion(item) {
  return Boolean(item?.ver_type === 'rollback' || rollbackRunMeta.value.rollbackVerId === item?.id)
}

function rollbackRetestState(item) {
  if (!isRollbackVersion(item)) return 'none'
  if (rollbackRunMeta.value.rollbackVerId !== item?.id) return 'plain'
  return rollbackRunMeta.value.pending ? 'pending' : (rollbackRunMeta.value.lastRunId ? 'done' : 'plain')
}

function rollbackRetestTitle(item) {
  const state = rollbackRetestState(item)
  const isAuto = rollbackRunMeta.value.source === 'auto' && rollbackRunMeta.value.rollbackVerId === item?.id
  if (state === 'pending') return isAuto ? '自动修复触发 rollback，等待首个验证运行' : '等待 rollback 首次复测'
  if (state === 'done') return isAuto ? '自动修复触发的 rollback 已完成首个验证运行' : 'rollback 首次复测已完成'
  return 'rollback 基线版本'
}

function rollbackRetestDesc(item) {
  const state = rollbackRetestState(item)
  const isAuto = rollbackRunMeta.value.source === 'auto' && rollbackRunMeta.value.rollbackVerId === item?.id
  if (state === 'pending') {
    return isAuto
      ? '该 rollback 由自动修复流程触发，等待后续运行以确认回退后的新基线表现。'
      : '该版本已成为最新 rollback 基线，等待运行测试以更新右侧反馈。'
  }
  if (state === 'done') {
    return isAuto
      ? `自动修复在触发 rollback 后，首个验证运行为 #${rollbackRunMeta.value.lastRunId || '-'}，结果：${rollbackRunMeta.value.lastRunResult || '-'}。`
      : `首次复测运行 #${rollbackRunMeta.value.lastRunId || '-'}，结果：${rollbackRunMeta.value.lastRunResult || '-'}。`
  }
  return isAuto
    ? '该版本由自动修复过程触发回退生成，表示系统已回到较优基线后继续尝试。'
    : '该版本由手动回退生成，可作为新的稳定基线继续修复。'
}

function rollbackRunTagText(row) {
  if (!isRollbackRetestRun(row)) return ''
  return rollbackRunMeta.value.source === 'auto' ? 'auto rollback 首验' : 'rollback 首测'
}

function rollbackRunMarkText(row) {
  if (!isRollbackRetestRun(row)) return ''
  const ok = row.result === 'pass'
  if (rollbackRunMeta.value.source === 'auto') {
    return ok ? 'auto rollback 首验通过' : 'auto rollback 首验失败'
  }
  return ok ? 'rollback 首测通过' : 'rollback 首测失败'
}

function isRollbackRetestRun(row) {
  return Boolean(row?.id && rollbackRunMeta.value.lastRunId && row.id === rollbackRunMeta.value.lastRunId)
}

function runRowClassName({ row }) {
  const classes = []
  if (isRollbackRetestRun(row)) classes.push('rollback-retest-row')
  if (isAutoActionRun(row)) classes.push(`auto-action-row-${autoActionMeta.value.action || 'plain'}`)
  if (currentRunId.value && row?.id === currentRunId.value) classes.push('current-run-row')
  return classes.join(' ')
}

function resetRollbackRunMeta() {
  rollbackRunMeta.value = {
    pending: false,
    source: null,
    rollbackVerId: null,
    rollbackVerNo: null,
    fromVerId: null,
    lastRunId: null,
    lastRunResult: null
  }
}

function resetAutoActionMeta() {
  autoActionMeta.value = {
    action: null,
    reason: '',
    verId: null,
    verNo: null,
    runId: null,
    runResult: null
  }
}

function findVerNoById(verId) {
  if (!verId) return null
  const row = versions.value.find(item => item.id === verId)
  return row?.ver_no ?? null
}

function applyAutoRollbackMeta(autoData) {
  const rollbackVerId = autoData?.rollback_ver_id || null
  if (!rollbackVerId) {
    resetRollbackRunMeta()
    return
  }

  rollbackRunMeta.value = {
    pending: !autoData?.last_run_id,
    source: 'auto',
    rollbackVerId,
    rollbackVerNo: findVerNoById(rollbackVerId),
    fromVerId: null,
    lastRunId: autoData?.last_run_id || null,
    lastRunResult: autoData?.last_run_id
      ? (feedback.value?.run_id === autoData.last_run_id ? feedback.value?.result || null : (runs.value.find(item => item.id === autoData.last_run_id)?.result || null))
      : null
  }
}

function applyAutoActionMeta(autoData) {
  const action = autoData?.last_action || null
  if (!action) {
    resetAutoActionMeta()
    return
  }

  const verId = autoData?.rollback_ver_id || autoData?.last_ver_id || null
  const runId = autoData?.last_run_id || null
  autoActionMeta.value = {
    action,
    reason: autoData?.last_action_reason || '',
    verId,
    verNo: findVerNoById(verId),
    runId,
    runResult: runId
      ? (feedback.value?.run_id === runId ? feedback.value?.result || null : (runs.value.find(item => item.id === runId)?.result || null))
      : null
  }
}

function isAutoActionVersion(item) {
  return Boolean(item?.id && autoActionMeta.value.verId && item.id === autoActionMeta.value.verId)
}

function autoActionTimelineTitle(item) {
  if (!isAutoActionVersion(item)) return ''
  const action = autoActionMeta.value.action
  if (action === 'accept') return '自动修复本轮动作：accept'
  if (action === 'continue') return '自动修复本轮动作：continue'
  if (action === 'rollback') return '自动修复本轮动作：rollback'
  return '自动修复动作标记'
}

function autoActionTimelineDesc(item) {
  if (!isAutoActionVersion(item)) return ''
  const action = autoActionMeta.value.action
  const reason = autoActionMeta.value.reason || '后端未返回动作说明'
  if (action === 'accept') {
    return `该版本被本轮自动修复接纳为更优结果。说明：${reason}`
  }
  if (action === 'continue') {
    return `该版本对应“继续尝试”动作，表示本轮未触发回退，将继续沿当前方向推进。说明：${reason}`
  }
  if (action === 'rollback') {
    return `该版本对应“回退到最佳基线”动作。说明：${reason}`
  }
  return reason
}

function autoActionTagType(action) {
  const map = {
    accept: 'success',
    continue: 'warning',
    rollback: 'danger'
  }
  return map[action] || 'info'
}

function autoActionTagText(action) {
  const map = {
    accept: 'accept',
    continue: 'continue',
    rollback: 'rollback'
  }
  return map[action] || 'action'
}

function isAutoActionRun(row) {
  return Boolean(row?.id && autoActionMeta.value.runId && row.id === autoActionMeta.value.runId)
}

function autoActionRunMarkText(row) {
  if (!isAutoActionRun(row)) return ''
  const action = autoActionMeta.value.action
  if (action === 'accept') return row.result === 'pass' ? 'accept 对应运行通过' : 'accept 对应运行'
  if (action === 'continue') return 'continue 对应运行'
  if (action === 'rollback') return 'rollback 触发前运行'
  return '自动修复动作运行'
}

function comboItemTitle(item) {
  return `R${item.roundNo} · ${item.action}
运行 #${item.runId}
版本 #${item.verId || '-'}
通过 ${item.passCnt}/${item.totalCnt}
历史最佳 ${item.bestCnt}`
}

function resetCodeFocusMeta() {
  codeFocusMeta.value = {
    source: null,
    title: '',
    desc: ''
  }
}

function getVersionById(verId) {
  if (!verId) return null
  return versions.value.find(item => item.id === verId) || null
}

function versionShortText(ver) {
  if (!ver) return '未知版本'
  return `V${ver.ver_no ?? '?'} / #${ver.id ?? '-'}`
}

function versionNoteText(ver) {
  if (!ver) return '暂无版本说明'
  return ver.note || '暂无版本说明'
}

function getVersionIndex(verId) {
  return versions.value.findIndex(item => item.id === verId)
}

function getPrevVersionId(verId) {
  const idx = getVersionIndex(verId)
  if (idx <= 0) return null
  return versions.value[idx - 1]?.id || null
}

function chooseCodeTabForActionRound(item) {
  const action = item?.action || ''
  const verId = item?.verId || null
  const prevVerId = getPrevVersionId(verId)
  const isLatest = latestVerId.value === verId
  const isBest = bestVerId.value === verId

  if (!verId) {
    return {
      tab: 'current',
      compareVerId: compareVerId.value || null,
      title: '已自动切到当前代码',
      desc: `该轮仅关联到运行记录，未找到明确版本信息，因此优先展示当前代码。`
    }
  }

  if ((action === 'rollback' || action === 'continue') && prevVerId && prevVerId !== verId) {
    return {
      tab: 'diff',
      compareVerId: prevVerId,
      title: `已自动切到 Diff 对比（R${item.roundNo} · ${action}）`,
      desc: `这一轮更适合直接看版本差异：当前版本 V${item.verNo || '?'} / #${verId} 与上一版本对比。`
    }
  }

  if (action === 'accept' && (isLatest || isBest || item?.result === 'pass')) {
    return {
      tab: 'current',
      compareVerId: compareVerId.value || prevVerId || null,
      title: `已自动切到当前代码（R${item.roundNo} · accept）`,
      desc: `这一轮是接纳动作，当前版本更值得直接阅读，因此优先展示该轮代码正文。`
    }
  }

  if (prevVerId && prevVerId !== verId) {
    return {
      tab: 'diff',
      compareVerId: prevVerId,
      title: `已自动切到 Diff 对比（R${item.roundNo} · ${action || 'round'}）`,
      desc: `该轮已定位到对应版本，优先展示它与上一版本的差异，便于说明这一轮具体改了什么。`
    }
  }

  return {
    tab: 'current',
    compareVerId: compareVerId.value || null,
    title: `已自动切到当前代码（R${item.roundNo}）`,
    desc: `当前轮没有更合适的对比版本，因此优先展示该轮对应代码。`
  }
}

async function focusTimelineVersion(verId) {
  if (!verId) return
  selectedTimelineVerId.value = verId
  await nextTick()
  const el = document.querySelector(`.timeline-box[data-ver-id="${verId}"]`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
  }
}

async function handleSelectActionRound(item) {
  if (!item) return
  selectedActionRunId.value = item.runId
  selectedTimelineVerId.value = item.verId || null

  if (item.runId) {
    currentRunId.value = item.runId
    await loadRunPanel(item.runId)
  }

  if (item.verId) {
    currentVerId.value = item.verId
    await loadCurrentCode(item.verId)

    const target = chooseCodeTabForActionRound(item)
    if (target.compareVerId && target.compareVerId !== currentVerId.value) {
      compareVerId.value = target.compareVerId
    }

    await loadDiffIfNeed()
    await focusTimelineVersion(item.verId)

    if (target.tab === 'diff' && !diffText.value) {
      codeTab.value = 'current'
      codeFocusMeta.value = {
        source: 'actionChart',
        title: `已自动切到当前代码（R${item.roundNo} · ${item.action}）`,
        desc: '原本更适合展示 Diff，但当前没有可用差异内容，因此已自动退回到当前代码视图。'
      }
      return
    }

    codeTab.value = target.tab
    codeFocusMeta.value = {
      source: 'actionChart',
      title: target.title,
      desc: target.desc
    }
  }
}



function resetActionStats() {
  actionStats.value = {
    accept: 0,
    continue: 0,
    rollback: 0,
    total: 0,
    maxCount: 0,
    rounds: []
  }
}

function safeScore(row) {
  const val = Number(row?.score)
  if (Number.isFinite(val)) return val
  return Number(row?.pass_cnt || 0)
}

async function rebuildActionStats() {
  if (!runs.value.length) {
    resetActionStats()
    return
  }

  try {
    const verTypeMap = new Map(versions.value.map(item => [item.id, item.ver_type]))
    const detailRes = await Promise.all(
      runs.value.map(item => getRunDetail(item.id).catch(() => null))
    )
    const detailRows = detailRes
      .map(item => item?.data || null)
      .filter(Boolean)
      .filter(item => verTypeMap.get(item.ver_id) !== 'rollback')

    if (!detailRows.length) {
      resetActionStats()
      return
    }

    const seedRows = detailRows.filter(item => Number(item.round_no || 0) < 1)
    let bestScore = seedRows.length ? Math.max(...seedRows.map(item => safeScore(item))) : 0
    let hasBest = seedRows.length > 0
    let previousScore = hasBest ? bestScore : null

    const autoRows = detailRows
      .filter(item => Number(item.round_no || 0) >= 1)
      .sort((a, b) => {
        const ra = Number(a.round_no || 0)
        const rb = Number(b.round_no || 0)
        if (ra !== rb) return ra - rb
        return Number(a.id || 0) - Number(b.id || 0)
      })

    const firstRunPerRound = []
    const seenRounds = new Set()
    for (const row of autoRows) {
      const roundNo = Number(row.round_no || 0)
      if (seenRounds.has(roundNo)) continue
      seenRounds.add(roundNo)
      firstRunPerRound.push(row)
    }

    if (!firstRunPerRound.length) {
      resetActionStats()
      return
    }

    const counts = { accept: 0, continue: 0, rollback: 0 }
    const rounds = []

    for (const row of firstRunPerRound) {
      const attemptedScore = safeScore(row)
      let action = 'continue'

      if (!hasBest) {
        action = 'accept'
        hasBest = true
        bestScore = attemptedScore
      } else if (attemptedScore > bestScore) {
        action = 'accept'
        bestScore = attemptedScore
      } else if (attemptedScore === bestScore) {
        action = 'continue'
      } else if (previousScore !== null && attemptedScore < previousScore) {
        action = 'rollback'
      } else {
        action = 'continue'
      }

      counts[action] += 1
      rounds.push({
        runId: row.id,
        verId: row.ver_id || null,
        roundNo: Number(row.round_no || 0),
        action,
        passCnt: Number(row.pass_cnt || 0),
        totalCnt: Number(row.total_cnt || 0),
        score: attemptedScore,
        result: row.result || ''
      })
      previousScore = attemptedScore
    }

    actionStats.value = {
      accept: counts.accept,
      continue: counts.continue,
      rollback: counts.rollback,
      total: rounds.length,
      maxCount: Math.max(counts.accept, counts.continue, counts.rollback, 1),
      rounds
    }
  } catch {
    resetActionStats()
  }
}

function clearTaskState() {
  taskInfo.value = null
  summaryInfo.value = null
  versions.value = []
  runs.value = []
  autoMeta.value = null
  resetRollbackRunMeta()
  resetAutoActionMeta()
  resetActionStats()
  feedback.value = null
  traceList.value = []
  selectedTimelineVerId.value = null
  selectedActionRunId.value = null
  taskCases.value = []
  runCaseList.value = []
  planList.value = []
  lessonList.value = []
  planDrawer.visible = false
  planDrawer.item = null
  lessonDrawer.visible = false
  lessonDrawer.item = null
  currentVerId.value = null
  compareVerId.value = null
  bestVerId.value = null
  currentRunId.value = null
  activeTaskId.value = null
  initCode.value = ''
  curCode.value = ''
  bestCode.value = ''
  diffText.value = ''
}

function resetForm() {
  const keepSessId = form.sessId
  resetCodeFocusMeta()
  Object.assign(form, defaultForm())
  form.sessId = keepSessId
}

function exitCurrentTask() {
  savedTaskDraftRef.value = ''
  clearTaskState()
  clearWorkbenchSnapshot()
  router.replace({ path: route.path, query: {} })
  ElMessage.success('已退出当前任务，返回空白工作台')
}


function normalizeCodeTextForView(code) {
  const raw = String(code || '')
  if (!raw) return ''

  let cleaned = raw
  const tailMatch = cleaned.match(/"\s*,\s*"cases"\s*:/)
  if (tailMatch && typeof tailMatch.index === 'number') {
    cleaned = cleaned.slice(0, tailMatch.index)
  }

  if (cleaned.includes('\\n') && !cleaned.includes('\n') && /^\s*(def |class |from |import )/.test(cleaned)) {
    cleaned = cleaned
      .replace(/\\r\\n/g, '\n')
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
  }

  return cleaned
}

function splitCodeLines(code) {
  if (!code) return []
  return normalizeCodeTextForView(code).replace(/\r\n/g, '\n').split('\n')
}

function normalizeLine(line) {
  return String(line || '').replace(/\s+$/g, '')
}

function markChangedLines(baseCode, targetCode) {
  const baseLines = splitCodeLines(baseCode).map(normalizeLine)
  const targetLines = splitCodeLines(targetCode)
  const baseBag = new Map()
  baseLines.forEach(line => {
    baseBag.set(line, (baseBag.get(line) || 0) + 1)
  })
  return targetLines.map(line => {
    const key = normalizeLine(line)
    const rest = baseBag.get(key) || 0
    if (rest > 0) {
      baseBag.set(key, rest - 1)
      return { text: line, changed: false }
    }
    return { text: line, changed: true }
  })
}

function splitDiffRows(diff) {
  return splitCodeLines(diff).map(line => {
    let cls = ''
    if (line.startsWith('+') && !line.startsWith('+++')) cls = 'code-line-added'
    else if (line.startsWith('-') && !line.startsWith('---')) cls = 'code-line-removed'
    else if (line.startsWith('@@')) cls = 'code-line-focus'
    return { text: line, cls }
  })
}

function applyProblemTemplate() {
  const templates = {
    func: [
      '请实现一个函数 solve(...)。',
      '要求：',
      '1. 明确输入参数含义和返回值。',
      '2. 说明正常输入、边界输入和异常输入的处理方式。',
      '3. 不要修改公开函数名。',
      '4. 代码需能直接被 assert 调用。'
    ].join('\n'),
    class: [
      '请实现一个完整的 Python 类文件。',
      '要求：',
      '1. 明确类名、初始化参数、公开方法名。',
      '2. 说明类内部状态如何变化。',
      '3. 说明多个方法之间的联动关系。',
      '4. 说明边界情况、非法输入和返回值约定。'
    ].join('\n'),
    file: [
      '请实现一个完整的 Python 模块（.py 文件）。',
      '要求：',
      '1. 明确模块级公开 API，包括函数名、类名和工具函数。',
      '2. 说明不同 API 之间的协作关系。',
      '3. 说明边界情况、排序规则、并列处理、空输入和非法输入。',
      '4. 不要退化成只实现 solve。'
    ].join('\n')
  }
  form.problemText = templates[form.scene] || templates.func
  ElMessage.success('已添加题目描述模板')
}
async function handleGenCases() {
  if (!form.problemText?.trim()) {
    ElMessage.warning('请先填写题目描述')
    return
  }
  loading.genCases = true
  try {
    const res = await genTaskCases({
      problem_text: form.problemText,
      scene: form.scene,
      title: form.title,
      count: form.caseCfg.count,
      preset: form.caseCfg.preset,
      focus: form.caseCfg.focus,
      hint: form.caseCfg.hint
    })
    const rows = Array.isArray(res.data) ? res.data : []
    form.casesText = rows.map(item => item.assert_text).filter(Boolean).join('\n\n')
    form.autoGenCases = true
    ElMessage.success(`已生成 ${rows.length} 条测试块`)
  } catch (error) {
    ElMessage.error(error?.message || 'AI 生成测试用例失败')
  } finally {
    loading.genCases = false
  }
}

function splitCaseBlocks(casesText, scene = 'func') {
  const raw = String(casesText || '').replace(/\r\n/g, '\n')
  if (!raw.trim()) return []
  const hasBlankSep = /\n\s*\n+/.test(raw)
  if (!hasBlankSep && scene === 'func') {
    return raw
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean)
      .map(line => ({ text: line, src_type: 'custom' }))
  }
  return raw
    .split(/\n\s*\n+/)
    .map(block => block.replace(/^\n+|\n+$/g, ''))
    .map(block => ({
      text: block,
      src_type: hasAssertLine(block) ? 'custom_block' : 'setup'
    }))
    .filter(item => item.text.trim())
}

function buildCases(casesText, scene = 'func') {
  const raw = String(casesText || '').replace(/\r\n/g, '\n').trim()
  if (!raw) return []
  if (scene === 'file' || scene === 'class') {
    return [{
      src_type: 'custom_block',
      case_in: null,
      expect_out: null,
      assert_text: raw,
      weight: 1.0,
      sort_no: 1
    }]
  }
  return splitCaseBlocks(casesText, scene).map((item, idx) => ({
    src_type: item.src_type,
    case_in: null,
    expect_out: null,
    assert_text: item.text.trim(),
    weight: 1.0,
    sort_no: idx + 1
  }))
}

function currentCasePayload() {
  const scene = taskInfo.value?.scene || form.scene
  return buildCases(form.casesText, scene)
}

async function ensureSessionReady() {
  sessLoading.value = true
  try {
    const res = await listSess()
    const list = Array.isArray(res.data) ? res.data : []
    sessList.value = list

    if (list.length) {
      if (!list.some(item => Number(item.id) === Number(form.sessId))) {
        form.sessId = list[0].id
      }
      return
    }

    const createRes = await createSess({ title: '默认修复会话' })
    const row = createRes.data
    if (row?.id) {
      sessList.value = [row]
      form.sessId = row.id
    }
  } catch (error) {
    ElMessage.error(error?.message || '初始化会话失败')
  } finally {
    sessLoading.value = false
  }
}

async function handleCreateSess() {
  sessCreating.value = true
  try {
    const title = `修复会话 ${Date.now()}`
    const res = await createSess({ title })
    const row = res.data
    if (row?.id) {
      sessList.value.unshift(row)
      clearTaskState()
      resetForm()
      form.sessId = row.id
      router.replace({ path: route.path, query: {} })
      ElMessage.success('新会话创建成功，工作台已重置')
    }
  } catch (error) {
    ElMessage.error(error?.message || '新建会话失败')
  } finally {
    sessCreating.value = false
  }
}

async function handleRenameSess() {
  if (!form.sessId) {
    ElMessage.warning('请先选择一个会话')
    return
  }
  try {
    const currentTitle = currentSessTitle.value
    const { value } = await ElMessageBox.prompt('请输入新的会话名称', '修改会话名称', {
      inputValue: currentTitle === '未选择会话' ? '' : currentTitle,
      inputPlaceholder: '例如：MBPP 调试会话',
      confirmButtonText: '保存',
      cancelButtonText: '取消'
    })
    const title = String(value || '').trim()
    if (!title) {
      ElMessage.warning('会话名称不能为空')
      return
    }
    const res = await updateSess(form.sessId, { title })
    const row = res.data || {}
    sessList.value = sessList.value.map(item => Number(item.id) === Number(form.sessId) ? { ...item, title: row.title || title } : item)
    ElMessage.success('会话名称已更新')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '修改会话名称失败')
    }
  }
}

async function loadDatasetOptions() {
  try {
    const res = await listDataset()
    if (Array.isArray(res.data) && res.data.length) {
      datasetOptions.value = res.data
      if (!datasetOptions.value.includes(form.dataset)) {
        form.dataset = datasetOptions.value[0]
      }
    }
  } catch {
    ElMessage.warning('数据集列表加载失败，已使用默认选项')
  }
}

async function loadTaskList() {
  try {
    const res = await listTask()
    taskList.value = Array.isArray(res.data) ? res.data : []
  } catch {
    ElMessage.error('历史任务加载失败')
  }
}

function hasTaskInList(taskId) {
  const id = Number(taskId || 0)
  if (!id) return false
  return (taskList.value || []).some(item => Number(item?.id || 0) === id)
}

function isMissingTaskError(error) {
  const status = Number(error?.response?.status || 0)
  if (status === 404) return true
  const detail = String(error?.response?.data?.detail || error?.message || '').toLowerCase()
  return detail.includes('任务不存在') || detail.includes('无权访问')
}

async function handleMissingTaskReference(taskId, message = '要打开的任务不存在，已返回空白工作台') {
  clearTaskState()
  clearWorkbenchSnapshot()
  const nextQuery = { ...route.query }
  if ('taskId' in nextQuery) {
    delete nextQuery.taskId
    await router.replace({ path: route.path, query: nextQuery })
  }
  ElMessage.warning(message)
}

async function tryOpenTaskById(taskId, message = '要打开的任务不存在，已返回空白工作台') {
  const num = Number(taskId || 0)
  if (!num) return false
  try {
    await loadTaskAll(num)
    return true
  } catch (error) {
    if (isMissingTaskError(error)) {
      await handleMissingTaskReference(num, message)
      return false
    }
    throw error
  }
}

async function refreshTaskInfo() {

  if (!taskInfo.value?.id) return
  try {
    const res = await getTaskDetail(taskInfo.value.id, { silentError: true })
    taskInfo.value = res.data
    activeTaskId.value = taskInfo.value?.id || null
    bestVerId.value = taskInfo.value?.best_ver_id || null
    syncFormFromTask(taskInfo.value)
  } catch (error) {
    if (isMissingTaskError(error)) {
      await handleMissingTaskReference(taskInfo.value?.id, '当前任务已不存在或无权访问，已退出该任务')
      return
    }
    throw error
  }
}

async function refreshSummary() {
  if (!taskInfo.value?.id) return
  try {
    const res = await getTaskSummary(taskInfo.value.id)
    summaryInfo.value = res.data
  } catch {
    summaryInfo.value = null
  }
}

async function refreshVersions() {
  if (!taskInfo.value?.id) return
  const res = await listTaskVers(taskInfo.value.id)
  const list = Array.isArray(res.data) ? res.data : []
  versions.value = list.sort((a, b) => (a.ver_no || 0) - (b.ver_no || 0))

  if (versions.value.length) {
    if (!currentVerId.value) {
      currentVerId.value = versions.value[versions.value.length - 1].id
    }
    if (!compareVerId.value) {
      compareVerId.value = versions.value[0].id
    }
  } else {
    currentVerId.value = null
    compareVerId.value = null
  }
}

async function refreshRuns() {
  if (!taskInfo.value?.id) return
  const res = await listTaskRuns(taskInfo.value.id)
  runs.value = Array.isArray(res.data) ? res.data : []
  if (runs.value.length && !currentRunId.value) {
    currentRunId.value = runs.value[0].id
  }
  if (currentRunId.value && !runs.value.some(item => item.id === currentRunId.value)) {
    currentRunId.value = runs.value[0]?.id || null
  }
}

async function refreshCasesPlansLessons() {
  if (!taskInfo.value?.id) return
  const [caseRes, planRes, lessonRes] = await Promise.all([
    getTaskCases(taskInfo.value.id).catch(() => ({ data: [] })),
    getTaskPlans(taskInfo.value.id).catch(() => ({ data: [] })),
    getTaskLessons(taskInfo.value.id).catch(() => ({ data: [] }))
  ])
  taskCases.value = Array.isArray(caseRes.data) ? caseRes.data : []
  planList.value = Array.isArray(planRes.data) ? planRes.data : []
  lessonList.value = Array.isArray(lessonRes.data) ? lessonRes.data : []
  syncCasesTextFromTaskCases()
  refreshSavedTaskDraft()
}

async function loadInitCode() {
  if (!versions.value.length) {
    initCode.value = ''
    return
  }
  const initVer = versions.value.find(item => item.ver_no === 1) || versions.value[0]
  const res = await getVerCode(initVer.id)
  initCode.value = normalizeCodeTextForView(res.data?.code_text || '')
}

async function loadCurrentCode(verId) {
  if (!verId) {
    curCode.value = ''
    return
  }
  const res = await getVerCode(verId)
  curCode.value = normalizeCodeTextForView(res.data?.code_text || '')
}

async function loadBestCode(verId) {
  if (!verId) {
    bestCode.value = ''
    return
  }
  const res = await getVerCode(verId)
  bestCode.value = normalizeCodeTextForView(res.data?.code_text || '')
}

async function loadDiffIfNeed() {
  if (!currentVerId.value || !compareVerId.value || currentVerId.value === compareVerId.value) {
    diffText.value = ''
    return
  }

  try {
    const res = await getVerDiff(compareVerId.value, currentVerId.value, { silentError: true })
    diffText.value = res.data?.diff || ''
  } catch {
    diffText.value = ''
  }
}

async function loadRunPanel(runId) {
  if (!runId) {
    feedback.value = null
    traceList.value = []
    runCaseList.value = []
    return
  }

  const [fbRes, traceRes, caseRes] = await Promise.all([
    getRunFb(runId),
    getRunTrace(runId),
    getRunCases(runId).catch(() => ({ data: [] }))
  ])

  feedback.value = fbRes.data || null
  traceList.value = Array.isArray(traceRes.data) ? traceRes.data : []
  runCaseList.value = Array.isArray(caseRes.data) ? caseRes.data : []
}

async function loadTaskAll(taskId) {
  loading.page = true
  try {
    if (activeTaskId.value && activeTaskId.value !== taskId) {
      autoMeta.value = null
      resetRollbackRunMeta()
      resetAutoActionMeta()
      currentVerId.value = null
      compareVerId.value = null
      diffText.value = ""
    }
    let detailRes
    try {
      detailRes = await getTaskDetail(taskId, { silentError: true })
    } catch (error) {
      if (isMissingTaskError(error)) {
        await handleMissingTaskReference(taskId)
        return
      }
      throw error
    }
    taskInfo.value = detailRes.data
    activeTaskId.value = taskInfo.value?.id || null
    bestVerId.value = taskInfo.value?.best_ver_id || null
    syncFormFromTask(taskInfo.value)

    await Promise.all([
      refreshSummary(),
      refreshVersions(),
      refreshRuns(),
      refreshCasesPlansLessons()
    ])

    syncCasesTextFromTaskCases()
    await rebuildActionStats()

    await loadInitCode()

    if (versions.value.length) {
      const latestVer = versions.value[versions.value.length - 1]
      currentVerId.value = latestVer.id
      await loadCurrentCode(currentVerId.value)
    } else {
      curCode.value = ''
    }

    if (bestVerId.value) {
      await loadBestCode(bestVerId.value)
    } else {
      bestCode.value = ''
    }

    if (!compareVerId.value && versions.value.length) {
      compareVerId.value = versions.value[0].id
    }

    await loadDiffIfNeed()
    refreshSavedTaskDraft()

    if (runs.value.length) {
      const keptRun = currentRunId.value && runs.value.some(item => item.id === currentRunId.value)
      if (keptRun) {
        await loadRunPanel(currentRunId.value)
      } else if (currentVerId.value) {
        await syncRunPanelByVersion(currentVerId.value)
      } else {
        currentRunId.value = runs.value[0].id
        await loadRunPanel(currentRunId.value)
      }
    } else {
      feedback.value = null
      traceList.value = []
      runCaseList.value = []
      currentRunId.value = null
    }
  } finally {
    loading.page = false
  }
}

async function refreshAll() {
  if (!taskInfo.value?.id) {
    ElMessage.warning('当前没有可刷新的任务')
    return
  }
  await loadTaskAll(taskInfo.value.id)
  await loadTaskList()
  ElMessage.success('刷新完成')
}

async function onSaveTaskEdits() {
  if (!taskInfo.value?.id) {
    ElMessage.warning('当前没有可保存的任务')
    return
  }
  if (!hasPendingTaskEdits.value) {
    ElMessage.info('当前没有需要保存的修改')
    return
  }
  loading.saveTask = true
  try {
    await saveTaskDraftToServer({ showSuccess: true })
  } catch (error) {
    ElMessage.error(error?.message || '保存当前任务失败')
  } finally {
    loading.saveTask = false
  }
}

async function onCreateTask() {
  if (!canCreateTask.value) {
    ElMessage.warning('请先填写会话、任务标题和题目描述')
    return
  }

  loading.createTask = true
  try {
    const res = await createTask({
      sess_id: form.sessId,
      model_id: null,
      title: form.title,
      lang: form.lang,
      scene: form.scene,
      dataset: form.dataset,
      problem_text: form.problemText,
      max_round: form.maxRound,
      is_trace_on: form.isTraceOn,
      is_lesson_on: form.isLessonOn,
      cases: buildCases(form.casesText, form.scene)
    })

    const taskId = res.data?.id
    if (!taskId) throw new Error('任务创建失败，未返回任务ID')

    resetRollbackRunMeta()
    resetAutoActionMeta()
    await loadTaskAll(taskId)
    await loadTaskList()
    ElMessage.success('任务创建成功')
  } catch (error) {
    ElMessage.error(error?.message || '任务创建失败')
  } finally {
    loading.createTask = false
  }
}

async function onGenCode() {
  const taskId = Number(taskInfo.value?.id || 0)
  if (!taskId) {
    ElMessage.warning('请先创建任务')
    return
  }
  if (!(await confirmSaveBeforeAction('生成初始代码'))) return

  loading.gen = true
  markTaskAction(taskId, 'generating')
  try {
    resetRollbackRunMeta()
    resetAutoActionMeta()
    resetCodeFocusMeta()
    const res = await genTask(taskId, {
      auto_gen_cases: Boolean(form.autoGenCases),
      case_cfg: { ...form.caseCfg }
    })
    if (isViewingTask(taskId)) {
      currentVerId.value = res.data?.ver_id || null
      await loadTaskAll(taskId)
      codeTab.value = 'current'
    }
    await loadTaskList()
    ElMessage.success(res.data?.case_source && res.data.case_source !== 'manual' ? `初始代码生成成功（测试块来源：${res.data.case_source}）` : '初始代码生成成功')
  } catch (error) {
    ElMessage.error(error?.message || '初始代码生成失败')
  } finally {
    clearTaskAction(taskId, 'generating')
    loading.gen = false
  }
}

async function onRunTask() {
  const taskId = Number(taskInfo.value?.id || 0)
  if (!taskId) {
    ElMessage.warning('请先创建任务')
    return
  }
  if (!(await confirmSaveBeforeAction('运行测试'))) return

  loading.run = true
  markTaskAction(taskId, 'testing')
  try {
    resetCodeFocusMeta()
    const res = await runTask(taskId, { cases: currentCasePayload() })
    if (isViewingTask(taskId)) {
      currentRunId.value = res.data?.run_id || null
      await refreshRuns()
      await rebuildActionStats()
      await refreshTaskInfo()
      await refreshCasesPlansLessons()
      await loadRunPanel(currentRunId.value)
    }
    await loadTaskList()
    ElMessage.success('运行完成')
  } catch (error) {
    ElMessage.error(error?.message || '运行失败')
  } finally {
    clearTaskAction(taskId, 'testing')
    loading.run = false
  }
}


function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function pollTaskStatusUntilSettled(taskId, { maxTries = 20, intervalMs = 1500 } = {}) {
  let settled = false
  for (let i = 0; i < maxTries; i += 1) {
    try {
      const res = await getTaskStatus(taskId)
      const statusData = res.data || {}
      if (taskInfo.value && Number(taskInfo.value.id) === Number(taskId)) {
        taskInfo.value = {
          ...taskInfo.value,
          status: statusData.status || taskInfo.value.status,
          cur_round: statusData.cur_round ?? taskInfo.value.cur_round,
          best_ver_id: statusData.best_ver_id ?? taskInfo.value.best_ver_id,
          best_score: statusData.best_score ?? taskInfo.value.best_score,
        }
      }
      if ((statusData.status || '').toLowerCase() !== 'running') {
        settled = true
        break
      }
    } catch {
      // ignore and retry
    }
    await sleep(intervalMs)
  }
  if (settled) {
    await loadTaskAll(taskId)
    await loadTaskList()
  }
  return settled
}

async function handleStopTask() {
  const taskId = Number(taskInfo.value?.id || 0)
  if (!taskId) {
    ElMessage.warning('当前没有可中止的任务')
    return
  }

  try {
    await ElMessageBox.confirm(
      '确认中止当前任务吗？当前正在运行的这一轮会尽量执行到结束，然后停止后续自动修复。',
      '中止确认',
      {
        type: 'warning',
        confirmButtonText: '确认中止',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }

  loading.stop = true
  markTaskAction(taskId, 'stopping')
  try {
    await stopTask(taskId)
    if (taskInfo.value) taskInfo.value.status = 'stop'
    autoMeta.value = {
      ...(autoMeta.value || {}),
      stopped_reason: 'stop_requested',
      last_action: 'stop',
      last_action_reason: '用户手动请求中止任务；当前轮结束后停止后续自动修复。'
    }
    await loadTaskList()
    ElMessage.success('已提交中止请求，当前轮结束后会停止后续自动修复')
  } catch (error) {
    ElMessage.error(error?.message || '中止任务失败')
  } finally {
    clearTaskAction(taskId, 'stopping')
    loading.stop = false
  }
}


async function onAutoFix() {
  const taskId = Number(taskInfo.value?.id || 0)
  if (!taskId) {
    ElMessage.warning('请先创建任务')
    return
  }
  if (!versions.value.length) {
    ElMessage.warning('请先生成初始代码')
    return
  }

  loading.auto = true
  markTaskAction(taskId, 'fixing')
  try {
    if (isViewingTask(taskId) && taskInfo.value) taskInfo.value.status = 'running'
    resetRollbackRunMeta()
    resetCodeFocusMeta()
    const res = await autoFixTask(taskId, {
      max_round: form.maxRound,
      trace_on: form.isTraceOn,
      lesson_on: form.isLessonOn,
      stop_on_pass: form.stopOnPass,
      cases: currentCasePayload()
    })

    if (isViewingTask(taskId)) {
      autoMeta.value = res.data || null
      currentRunId.value = res.data?.last_run_id || null
      currentVerId.value = res.data?.last_ver_id || null
      bestVerId.value = res.data?.best_ver_id || null

      await loadTaskAll(taskId)
      autoMeta.value = res.data || null
      applyAutoRollbackMeta(res.data)
      applyAutoActionMeta(res.data)
      codeTab.value = 'current'
    }
    await loadTaskList()
    if (res.data?.repair_error) {
      ElMessage.warning(`自动修复已停止：${res.data.repair_error}`)
    } else {
      ElMessage.success(`自动修复完成：${stopReasonLabel(res.data?.stopped_reason)} / ${autoActionLabel(res.data?.last_action)}`)
    }
  } catch (error) {
    const stillRunning = Boolean(isViewingTask(taskId) && taskInfo.value?.status === 'running')
    if (stillRunning) {
      await pollTaskStatusUntilSettled(taskId, { maxTries: 30, intervalMs: 1500 })
    } else if (isViewingTask(taskId)) {
      await refreshTaskInfo().catch(() => {})
    } else {
      await loadTaskList().catch(() => {})
    }
    ElMessage.error(error?.message || '自动修复失败')
  } finally {
    clearTaskAction(taskId, 'fixing')
    loading.auto = false
  }
}

async function handleSelectCurrentVersion(verId) {
  resetCodeFocusMeta()
  currentVerId.value = verId
  await loadCurrentCode(verId)
  await loadDiffIfNeed()
  await syncRunPanelByVersion(verId)
}

async function handleSelectRun(row) {
  resetCodeFocusMeta()
  currentRunId.value = row.id
  selectedActionRunId.value = row.id
  if (row?.ver_id) {
    currentVerId.value = row.ver_id
    selectedTimelineVerId.value = row.ver_id
    await loadCurrentCode(row.ver_id)
    await loadDiffIfNeed()
  }
  await loadRunPanel(row.id)
}

async function switchToVersion(item) {
  resetCodeFocusMeta()
  currentVerId.value = item.id
  selectedTimelineVerId.value = item.id
  await loadCurrentCode(item.id)
  await loadDiffIfNeed()
  await syncRunPanelByVersion(item.id)
  await focusTimelineVersion(item.id)
  codeTab.value = 'current'
}

async function handleManualRollback(item) {
  if (!taskInfo.value?.id) {
    ElMessage.warning('当前没有可操作的任务')
    return
  }
  if (!item?.id) {
    ElMessage.warning('目标版本无效')
    return
  }
  if (latestVerId.value === item.id) {
    ElMessage.info('当前最新版本就是目标版本，无需回退')
    return
  }

  const fromVerId = latestVerId.value
  const staleRunId = currentRunId.value
  try {
    await ElMessageBox.confirm(
      `确认把历史版本 V${item.ver_no}（#${item.id}）落成一个新的 rollback 基线版本吗？`,
      '手动回退确认',
      {
        confirmButtonText: '确认回退',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  loading.rollback = true
  try {
    resetAutoActionMeta()
    resetCodeFocusMeta()
    const res = await rollbackVersion(item.id)
    const newVerId = res.data?.ver_id || null
    const newVerNo = res.data?.ver_no || null

    compareVerId.value = fromVerId || item.id
    currentVerId.value = newVerId

    await loadTaskAll(taskInfo.value.id)

    rollbackRunMeta.value = {
      pending: true,
      source: 'manual',
      rollbackVerId: newVerId,
      rollbackVerNo: newVerNo,
      fromVerId: fromVerId || null,
      lastRunId: staleRunId || null,
      lastRunResult: feedback.value?.result || null
    }

    if (fromVerId) {
      compareVerId.value = fromVerId
      await loadDiffIfNeed()
      codeTab.value = 'diff'
      codeFocusMeta.value = {
        source: 'manualRollback',
        title: `已自动切到 Diff 对比（手动 rollback）`,
        desc: `当前展示的是回退前最新版本 V${versions.value.find(v => v.id === fromVerId)?.ver_no || '?'} 与新生成 rollback 版本 V${newVerNo || '?'} 的差异，便于直接说明这次回退到底把代码恢复到了哪一版。`
      }
    } else {
      codeTab.value = 'current'
    }

    ElMessage.success(`手动回退成功，已生成 rollback 版本 V${newVerNo || '-'} / #${newVerId || '-'}，可直接一键重新运行测试`)
  } catch (error) {
    ElMessage.error(error?.message || '手动回退失败')
  } finally {
    loading.rollback = false
  }
}

async function handleRunRollbackVersion() {
  if (!taskInfo.value?.id) {
    ElMessage.warning('当前没有可运行的任务')
    return
  }
  if (!rollbackRunMeta.value.rollbackVerId) {
    ElMessage.warning('当前没有待复测的 rollback 版本')
    return
  }
  if (latestVerId.value !== rollbackRunMeta.value.rollbackVerId) {
    ElMessage.warning('当前最新版本已经发生变化，请先确认版本时间线再运行')
    return
  }

  loading.rerunRollback = true
  try {
    resetCodeFocusMeta()
    const rollbackVerId = rollbackRunMeta.value.rollbackVerId
    const rollbackVerNo = rollbackRunMeta.value.rollbackVerNo

    const res = await runTask(taskInfo.value.id, { cases: currentCasePayload() })
    const runId = res.data?.run_id || null

    currentRunId.value = runId
    currentVerId.value = rollbackVerId

    await refreshRuns()
    await rebuildActionStats()
    await refreshTaskInfo()
    await refreshCasesPlansLessons()
    await loadCurrentCode(rollbackVerId)
    if (bestVerId.value) {
      await loadBestCode(bestVerId.value)
    }
    await loadDiffIfNeed()
    await loadRunPanel(runId)

    rollbackRunMeta.value = {
      pending: false,
      source: 'manual',
      rollbackVerId,
      rollbackVerNo,
      fromVerId: rollbackRunMeta.value.fromVerId,
      lastRunId: runId,
      lastRunResult: res.data?.result || feedback.value?.result || null
    }

    codeTab.value = 'current'
    ElMessage.success(`已基于 rollback 版本 V${rollbackVerNo || '-'} / #${rollbackVerId || '-'} 重新运行测试`)
  } catch (error) {
    ElMessage.error(error?.message || '重新运行 rollback 版本失败')
  } finally {
    loading.rerunRollback = false
  }
}

async function selectHistoryTask(item) {
  resetCodeFocusMeta()
  await loadTaskAll(item.id)
}

async function refreshRunPanel() {
  if (!currentRunId.value) {
    ElMessage.warning('当前没有运行记录')
    return
  }
  await loadRunPanel(currentRunId.value)
  ElMessage.success('反馈已刷新')
}

async function copyCurrentCode() {
  if (!curCode.value) {
    ElMessage.warning('当前没有代码可复制')
    return
  }
  try {
    await navigator.clipboard.writeText(curCode.value)
    ElMessage.success('当前代码已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function openPlanDrawer(row) {
  if (!row) return
  planDrawer.item = row
  planDrawer.visible = true
}

function openLessonDrawer(row) {
  if (!row) return
  lessonDrawer.item = row
  lessonDrawer.visible = true
}

async function copyPlanDetail(field) {
  await copyText(planDrawer.item?.[field] || '')
}

async function copyLessonDetail(field) {
  await copyText(lessonDrawer.item?.[field] || '')
}

function buildTaskReportText() {
  const lines = []
  lines.push(`# 任务报告：${taskInfo.value?.title || '未命名任务'}`)
  lines.push('')
  lines.push('## 一、任务概览')
  lines.push(`- 任务ID：${taskInfo.value?.id || '-'}`)
  lines.push(`- 状态：${statusLabel(taskInfo.value?.status)}`)
  lines.push(`- 当前轮次：${taskInfo.value?.cur_round ?? 0}`)
  lines.push(`- 最佳版本：${taskInfo.value?.best_ver_id ?? '-'}`)
  lines.push(`- 最佳分数：${taskInfo.value?.best_score ?? 0}`)
  lines.push(`- Trace 开关：${boolText(taskInfo.value?.is_trace_on)}`)
  lines.push(`- Lesson 开关：${boolText(taskInfo.value?.is_lesson_on)}`)
  lines.push('')
  lines.push('## 二、题目描述')
  lines.push(taskInfo.value?.problem_text || form.problemText || '-')
  lines.push('')
  lines.push('## 三、执行反馈')
  lines.push(`- 运行ID：${feedback.value?.run_id ?? '-'}`)
  lines.push(`- 运行结果：${feedback.value?.result || '-'}`)
  lines.push(`- 错误类型：${feedback.value?.err_type || '-'}`)
  lines.push(`- 报错行号：${feedback.value?.line_no ?? '-'}`)
  lines.push(`- 通过用例：${feedback.value?.pass_cnt ?? 0}/${feedback.value?.total_cnt ?? 0}`)
  lines.push(`- 轨迹摘要：${feedback.value?.trace_sum || '暂无轨迹摘要'}`)
  lines.push(`- 错误提示：${feedback.value?.err_msg || '暂无错误提示'}`)
  lines.push('')
  lines.push('## 四、版本时间线')
  ;(versions.value || []).forEach(item => {
    lines.push(`- V${item.ver_no} / #${item.id} / ${item.ver_type} / ${item.note || '暂无备注'}`)
  })
  lines.push('')
  lines.push('## 五、失败样例 / 单用例结果')
  if (runCaseView.value.length) {
    runCaseView.value.forEach(item => {
      lines.push(`- [${item.result}] 用例 ${item.case_id} | ${item.assert_text} | 实际输出：${item.actual_out_text} | 错误：${item.err_msg || '-'}`)
    })
  } else {
    lines.push('- 暂无单用例结果')
  }
  lines.push('')
  lines.push('## 六、修复计划')
  if (planList.value.length) {
    planList.value.forEach(item => {
      lines.push(`### 第 ${item.round_no} 轮`)
      lines.push(`- 根因分析：${item.root_cause || '-'}`)
      lines.push(`- 修复策略：${item.fix_plan || '-'}`)
      lines.push(`- 插桩建议：${item.inst_sugg || '-'}`)
    })
  } else {
    lines.push('- 暂无修复计划')
  }
  lines.push('')
  lines.push('## 七、Lesson')
  if (lessonList.value.length) {
    lessonList.value.forEach(item => {
      lines.push(`- 第 ${item.round_no} 轮 | 错误模式：${item.bad_pattern || '-'} | 经验：${item.lesson_text || '-'}`)
    })
  } else {
    lines.push('- 暂无 Lesson 记录')
  }
  lines.push('')
  lines.push('## 八、代码快照')
  lines.push('### 原始代码')
  lines.push('```python')
  lines.push(initCode.value || '')
  lines.push('```')
  lines.push('### 当前代码')
  lines.push('```python')
  lines.push(curCode.value || '')
  lines.push('```')
  if (bestCode.value) {
    lines.push('### 最佳代码')
    lines.push('```python')
    lines.push(bestCode.value)
    lines.push('```')
  }
  return lines.join('\n')
}

function exportTaskReport() {
  if (!taskInfo.value?.id) {
    ElMessage.warning('当前没有可导出的任务')
    return
  }
  const text = buildTaskReportText()
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const safeTitle = (taskInfo.value?.title || `task_${taskInfo.value?.id}`).replace(/[\\/:*?"<>|\s]+/g, '_')
  a.href = url
  a.download = `${safeTitle}_report.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('任务报告已导出')
}

onMounted(async () => {
  snapshotSuspend.value = true
  try {
    await Promise.all([
      loadDatasetOptions(),
      loadTaskList(),
      ensureSessionReady()
    ])

    const taskIdFromRoute = route.query.taskId
    if (taskIdFromRoute) {
      await tryOpenTaskById(taskIdFromRoute)
    } else {
      await restoreWorkbenchSnapshot()
    }
  } catch (error) {
    ElMessage.error(error?.message || '工作台初始化失败')
  } finally {
    snapshotSuspend.value = false
    persistWorkbenchSnapshot()
  }
})

onActivated(async () => {
  const taskIdFromRoute = route.query.taskId
  snapshotSuspend.value = true
  try {
    if (taskIdFromRoute && Number(taskIdFromRoute) !== Number(activeTaskId.value || 0)) {
      await tryOpenTaskById(taskIdFromRoute)
    } else if (!taskIdFromRoute && !taskInfo.value?.id) {
      await restoreWorkbenchSnapshot()
    }
  } catch (error) {
    ElMessage.error(error?.message || '工作台恢复失败')
  } finally {
    snapshotSuspend.value = false
    persistWorkbenchSnapshot()
  }
})

onDeactivated(() => {
  persistWorkbenchSnapshot()
})

watch(
  () => route.query.taskId,
  async (taskId) => {
    if (!taskId) return
    const num = Number(taskId)
    if (!num || num === Number(activeTaskId.value || 0)) return
    try {
      await tryOpenTaskById(num)
    } catch (error) {
      ElMessage.error(error?.message || '任务加载失败')
    }
  }
)

watch(form, () => {
  persistWorkbenchSnapshot()
}, { deep: true })

watch([activeTaskId, currentVerId, compareVerId, currentRunId, codeTab, detailTab], () => {
  persistWorkbenchSnapshot()
})
</script>

<style scoped>
.workbench-page {
  min-height: 100%;
  padding: 16px;
  background: #f5f7fa;
  box-sizing: border-box;
}

.top-card {
  margin-bottom: 16px;
  border-radius: 16px;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.top-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.page-subtitle {
  font-size: 13px;
  color: #909399;
}

.top-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rollback-run-banner {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  flex-wrap: wrap;
}

.rollback-run-banner.pending {
  background: #fff7e6;
  border: 1px solid #f7d9a8;
}

.rollback-run-banner.success {
  background: #f0f9eb;
  border: 1px solid #c2e7b0;
}

.rollback-run-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rollback-run-title {
  font-size: 14px;
  font-weight: 700;
  color: #303133;
}

.rollback-run-desc {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.summary-row {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  padding: 12px 14px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 12px;
}

.summary-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: #909399;
}

.summary-value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  word-break: break-all;
}

.main-grid {
  display: grid;
  grid-template-columns: 340px 1fr 400px;
  gap: 16px;
  align-items: start;
}

.input-panel-card :deep(.el-card__body) {
  max-height: calc(100vh - 220px);
  overflow: auto;
  padding-right: 12px;
}

.left-panel,
.middle-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.panel-card {
  border-radius: 16px;
}

.fill-card {
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
  color: #303133;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.small-tip {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}

.inline-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.switch-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: start;
}

.switch-group-3 {
  grid-template-columns: 1fr 1fr 1fr;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: 40px;
  gap: 12px;
  align-items: stretch;
}

.action-cell {
  min-width: 0;
  height: 40px;
  display: flex;
  align-items: stretch;
}

.action-grid .el-button {
  width: 100%;
  min-width: 0;
  height: 40px;
  margin: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.action-grid-spacer {
  visibility: hidden;
}

.action-save-cell {
  grid-column: 2;
}

.action-save-btn {
  width: 100%;
}

.sess-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.sess-current-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  word-break: break-all;
}

.flag-feedback {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.flag-chip {
  padding: 10px 12px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 140px;
}

.flag-chip.wide {
  flex: 1;
  min-width: 260px;
}

.chip-label {
  font-size: 12px;
  color: #909399;
}

.chip-value {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
}

.local-flag-tip {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px dashed #dcdfe6;
  color: #606266;
  font-size: 12px;
  line-height: 1.7;
}

.compact-lines {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  cursor: pointer;
  background: #fff;
  transition: all 0.2s ease;
}

.history-item:hover {
  border-color: #c6e2ff;
  background: #f7fbff;
}

.history-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.history-main {
  min-width: 0;
}

.history-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
  word-break: break-all;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #909399;
}

.history-id {
  flex-shrink: 0;
  font-size: 12px;
  color: #909399;
}

.code-tabs :deep(.el-tabs__content) {
  min-height: 440px;
}

.code-panel {
  min-height: 440px;
  max-height: 560px;
  overflow: auto;
  border-radius: 12px;
  background: #e8f4fc;
  border: 1px solid #b3d9ff;
}

.code-block {
  margin: 0;
  padding: 16px;
  color: #1f2937;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Fira Code', 'Consolas', 'Courier New', monospace;
}

.diff-block {
  color: #0f172a;
}

.diff-compare-tip {
  margin-bottom: 14px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.diff-compare-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.diff-compare-title {
  font-size: 14px;
  font-weight: 700;
  color: #1d4ed8;
}

.diff-compare-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.7;
}

.diff-compare-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 36px minmax(0, 1fr);
  gap: 10px;
  align-items: stretch;
}

.diff-compare-card {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #dbeafe;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.diff-compare-card.to {
  border-color: #c7e0b4;
}

.diff-card-label {
  font-size: 12px;
  color: #64748b;
}

.diff-card-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.diff-card-ver {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.diff-card-note {
  font-size: 12px;
  color: #475569;
  line-height: 1.7;
  word-break: break-word;
}

.diff-compare-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  color: #60a5fa;
}

.timeline-box {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  cursor: pointer;
}

.timeline-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-weight: 600;
  color: #303133;
}

.timeline-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.timeline-desc {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.timeline-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.best-mark {
  color: #67c23a;
}


.action-stat-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.action-stat-head {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.action-stat-kpi {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.action-stat-kpi.accept {
  background: #f0f9eb;
  border-color: #c2e7b0;
}

.action-stat-kpi.continue {
  background: #fff7e6;
  border-color: #f7d9a8;
}

.action-stat-kpi.rollback {
  background: #fef0f0;
  border-color: #f3c0c0;
}

.kpi-label {
  font-size: 12px;
  color: #606266;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.action-combo-box {
  padding: 12px;
  border-radius: 14px;
  border: 1px solid #ebeef5;
  background: #fcfcfd;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-combo-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.action-combo-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.action-combo-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.legend-dot.pass {
  background: #79bbff;
}

.legend-dot.best {
  background: #9b6bff;
}

.action-combo-chart-wrap {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.action-combo-chart {
  width: 100%;
  min-width: 640px;
  height: 260px;
  display: block;
}

.combo-grid-line {
  stroke: #ebeef5;
  stroke-width: 1;
}

.combo-axis-text {
  font-size: 11px;
  fill: #909399;
}

.combo-bar {
  fill: #79bbff;
  opacity: 0.92;
}

.combo-bar.combo-accept {
  fill: #67c23a;
}

.combo-bar.combo-continue {
  fill: #e6a23c;
}

.combo-bar.combo-rollback {
  fill: #f56c6c;
}

.combo-bar-text {
  font-size: 11px;
  fill: #606266;
}

.combo-best-line {
  fill: none;
  stroke: #9b6bff;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.combo-best-dot {
  fill: #9b6bff;
  stroke: #ffffff;
  stroke-width: 2;
}

.combo-best-text {
  font-size: 11px;
  fill: #7c4dff;
}

.combo-action-text {
  font-size: 11px;
  font-weight: 600;
}

.combo-action-text.action-accept {
  fill: #4e8f2b;
}

.combo-action-text.action-continue {
  fill: #9a6d18;
}

.combo-action-text.action-rollback {
  fill: #c45656;
}

.action-mini-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-bar-row {
  display: grid;
  grid-template-columns: 76px 1fr 40px;
  gap: 10px;
  align-items: center;
}

.action-bar-label,
.action-bar-value {
  font-size: 12px;
  color: #606266;
}

.action-bar-value {
  text-align: right;
  font-weight: 600;
  color: #303133;
}

.action-bar-track {
  height: 12px;
  border-radius: 999px;
  background: #f2f3f5;
  overflow: hidden;
}

.action-bar-fill {
  height: 100%;
  border-radius: 999px;
  min-width: 8px;
}

.action-bar-fill.bar-accept {
  background: linear-gradient(90deg, #8fd16a, #67c23a);
}

.action-bar-fill.bar-continue {
  background: linear-gradient(90deg, #f7c96b, #e6a23c);
}

.action-bar-fill.bar-rollback {
  background: linear-gradient(90deg, #f59a9a, #f56c6c);
}

.action-round-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-round-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid #ebeef5;
  background: #fafafa;
  color: #606266;
}

.action-round-chip.chip-accept {
  background: #f0f9eb;
  border-color: #c2e7b0;
  color: #4e8f2b;
}

.action-round-chip.chip-continue {
  background: #fff7e6;
  border-color: #f7d9a8;
  color: #9a6d18;
}

.action-round-chip.chip-rollback {
  background: #fef0f0;
  border-color: #f3c0c0;
  color: #c45656;
}

.feedback-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feedback-stale-tip {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff7e6;
  border: 1px solid #f7d9a8;
  color: #8c6c1f;
  font-size: 13px;
  line-height: 1.7;
}

.feedback-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  background: #fafafa;
}

.feedback-label {
  font-size: 13px;
  color: #606266;
}

.feedback-value {
  font-size: 13px;
  color: #303133;
  font-weight: 600;
  word-break: break-all;
  text-align: right;
}

.feedback-block {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  overflow: hidden;
}

.feedback-block-title {
  padding: 10px 12px;
  background: #f5f7fa;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.feedback-block-body {
  padding: 12px;
  font-size: 13px;
  color: #606266;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.code-focus-tip {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #d9ecff;
  border-radius: 10px;
  background: #f5f9ff;
}

.code-focus-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.code-focus-title {
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}

.code-focus-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.code-focus-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}


.fixed-scroll-body {
  min-height: 300px;
  max-height: 300px;
  overflow-y: auto;
}

.fixed-body-case,
.fixed-body-case-result,
.fixed-body-feedback,
.fixed-body-run {
  padding-right: 2px;
}

.fixed-body-feedback {
  min-height: 360px;
  max-height: 360px;
}

.action-stat-body {
  min-height: 0;
}

.fixed-body-run {
  min-height: 280px;
  max-height: 280px;
}

.fixed-body-trace {
  min-height: 300px;
  max-height: 300px;
}

.detail-tabs :deep(.el-tabs__content) {
  min-height: 320px;
}

@media (max-width: 1440px) {
  .main-grid {
    grid-template-columns: 320px 1fr 380px;
  }

  .summary-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: 1fr;
  }

  .summary-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}


.run-id-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.run-mark-empty {
  color: #c0c4cc;
}

:deep(.rollback-retest-row) {
  background: #fff8e8;
}

:deep(.rollback-retest-row:hover > td.el-table__cell) {
  background: #fff3d6 !important;
}

@media (max-width: 768px) {
  .workbench-page {
    padding: 10px;
  }

  .summary-row,
  .inline-grid,
  .switch-group,
  .action-grid,
  .action-stat-head {
    grid-template-columns: 1fr;
  }

  .top-bar,
  .panel-header,
  .header-tools,
  .sess-row {
    align-items: flex-start;
    flex-direction: column;
  }
}

.auto-action-timeline-mark {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #ebeef5;
  background: #fafafa;
}

.auto-action-timeline-mark.action-accept {
  background: #f0f9eb;
  border-color: #c2e7b0;
}

.auto-action-timeline-mark.action-continue {
  background: #fff7e6;
  border-color: #f7d9a8;
}

.auto-action-timeline-mark.action-rollback {
  background: #fef0f0;
  border-color: #f3c0c0;
}

.auto-action-timeline-title {
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}

.auto-action-timeline-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #606266;
}

.run-mark-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.el-table .auto-action-row-accept) td {
  background: #f6ffed;
}

:deep(.el-table .auto-action-row-continue) td {
  background: #fffaf0;
}

:deep(.el-table .auto-action-row-rollback) td {
  background: #fff5f5;
}


.timeline-box.active {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.12);
  background: #f5f9ff;
}

.current-run-row > td {
  background: #eef6ff !important;
}

.combo-hit-area {
  fill: transparent;
  cursor: pointer;
}

.combo-item-group,
.combo-point-group {
  cursor: pointer;
}

.combo-item-group.selected .combo-bar {
  stroke: #303133;
  stroke-width: 2;
}

.combo-point-group.selected .combo-best-dot {
  stroke: #303133;
  stroke-width: 3;
}

.click-tip {
  color: #409eff;
}

.detail-section {
  margin-top: 16px;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}

.detail-pre {
  margin: 0;
  padding: 12px 14px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: #606266;
  background: #f7f9fc;
  border: 1px solid #ebeef5;
  border-radius: 12px;
}


.field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}

.field-head-between {
  gap: 12px;
  flex-wrap: wrap;
}

.field-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.case-hint-input {
  margin-bottom: 8px;
}

.case-cell {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}

.case-pop-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

.full-field {
  width: 100%;
}

.code-line {
  display: block;
  min-height: 1.6em;
}

.code-line-added {
  background: rgba(103, 194, 58, 0.15);
  color: #166534;
}

.code-line-removed {
  background: rgba(245, 108, 108, 0.15);
  color: #991b1b;
}

.code-line-focus {
  background: rgba(64, 158, 255, 0.15);
  color: #1e40af;
}


.legacy-case-alert {
  margin-top: 10px;
}

.draft-tip {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f4f4f5;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
}
</style>

