<template>
  <n-config-provider
      :theme="activeTheme"
      :theme-overrides="dynamicOverrides"
      :locale="zhCN"
      :date-locale="dateZhCN"
      :hljs="hljs"
  >
    <n-global-style/>
    <n-message-provider>
      <n-dialog-provider>

        <router-view v-if="isStandalonePage"/>

        <n-layout v-else class="main-layout" :has-sider="!isMobile" position="absolute">

          <n-layout-sider
              v-if="!isMobile"
              bordered
              collapse-mode="width"
              :collapsed-width="64"
              :width="240"
              :collapsed="collapsed"
              :native-scrollbar="false"
              class="custom-sider"
          >
            <div class="logo" @click="toggleSider">
              <img src="/apple-touch-icon.png" class="logo-image" alt="Logo" />
              <span class="logo-text" :class="{ 'hide-text': collapsed }">Shield Admin</span>
            </div>

            <n-menu
                :collapsed="collapsed"
                :collapsed-width="64"
                :collapsed-icon-size="22"
                :options="menuOptions"
                :value="currentMenu"
                @update:value="handleMenuClick"
            />
          </n-layout-sider>

          <n-drawer v-model:show="showDrawer" :width="240" placement="left" v-if="isMobile">
            <n-drawer-content body-content-style="padding: 0;">
              <div class="logo" @click="showDrawer = false">
                <img src="/apple-touch-icon.png" class="logo-image" alt="Logo" />
                <span class="logo-text">Shield Admin</span>
              </div>
              <n-menu
                  :options="menuOptions"
                  :value="currentMenu"
                  @update:value="handleMenuClick"
              />
            </n-drawer-content>
          </n-drawer>

          <n-layout>
            <n-layout-header bordered class="nav-header">
              <div class="header-left">
                <n-button v-if="isMobile" text style="margin-right: 12px; font-size: 24px" @click="showDrawer = true">
                  <n-icon><MenuOutline /></n-icon>
                </n-button>
                <span v-if="isMobile" class="page-title">{{ route.meta.title || 'Shield Admin' }}</span>
              </div>

              <div class="header-right">
                <n-input-group>
                  <n-input
                      v-model:value="searchQQ"
                      placeholder="查QQ"
                      :allow-input="onlyAllowNumber"
                      :maxlength="11"
                      :style="{ width: isMobile ? '130px' : '200px' }"
                      @keydown.enter.prevent="handleSearch"
                  >
                    <template #prefix>🔍</template>
                  </n-input>
                  <n-button type="primary" ghost @click="handleSearch" :disabled="!searchQQ">
                    查询
                  </n-button>
                </n-input-group>
              </div>

              <div class="header-right" style="margin-left: 12px;">
                <n-dropdown :options="userOptions" @select="handleUserSelect">
                  <n-button text class="user-btn">
                    <template #icon>
                      <n-avatar
                          round
                          :size="32"
                          :src="avatarUrl"
                          style="margin-right: 20px; flex-shrink: 0;"
                          fallback-src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png"
                      />
                    </template>
                    <span v-if="!isMobile" style="margin-left: 4px;">{{ currentUser.qq || '未知用户' }}</span>
                  </n-button>
                </n-dropdown>
              </div>
            </n-layout-header>

            <n-layout-content :content-style="{ padding: isMobile ? '12px' : '24px', backgroundColor: 'var(--n-color-embedded)' }">
              <router-view v-slot="{ Component }">
                <transition name="fade" mode="out-in">
                  <component :is="Component"/>
                </transition>
              </router-view>
            </n-layout-content>
          </n-layout>
        </n-layout>

        <GlobalProfileModal/>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import {computed, h, onMounted, onUnmounted, ref} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {
  createDiscreteApi,
  darkTheme,
  dateZhCN,
  GlobalThemeOverrides,
  NAvatar,
  NButton,
  NConfigProvider,
  NDialogProvider,
  NDropdown,
  NGlobalStyle,
  NInput,
  NInputGroup,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NMessageProvider,
  NDrawer,
  NDrawerContent,
  NIcon,
  useOsTheme,
  zhCN
} from 'naive-ui'
import { MenuOutline } from '@vicons/ionicons5'
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'
import {wsClient} from './api/ws'
import {themeStore} from './store/theme'
import {userStore} from './store/user'
import GlobalProfileModal from './components/GlobalProfileModal.vue'
import {adjustColor} from './utils/color'
import {uiStore} from "./store/ui";
import {formatTime} from "./utils/date";

// 注册语言
hljs.registerLanguage('json', json)

const route = useRoute()
const router = useRouter()
const osTheme = useOsTheme()

const {message} = createDiscreteApi(['message'])

// === 移动端适配逻辑 ===
const isMobile = ref(false)
const showDrawer = ref(false)

const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
  if (!isMobile.value) {
    showDrawer.value = false // 切回 PC 时自动关闭抽屉
  }
}

const avatarUrl = computed(() => {
  const qq = currentUser.value.qq
  if (!qq) return ''
  // 使用 spec=100 获取小尺寸头像，加载更快
  return `https://q1.qlogo.cn/g?b=qq&nk=${qq}&s=100`
})

// 搜索逻辑
const searchQQ = ref('')
const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

const handleSearch = () => {
  if (!searchQQ.value) return

  (document.activeElement as HTMLElement)?.blur()

  // 调用全局 UI Store 打开资料卡
  uiStore.openProfile(searchQQ.value)
  // 查询后清空
  searchQQ.value = ''
  // 移动端搜索后关闭抽屉（如果未来把搜索放进抽屉的话）
  if (isMobile.value) showDrawer.value = false
}

// --- 1. 侧边栏折叠逻辑 ---
const collapsed = ref(false)
const toggleSider = () => collapsed.value = !collapsed.value

// --- 2. 主题配置 ---
// 计算当前主题
const activeTheme = computed(() => {
  if (themeStore.mode === 'dark') return darkTheme
  if (themeStore.mode === 'light') return null
  return osTheme.value === 'dark' ? darkTheme : null
})

// === 样式覆盖 ===
const dynamicOverrides = computed<GlobalThemeOverrides>(() => {
  const primary = themeStore.primaryColor
  // 增加调整幅度，让交互更明显
  const hoverColor = adjustColor(primary, 0.15) // 变亮 15%
  const pressedColor = adjustColor(primary, -0.15) // 变暗 15%
  const isDark = activeTheme.value?.name === 'dark'

  return {
    common: {
      primaryColor: primary,
      primaryColorHover: hoverColor,
      primaryColorPressed: pressedColor,
      primaryColorSuppl: hoverColor, // 辅助色通常与 Hover 一致
      borderRadius: '8px'
    },
    // 针对按钮的深度定制
    Button: {
      colorPrimary: primary,
      colorHoverPrimary: hoverColor,
      colorPressedPrimary: pressedColor,
      colorFocusPrimary: hoverColor,
      // 修复 Ghost/Secondary 按钮的文本颜色
      textColorPrimary: isDark ? '#fff' : '#fff',
      border: `1px solid ${primary}`,
    },
    // 针对 Switch 的深度定制 (解决看不清字的问题)
    Switch: {
      railColorActive: primary,
      // 关键：如果开启状态背景是亮色(如绿色)，文字必须是深色；如果是深色背景，文字为白色
      // 这里我们在 Switch 开启时，强制把内部文字颜色设为具有高对比度的颜色
      // 由于 Naive UI 没有直接暴露 "activeTextColor" 这种配置，我们通过调整 rail 透明度或使用深色文字来解决
      loadingColor: primary,
      // 强制让开关上的文字在深色模式下稍微亮一点，或者依靠 CSS 修正
      textColor: isDark ? 'rgba(255,255,255,0.9)' : 'white'
    },
    Card: {
      borderRadius: '12px',
      // 让卡片在深色模式下稍微黑一点，突出图表
      color: isDark ? 'rgba(24, 24, 28, 0.6)' : '#fff',
      borderColor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgb(239, 239, 245)'
    }
  }
})

// --- 2. 路由与布局判断 ---
const isStandalonePage = computed(() => ['/', '/appeal'].includes(route.path))
const currentUser = computed(() => userStore.userInfo)

// 菜单配置
const menuOptions = computed(() => {
  const menus: any[] = [
    {label: '控制台', key: 'dashboard', icon: renderIcon('📊')},
    {label: '我的申请', key: 'my-apps', icon: renderIcon('📝')},
    {label: '黑名单', key: 'blacklist', icon: renderIcon('🚫')},
    {label: '白名单', key: 'whitelist', icon: renderIcon('🏳️')}
  ]

  // 仅管理员可见审批入口
  if (['owner', 'super_admin', 'admin'].includes(currentUser.value.role)) {
    menus.push(
        {label: '审批管理', key: 'approvals', icon: renderIcon('🔔')},
        {label: 'API 密钥', key: 'keys', icon: renderIcon('🔑')},
    )
  }

  if (['owner', 'super_admin'].includes(currentUser.value.role)) {
    menus.push(
        {label: '用户管理', key: 'users', icon: renderIcon('👥')},
        {label: '操作日志', key: 'logs', icon: renderIcon('📜')},
    )
  }

  menus.push(
      {label: '在线会话', key: 'sessions', icon: renderIcon('🔌')},
      {label: '系统设置', key: 'settings', icon: renderIcon('⚙️')},
  )
  return menus
})

const currentMenu = computed(() => String(route.path).replace('/', ''))

function handleMenuClick(key: string) {
  router.push(`/${key}`)
  // 移动端点击菜单后自动收起抽屉
  if (isMobile.value) {
    showDrawer.value = false
  }
}

function renderIcon(icon: string) {
  return () => h('span', {style: 'font-size: 18px'}, icon)
}

// --- 4. 用户下拉菜单 ---
const userOptions = [
  {label: '退出登录', key: 'logout'}
]

function handleUserSelect(key: string) {
  if (key === 'logout') {
    userStore.clear()
    router.push('/')
  }
}

// === 全局通知监听器 ===
const handleGlobalNotify = (data: any, event?: string) => {
  // 1. 新申请通知
  if (event === 'app.created' && !themeStore.notifyApply) {
    sendNotification('🔔 新的审批申请', `申请人: ${data.applicant}\n目标: ${data.target}\n理由: ${data.reason}`)
  }

  // 2. 权限变更通知
  if (event === 'user.updated') {
    if (String(data.target_qq) === String(currentUser.value.qq)) {
      userStore.fetchUser()
      message.info('权限已更新')
    }
  }

  // 3. 强制下线通知
  if (event === 'system.kicked') {
    // 优先显示后端传来的理由
    message.error(data.reason || '您已被强制下线')
    userStore.clear()
    router.push('/')
  }

  // 4. 新设备登录通知
  if (event === 'account.login') {
    // 后端已通过 exclude_token 排除了本机，能收到说明是别的设备
    message.warning(`您的账号在别处登录: ${data.ip || '未知IP'} (${formatTime(data.time, 'HH:mm:ss')})`)
  }
}

const sendNotification = (title: string, body: string) => {
  if (!('Notification' in window)) return

  if (Notification.permission === 'granted') {
    new Notification(title, {body, icon: '/favicon.ico'})
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then(permission => {
      if (permission === 'granted') {
        new Notification(title, {body, icon: '/favicon.ico'})
      }
    })
  }
}

onMounted(() => {
  checkMobile() // 初始化检测
  window.addEventListener('resize', checkMobile) // 监听窗口变化

  userStore.fetchUser()
  // 注册监听
  wsClient.on('*', handleGlobalNotify)
})

onUnmounted(() => {
  // 销毁监听
  wsClient.off('*', handleGlobalNotify)
})

</script>

<style>
/* 全局样式 */
.main-layout {
  height: 100vh;
}

/* Logo 样式修复 */
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-bottom: 1px solid var(--n-border-color);
  overflow: hidden;
  transition: all 0.3s var(--n-bezier);
}

.logo:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.logo-image {
  width: 32px;
  height: 32px;
  margin: 0 16px; /* 保持与原 min-width: 64px 类似的占位效果 */
  object-fit: contain;
  transition: all 0.3s var(--n-bezier);
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
  color: var(--n-primary-color);
  white-space: nowrap;
  opacity: 1;
  /* 平滑过渡 opacity 和 max-width */
  transition: opacity 0.2s ease, max-width 0.3s ease, transform 0.3s ease;
  max-width: 200px; /* 足够大以显示文字 */
  transform: translateX(0);
}

/* 隐藏状态 */
.logo-text.hide-text {
  opacity: 0;
  max-width: 0;
  transform: translateX(-10px);
}

.nav-header {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 移动端 Header 内边距微调 */
@media (max-width: 768px) {
  .nav-header {
    padding: 0 12px;
  }
}

.header-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  margin-left: 4px;
  color: var(--n-text-color);
}
</style>
