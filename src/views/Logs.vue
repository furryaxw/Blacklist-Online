<template>
  <div class="logs-page">
    <n-card title="📜 操作日志" :bordered="false">
      <template #header-extra>
        <n-button size="small" secondary @click="fetchLogs">刷新</n-button>
      </template>

      <n-data-table
          v-if="!isMobile"
          remote
          :columns="columns"
          :data="logs"
          :loading="loading"
          :pagination="pagination"
          :row-key="(row) => row.id"
          :size="themeStore.density"
          striped
      />

      <div v-else class="mobile-logs">
        <div v-for="log in logs" :key="log.id" class="log-card">
          <div class="log-header">
            <div class="left">
              <n-tag :type="getEventType(log.event)" size="small" :bordered="false">
                {{ log.event }}
              </n-tag>
              <span class="id-text">#{{ log.id }}</span>
            </div>
            <div class="time">{{ formatTime(log.created_at) }}</div>
          </div>

          <div class="log-body">
            <div class="info-row">
              <span class="label">操作人:</span>
              <QQUser v-if="log.operator" :qq="log.operator" :show-tag="false" size="small"/>
              <span v-else>System</span>
              <n-button size="small" secondary @click="openDetail(log)">
                显示详细信息
              </n-button>
            </div>
          </div>
        </div>

        <div class="mobile-pagination">
          <n-pagination
              simple
              v-model:page="pagination.page"
              :item-count="pagination.itemCount"
              :page-size="pagination.pageSize"
              @update:page="pagination.onChange"
          />
        </div>
      </div>
    </n-card>

    <n-modal v-model:show="showModal">
      <n-card
          title="日志详情"
          style="width: 600px; max-width: 90vw"
          role="dialog"
          aria-modal="true"
          closable
          @close="showModal = false"
      >
        <n-descriptions bordered :column="1" label-placement="left">
          <n-descriptions-item label="日志 ID">
            {{ activeLog.id }}
          </n-descriptions-item>
          <n-descriptions-item label="事件类型">
            <n-tag :type="getEventType(activeLog.event)" size="small">
              {{ activeLog.event }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="操作人">
            <QQUser v-if="activeLog.operator" :qq="activeLog.operator"/>
            <span v-else>System</span>
          </n-descriptions-item>
          <n-descriptions-item label="操作时间">
            {{ formatTime(activeLog.created_at) }}
          </n-descriptions-item>
          <n-descriptions-item label="详细数据 (JSON)">
            <n-scrollbar style="max-height: 300px">
              <n-code
                  :code="tryFormatJson(activeLog.details)"
                  language="json"
                  word-wrap
              />
            </n-scrollbar>
          </n-descriptions-item>
        </n-descriptions>

        <template #footer>
          <n-space justify="end">
            <n-button @click="showModal = false">关闭</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import {h, onMounted, onUnmounted, reactive, ref} from 'vue'
import {
  NButton,
  NCard,
  NCode,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NModal,
  NPagination,
  NScrollbar,
  NSpace,
  NTag
} from 'naive-ui'
import {wsClient} from '../api/ws'
import {themeStore} from '../store/theme'
import QQUser from "../components/QQUser.vue";
import {formatTime} from "../utils/date";

const logs = ref<any[]>([])
const loading = ref(false)
const showModal = ref(false)
const activeLog = ref<any>({})

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
  onChange: (page: number) => {
    pagination.page = page
    fetchLogs()
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    fetchLogs()
  }
})

// 打开详情弹窗
const openDetail = (row: any) => {
  activeLog.value = row
  showModal.value = true
}

const columns = [
  {
    title: 'ID',
    key: 'id',
    width: 60
  },
  {
    title: '事件',
    key: 'event',
    width: 160,
    render: (row: any) => h(NTag, {type: getEventType(row.event), bordered: false, size: 'small'}, () => row.event)
  },
  {
    title: '操作人',
    key: 'operator',
    width: 120,
    render: (row: any) => row.operator ? h(QQUser, {qq: row.operator}) : 'System'
  },
  {
    title: '操作详情',
    key: 'details',
    render: (row: any) => {
      // 修改：这里不再显示 Popover，而是显示一个按钮
      return h(NButton, {
        size: 'tiny',
        secondary: true,
        onClick: () => openDetail(row)
      }, () => '查看详情')
    }
  },
  {
    title: '时间',
    key: 'created_at',
    width: 180,
    render: (row: any) => formatTime(row.created_at)
  }
]

const getEventType = (event: string) => {
  if (!event) return 'default'
  if (event.includes('created') || event.includes('added')) return 'success'
  if (event.includes('deleted') || event.includes('removed')) return 'error'
  if (event.includes('updated')) return 'warning'
  return 'default'
}

const tryFormatJson = (str: string) => {
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch (e) {
    return str
  }
}

const fetchLogs = async () => {
  loading.value = true
  try {
    const res: any = await wsClient.call('admin.logs.list', {
      page: pagination.page,
      size: pagination.pageSize
    })
    logs.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    // 错误处理由拦截器接管或忽略
  } finally {
    loading.value = false
  }
}

// 监听器：收到任何广播都延迟刷新一下日志
const handleLogUpdate = () => {
  // 简单的防抖或直接刷新
  fetchLogs()
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchLogs()
  wsClient.on('*', handleLogUpdate) // 监听所有广播
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleLogUpdate)
})
</script>

<style scoped>
.mobile-logs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-card {
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--n-divider-color);
}

.log-header .left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.id-text {
  font-size: 12px;
  color: var(--n-text-color-3);
  font-family: monospace;
}

.time {
  color: var(--n-text-color-3);
  font-size: 12px;
}

.log-body {
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 13px;
}

.label {
  color: var(--n-text-color-3);
}

.mobile-pagination {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
</style>