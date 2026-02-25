<template>
  <div class="dashboard-container">

    <n-card class="mb-4 welcome-card" :bordered="false" size="small">
      <div class="welcome-header">
        <div class="greeting-section">
          <n-avatar
              round
              :size="54"
              :src="`https://q1.qlogo.cn/g?b=qq&nk=${currentUser.qq}&s=100`"
              class="user-avatar"
          />
          <div class="greeting-text">
            <h2 class="title">{{ greetingPhrase }}，{{ roleName }}</h2>
            <p class="subtitle">
              今天是 {{ currentDate }}
            </p>
          </div>
        </div>

        <div class="health-check-section">
          <n-space size="large" justify="end" class="health-space">
            <div class="health-item">
              <div class="label">数据库</div>
              <div class="value">
                <n-badge dot :type="stats.system_info.db_status === 'ok' ? 'success' : 'error'" processing/>
                <span class="ml-2">{{ stats.system_info.db_latency }}ms</span>
              </div>
            </div>

            <div class="health-item">
              <div class="label">连接数</div>
              <div class="value">
                <n-badge dot :type="wsStatus.connected ? 'success' : 'error'" processing/>
                <span class="ml-2">{{ wsStatus.connected ? stats.system_info.ws_active : 'Off' }}</span>
              </div>
            </div>

            <div class="health-item hidden-mobile">
              <div class="label">服务端时间</div>
              <div class="value font-mono">{{ formatServerTime(stats.system_info.server_time) }}</div>
            </div>
          </n-space>
        </div>
      </div>
    </n-card>

    <n-grid x-gap="12" y-gap="12" :cols="4" item-responsive responsive="screen" class="mb-4 stats-grid">
      <n-grid-item span="4 s:2 m:1">
        <n-card size="small" hoverable class="stat-card" @click="$router.push('/blacklist')">
          <n-statistic label="黑名单" :value="stats.counts.blacklist">
            <template #prefix>
              <n-icon color="#d03050" :component="ForbidIcon"/>
            </template>
            <template #suffix>
              <n-tag v-if="stats.counts.blacklist_today > 0" type="success" size="tiny" round :bordered="false"
                     class="today-tag">
                +{{ stats.counts.blacklist_today }}
              </n-tag>
            </template>
          </n-statistic>
        </n-card>
      </n-grid-item>

      <n-grid-item span="4 s:2 m:1">
        <n-card size="small" hoverable class="stat-card" @click="$router.push('/whitelist')">
          <n-statistic label="白名单" :value="stats.counts.whitelist">
            <template #prefix>
              <n-icon color="#2080f0" :component="CheckmarkCircleIcon"/>
            </template>
          </n-statistic>
        </n-card>
      </n-grid-item>

      <n-grid-item span="4 s:2 m:1" v-if="isAdmin">
        <n-card size="small" hoverable class="stat-card" @click="$router.push('/users')">
          <n-statistic label="用户数" :value="stats.counts.users">
            <template #prefix>
              <n-icon color="#f0a020" :component="PeopleIcon"/>
            </template>
          </n-statistic>
        </n-card>
      </n-grid-item>

      <n-grid-item span="4 s:2 m:1" v-if="isAdmin">
        <n-card size="small" hoverable class="stat-card" @click="$router.push('/approvals')">
          <n-statistic label="待办审批" :value="stats.counts.pending">
            <template #prefix>
              <n-icon :color="stats.counts.pending > 0 ? '#d03050' : '#18a058'" :component="NotificationsIcon"/>
            </template>
            <template #suffix>
              <n-tag v-if="stats.counts.pending > 0" type="error" round size="small" class="ml-2">待办</n-tag>
            </template>
          </n-statistic>
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-grid x-gap="12" y-gap="12" :cols="24" item-responsive responsive="screen">

      <n-grid-item span="24 m:16 l:16">
        <n-card title="动态" content-style="padding: 0; position: relative;" :bordered="false"
                class="h-full card-bg timeline-card">
          <template #header-extra>
            <n-tag :type="wsStatus.connected ? 'success' : 'error'" size="small" round :bordered="false">
              <template #icon>
                <n-icon :component="PulseIcon"/>
              </template>
              {{ wsStatus.connected ? `${wsStatus.latency}ms` : '断开' }}
            </n-tag>
          </template>

          <n-scrollbar style="max-height: 400px; padding-bottom: 20px;" class="p-4 timeline-scroll">
            <n-timeline size="large">
              <n-timeline-item
                  v-for="log in stats.recent_logs"
                  :key="log.id"
                  :type="getLogType(log.event)"
                  :time="formatToNow(log.created_at)"
                  line-type="dashed"
              >
                <template #header>
                  <span class="timeline-header">{{ getEventLabel(log.event) }}</span>
                  <span class="operator-text ml-2">by {{ log.operator }}</span>
                </template>
                <div class="timeline-content">{{ parseDetails(log.details) }}</div>
              </n-timeline-item>
            </n-timeline>
          </n-scrollbar>

          <div class="timeline-fade-mask"></div>
        </n-card>
      </n-grid-item>

      <n-grid-item span="24 m:8 l:8">
        <n-space vertical :size="12">
          <n-card size="small" :bordered="false" class="card-bg tips-card">
            <template #header>
              <div style="display: flex; align-items: center; gap: 6px;">
                <n-icon size="18" color="#f0a020" :component="BulbIcon"/>
                <span>小贴士</span>
              </div>
            </template>
            <template #header-extra>
              <n-button text size="tiny" @click="nextTip">
                <template #icon>
                  <n-icon :component="RefreshIcon"/>
                </template>
              </n-button>
            </template>
            <div class="tip-content">
              {{ currentTip }}
            </div>
          </n-card>

          <n-card title="违规分布" :bordered="false" size="small" class="card-bg">
            <div ref="reasonChartRef" style="height: 180px; width: 100%"></div>
          </n-card>

          <n-card title="来源构成" :bordered="false" size="small" class="card-bg">
            <div ref="sourceChartRef" style="height: 180px; width: 100%"></div>
          </n-card>

          <n-card title="联系我们" :bordered="false" size="small" class="card-bg mt-3">
            <div class="contact-markdown" v-html="contactInfoHtml"></div>
          </n-card>

          <n-card size="small" :bordered="false" class="card-bg info-card">
            <n-descriptions label-placement="left" size="small" :column="2">
              <n-descriptions-item label="Python">
                <n-tag size="small" :bordered="false" type="info">{{ stats.system_info.python }}</n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="OS">
                <n-text depth="3" style="font-size: 12px">{{ stats.system_info.os }}</n-text>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>
        </n-space>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import {computed, nextTick, onMounted, onUnmounted, ref, watch} from 'vue'
import {
  NAvatar,
  NBadge,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NGrid,
  NGridItem,
  NIcon,
  NScrollbar,
  NSpace,
  NStatistic,
  NTag,
  NText,
  NTimeline,
  NTimelineItem
} from 'naive-ui'
import {
  Ban as ForbidIcon,
  BulbOutline as BulbIcon,
  CheckmarkCircle as CheckmarkCircleIcon,
  Notifications as NotificationsIcon,
  People as PeopleIcon,
  Pulse as PulseIcon,
  Refresh as RefreshIcon
} from '@vicons/ionicons5'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import {marked} from 'marked'

import {wsClient} from '../api/ws'
import {themeStore} from '../store/theme'
import {userStore} from "../store/user"
import {formatToNow} from "../utils/date";


const currentUser = computed(() => userStore.userInfo).value
const isAdmin = ['owner', 'super_admin', 'admin'].includes(currentUser.role)
const wsStatus = wsClient.status

// 计时器引用
let pollTimer: any = null

const stats = ref({
  counts: {blacklist: 0, blacklist_today: 0, whitelist: 0, users: 0, pending: 0},
  charts: {reasons: [], sources: []},
  recent_logs: [] as any[],
  system_info: {
    os: '-',
    python: '-',
    db_status: 'ok',
    db_latency: 0,
    ws_active: 0,
    server_time: '--:--:--'
  }
})

const contactInfoHtml = ref('<p style="color: gray; font-size: 12px;">加载中...</p>')

// === 小贴士逻辑 ===
const tips = [
  '点击顶部的统计卡片，可以快速跳转到对应的管理页面哦。',
  '想要快速查找记录？试试在“黑名单”页面的搜索框输入 QQ 号。',
  '建议在“个人设置”中开启审批通知，第一时间获取新申请消息。',
  '遇到数据不更新？尝试刷新页面或检查右上角的连接状态。',
  '点击表格或列表中的 QQ 号，可以快速查看该账号的详细资料。',
  '觉得屏幕太亮？试试深色模式！',
]
const currentTipIndex = ref(Math.floor(Math.random() * tips.length))
const currentTip = computed(() => tips[currentTipIndex.value])

const nextTip = () => {
  currentTipIndex.value = (currentTipIndex.value + 1) % tips.length
}

// === 欢迎词逻辑 ===
const greetingPhrase = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const roleName = computed(() => {
  const map: any = {owner: '站长', super_admin: '超级管理员', admin: '管理员', user: '用户'}
  return map[currentUser.role] || currentUser.role
})

const currentDate = computed(() => dayjs().format('MM月DD日 dddd'))

const reasonChartRef = ref<HTMLElement | null>(null)
const sourceChartRef = ref<HTMLElement | null>(null)
let reasonChart: echarts.ECharts | null = null
let sourceChart: echarts.ECharts | null = null

// 数据获取与轮询
const fetchStats = async () => {
  try {
    const res = await wsClient.call('dashboard.stats')
    if (res) {
      stats.value = {
        ...stats.value,
        ...res,
        charts: res.charts || {reasons: res.distribution || [], sources: []}
      }
      // 数据回来后，刷新图表数据
      updateCharts()
    }
  } catch (e) {
    console.error(e)
  }
}

const startPolling = () => {
  stopPolling()
  // 首次立即执行
  fetchStats()
  // 每秒更新
  pollTimer = setInterval(fetchStats, 1000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// === 辅助逻辑 ===
const getLogType = (event: string) => {
  if (event.includes('deleted') || event.includes('killed')) return 'error'
  if (event.includes('created') || event.includes('added') || event.includes('approved')) return 'success'
  if (event.includes('updated')) return 'warning'
  return 'info'
}

const getEventLabel = (event: string) => {
  const map: Record<string, string> = {
    'app.created': '新请求',
    'app.handled': '处理审批',
    'blacklist.created': '添加黑名单',
    'blacklist.updated': '更新黑名单',
    'blacklist.deleted': '移除黑名单',
    'whitelist.added': '添加白名单',
    'whitelist.deleted': '移除白名单',
  }
  return map[event] || event
}

// 格式化服务端时间 (UTC ISO -> Local HH:mm:ss)
const formatServerTime = (timeStr: string) => {
  if (!timeStr || timeStr === '--:--:--') return timeStr
  try {
    return dayjs(timeStr).format('HH:mm:ss')
  } catch {
    return timeStr
  }
}

const parseDetails = (jsonStr: string) => {
  try {
    const data = JSON.parse(jsonStr)
    if (data.reason) return `理由: ${data.reason}`
    if (data.target) return `目标: ${data.target}`
    if (data.action) return `动作: ${data.action}`
    if (data.count) return `数量: ${data.count}`
    return ''
  } catch {
    return 'Details...'
  }
}

const fetchPublicConfig = async () => {
  try {
    const res: any = await wsClient.call('admin.system.get_public')
    if (res && res.DASHBOARD_CONTACT_MD) {
      contactInfoHtml.value = await marked.parse(res.DASHBOARD_CONTACT_MD)
    } else {
      contactInfoHtml.value = '<p style="color: gray; font-size: 12px;">暂无联系信息，请在系统设置中配置。</p>'
    }
  } catch (e) {
    console.warn('获取公开配置失败:', e)
    contactInfoHtml.value = '<p style="color: #d03050; font-size: 12px;">无法加载联系信息</p>'
  }
}

// === 图表逻辑 (Init/Update 分离) ===
const getChartThemeVars = () => {
  const isDark = themeStore.mode === 'dark' || (themeStore.mode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  return {
    textColor: isDark ? '#e5e5e5' : '#333333',
    tooltipBg: isDark ? 'rgba(30, 30, 35, 0.95)' : 'rgba(255, 255, 255, 0.95)',
    tooltipText: isDark ? '#ffffff' : '#333333',
    tooltipBorder: isDark ? 'rgba(255, 255, 255, 0.1)' : '#eee',
    centerTextColor: isDark ? '#ffffff' : '#333333',
    pieBorderColor: isDark ? '#1e1e22' : '#ffffff',
    colors: ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
  }
}

// 1. 初始化实例 (仅执行一次)
const initCharts = () => {
  const theme = getChartThemeVars()

  if (reasonChartRef.value && !reasonChart) {
    reasonChart = echarts.init(reasonChartRef.value)
    // 初始配置，数据先空着，等 updateCharts 填入
    reasonChart.setOption({
      backgroundColor: 'transparent',
      color: theme.colors,
      animationDuration: 500, // 动画时长
      tooltip: {trigger: 'item'},
      series: [{
        name: '违规原因', type: 'pie', radius: ['50%', '80%'], center: ['50%', '50%'],
        itemStyle: {borderRadius: 4, borderWidth: 2},
        label: {show: false},
        data: []
      }]
    })
  }

  if (sourceChartRef.value && !sourceChart) {
    sourceChart = echarts.init(sourceChartRef.value)
    sourceChart.setOption({
      backgroundColor: 'transparent',
      color: ['#06b6d4', '#f97316'],
      animationDuration: 500,
      tooltip: {trigger: 'item'},
      legend: {bottom: 0, icon: 'circle', textStyle: {fontSize: 10}},
      series: [{
        name: '来源', type: 'pie', radius: ['40%', '70%'], center: ['50%', '40%'],
        itemStyle: {borderRadius: 4, borderWidth: 2},
        label: {show: true, position: 'inside', formatter: '{c}', color: '#fff', fontSize: 10},
        data: []
      }]
    })
  }

  // 首次立即填充数据（如果有）
  updateCharts()
}

// 2. 更新数据 (每秒执行，不做 dispose)
const updateCharts = () => {
  const theme = getChartThemeVars()

  // 更新数据和主题色
  if (reasonChart) {
    reasonChart.setOption({
      color: theme.colors,
      tooltip: {
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: {color: theme.tooltipText}
      },
      series: [{
        itemStyle: {borderColor: theme.pieBorderColor},
        data: stats.value.charts.reasons.length ? stats.value.charts.reasons : [{name: '无数据', value: 0}]
      }]
    })
  }

  if (sourceChart) {
    sourceChart.setOption({
      tooltip: {
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: {color: theme.tooltipText}
      },
      legend: {textStyle: {color: theme.textColor}},
      series: [{
        itemStyle: {borderColor: theme.pieBorderColor},
        data: stats.value.charts.sources.length ? stats.value.charts.sources : [{name: '暂无', value: 0}]
      }]
    })
  }
}

// 监听主题变化：不需要销毁，只需要调一次 updateCharts 刷颜色
watch(() => themeStore.mode, () => updateCharts())

const handleResize = () => {
  reasonChart?.resize()
  sourceChart?.resize()
}

// 保持 WS 广播监听，作为额外触发源 (例如别处有操作，立刻更新，不用等下一秒)
const handleBroadcast = (data: any, event?: string) => {
  if (event && ['blacklist.', 'app.', 'log.', 'user.'].some(prefix => event.startsWith(prefix))) fetchStats()
}

onMounted(() => {
  // DOM 渲染后初始化图表实例
  nextTick(() => {
    initCharts()
    startPolling() // 启动轮询
    fetchPublicConfig()
  })
  window.addEventListener('resize', handleResize)
  wsClient.on('*', handleBroadcast)
})

onUnmounted(() => {
  stopPolling() // 停止轮询
  window.removeEventListener('resize', handleResize)
  wsClient.off('*', handleBroadcast)
  reasonChart?.dispose()
  sourceChart?.dispose()
})
</script>

<style scoped>
/* 1. 间距修复 */
.mb-4 {
  margin-bottom: 16px !important;
}

/* 2. 欢迎卡片样式 */
.welcome-card {
  background: linear-gradient(120deg, var(--n-color) 0%, var(--n-color-embedded) 100%);
}

.welcome-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.greeting-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.greeting-text .title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.greeting-text .subtitle {
  margin: 2px 0 0 0;
  font-size: 12px;
  color: var(--n-text-color-3);
}

/* 3. 健康检查样式 */
.health-check-section {
  display: flex;
  align-items: center;
}

.health-item {
  text-align: right;
}

.health-item .label {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.health-item .value {
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.ml-2 {
  margin-left: 6px;
}

/* 移动端适配 */
@media (max-width: 600px) {
  .welcome-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .health-check-section {
    width: 100%;
  }

  .health-space {
    width: 100%;
    justify-content: space-between !important;
  }

  .health-item {
    text-align: left;
  }

  .health-item .value {
    justify-content: flex-start;
  }

  .hidden-mobile {
    display: none;
  }
}

.timeline-header {
  font-weight: 600;
  font-size: 13px;
}

.operator-text {
  font-size: 11px;
  color: var(--n-text-color-3);
}

.timeline-content {
  color: var(--n-text-color-2);
  font-size: 12px;
  margin-top: 1px;
}

.tips-card .tip-content {
  font-size: 12px;
  color: var(--n-text-color-2);
  min-height: 36px;
  display: flex;
  align-items: center;
}

.today-tag {
  font-weight: bold;
  margin-left: 4px;
}

.p-4 {
  padding: 12px;
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