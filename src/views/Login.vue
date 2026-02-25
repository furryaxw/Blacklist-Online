<template>
  <div class="login-container">
    <div class="login-bg"></div>
    <n-card class="login-card" :bordered="false" size="large">
      <div class="header">
        <img src="/apple-touch-icon.png" class="logo-image" alt="Logo"/>
        <h2>Shield Admin</h2>
        <p>安全 · 高效 · 简洁</p>
      </div>

      <n-tabs default-value="code" size="large" justify-content="space-evenly" animated>
        <n-tab-pane name="code" tab="验证码登录">
          <n-form size="large">
            <n-form-item :show-label="false">
              <n-input
                  v-model:value="form.qq"
                  placeholder="管理员 QQ 号"
                  :allow-input="onlyAllowNumber"
                  :maxlength="11"
                  clearable
              >
                <template #prefix>📱</template>
              </n-input>
            </n-form-item>

            <n-form-item :show-label="false">
              <n-input-group>
                <n-input
                    v-model:value="form.code"
                    placeholder="6 位验证码"
                    :maxlength="6"
                    :allow-input="onlyAllowNumber"
                    @keydown.enter="login"
                >
                  <template #prefix>🔒</template>
                </n-input>
                <n-button :disabled="cooldown > 0" @click="sendCode" ghost type="primary">
                  {{ cooldown > 0 ? `${cooldown}s` : '获取' }}
                </n-button>
              </n-input-group>
            </n-form-item>

            <div class="actions">
              <n-checkbox v-model:checked="rememberMe">自动登录</n-checkbox>
            </div>

            <n-button type="primary" block @click="login" :loading="loading" size="large" style="margin-top: 20px">
              进入系统
            </n-button>

            <div style="margin-top: 16px; text-align: center;">
              <n-button text type="primary" size="small" @click="$router.push('/appeal')">
                账号被误封？自助申诉
              </n-button>
            </div>
          </n-form>
        </n-tab-pane>
      </n-tabs>
    </n-card>


    <n-card
        v-if="contactInfoHtml"
        size="small"
        :bordered="false"
        class="contact-card"
    >
      <div class="contact-markdown" v-html="contactInfoHtml"></div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {NButton, NCard, NCheckbox, NForm, NFormItem, NInput, NInputGroup, NTabPane, NTabs, useMessage} from 'naive-ui'
import {wsClient} from '../api/ws'
import {userStore} from "../store/user";
import FingerprintJS from '@fingerprintjs/fingerprintjs'
import {marked} from "marked";

const router = useRouter()
const message = useMessage()
const form = ref({
  qq: '',
  code: '',
  fingerprint: ''
})
const loading = ref(false)
const cooldown = ref(0)
const rememberMe = ref(false)
const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

const contactInfoHtml = ref('')

// 拉取联系信息
const fetchPublicConfig = async () => {
  try {
    const res = await wsClient.call('admin.system.get_public')
    if (res && res.LOGIN_CONTACT_MD) {
      contactInfoHtml.value = await marked.parse(res.LOGIN_CONTACT_MD)
    }
  } catch (e) {
    console.warn('获取联系信息失败:', e)
  }
}

// 1. 页面加载时：自动拉取 localStorage 中的 QQ 号并填充
onMounted(async () => {
  const savedQQ = localStorage.getItem('remembered_qq')
  // 如果存在保存的 QQ，则自动填充并勾选“自动登录”
  if (savedQQ) {
    form.value.qq = savedQQ
    rememberMe.value = true
  }
  try {
    const fpPromise = await FingerprintJS.load()
    const result = await fpPromise.get()
    form.value.fingerprint = result.visitorId
    console.log('Device Fingerprint:', form.value.fingerprint)
  } catch (e) {
    console.error('指纹生成失败', e)
    // 降级处理：生成一个随机指纹或阻止登录，视安全要求而定
    form.value.fingerprint = 'unknown_device_' + Math.random().toString(36).slice(2)
  }
  await fetchPublicConfig()
})

const sendCode = async () => {
  if (!form.value.qq) return message.warning('请输入QQ号')
  try {
    await wsClient.call('auth.send_code', {qq: form.value.qq})
    message.success('验证码已发送')
    cooldown.value = 60
    const timer = setInterval(() => {
      cooldown.value--;
      if (cooldown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) {
  }
}

// 2. 登录成功后：固化“记住我”的选项逻辑
const login = async () => {
  if (!form.value.code) return message.warning('请输入验证码')
  loading.value = true
  try {
    const res = await wsClient.call('auth.login', form.value)

    userStore.setUserInfo(res.user)

    // === 区分存储策略 ===
    if (rememberMe.value) {
      // 场景 A：勾选了“记住我” -> 使用 localStorage (持久化)
      // 1. 保存 Token 到持久存储
      localStorage.setItem('token', res.access_token)
      // 2. 保存 QQ 号方便下次回显
      localStorage.setItem('remembered_qq', form.value.qq)

      // 3. 清理 sessionStorage (防止状态混淆)
      sessionStorage.removeItem('token')
    } else {
      // 场景 B：未勾选 (公共设备) -> 使用 sessionStorage (即用即焚)
      // 1. 保存 Token 到会话存储 (关闭浏览器即消失)
      sessionStorage.setItem('token', res.access_token)

      // 2. 为了安全，必须清除可能残留的持久化数据
      localStorage.removeItem('token')
      localStorage.removeItem('remembered_qq')
    }

    message.success('欢迎回来')
    router.push('/dashboard')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
  background-color: #0f172a;
}

/* 动态背景 */
.login-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(circle at 10% 20%, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 90%);
  opacity: 0.8;
  z-index: 0;
  filter: blur(80px);
  transform: scale(1.2);
}

.login-card {
  /* 移动端适配 */
  width: 90%;
  max-width: 420px;
  z-index: 1;
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(10px);
  /* 默认亮色模式背景 */
  background-color: rgba(255, 255, 255, 0.9);
  transition: background-color 0.3s, color 0.3s;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.logo-image {
  width: 128px;
  height: 128px;
  margin: 0 16px;
  object-fit: contain;
  transition: all 0.3s var(--n-bezier);
}

.header h2 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.header p {
  margin: 5px 0 0;
  color: #666;
  font-size: 14px;
}

.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* --- 核心修复：暗黑模式适配 (Media Query) --- */
@media (prefers-color-scheme: dark) {
  .login-card {
    /* 暗色背景，带透明度 */
    background-color: rgba(24, 24, 28, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .header h2 {
    color: #fff;
  }

  .header p {
    color: rgba(255, 255, 255, 0.7);
  }
}

.contact-card {
  max-width: 380px;
  margin: 16px auto;
  background: var(--n-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); /* 稍微加点阴影融入背景 */
}

.contact-markdown {
  font-size: 13px;
  line-height: 1.6;
  color: var(--n-text-color);
}

/* 深浅色模式自适应的简单样式 */
:deep(.contact-markdown h1),
:deep(.contact-markdown h2),
:deep(.contact-markdown h3) {
  margin-top: 0;
  margin-bottom: 8px;
  color: var(--n-title-text-color);
  font-size: 15px;
}

:deep(.contact-markdown p) {
  margin: 4px 0;
}

:deep(.contact-markdown ul) {
  padding-left: 20px;
  margin: 4px 0;
}

:deep(.contact-markdown a) {
  color: var(--n-primary-color);
  text-decoration: none;
}
</style>