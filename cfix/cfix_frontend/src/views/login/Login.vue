<template>
  <div class="login-page">
    <div class="login-bg"></div>
    <div class="login-card-wrap">
      <el-card class="login-card" shadow="always">
        <div class="login-head">
          <div class="login-title">基于代码执行反馈的代码生成与自修复系统</div>
          <div class="login-subtitle">登录后进入代码自修复工作台，体验“生成 - 执行 - 反馈 - 修复”的闭环流程。</div>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="handleLogin">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" clearable size="large" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password clearable size="large" />
          </el-form-item>

          <div class="login-tip">当前后端支持“用户不存在时自动注册并登录”，便于原型联调。</div>
          <el-button class="login-btn" type="primary" size="large" :loading="loading" @click="handleLogin">登录并进入系统</el-button>
        </el-form>

        <div class="demo-box">
          <div class="demo-title">联调示例</div>
          <div class="demo-text">用户名：test01</div>
          <div class="demo-text">密码：123456</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
// 登录页面，负责输入账号并恢复用户登录态。
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'
import { useUserStore } from '@/store'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: 'test01', password: '123456' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const res = await login({ username: form.username.trim(), password: form.password })
    const token = res?.data?.access_token
    const tokenType = res?.data?.token_type || 'bearer'
    if (!token) throw new Error('登录成功，但未获取到 token')

    userStore.setLogin({ access_token: token, token_type: tokenType, username: form.username.trim() })
    ElMessage.success('登录成功')

    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' ? redirect : '/workbench')
  } catch (error) {
    ElMessage.error(error?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { position:relative; min-height:100vh; overflow:hidden; background:linear-gradient(135deg,#eef4ff 0%,#f7f9fc 45%,#eef7f8 100%); }
.login-bg { position:absolute; inset:0; background:radial-gradient(circle at 20% 20%, rgba(64, 158, 255, 0.16), transparent 22%), radial-gradient(circle at 80% 18%, rgba(103, 194, 58, 0.12), transparent 18%), radial-gradient(circle at 78% 80%, rgba(230, 162, 60, 0.12), transparent 16%); }
.login-card-wrap { position:relative; z-index:1; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }
.login-card { width:100%; max-width:520px; border-radius:20px; border:1px solid #ebeef5; }
.login-head { margin-bottom:20px; }
.login-title { font-size:24px; line-height:1.4; font-weight:700; color:#303133; margin-bottom:10px; }
.login-subtitle { font-size:14px; line-height:1.8; color:#606266; }
.login-tip { margin:2px 0 16px; font-size:13px; line-height:1.7; color:#909399; }
.login-btn { width:100%; margin-top:6px; }
.demo-box { margin-top:22px; padding:14px 16px; border-radius:14px; background:#f5f7fa; border:1px solid #ebeef5; }
.demo-title { font-size:13px; font-weight:600; color:#303133; margin-bottom:8px; }
.demo-text { font-size:13px; color:#606266; line-height:1.8; }
@media (max-width: 768px) {
  .login-card-wrap { padding:14px; }
  .login-title { font-size:20px; }
}
</style>
