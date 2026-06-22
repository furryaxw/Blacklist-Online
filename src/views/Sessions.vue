<template>
  <div class="sessions-page">
    <n-card title="🔌 在线会话管理" :bordered="false">
      <template #header-extra>
        <n-button size="small" secondary @click="fetchList">刷新列表</n-button>
      </template>

      <n-alert type="info" style="margin-bottom: 16px" :bordered="false" show-icon v-if="!isMobile">
        <span v-if="['owner', 'super_admin'].includes(userStore.userInfo.role)">
          您是超级管理员，可以管理所有在线用户的会话状态。
        </span>
        <span v-else>
          管理您的在线设备。
        </span>
      </n-alert>

      <n-data-table
          v-if="!isMobile"
          :columns="columns"
          :data="list"
          :loading="loading"
          :size="themeStore.density"
          striped
      />

      <div v-else class="mobile-list">
        <n-card v-for="item in list" :key="item.token" size="small" class="session-card">
           <div class="card-top">
             <QQUser :qq="item.user_id"/>
             <n-tag size="tiny" :bordered="false">{{ item.role }}</n-tag>
           </div>

           <div class="card-info">
             <div>登录时间: {{ formatTime(item.created_at) }}</div>
             <div>最后活跃: {{ formatLastActive(item.last_activity) }}</div>
           </div>

           <div class="card-action">
             <n-popconfirm @positive-click="killSession(item.token)">
                <template #trigger>
                   <n-button
                     size="small"
                     secondary
                     type="error"
                     block
                     :disabled="false"
                   >
                     {{ String(item.user_id) === String(userStore.userInfo.qq) ? '强制下线（自己）' : '强制下线' }}
                   </n-button>
                </template>
                确定强制下线?
             </n-popconfirm>
           </div>
        </n-card>
      </div>

    </n-card>
  </div>
</template>

<script setup lang="ts">
import {h, onMounted, onUnmounted, ref} from 'vue'
import {NAlert, NButton, NCard, NDataTable, NPopconfirm, NTag, NTime, useMessage} from 'naive-ui'
import {wsClient} from '../api/ws'
import {themeStore} from '../store/theme'
import QQUser from '../components/QQUser.vue'
import {userStore} from "../store/user";
import {formatTime, toLocalDate} from "../utils/date";

const message = useMessage()
const list = ref<any[]>([])
const loading = ref(false)

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => { isMobile.value = window.innerWidth <= 768 }

const fetchList = async () => {
  loading.value = true
  try {
    const res: any = await wsClient.call('admin.sessions.list')
    list.value = res
  } finally {
    loading.value = false
  }
}

const killSession = async (token: string) => {
  try {
    await wsClient.call('admin.sessions.kill', {token})
    message.success('已踢下线')
    fetchList()
  } catch (e) {
  }
}

const formatLastActive = (ts: number) => {
  const diff = Math.floor((Date.now() / 1000) - ts)
  return diff < 60 ? '刚刚' : `${Math.floor(diff / 60)} 分钟前`
}

const columns = [
  {
    title: '用户',
    key: 'user_id',
    render: (row: any) => h(QQUser, {qq: row.user_id})
  },
  {
    title: '角色',
    key: 'role',
    render: (row: any) => h(NTag, {size: 'small', bordered: false}, () => row.role)
  },
  {
    title: '登录时间',
    key: 'created_at',
    render: (row: any) => h(NTime, {time: toLocalDate(row.created_at) || new Date(0)})
  },
  {
    title: '最后活跃',
    key: 'last_activity',
    render: (row: any) => formatLastActive(row.last_activity)
  },
  {
    title: '操作',
    key: 'action',
    render(row: any) {
      // 标记当前自己的会话（前端没有存 session token，无法精确判断哪个是自己，
      // 但可以通过 qq 号判断是否是自己的账号。如果有多端登录，这里会显示多个自己）
      const isSelf = String(row.user_id) === String(userStore.userInfo.qq)

      return h(NPopconfirm, {
        onPositiveClick: () => killSession(row.token)
      }, {
        trigger: () => h(NButton, {
          size: 'small',
          type: 'error',
          secondary: true,
          disabled: false // 允许踢自己（测试用），或者改为 isSelf 禁止踢自己
        }, () => isSelf ? '强制下线（自己）' : '强制下线'),
        default: () => '确定要强制该设备下线吗？'
      })
    }
  }
]

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchList()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.mobile-list { display: flex; flex-direction: column; gap: 12px; }
.session-card { border: 1px solid var(--n-border-color); }

.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.card-info { font-size: 13px; color: var(--n-text-color-2); display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.card-action { margin-top: 8px; }
</style>
