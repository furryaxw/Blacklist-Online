<template>
  <div class="settings-page">
    <n-card title="⚙️ 设置" :bordered="false">
      <n-tabs type="line" animated>

        <n-tab-pane name="preference" tab="个人偏好">
          <n-form
              :label-placement="isMobile ? 'top' : 'left'"
              :label-width="isMobile ? 'auto' : 200"
              style="max-width: 800px"
          >

            <n-divider title-placement="left">外观与主题</n-divider>

            <n-form-item label="外观模式">
              <n-radio-group v-model:value="themeStore.mode">
                <n-radio-button value="light">☀️ 浅色</n-radio-button>
                <n-radio-button value="auto">🤖 跟随系统</n-radio-button>
                <n-radio-button value="dark">🌙 深色</n-radio-button>
              </n-radio-group>
            </n-form-item>

            <n-form-item label="主题色">
              <n-space>
                <div
                    v-for="color in presetColors"
                    :key="color.value"
                    class="color-dot"
                    :style="{ background: color.value, border: themeStore.primaryColor === color.value ? '2px solid var(--n-text-color)' : 'none' }"
                    @click="themeStore.setColor(color.value)"
                    :title="color.name"
                ></div>
              </n-space>
            </n-form-item>

            <n-form-item label="表格密度">
              <n-radio-group v-model:value="themeStore.density">
                <n-radio-button value="small">紧凑</n-radio-button>
                <n-radio-button value="medium">标准</n-radio-button>
                <n-radio-button value="large">宽敞</n-radio-button>
              </n-radio-group>
            </n-form-item>

            <n-divider title-placement="left">浏览器通知</n-divider>

            <n-form-item label="审批通知" v-if="['owner', 'super_admin', 'admin'].includes(userStore.userInfo.role)">
              <n-switch v-model:value="themeStore.notifyApply" @update:value="onNotifyChange">
                <template #checked>开启</template>
                <template #unchecked>关闭</template>
              </n-switch>
            </n-form-item>

            <n-divider title-placement="left">QQ通知</n-divider>

            <n-form-item label="审批通知" v-if="['owner', 'super_admin', 'admin'].includes(userStore.userInfo.role)">
              <n-switch v-model:value="subs.approval" @update:value="updateSub('approval', $event)">
                <template #checked>开启</template>
                <template #unchecked>关闭</template>
              </n-switch>
            </n-form-item>

            <n-form-item label="账号通知">
              <n-switch v-model:value="subs.account" @update:value="updateSub('account', $event)">
                <template #checked>开启</template>
                <template #unchecked>关闭</template>
              </n-switch>
            </n-form-item>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="system" tab="系统配置" v-if="['owner', 'super_admin'].includes(userStore.userInfo.role)">

          <n-form
              :label-placement="isMobile ? 'top' : 'left'"
              :label-width="isMobile ? 'auto' : 160"
              style="max-width: 900px"
          >
            <n-card size="small" title="⚙️ 基础参数" style="margin-bottom: 16px">
              <n-grid :cols="isMobile ? 1 : 2" :x-gap="24" :y-gap="isMobile ? 12 : 0">
                <n-form-item-gi label="会话超时 (秒)">
                  <n-input-number
                      v-model:value="sysConfig.SESSION_TIMEOUT"
                      :min="60"
                      placeholder="默认 1800"
                      style="width: 100%"
                  />
                </n-form-item-gi>

                <n-form-item-gi label="验证码有效期 (秒)">
                  <n-input-number
                      v-model:value="sysConfig.CODE_TIMEOUT"
                      :min="60"
                      placeholder="默认 300"
                      style="width: 100%"
                  />
                </n-form-item-gi>
              </n-grid>
            </n-card>

            <n-card size="small" title="📝 站点信息" style="margin-bottom: 16px">
              <n-grid :cols="isMobile ? 1 : 2" :x-gap="24" :y-gap="isMobile ? 12 : 0">
                <n-form-item-gi label="登录页联系信息">
                  <n-input
                      v-model:value="sysConfig.LOGIN_CONTACT_MD"
                      type="textarea"
                      placeholder="**🤖 关于 Bot**&#10;💡 *提示：获取验证码前，请先加 Bot*&#10;* **QQ**：12345678"
                      :autosize="{ minRows: 4, maxRows: 10 }"
                  />
                </n-form-item-gi>
                <n-form-item-gi label="控制台联系信息">
                  <n-input
                      v-model:value="sysConfig.DASHBOARD_CONTACT_MD"
                      type="textarea"
                      placeholder="**📞 联系我们**&#10;* **🤖 Bot QQ**：12345678&#10;* **👨‍💻 开发者**：87654321"
                      :autosize="{ minRows: 4, maxRows: 10 }"
                  />
                </n-form-item-gi>
              </n-grid>
            </n-card>

            <n-card size="small" title="💾 数据管理" style="margin-bottom: 16px">
              <n-descriptions bordered label-placement="left" :column="1" size="small">
                <n-descriptions-item label="黑名单数据">
                  <n-space :vertical="isMobile">
                    <n-button size="small" @click="exportData">📤 导出 JSON</n-button>
                    <input type="file" ref="fileInputRef" style="display: none" accept=".json"
                           @change="handleFileImport"/>
                    <n-button size="small" @click="triggerFileInput">📥 导入数据</n-button>
                  </n-space>
                </n-descriptions-item>

                <n-descriptions-item label="日志管理">
                  <n-space :vertical="isMobile">
                    <n-button size="small" @click="exportLogs">📜 导出操作日志</n-button>
                    <n-popconfirm @positive-click="cleanLogs">
                      <template #trigger>
                        <n-button size="small" type="error" secondary>🧹 清理旧日志</n-button>
                      </template>
                      确定删除 30 天前的操作日志吗？此操作不可逆。
                    </n-popconfirm>
                  </n-space>
                </n-descriptions-item>

                <n-descriptions-item label="同步日志">
                  <n-space align="center" :vertical="isMobile" :item-style="isMobile ? {width: '100%'} : {}">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span>保留最近</span>
                      <n-input-number v-model:value="logDays" size="small" style="width: 80px"/>
                      <span>天的 Sync 记录</span>
                    </div>
                    <n-popconfirm @positive-click="cleanSyncLogs">
                      <template #trigger>
                        <n-button type="warning" size="small">清理</n-button>
                      </template>
                      删除旧的同步事件记录（不影响现有黑名单）。
                    </n-popconfirm>
                  </n-space>
                </n-descriptions-item>
              </n-descriptions>
            </n-card>

            <n-card size="small" title="🛡️ 安全与隐私" style="margin-bottom: 16px">
              <n-grid :cols="isMobile ? 1 : 2" :x-gap="24">
                <n-form-item-gi label="加强安全模式">
                  <n-space vertical :size="0">
                    <n-switch
                        v-model:value="sysConfig.ENABLE_SENSITIVE_MASKING"
                        checked-value="true"
                        unchecked-value="false"
                    >
                      <template #checked>开启</template>
                      <template #unchecked>关闭</template>
                    </n-switch>
                    <div style="font-size: 12px; color: #888; margin-top: 4px">
                      开启后，API 返回的敏感配置（如密码、密钥）将以星号脱敏显示。
                    </div>
                  </n-space>
                </n-form-item-gi>
              </n-grid>
            </n-card>

            <n-card size="small" title="🛡️ 注册与权限" style="margin-bottom: 16px">
              <n-grid :cols="isMobile ? 1 : 2" :x-gap="24" :y-gap="isMobile ? 12 : 0">
                <n-form-item-gi label="自动注册">
                  <n-switch
                      v-model:value="sysConfig.ENABLE_AUTO_REG"
                      checked-value="true"
                      unchecked-value="false"
                  >
                    <template #checked>开启</template>
                    <template #unchecked>关闭</template>
                  </n-switch>
                </n-form-item-gi>

                <n-form-item-gi label="默认角色">
                  <n-select
                      v-model:value="sysConfig.DEFAULT_AUTO_ROLE"
                      :options="[
                      { label: '用户 (User)', value: 'user' },
                      { label: '管理员 (Admin)', value: 'admin' }
                    ]"
                      :disabled="sysConfig.ENABLE_AUTO_REG !== 'true'"
                  />
                </n-form-item-gi>
              </n-grid>

              <n-divider style="margin: 12px 0"/>

              <n-form-item label="新 API Key 默认权限">
                <n-checkbox-group v-model:value="sysConfig.DEFAULT_KEY_PERMS">
                  <n-space>
                    <n-checkbox value="read" label="读权限"/>
                    <n-checkbox value="write" label="写权限"/>
                  </n-space>
                </n-checkbox-group>
              </n-form-item>
            </n-card>

            <n-card size="small" title="🤖 Bot 连接配置">
              <n-grid :cols="isMobile ? 1 : 2" :x-gap="24" :y-gap="isMobile ? 12 : 0">
                <n-form-item-gi label="OneBot API 地址">
                  <n-input v-model:value="sysConfig.ONEBOT_API_URL" placeholder="http://127.0.0.1:3000"/>
                </n-form-item-gi>
                <n-form-item-gi label="连接测试">
                  <n-space>
                    <n-button @click="testBot" :loading="testingBot">连通性</n-button>
                    <n-button @click="showBotTestModal = true">发消息</n-button>
                  </n-space>
                </n-form-item-gi>
              </n-grid>
            </n-card>

            <n-card size="small" title="📧 邮件通知配置" style="margin-top: 16px">
              <n-grid :cols="isMobile ? 1 : 2" :x-gap="24" :y-gap="isMobile ? 12 : 0">
                <n-form-item-gi label="SMTP 服务器">
                  <n-input v-model:value="sysConfig.MAIL_HOST" placeholder="例如: smtp.qq.com"/>
                </n-form-item-gi>
                <n-form-item-gi label="SMTP 端口">
                  <n-input v-model:value="sysConfig.MAIL_PORT" placeholder="SSL通常为465"/>
                </n-form-item-gi>
                <n-form-item-gi label="认证账号">
                  <n-input v-model:value="sysConfig.MAIL_USER" placeholder="SMTP登录名"/>
                </n-form-item-gi>
                <n-form-item-gi label="认证密码">
                  <n-input
                      type="password"
                      show-password-on="click"
                      v-model:value="sysConfig.MAIL_PASS"
                      placeholder="SMTP密码 / API Key"
                  />
                </n-form-item-gi>
                <n-form-item-gi label="发件人邮箱">
                  <n-input
                      v-model:value="sysConfig.MAIL_FROM"
                      placeholder="选填。若认证账号与发件地址不同，请在此填写域名邮箱"
                  />
                </n-form-item-gi>
                <n-form-item-gi label="连接测试">
                  <n-button @click="showEmailTestModal = true">发送测试邮件</n-button>
                </n-form-item-gi>
              </n-grid>
            </n-card>

            <div style="margin-top: 20px; text-align: right">
              <n-button type="primary" size="large" @click="saveConfig" :loading="saving" :block="isMobile">
                保存所有系统配置
              </n-button>
            </div>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="about" tab="关于系统">
          <div class="about-content">
            <img src="/apple-touch-icon.png" class="about-logo" alt="Logo"/>
            <h3>Shield Admin</h3>
            <div class="version-info">
              <span style="font-weight: 500;">前端版本：</span>
              <n-tag type="info" size="small" :bordered="false">
                v{{ FRONTEND_VERSION }}
              </n-tag>

              <span style="margin: 0 4px; color: var(--n-text-color-3);">|</span>

              <span style="font-weight: 500;">后端版本：</span>
              <n-tag :type="backendVersionType" size="small" :bordered="false">
                {{ backendVersionStr }}
              </n-tag>
            </div>
            <p class="desc">
              一个轻量级、高效的黑名单管理系统。<br/>
              前端: Vue 3 + Naive UI + Vite<br/>
              后端: Python + FastAPI + SQLite
            </p>
            <n-button text tag="a" href="https://github.com/furryaxw/Blacklist-Online" target="_blank" type="primary">
              GitHub 仓库
            </n-button>
          </div>

          <n-divider title-placement="left">连接状态</n-divider>

          <n-form-item label="WS 延迟">
            <n-space align="center">
              <n-tag :type="wsClient.status.connected ? 'success' : 'error'">
                {{ wsClient.status.connected ? '已连接' : '断开' }}
              </n-tag>
              <span v-if="wsClient.status.connected">往返: {{ wsClient.status.latency }}ms</span>
              <n-button size="small" @click="checkPing">测速</n-button>
            </n-space>
          </n-form-item>
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <n-modal v-model:show="showBotTestModal" preset="dialog" title="测试 Bot 消息发送"
             :style="{width: isMobile ? '90%' : '500px'}">
      <div style="padding-top: 20px;">
        <n-input
            v-model:value="testBotQQ"
            placeholder="请输入接收测试消息的 QQ 号"
            autofocus
        />
      </div>
      <template #action>
        <n-button @click="showBotTestModal = false">取消</n-button>
        <n-button type="primary" :loading="testingBotMsg" @click="runTestBot">发送</n-button>
      </template>
    </n-modal>

    <n-modal v-model:show="showEmailTestModal" preset="dialog" title="测试邮件发送"
             :style="{width: isMobile ? '90%' : '500px'}">
      <div style="padding-top: 20px;">
        <n-input
            v-model:value="testEmailAddr"
            placeholder="请输入接收测试邮件的邮箱"
            autofocus
        />
      </div>
      <template #action>
        <n-button @click="showEmailTestModal = false">取消</n-button>
        <n-button type="primary" :loading="testingEmail" @click="runTestEmail">发送</n-button>
      </template>
    </n-modal>

    <n-modal
        v-model:show="showConfirmModal"
        preset="dialog"
        title="⚠️ 确认保存变更"
        positive-text="确认提交"
        negative-text="取消"
        @positive-click="executeSave"
        @negative-click="showConfirmModal = false"
        style="width: 500px"
    >
      <div v-if="Object.keys(pendingChanges).length > 0">
        <p>检测到以下配置项将被修改：</p>
        <n-table size="small" :single-line="false">
          <thead>
          <tr>
            <th>配置项</th>
            <th>原值</th>
            <th>新值</th>
          </tr>
          </thead>
          <tbody>
          <tr v-for="(change, key) in pendingChanges" :key="key">
            <td>{{ getFieldLabel(key) }} <br/><span style="font-size: 10px; color: #999">({{ key }})</span></td>
            <td style="color: #999; word-break: break-all">{{ formatValue(change.oldVal) }}</td>
            <td style="color: var(--n-primary-color); font-weight: bold; word-break: break-all">
              {{ formatValue(change.newVal) }}
            </td>
          </tr>
          </tbody>
        </n-table>
      </div>
      <div v-else>
        <p>未检测到任何变更。</p>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, onUnmounted, ref, watch} from 'vue'
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NDescriptions,
  NDescriptionsItem,
  NDivider,
  NForm,
  NFormItem,
  NFormItemGi,
  NGrid,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpace,
  NSwitch,
  NTable,
  NTabPane,
  NTabs,
  NTag,
  useMessage
} from 'naive-ui'
import {wsClient} from '../api/ws'
import {presetColors, themeStore} from '../store/theme'
import {userStore} from "../store/user";
import router from "../router";
import {FRONTEND_VERSION, REQUIRED_BACKEND_MAJOR, REQUIRED_BACKEND_MINOR} from "../config";

const message = useMessage()
const fileInputRef = ref<HTMLInputElement | null>(null)

const showBotTestModal = ref(false)
const testingBotMsg = ref(false)
const testBotQQ = ref('')
const showEmailTestModal = ref(false)
const testingEmail = ref(false)
const testEmailAddr = ref('')

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

interface Subscriptions {
  approval: boolean,
  account: boolean
}

const subs = ref<Subscriptions>({
  approval: false,
  account: false
})

// 状态
const sysConfig = ref<any>({ONEBOT_API_URL: '', DEFAULT_KEY_PERMS: ['read', 'write']})
const originalConfig = ref<any>({})
const showConfirmModal = ref(false)
const pendingChanges = ref<Record<string, { oldVal: any, newVal: any }>>({})

const logDays = ref(30)
const saving = ref(false)
const testingBot = ref(false)

// 存储原始版本字符串
const backendVersion = ref('获取中...')

// 计算显示的文本 (处理加载中、失败等状态)
const backendVersionStr = computed(() => {
  const v = backendVersion.value
  if (['获取中...', '获取失败', '未知'].includes(v)) return v
  return `v${v}`
})

// 计算 Tag 颜色类型
const backendVersionType = computed(() => {
  const v = backendVersion.value
  if (['获取中...', '获取失败', '未知'].includes(v)) return 'default'

  try {
    // 假设版本号格式为 x.y.z
    const parts = v.split('.')
    const major = parseInt(parts[0] || '0', 10)
    const minor = parseInt(parts[1] || '0', 10)

    // 判断逻辑：以 主版本(Major) 和 次版本(Minor) 为准
    if (major < REQUIRED_BACKEND_MAJOR || (major === REQUIRED_BACKEND_MAJOR && minor < REQUIRED_BACKEND_MINOR)) {
      return 'error'   // 红色：后端版本过低
    } else if (major > REQUIRED_BACKEND_MAJOR || (major === REQUIRED_BACKEND_MAJOR && minor > REQUIRED_BACKEND_MINOR)) {
      return 'warning' // 橙色：后端版本过高（可能有兼容性风险）
    } else {
      return 'success' // 绿色：版本匹配
    }
  } catch (e) {
    return 'default'
  }
})

// 拉取后端版本
const fetchBackendVersion = async () => {
  try {
    const res: any = await wsClient.call('admin.system.get_public')
    if (res && res.BACKEND_VERSION) {
      // 拿到后端版本号（例如 "1.0.0"）
      backendVersion.value = res.BACKEND_VERSION
    } else {
      backendVersion.value = '未知'
    }
  } catch (e) {
    backendVersion.value = '获取失败'
    console.warn('获取后端版本失败:', e)
  }
}

// === 偏好逻辑 ===
const checkPing = async () => {
  const rtt = await wsClient.sendPing()
  if (rtt < 0) message.error('测速失败')
}

// === 系统逻辑 ===
const onNotifyChange = (val: boolean) => {
  if (val) {
    if (!('Notification' in window)) {
      message.error('当前浏览器不支持系统通知')
      themeStore.notifyApply = false
      return
    }

    if (Notification.permission !== 'granted') {
      Notification.requestPermission().then((permission) => {
        if (permission !== 'granted') {
          message.warning('请在浏览器设置中允许通知权限')
          themeStore.notifyApply = false
        } else {
          new Notification('通知已开启', {body: '您将收到新的审批申请提醒'})
        }
      })
    }
  }
}

const fetchConfig = async () => {
  if (!['owner', 'super_admin'].includes(userStore.userInfo.role)) return
  try {
    const res: any = await wsClient.call('admin.system.get')

    // 处理数据格式
    const processedConfig = {
      ...res,
      SESSION_TIMEOUT: Number(res.SESSION_TIMEOUT || 1800),
      CODE_TIMEOUT: Number(res.CODE_TIMEOUT || 300),
      // 保持数组格式用于前端组件
      DEFAULT_KEY_PERMS: res.DEFAULT_KEY_PERMS ? res.DEFAULT_KEY_PERMS.split(',') : ['read', 'write']
    }

    sysConfig.value = {...processedConfig}

    // 关键：深拷贝一份作为原始对照组
    // 使用 JSON.parse/stringify 简单深拷贝，足以应对配置数据
    originalConfig.value = JSON.parse(JSON.stringify(processedConfig))

  } catch (e) {
    message.error('获取系统配置失败')
  }
}

// === 配置项名称映射（用于弹窗显示中文名） ===
const fieldLabels: Record<string, string> = {
  SESSION_TIMEOUT: '会话超时',
  CODE_TIMEOUT: '验证码有效期',
  ENABLE_SENSITIVE_MASKING: '加强安全模式',
  ENABLE_AUTO_REG: '自动注册开关',
  DEFAULT_AUTO_ROLE: '自动注册默认角色',
  DEFAULT_KEY_PERMS: 'API Key 默认权限',
  ONEBOT_API_URL: 'OneBot API 地址',
  MAIL_HOST: 'SMTP 服务器',
  MAIL_PORT: 'SMTP 端口',
  MAIL_USER: 'SMTP 账号',
  MAIL_PASS: 'SMTP 密码',
  MAIL_FROM: '发件人地址',
  LOGIN_CONTACT_MD: '登录页联系信息',
  DASHBOARD_CONTACT_MD: '控制台联系信息'
}

const getFieldLabel = (key: string) => fieldLabels[key] || key

const formatValue = (val: any) => {
  if (Array.isArray(val)) return val.join(',')
  if (val === '') return '(空)'
  return val
}

// === 修改：点击保存按钮（触发比对） ===
const saveConfig = () => {
  const changes: Record<string, { oldVal: any, newVal: any }> = {}

  // 遍历当前配置进行比对
  for (const key in sysConfig.value) {
    let newVal = sysConfig.value[key]
    let oldVal = originalConfig.value[key]

    // 特殊处理：数组比较 (针对权限复选框)
    if (Array.isArray(newVal) && Array.isArray(oldVal)) {
      // 简单排序后比较字符串
      if ([...newVal].sort().toString() !== [...oldVal].sort().toString()) {
        changes[key] = {oldVal, newVal}
      }
      continue
    }

    // 普通类型比较 (转为字符串比较以避免数字/字符串类型不一致问题)
    if (String(newVal) !== String(oldVal)) {
      changes[key] = {oldVal, newVal}
    }
  }

  // 检查是否为空
  if (Object.keys(changes).length === 0) {
    message.info('未检测到任何配置变更')
    return
  }

  pendingChanges.value = changes
  showConfirmModal.value = true
}

// === 执行真正的保存 ===
const executeSave = async () => {
  showConfirmModal.value = false
  saving.value = true

  try {
    const payload: Record<string, any> = {}

    // 只提取变更了的字段构建 Payload
    for (const key in pendingChanges.value) {
      let val = pendingChanges.value[key].newVal

      // 特殊处理：后端需要逗号分隔的字符串
      if (key === 'DEFAULT_KEY_PERMS' && Array.isArray(val)) {
        val = val.join(',')
      }

      payload[key] = val
    }

    // 发送增量数据
    await wsClient.call('admin.system.update', payload)
    message.success('配置已更新')

    // 保存成功后，更新本地快照，避免重复提示
    // 注意：这里需要把 pendingChanges 应用到 originalConfig
    for (const key in pendingChanges.value) {
      originalConfig.value[key] = pendingChanges.value[key].newVal
    }

  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const updateSub = async (key: keyof Subscriptions, val: boolean) => {
  try {
    const payload = {[key]: val}
    // 乐观更新 UI
    subs.value[key] = val

    // 发送请求
    await wsClient.call('auth.update_subscriptions', payload)

    // 更新 Store 中的数据，保持同步
    userStore.fetchUser()
    message.success('设置已保存')
  } catch (e) {
    message.error('保存失败')
    // 回滚
    subs.value[key] = !val
  }
}

const testBot = async () => {
  testingBot.value = true
  try {
    const res: any = await wsClient.call('admin.system.test_bot')
    message.success(`连接成功: ${res.detail.data?.nickname || 'Bot'}`)
  } catch (e: any) {
    message.error(e.message || '连接失败')
  } finally {
    testingBot.value = false
  }
}

const runTestBot = async () => {
  if (!testBotQQ.value) {
    message.warning('请输入 QQ 号')
    return
  }
  testingBotMsg.value = true
  try {
    const res: any = await wsClient.call('admin.system.test_msg', {target_qq: testBotQQ.value})
    message.success(res.msg || '发送成功')
    showBotTestModal.value = false
  } catch (e: any) {
    message.error(e.message || '测试失败')
  } finally {
    testingBotMsg.value = false
  }
}

const runTestEmail = async () => {
  if (!testEmailAddr.value) {
    message.warning('请输入邮箱地址')
    return
  }
  testingEmail.value = true
  try {
    const res: any = await wsClient.call('admin.system.test_email', {target_email: testEmailAddr.value})
    message.success(res.msg || '发送成功')
    showEmailTestModal.value = false
  } catch (e: any) {
    message.error(e.message || '测试失败')
  } finally {
    testingEmail.value = false
  }
}

// === 数据导入导出 ===
const exportData = async () => {
  const data = await wsClient.call('admin.system.export')
  downloadFile(data, `blacklist_backup_${getDateStr()}.json`)
  message.success('导出已开始')
}

// === 日志管理 ===
const exportLogs = async () => {
  const data = await wsClient.call('admin.logs.export')
  downloadFile(data, `audit_logs_${getDateStr()}.json`)
  message.success('日志导出成功')
}

const cleanLogs = async () => {
  try {
    const res: any = await wsClient.call('admin.logs.clean', {days: 30})
    message.success(res.msg)
  } catch (e) {
  }
}

// 同步日志清理
const cleanSyncLogs = async () => {
  const res: any = await wsClient.call('admin.system.clean_logs', {days: logDays.value})
  message.success(res.msg)
}

// 辅助函数
const getDateStr = () => new Date().toISOString().split('T')[0]

const downloadFile = (data: any, filename: string) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// 触发文件选择
const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileImport = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const json = JSON.parse(e.target?.result as string)
      if (!Array.isArray(json)) throw new Error('格式错误：必须是数组')

      const res: any = await wsClient.call('admin.system.import', json)
      message.success(res.msg)
    } catch (err) {
      message.error('导入失败: 格式错误')
    }
    // 重置 input
    target.value = ''
  }
  reader.readAsText(file)
}

watch(() => userStore.userInfo.subscriptions, (newSubStr) => {
  if (newSubStr) {
    try {
      const remoteSubs = JSON.parse(newSubStr)
      subs.value = {
        ...subs.value,
        ...remoteSubs
      }
    } catch (e) {
    }
  }
}, {immediate: true})

watch(() => userStore.userInfo.role, () => {
  fetchConfig()
}, {immediate: true})

const handleSystemEvent = (data: any, event?: string) => {
  if (event === 'system.updated') {
    fetchConfig()
  }
  if (event === 'system.secret_refreshed') {
    message.error('密钥已重置，请重新登录')
    userStore.clear()
    router.push('/')
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  wsClient.on('*', handleSystemEvent)
  fetchBackendVersion()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleSystemEvent)
})
</script>

<style scoped>
.color-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  cursor: pointer;
  transition: transform 0.2s;
}

.color-dot:hover {
  transform: scale(1.1);
}
</style>