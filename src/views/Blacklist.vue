<template>
  <div class="blacklist-page">
    <n-card :bordered="false" title="📋 黑名单列表">
      <template #header-extra v-if="!isMobile">
        <n-space align="center">
          <n-input
              v-model:value="search"
              placeholder="搜索 QQ..."
              size="small"
              :allow-input="onlyAllowNumber"
              :maxlength="11"
              style="width: 180px"
              @keydown.enter="handleSearch"
          >
            <template #prefix>🔍</template>
          </n-input>
          <n-button size="small" @click="handleSearch">搜索</n-button>
          <n-button
              size="small"
              @click="handleDirectQuery"
              v-if="['owner', 'super_admin'].includes(currentUser.role)"
          >
            档案查询
          </n-button>

          <transition name="fade">
            <n-space v-if="checkedRowKeys.length > 0 && isAdmin">
              <n-button size="small" type="success" secondary @click="batchUpdateStatus(false)">批量生效</n-button>
              <n-button size="small" type="error" secondary @click="batchUpdateStatus(true)">批量失效</n-button>
              <n-popconfirm v-if="['owner', 'super_admin'].includes(currentUser.role)"
                            @positive-click="batchHardDelete">
                <template #trigger>
                  <n-button size="small" type="error" ghost>批量删除</n-button>
                </template>
                确定要彻底删除选中的 {{ checkedRowKeys.length }} 条记录吗？
              </n-popconfirm>
              <n-divider vertical/>
            </n-space>
          </transition>

          <n-button
              v-if="isAdmin"
              type="primary"
              size="small"
              @click="showAddModal = true"
          >
            + 添加记录
          </n-button>
        </n-space>
      </template>

      <div v-if="isMobile" class="mobile-toolbar">
        <div class="toolbar-row">
          <n-input
              v-model:value="search"
              placeholder="搜索 QQ..."
              :allow-input="onlyAllowNumber"
              :maxlength="11"
              class="flex-1"
              @keydown.enter="handleSearch"
          >
            <template #prefix>🔍</template>
          </n-input>
          <n-button type="primary" ghost @click="handleSearch" style="margin-left: 8px; flex-shrink: 0;">
            搜索
          </n-button>
        </div>

        <div class="toolbar-row actions">
          <n-button
              size="small"
              @click="handleDirectQuery"
              v-if="['owner', 'super_admin'].includes(currentUser.role)"
              style="flex-shrink: 0;"
          >
            档案查询
          </n-button>

          <n-button
              v-if="isAdmin"
              type="primary"
              size="small"
              @click="showAddModal = true"
              style="flex-shrink: 0;"
          >
            + 添加记录
          </n-button>
        </div>
      </div>

      <n-data-table
          v-if="!isMobile"
          remote
          v-model:checked-row-keys="checkedRowKeys"
          :columns="columns"
          :data="data"
          :loading="loading"
          :pagination="pagination"
          :row-key="(row) => row.user_id"
          :size="themeStore.density"
          striped
      />

      <div v-else class="mobile-list">
        <n-empty v-if="data.length === 0" description="暂无数据" class="py-8"/>
        <div v-for="item in data" :key="item.user_id" class="mobile-card">
          <div class="card-header">
            <QQUser :qq="item.user_id" :data="item"/>
            <n-tag :type="item.disabled ? 'error' : 'success'" size="small" round :bordered="false">
              {{ item.disabled ? '已失效' : '生效中' }}
            </n-tag>
          </div>

          <div class="card-body">
            <div class="reason-text">{{ item.reason || '无理由' }}</div>
            <div class="meta-info">
              <span>操作人: <QQUser :qq="item.operator_id || item.source_id" :show-tag="false" size="small"/></span>
            </div>
          </div>

          <div class="card-actions">
            <n-button size="small" secondary @click="openDetail(item)">
              详情
            </n-button>

            <template v-if="isAdmin">
              <n-button size="small" secondary type="primary" @click="openEdit(item)">
                编辑
              </n-button>

              <n-popconfirm v-if="!item.disabled" @positive-click="toggleStatus(item.user_id, true)">
                <template #trigger>
                  <n-button size="small" secondary type="warning">失效</n-button>
                </template>
                确定失效？
              </n-popconfirm>
              <n-popconfirm v-else @positive-click="toggleStatus(item.user_id, false)">
                <template #trigger>
                  <n-button size="small" secondary type="success">启用</n-button>
                </template>
                确定启用？
              </n-popconfirm>

              <n-popconfirm v-if="['owner', 'super_admin'].includes(currentUser.role)"
                            @positive-click="hardDelete(item.user_id)">
                <template #trigger>
                  <n-button size="small" ghost type="error">删除</n-button>
                </template>
                确认彻底删除？
              </n-popconfirm>
            </template>
          </div>
        </div>

        <div class="mobile-pagination">
          <n-pagination
              v-model:page="pagination.page"
              :item-count="pagination.itemCount"
              :page-size="pagination.pageSize"
              simple
              @update:page="pagination.onChange"
          />
        </div>
      </div>

    </n-card>

    <n-modal v-model:show="showDetailModal">
      <n-card title="📜 数据详情" style="width: 600px; max-width: 95vw;" role="dialog" aria-modal="true" closable
              @close="showDetailModal = false">
        <n-descriptions bordered :column="1" label-placement="left" size="small">
          <n-descriptions-item label="QQ">
            <QQUser :qq="currentDetail.user_id"/>
          </n-descriptions-item>
          <n-descriptions-item label="原因">{{ currentDetail.reason }}</n-descriptions-item>
          <n-descriptions-item label="当前状态">
            <n-tag :type="currentDetail.disabled ? 'error' : 'success'" size="small">
              {{ currentDetail.disabled ? '失效' : '生效中' }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="来源/申请人">
            <QQUser :qq="currentDetail.source_id"/>
            <span v-if="!currentDetail.source_id" style="color: #999; margin-left:5px">(手动添加)</span>
          </n-descriptions-item>
          <n-descriptions-item label="操作人/批准人">
            <QQUser :qq="currentDetail.operator_id"/>
            <span v-if="!currentDetail.operator_id">-</span>
          </n-descriptions-item>
          <n-descriptions-item label="最后更新">
            {{ formatTime(currentDetail.updated_at) }}
          </n-descriptions-item>

          <n-descriptions-item label="变更追溯">
            <n-scrollbar style="max-height: 300px; padding-right: 12px;">
              <n-empty v-if="!targetHistory.length" description="暂无历史记录" class="py-4"/>

              <n-timeline v-else size="large">
                <n-timeline-item
                    v-for="(log, index) in targetHistory"
                    :key="log.id"
                    :type="getLogType(log.event)"
                    :line-type="index === targetHistory.length - 1 ? 'default' : 'dashed'"
                >
                  <template #header>
                    <div class="timeline-header">
                      <n-tag :type="getLogType(log.event)" size="small" :bordered="false" style="margin-right: 8px">
                        {{ getEventLabel(log.event) }}
                      </n-tag>
                      <span class="time">{{ formatTime(log.created_at) }}</span>
                    </div>
                  </template>

                  <div class="timeline-body">
                    <div class="operator-line">
                      <span class="operator-name">
                        <QQUser :qq="log.operator" :show-tag="false"/>
                      </span>
                      <span class="action-verb">执行操作</span>
                    </div>

                    <div class="detail-text">
                      {{ parseLogDetail(log) }}
                    </div>
                  </div>
                </n-timeline-item>
              </n-timeline>
            </n-scrollbar>
          </n-descriptions-item>

          <n-descriptions-item label="原始数据">
            <n-code :code="JSON.stringify(currentDetail, null, 2)" language="json" word-wrap
                    style="max-height: 200px; overflow: auto;"/>
          </n-descriptions-item>
        </n-descriptions>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showDetailModal = false">关闭</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <n-modal v-model:show="showAddModal">
      <n-card :title="modalMode === 'add' ? '手动添加黑名单' : '编辑黑名单'" style="width: 500px; max-width: 95vw"
              role="dialog"
              aria-modal="true">
        <n-form label-placement="left" label-width="60">
          <n-form-item label="QQ 号">
            <n-input
                v-model:value="addForm.user_id"
                placeholder="输入QQ号"
                :allow-input="onlyAllowNumber"
                :maxlength="11"
                :disabled="modalMode === 'edit'"/>
          </n-form-item>
          <n-form-item label="理由">
            <n-input
                type="textarea"
                v-model:value="addForm.reason"
                placeholder="违规原因"
                :maxlength="50"
                show-count
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showAddModal = false">取消</n-button>
            <n-button @click="submitBlacklistForm" type="primary">提交</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import {computed, h, onMounted, onUnmounted, reactive, ref} from 'vue'
import {
  DataTableColumns,
  NButton,
  NCard,
  NCode,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NDivider,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPagination,
  NPopconfirm,
  NScrollbar,
  NSpace,
  NTag,
  NTimeline,
  NTimelineItem,
  useMessage
} from 'naive-ui'
import {wsClient} from '../api/ws'
import QQUser from '../components/QQUser.vue'
import {themeStore} from '../store/theme'
import type {BlacklistEntry, PaginatedResponse} from '../types'
import {userStore} from "../store/user";
import {formatTime} from "../utils/date";

const message = useMessage()
const currentUser = computed(() => userStore.userInfo).value
const isAdmin = ['owner', 'super_admin', 'admin'].includes(currentUser.role)

const data = ref<BlacklistEntry[]>([])
const search = ref('')
const loading = ref(false)
const checkedRowKeys = ref<string[]>([])

const showDetailModal = ref(false)
const showAddModal = ref(false)
const currentDetail = ref<Partial<BlacklistEntry>>({})
const addForm = ref({user_id: '', reason: ''})
const modalMode = ref<'add' | 'edit'>('add')
const targetHistory = ref<any[]>([])

// --- 移动端检测逻辑 ---
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

const pagination = reactive({
  page: 1,
  pageSize: 25,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [25, 50, 100, 200],
  onChange: (page: number) => {
    pagination.page = page
    refreshList()
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    refreshList()
  }
})

const refreshList = async () => {
  loading.value = true
  try {
    const res = await wsClient.call<PaginatedResponse<BlacklistEntry>>('admin.blacklist.list', {
      page: pagination.page,
      size: pagination.pageSize,
      keyword: search.value
    })
    data.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  refreshList()
}

const toggleStatus = async (id: string, targetDisabledStatus: boolean) => {
  try {
    await wsClient.call('admin.blacklist.set_status', {user_id: id, disabled: targetDisabledStatus})
    message.success(targetDisabledStatus ? '已移除' : '已恢复')
    refreshList()
  } catch (e) {
  }
}

// 修改提交函数
const submitBlacklistForm = async () => {
  try {
    if (modalMode.value === 'add') {
      await wsClient.call('admin.blacklist.add', addForm.value)
      message.success('添加成功')
    } else {
      await wsClient.call('admin.blacklist.update_info', addForm.value)
      message.success('更新成功')
    }
    showAddModal.value = false
    await refreshList()
  } catch (e) {
    // 错误处理交由 wsClient 或拦截器
  }
}

const handleDirectQuery = async () => {
  const targetQQ = search.value
  if (!targetQQ) return message.warning('请先在搜索框输入 QQ 号')

  // 1. 先尝试在当前已加载的列表中查找
  let target = data.value.find(item => item.user_id === targetQQ)

  // 2. 如果没找到，尝试向后端请求精确匹配 (复用 list 接口)
  if (!target) {
    loading.value = true
    try {
      const res = await wsClient.call<PaginatedResponse<BlacklistEntry>>('admin.blacklist.list', {
        page: 1,
        size: 1,
        keyword: targetQQ
      })
      if (res.items && res.items.length > 0 && res.items[0].user_id === targetQQ) {
        target = res.items[0]
      }
    } catch (e) {
      // 忽略错误
    } finally {
      loading.value = false
    }
  }

  // 3. 如果还是没有，说明该用户不在黑名单中
  // 此时构造一个“虚拟对象”，以便打开详情页查看历史记录
  if (!target) {
    message.info('该用户当前未在黑名单中，显示历史档案')
    target = {
      user_id: targetQQ,
      reason: '当前未在黑名单中',
      disabled: true, // 视为失效状态
      source_id: '',
      operator_id: '',
      updated_at: 0 // 空时间
    } as BlacklistEntry
  }

  // 4. 打开详情页
  openDetail(target)
}

const openEdit = (row: BlacklistEntry) => {
  addForm.value = {user_id: row.user_id, reason: row.reason}
  modalMode.value = 'edit'
  showAddModal.value = true
}

const fetchHistory = async (targetQq: string) => {
  targetHistory.value = []
  try {
    const res: any = await wsClient.call('admin.logs.history', {target: targetQq})
    targetHistory.value = res
  } catch (e) {
    console.error(e)
  }
}

// 1. 定义事件类型的颜色 (参考 Logs.vue)
const getLogType = (event: string) => {
  if (event.includes('created') || event.includes('added')) return 'success'
  if (event.includes('deleted') || event.includes('removed')) return 'error'
  if (event.includes('updated')) return 'warning'
  if (event.includes('handled')) return 'info'
  return 'default'
}

// 2. 定义事件的中文名称 (参考 Dashboard.vue)
const getEventLabel = (event: string) => {
  const map: Record<string, string> = {
    'blacklist.created': '新增记录',
    'blacklist.updated': '更新信息',
    'blacklist.deleted': '移除记录',
    'app.handled': '审批处理',
    'app.created': '提交申请'
  }
  return map[event] || event
}

// 3. 核心：由事件类型决定显示什么内容 (解决信息映射混乱的问题)
const parseLogDetail = (log: any) => {
  let data: any = {}
  try {
    data = JSON.parse(log.details)
  } catch (e) {
    return log.details // 解析失败直接显示原样
  }

  // 根据 event 类型精准提取字段，而不是遍历 keys
  switch (log.event) {
    case 'blacklist.created':
      // 新增通常关注：理由、来源
      return `初始理由：${data.reason || '无'} (来源: ${data.source || '未知'})`

    case 'blacklist.updated':
      // 更新通常关注：改了什么。配合后端传来的 "new (原: old)" 格式
      if (data.action === 'update_reason') {
        return `理由变更为：${data.reason}`
      }
      if (data.action === 'disable') return '操作：设为失效 (移除)'
      if (data.action === 'enable') return '操作：设为生效 (恢复)'
      // 兜底
      return data.reason ? `理由更新: ${data.reason}` : '更新了记录状态'

    case 'blacklist.deleted':
      return `操作类型：${data.type === 'hard_delete' ? '彻底物理删除' : '软删除'}`

    case 'app.handled':
      // 审批关注：结果
      const statusMap: any = {'approve': '批准', 'reject': '驳回', 'approved': '批准', 'rejected': '驳回'}
      const actionCN = statusMap[data.action] || data.action
      return `审批结果：${actionCN} (申请ID: ${data.app_id?.substring(0, 8)})`

    default:
      // 其他未知事件，尝试提取通用字段
      if (data.msg) return data.msg
      if (data.reason) return `理由: ${data.reason}`
      return JSON.stringify(data) // 实在没办法才显示 JSON
  }
}

// Columns 定义
const columns = computed<DataTableColumns<BlacklistEntry>>(() => {
  const cols: DataTableColumns<BlacklistEntry> = []
  if (isAdmin) cols.push({type: 'selection'})
  cols.push(
      {
        title: 'QQ',
        key: 'user_id',
        width: 140,
        render: (row) => h(QQUser, {qq: row.user_id, data: row})
      },
      {
        title: '理由',
        key: 'reason',
        ellipsis: {tooltip: true}
      },
      {
        title: '状态',
        key: 'disabled',
        width: 100,
        render: (row) => h(NTag, {
          type: row.disabled ? 'error' : 'success',
          size: 'small',
          bordered: false
        }, () => row.disabled ? '已失效' : '生效中')
      },
      {
        title: '操作',
        key: 'actions',
        width: 240,
        render(row) {
          const infoBtn = h(NButton, {
            size: 'small',
            secondary: true,
            type: 'info',
            style: 'margin-right: 8px',
            onClick: (e) => {
              e.stopPropagation();
              openDetail(row);
            }
          }, () => '详情')

          const buttons = [infoBtn]

          if (!isAdmin) return h('div', buttons)

          buttons.push(h(NButton, {
            size: 'small',
            secondary: true,
            type: 'primary',
            style: 'margin-right: 8px',
            onClick: (e) => {
              e.stopPropagation();
              openEdit(row);
            }
          }, () => '编辑'))

          if (!row.disabled) {
            buttons.push(h(NPopconfirm, {onPositiveClick: () => toggleStatus(row.user_id, true)}, {
              trigger: () => h(NButton, {
                size: 'small',
                type: 'warning',
                secondary: true,
                style: 'margin-right: 8px'
              }, () => '失效'), default: () => '确定失效？'
            }))
          } else {
            buttons.push(h(NPopconfirm, {onPositiveClick: () => toggleStatus(row.user_id, false)}, {
              trigger: () => h(NButton, {
                size: 'small',
                type: 'success',
                secondary: true,
                style: 'margin-right: 8px'
              }, () => '启用'), default: () => '确定启用？'
            }))
          }

          if (['owner', 'super_admin'].includes(currentUser.role)) {
            buttons.push(h(NPopconfirm, {onPositiveClick: () => hardDelete(row.user_id)}, {
              trigger: () => h(NButton, {
                size: 'small',
                type: 'error',
                ghost: true
              }, () => '删除'), default: () => '⚠️ 彻底删除记录？无法恢复！'
            }))
          }

          return h('div', buttons)
        }
      }
  )
  return cols
})

const batchUpdateStatus = async (targetDisabled: boolean) => {
  if (checkedRowKeys.value.length === 0) return
  try {
    await Promise.all(checkedRowKeys.value.map(id =>
        wsClient.call('admin.blacklist.set_status', {user_id: id, disabled: targetDisabled})
    ))
    message.success('批量操作成功')
    checkedRowKeys.value = []
    refreshList()
  } catch (e) {
    message.error('部分操作失败')
  }
}

const openDetail = (row: BlacklistEntry) => {
  currentDetail.value = row
  showDetailModal.value = true
  fetchHistory(row.user_id)
}

const batchHardDelete = async () => {
  if (checkedRowKeys.value.length === 0) return
  try {
    await Promise.all(checkedRowKeys.value.map(id =>
        wsClient.call('admin.blacklist.hard_delete', {user_id: id})
    ))
    message.success('批量删除成功')
    checkedRowKeys.value = []
    refreshList()
  } catch (e) {
    message.error('删除失败')
  }
}

const hardDelete = async (id: string) => {
  await wsClient.call('admin.blacklist.hard_delete', {user_id: id})
  message.success('已彻底删除')
  refreshList()
}

const handleBroadcast = (data: any, event?: string) => {
  if (event?.startsWith('blacklist.')) {
    refreshList()
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  refreshList()
  wsClient.on('*', handleBroadcast)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleBroadcast)
})
</script>

<style scoped>
/* 移动端专用工具栏 */
.mobile-toolbar {
  margin-bottom: 16px;
  background-color: var(--n-color-embedded);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--n-border-color);
}

.toolbar-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.toolbar-row:last-child {
  margin-bottom: 0;
}

.toolbar-row.actions {
  justify-content: flex-end;
  gap: 12px; /* 增加按钮之间的间距 */
}

.flex-1 {
  flex: 1;
}

/* PC端样式 */
.history-section {
  margin-top: 16px;
  background-color: var(--n-color-embedded); /* 适配深色模式，加一点底色区别 */
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--n-border-color);
}

.timeline-header {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.timeline-header .time {
  color: var(--n-text-color-3);
  font-size: 12px;
}

.timeline-body {
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  padding: 8px 12px;
  margin-top: 4px;
}

.operator-line {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  font-size: 13px;
}

.operator-name {
  font-weight: 500;
  margin-right: 4px;
}

.action-verb {
  color: var(--n-text-color-3);
  font-size: 12px;
}

.detail-text {
  font-size: 13px;
  color: var(--n-text-color-2);
  line-height: 1.5;
  /* 自动换行 */
  white-space: pre-wrap;
  word-break: break-all;
}

/* 移动端卡片样式 */
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
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--n-divider-color);
}

.card-body {
  margin-bottom: 12px;
}

.reason-text {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--n-text-color);
}

.meta-info {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.card-actions {
  display: flex;
  justify-content: flex-end; /* 按钮靠右 */
  gap: 8px;
}

.mobile-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
