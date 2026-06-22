{
type: created file
fileName: src/views/Whitelist.vue
fullContent:
<template>
  <div class="whitelist-page">
    <n-card title="🏳️ 白名单管理" :bordered="false">
      <template #header-extra v-if="!isMobile">
        <n-space>
          <n-input
              v-model:value="form.user_id"
              placeholder="输入 QQ 号"
              size="small"
              style="width: 200px"
              :allow-input="onlyAllowNumber"
              :maxlength="11"
          />
          <n-input
              v-model:value="form.reason"
              placeholder="备注原因"
              size="small"
              style="width: 150px"
              :maxlength="20"
              show-count
          />
          <n-button type="primary" size="small" @click="addEntry" :disabled="!form.user_id">添加白名单</n-button>
        </n-space>
      </template>

      <div v-if="isMobile" class="mobile-input-area">
        <div class="input-header">➕ 添加新白名单</div>
        <n-input
            v-model:value="form.user_id"
            placeholder="输入 QQ 号"
            :allow-input="onlyAllowNumber"
            :maxlength="11"
            class="mb-2"
        />
        <n-input
            v-model:value="form.reason"
            placeholder="备注原因 (选填)"
            :maxlength="20"
            show-count
            class="mb-2"
        />
        <n-button type="primary" block @click="addEntry" :disabled="!form.user_id">
          添加至白名单
        </n-button>
      </div>

      <n-alert type="info" style="margin-bottom: 16px" :bordered="false" show-icon v-if="!isMobile">
        白名单内的用户将<b>免受黑名单检测</b>。
      </n-alert>

      <n-data-table
          v-if="!isMobile"
          :columns="columns"
          :data="data"
          :loading="loading"
          :pagination="{ pageSize: 20 }"
          :size="themeStore.density" striped
      />

      <div v-else class="mobile-list">
        <n-empty v-if="data.length === 0" description="暂无数据"/>
        <div v-for="item in data" :key="item.user_id" class="mobile-card">
          <div class="card-top">
            <div class="user-wrapper">
              <QQUser :qq="item.user_id"/>
            </div>
            <n-popconfirm @positive-click="deleteEntry(item.user_id)">
              <template #trigger>
                <n-button size="tiny" type="error" secondary>移除</n-button>
              </template>
              确定移除？
            </n-popconfirm>
          </div>
          <div class="card-content">
            <div class="reason">{{ item.reason || '无备注' }}</div>
            <div class="meta">
              <span>添加人: <QQUser :qq="item.operator_id" :show-tag="false" size="small"/></span>
              <span>{{ formatDate(item.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import {h, onMounted, onUnmounted, ref} from 'vue'
import {NAlert, NButton, NCard, NDataTable, NEmpty, NInput, NPopconfirm, NSpace, useMessage} from 'naive-ui'
import {wsClient} from '../api/ws'
import QQUser from '../components/QQUser.vue'
import {themeStore} from "../store/theme";
import {formatDate} from "../utils/date";

const message = useMessage()
const data = ref<any[]>([])
const loading = ref(false)
const form = ref({user_id: '', reason: ''})

// --- 移动端检测 ---
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

const fetchList = async () => {
  loading.value = true
  try {
    const res: any = await wsClient.call('admin.whitelist.list')
    data.value = res
  } finally {
    loading.value = false
  }
}

const addEntry = async () => {
  if (!form.value.user_id) return
  try {
    await wsClient.call('admin.whitelist.add', form.value)
    message.success('添加成功')
    form.value = {user_id: '', reason: ''}
    fetchList()
  } catch (e) {
  }
}

const deleteEntry = async (id: string) => {
  try {
    await wsClient.call('admin.whitelist.delete', {user_id: id})
    message.success('已移除')
    fetchList()
  } catch (e) {
  }
}

const columns = [
  {
    title: 'QQ',
    key: 'user_id',
    render: (row: any) => h(QQUser, {qq: row.user_id})
  },
  {title: '备注', key: 'reason'},
  {
    title: '添加人',
    key: 'operator_id',
    render: (row: any) => h(QQUser, {qq: row.operator_id})
  },
  {
    title: '添加时间',
    key: 'created_at',
    render: (row: any) => formatDate(row.created_at)
  },
  {
    title: '操作',
    key: 'action',
    render(row: any) {
      return h(NPopconfirm, {onPositiveClick: () => deleteEntry(row.user_id)}, {
        trigger: () => h(NButton, {size: 'small', type: 'error', secondary: true}, () => '移除'),
        default: () => '确定移除出白名单？'
      })
    }
  }
]

const handleEvent = (d: any, e?: string) => {
  if (e?.startsWith('whitelist.')) fetchList()
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchList()
  wsClient.on('*', handleEvent)
})
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleEvent)
})
</script>

<style scoped>
.mobile-input-area {
  display: flex;
  flex-direction: column;
  width: 100%;
  background-color: var(--n-color-embedded);
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  border: 1px solid var(--n-border-color);
  box-sizing: border-box;
}

.input-header {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 12px;
  color: var(--n-text-color);
}

.mb-2 {
  margin-bottom: 12px;
}

.mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-card {
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  padding: 12px;
  width: 100%;
  box-sizing: border-box;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.user-wrapper {
  flex: 1;
  min-width: 0;
  margin-right: 8px;
  overflow: hidden;
}

.card-content .reason {
  font-weight: 500;
  margin-bottom: 6px;
  word-break: break-all;
  white-space: normal;
}

.card-content .meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--n-text-color-3);
  flex-wrap: wrap;
}
</style>
