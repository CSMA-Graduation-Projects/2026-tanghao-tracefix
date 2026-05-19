<template>
  <div class="page-wrap">
    <PageHead title="系统设置" desc="本页同时维护前端默认参数和当前登录用户的大模型调用配置。" />

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card class="page-card" shadow="never">
          <template #header><span>本地显示设置</span></template>
          <el-form label-position="top">
            <el-form-item label="默认 API 地址">
              <el-input :model-value="apiBaseUrl" disabled />
            </el-form-item>
            <el-form-item label="建议最大修复轮次">
              <el-input-number v-model="localSetting.maxRound" :min="1" :max="10" />
            </el-form-item>
            <el-form-item label="默认开启 Trace">
              <el-switch v-model="localSetting.traceOn" />
            </el-form-item>
            <el-form-item label="默认开启 Lesson">
              <el-switch v-model="localSetting.lessonOn" />
            </el-form-item>
            <el-form-item label="默认通过即停">
              <el-switch v-model="localSetting.stopOnPass" />
            </el-form-item>
            <el-button type="primary" @click="save">保存到本地</el-button>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card v-loading="modelLoading" class="page-card model-card" shadow="never">
          <template #header>
            <div class="model-card-head">
              <span>大模型 API 配置</span>
              <el-tag :type="activeProvider ? 'success' : 'info'" effect="light">
                {{ activeProviderLabel }}
              </el-tag>
            </div>
          </template>

          <el-form label-position="top" @submit.prevent>
            <el-form-item label="模型提供方">
              <el-radio-group v-model="selectedProvider" class="provider-group">
                <el-radio-button
                  v-for="item in providerOptions"
                  :key="item.provider"
                  :label="item.provider"
                >
                  {{ item.label }}
                </el-radio-button>
              </el-radio-group>
            </el-form-item>

            <div class="model-meta-bar">
              <div class="meta-chip">
                <span class="meta-label">默认 URL</span>
                <span class="meta-value">{{ currentProviderMeta.default_base_url || '-' }}</span>
              </div>
              <el-button text @click="resetProviderDefaults">恢复默认值</el-button>
            </div>

            <div class="inline-grid compact-grid">
              <el-form-item label="配置名称">
                <el-input v-model="modelForm.name" placeholder="例如：我的 OpenAI 配置" clearable />
              </el-form-item>
              <el-form-item label="模型 API 名称">
                <el-input v-model="modelForm.model_key" placeholder="例如：gpt-4.1-mini" clearable />
              </el-form-item>
            </div>

            <el-form-item label="URL">
              <el-input v-model="modelForm.base_url" placeholder="选择模型后将自动填充默认地址" clearable />
            </el-form-item>

            <div class="inline-grid compact-grid">
              <el-form-item label="最大输出 Token">
                <el-input-number
                  v-model="modelForm.max_tok"
                  :min="1"
                  :max="32768"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="是否启用">
                <div class="switch-line">
                  <el-switch v-model="modelForm.enabled" />
                  <span class="switch-text">保存后允许系统调用该配置</span>
                </div>
              </el-form-item>
            </div>

            <el-form-item label="API Key">
              <el-input
                :model-value="apiKeyDisplay"
                :placeholder="apiKeyPlaceholder"
                clearable
                @focus="beginApiKeyEdit"
                @update:model-value="handleApiKeyInput"
              >
                <template #append>
                  <el-button @click="toggleApiKeyEdit">
                    {{ apiKeyEditing ? '取消编辑' : (hasStoredApiKey ? '更新密钥' : '输入密钥') }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                输入时显示明文，保存后前端仅展示前三位和后三位，中间自动遮罩。
              </div>
            </el-form-item>

            <div class="model-status-row">
              <div class="meta-chip" :class="{ active: modelForm.is_active }">
                <span class="meta-label">保存后生效</span>
                <span class="meta-value">{{ modelForm.is_active ? '是' : '否' }}</span>
              </div>
              <div class="meta-chip" :class="{ active: hasStoredApiKey }">
                <span class="meta-label">密钥状态</span>
                <span class="meta-value">{{ hasStoredApiKey ? '已保存' : '未配置' }}</span>
              </div>
            </div>

            <div class="action-row">
              <el-checkbox v-model="modelForm.is_active">保存后设为当前系统默认模型</el-checkbox>
              <div class="action-buttons">
                <el-button @click="loadModelSetting">重新加载</el-button>
                <el-button type="primary" :loading="modelSaving" @click="saveModelSetting">
                  保存模型配置
                </el-button>
              </div>
            </div>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// 系统设置页面，负责模型和系统参数配置。
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PageHead from '@/comps/PageHead.vue'
import { getModelConfig, saveModelConfig } from '@/api/model'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

const fallbackProviders = [
  {
    provider: 'qwen',
    label: 'Qwen',
    default_model_key: 'qwen3-coder-next',
    default_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    default_max_tok: 4096,
    default_temp: 0.2
  },
  {
    provider: 'deepseek',
    label: 'DeepSeek',
    default_model_key: 'deepseek-chat',
    default_base_url: 'https://api.deepseek.com/v1',
    default_max_tok: 4096,
    default_temp: 0.2
  },
  {
    provider: 'openai',
    label: 'OpenAI',
    default_model_key: 'gpt-4.1-mini',
    default_base_url: 'https://api.openai.com/v1',
    default_max_tok: 4096,
    default_temp: 0.2
  }
]

const localSetting = reactive({
  maxRound: Number(localStorage.getItem('cfix_max_round') || 3),
  traceOn: localStorage.getItem('cfix_trace_on') !== '0',
  lessonOn: localStorage.getItem('cfix_lesson_on') !== '0',
  stopOnPass: localStorage.getItem('cfix_stop_on_pass') !== '0'
})

const providerOptions = ref([...fallbackProviders])
const selectedProvider = ref('qwen')
const activeProvider = ref('')
const configsMap = ref({})
const modelLoading = ref(false)
const modelSaving = ref(false)
const apiKeyEditing = ref(false)
const apiKeyMasked = ref('')
const apiKeyRaw = ref('')
const hasStoredApiKey = ref(false)

const modelForm = reactive({
  name: '',
  model_key: '',
  base_url: '',
  max_tok: 4096,
  enabled: true,
  is_active: true
})

const currentProviderMeta = computed(() => {
  return providerOptions.value.find(item => item.provider === selectedProvider.value) || providerOptions.value[0] || fallbackProviders[0]
})

const activeProviderLabel = computed(() => {
  const target = providerOptions.value.find(item => item.provider === activeProvider.value)
  return target ? `当前生效：${target.label}` : '当前生效：未设置'
})

const apiKeyDisplay = computed(() => (apiKeyEditing.value ? apiKeyRaw.value : apiKeyMasked.value))

const apiKeyPlaceholder = computed(() => {
  if (apiKeyEditing.value) return '请输入当前提供方的 API Key'
  if (hasStoredApiKey.value) return '已保存 API Key，点击右侧按钮可重新输入'
  return '请输入当前提供方的 API Key'
})

function fillFormFromProvider(provider, { keepActive = true } = {}) {
  const meta = providerOptions.value.find(item => item.provider === provider) || currentProviderMeta.value
  const saved = configsMap.value?.[provider] || {}
  const hasExplicitActive = Boolean(activeProvider.value)

  modelForm.name = saved.name || meta?.label || provider
  modelForm.model_key = saved.model_key || meta?.default_model_key || ''
  modelForm.base_url = saved.base_url || meta?.default_base_url || ''
  modelForm.max_tok = Number(saved.max_tok || meta?.default_max_tok || 4096)
  modelForm.enabled = saved.enabled ?? true
  if (!keepActive) {
    modelForm.is_active = true
  } else if (saved.id != null) {
    modelForm.is_active = hasExplicitActive ? (provider === activeProvider.value || Boolean(saved.is_active)) : Boolean(saved.enabled ?? true)
  } else {
    modelForm.is_active = provider === activeProvider.value || !hasExplicitActive
  }

  hasStoredApiKey.value = Boolean(saved.has_api_key)
  apiKeyMasked.value = saved.api_key_masked || ''
  apiKeyRaw.value = ''
  apiKeyEditing.value = false
}

function resetProviderDefaults() {
  const meta = currentProviderMeta.value
  modelForm.name = meta?.label || selectedProvider.value
  modelForm.model_key = meta?.default_model_key || ''
  modelForm.base_url = meta?.default_base_url || ''
  modelForm.max_tok = Number(meta?.default_max_tok || 4096)
  modelForm.enabled = true
  ElMessage.success('已恢复当前提供方默认值')
}

function beginApiKeyEdit() {
  if (!apiKeyEditing.value) {
    apiKeyEditing.value = true
    apiKeyRaw.value = ''
  }
}

function toggleApiKeyEdit() {
  if (apiKeyEditing.value) {
    apiKeyEditing.value = false
    apiKeyRaw.value = ''
    return
  }
  beginApiKeyEdit()
}

function handleApiKeyInput(value) {
  if (!apiKeyEditing.value) {
    apiKeyEditing.value = true
  }
  apiKeyRaw.value = value
}

function hydrateModelPayload(payload, preferredProvider = '') {
  providerOptions.value = payload?.providers?.length ? payload.providers : [...fallbackProviders]
  configsMap.value = payload?.configs || {}
  activeProvider.value = payload?.active_provider || ''

  const nextProvider = preferredProvider || payload?.active_provider || selectedProvider.value || providerOptions.value[0]?.provider || 'qwen'
  selectedProvider.value = nextProvider
  fillFormFromProvider(nextProvider)
}

async function loadModelSetting() {
  modelLoading.value = true
  try {
    const res = await getModelConfig()
    hydrateModelPayload(res.data || {})
  } catch (error) {
    providerOptions.value = [...fallbackProviders]
    configsMap.value = {}
    selectedProvider.value = providerOptions.value[0]?.provider || 'qwen'
    fillFormFromProvider(selectedProvider.value)
    ElMessage.error(error?.message || '加载模型配置失败')
  } finally {
    modelLoading.value = false
  }
}

async function saveModelSetting() {
  if (!modelForm.model_key.trim()) {
    ElMessage.warning('请填写模型 API 名称')
    return
  }
  if (!modelForm.base_url.trim()) {
    ElMessage.warning('请填写模型 URL')
    return
  }
  if (!hasStoredApiKey.value && !apiKeyRaw.value.trim()) {
    ElMessage.warning('请先输入 API Key')
    return
  }

  modelSaving.value = true
  try {
    const res = await saveModelConfig({
      provider: selectedProvider.value,
      name: modelForm.name.trim(),
      model_key: modelForm.model_key.trim(),
      base_url: modelForm.base_url.trim(),
      max_tok: Number(modelForm.max_tok || 4096),
      enabled: Boolean(modelForm.enabled),
      is_active: Boolean(modelForm.is_active),
      api_key: apiKeyEditing.value ? apiKeyRaw.value.trim() : ''
    })

    hydrateModelPayload(res.data || {}, selectedProvider.value)
    ElMessage.success('模型配置已保存')
  } catch (error) {
    ElMessage.error(error?.message || '保存模型配置失败')
  } finally {
    modelSaving.value = false
  }
}

function save() {
  localStorage.setItem('cfix_max_round', String(localSetting.maxRound))
  localStorage.setItem('cfix_trace_on', localSetting.traceOn ? '1' : '0')
  localStorage.setItem('cfix_lesson_on', localSetting.lessonOn ? '1' : '0')
  localStorage.setItem('cfix_stop_on_pass', localSetting.stopOnPass ? '1' : '0')
  ElMessage.success('本地设置已保存')
}

watch(selectedProvider, value => {
  if (!value) return
  fillFormFromProvider(value)
})

onMounted(() => {
  fillFormFromProvider(selectedProvider.value)
  loadModelSetting()
})
</script>

<style scoped>
.model-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.provider-group {
  display: flex;
  width: 100%;
}

.provider-group :deep(.el-radio-button) {
  flex: 1;
}

.provider-group :deep(.el-radio-button__inner) {
  width: 100%;
}

.inline-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.compact-grid {
  align-items: start;
}

.model-meta-bar,
.action-row,
.model-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.model-meta-bar {
  margin-bottom: 12px;
}

.model-status-row {
  margin-bottom: 12px;
}

.meta-chip {
  min-width: 0;
  flex: 1;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef3ff 100%);
  border: 1px solid #dbe7ff;
}

.meta-chip.active {
  border-color: #b7e1c4;
  background: linear-gradient(135deg, #f4fff8 0%, #ecfbf2 100%);
}

.meta-label {
  display: block;
  font-size: 12px;
  color: #7a8799;
  margin-bottom: 6px;
}

.meta-value {
  display: block;
  font-size: 13px;
  color: #22304a;
  line-height: 1.5;
  word-break: break-all;
}

.switch-line {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 32px;
}

.switch-text,
.field-tip {
  font-size: 12px;
  color: #7a8799;
  line-height: 1.7;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 992px) {
  .inline-grid {
    grid-template-columns: 1fr;
  }
}
</style>
