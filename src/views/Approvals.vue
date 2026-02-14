<template>
  <div class="approvals-page">
    <n-card title="🔔 审批管理" :bordered="false" style="margin-bottom: 20px;">
      <n-tabs type="line" animated>
        <n-tab-pane name="pending" tab="待处理申请">
          <template #tab>
            待处理申请
            <n-tag v-if="pendingApps.length" type="error" round size="small" style="margin-left: 5px">
              {{ pendingApps.length }}
            </n-tag>
          </template>

          <div v-if="pendingApps.length === 0" class="empty-state">
            <n-empty description="暂无待处理申请"/>
          </div>

          <n-list v-else hoverable clickable>
            <n-list-item v-for="app in pendingApps" :key="app.id">
              <n-thing content-style="margin-top: 10px;">
                <template #header>
                  {{ app.type === 'ADD' ? '申请拉黑' : '申请移除' }}
                  <QQUser :qq="app.target_user_id" size="small"/>
                </template>

                <template #description>
                  <n-space size="small" align="center" style="flex-wrap: wrap; gap: 4px;">
                    <n-tag :type="app.type === 'ADD' ? 'error' : 'success'" size="small">{{ app.type }}</n-tag>
                    <span class="text-gray">目标:</span>
                    <QQUser :qq="app.target_user_id"/>

                    <n-tag v-if="app.existing_entry" type="warning" size="small" round bordered>
                      ⚠️ 目标已存在
                    </n-tag>
                  </n-space>
                </template>

                <div v-if="app.existing_entry" class="diff-view">
                  <n-alert type="warning" :show-icon="true" class="mb-2" size="small">
                    这是一次<b>更新请求</b>。批准将覆盖已有记录。
                  </n-alert>

                  <n-grid :cols="2" x-gap="12" class="diff-grid">
                    <n-grid-item class="diff-col diff-old">
                      <div class="diff-label">当前数据 (Old)</div>
                      <div class="diff-item">
                        <span class="label">理由:</span>
                        <n-text :delete="app.reason !== app.existing_entry.reason" class="value">
                          {{ app.existing_entry.reason }}
                        </n-text>
                      </div>
                      <div class="diff-item">
                        <span class="label">来源:</span>
                        <span class="value">{{ app.existing_entry.source_id || '未知' }}</span>
                      </div>
                    </n-grid-item>

                    <n-grid-item class="diff-col diff-new">
                      <div class="diff-label">申请数据 (New)</div>
                      <div class="diff-item">
                        <span class="label">理由:</span>
                        <n-text :type="app.reason !== app.existing_entry.reason ? 'success' : 'default'" strong
                                class="value">
                          {{ app.reason }}
                        </n-text>
                        <n-tag v-if="app.reason !== app.existing_entry.reason" type="success" size="tiny" class="ml-1">
                          变更
                        </n-tag>
                      </div>
                      <div class="diff-item">
                        <span class="label">来源:</span>
                        <span class="value">{{ app.applicant_id }}</span>
                      </div>
                    </n-grid-item>
                  </n-grid>
                </div>

                <div v-else style="margin-bottom: 8px;">
                  <span class="text-gray">理由: </span> {{ app.reason }}
                </div>

                <template #footer>
                  <div class="app-footer">
                    <div class="footer-info">
                      <span class="text-gray text-xs">申请人:</span>
                      <QQUser :qq="app.applicant_id" :show-tag="false" size="tiny"/>
                      <span class="text-gray text-xs hidden-xs">| {{ formatTime(app.created_at, 'YYYY/MM/DD') }}</span>
                    </div>
                    <div class="footer-actions">
                      <n-button size="tiny" secondary type="info" @click="openEvidence(app)">证据</n-button>
                      <n-button size="tiny" type="primary" @click="onApproveClick(app)">批准</n-button>
                      <n-button size="tiny" type="error" secondary @click="handleApp(app, 'reject')">驳回</n-button>
                    </div>
                  </div>
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
        </n-tab-pane>

        <n-tab-pane name="history" tab="历史">
          <div v-if="isMobile" class="mobile-history-list">
            <n-card v-for="row in appHistory" :key="row.id" size="small" class="mb-2">
              <div class="history-card-header">
                <QQUser :qq="row.target_user_id"/>
                <n-tag :type="row.status === 'approved' ? 'success' : (row.status === 'rejected' ? 'error' : 'default')"
                       size="small">
                  {{ getStatusText(row.status) }}
                </n-tag>
              </div>
              <div class="history-card-body">
                <div>类型:
                  <n-tag :type="row.type === 'ADD' ? 'error' : 'success'" size="small">{{ row.type }}</n-tag>
                </div>
                <div>处理人:
                  <QQUser :qq="row.processed_by" :show-tag="false"/>
                </div>
                <div class="text-xs text-gray">{{ new Date(row.processed_at).toLocaleString() }}</div>
              </div>
            </n-card>
          </div>

          <n-data-table
              v-else
              :columns="historyColumns"
              :data="appHistory"
              :size="themeStore.density"
              :pagination="{ pageSize: 10 }"
              striped
          />
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <n-modal v-model:show="showApproveModal">
      <n-card
          style="width: 500px; max-width: 95vw"
          title="✅ 批准申请"
          :bordered="false"
          size="small"
          role="dialog"
          aria-modal="true"
      >
        <n-text depth="3" class="mb-2" style="display: block; margin-bottom: 10px; font-size: 13px">
          您可以修改最终入库的理由。
        </n-text>

        <n-form-item label="入库理由">
          <n-input
              v-model:value="approveReason"
              type="textarea"
              :rows="3"
              placeholder="理由"
              :maxlength="100"
              show-count
          />
        </n-form-item>

        <template #footer>
          <n-space justify="end">
            <n-button @click="showApproveModal = false">取消</n-button>
            <n-button type="primary" @click="confirmApprove" :loading="approving">
              确认
            </n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <n-modal v-model:show="showEvidenceModal">
      <n-card
          style="width: 700px; max-width: 95vw; max-height: 85vh; overflow-y: auto;"
          title="📂 证据详情"
          :bordered="false"
          role="dialog"
          aria-modal="true"
      >
        <n-empty v-if="evidenceList.length === 0" description="暂无证据"/>

        <div v-else>
          <div v-for="(item, index) in evidenceList" :key="index" class="evidence-item">

            <div v-if="item.type === 'system'">
              <n-divider dashed>
                <n-tag size="small" type="info">上传图片</n-tag>
              </n-divider>
              <n-image-group>
                <n-space>
                  <n-image
                      v-for="(url, idx) in item.data"
                      :key="idx"
                      width="80"
                      :src="url"
                      object-fit="cover"
                      style="border: 1px solid #eee; border-radius: 4px"
                  />
                </n-space>
              </n-image-group>
            </div>

            <div v-else-if="item.type === 'bot'">
              <n-divider dashed>
                <n-tag size="small" type="warning">聊天记录</n-tag>
              </n-divider>
              <div class="chat-container">
                <div v-for="(node, nIdx) in item.data" :key="nIdx" class="chat-node">
                  <div class="chat-header" v-if="node.sender">
                    <span class="chat-name">{{ node.sender.nickname }}</span>
                    <span class="chat-uid">({{ node.sender.user_id }})</span>
                    <span class="chat-time" v-if="node.time">{{ formatTime(node.time) }}</span>
                  </div>
                  <div class="chat-content">
                    <template v-if="isImageUrl(node.data)">
                      <n-image :src="node.data" width="100" style="max-width: 100%"/>
                    </template>
                    <template v-else>{{ node.data }}</template>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </n-card>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import {h, onMounted, onUnmounted, ref} from 'vue'
import {wsClient} from '../api/ws'
import {themeStore} from '../store/theme'
import QQUser from '../components/QQUser.vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDivider,
  NEmpty,
  NFormItem,
  NGrid,
  NGridItem,
  NImage,
  NImageGroup,
  NInput,
  NList,
  NListItem,
  NModal,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NThing,
  useMessage
} from 'naive-ui'
import {formatTime} from "../utils/date";

const message = useMessage()
const pendingApps = ref<any[]>([])
const appHistory = ref<any[]>([])

const showApproveModal = ref(false)
const approving = ref(false)
const approveReason = ref('')
const currentAppId = ref('')

const showEvidenceModal = ref(false)
const evidenceList = ref<any[]>([])

// 移动端判断
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

// 待处理逻辑
const fetchPending = async () => {
  try {
    // 假设后端 admin.apps.list 已经像之前约定那样返回了 existing_entry 字段
    const res: any = await wsClient.call('admin.apps.list', {status: 'pending'})
    pendingApps.value = res
  } catch (e) {
    message.error('加载申请失败')
  }
}

const onApproveClick = (app: any) => {
  // 只有 "ADD" (请求拉黑) 类型的申请才需要重写理由
  // 移除申请(REMOVE)通常不需要理由，或者沿用原有逻辑
  if (app.type === 'ADD') {
    currentAppId.value = app.id
    approveReason.value = app.reason // 预填原有理由
    showApproveModal.value = true
  } else {
    // 其他类型直接批准
    handleApp(app, 'approve')
  }
}

const confirmApprove = async () => {
  if (!approveReason.value) return message.warning('理由不能为空')

  approving.value = true
  try {
    // 调用 handleApp，传入第三个参数：overrideReason
    await handleApp({id: currentAppId.value}, 'approve', approveReason.value)
    showApproveModal.value = false
  } finally {
    approving.value = false
  }
}

// handleApp 现在接收整个 app 对象以便判断逻辑
const handleApp = async (app: any, action: string, overrideReason?: string) => {
  try {
    // 构造 payload
    const payload: any = {
      app_id: app.id,
      action
    }

    // 如果有重写的理由，带上它
    if (overrideReason) {
      payload.reason = overrideReason
    }

    const res: any = await wsClient.call('admin.apps.handle', payload)

    // 根据后端返回显示更详细的提示
    if (res && res.msg) {
      if (action === 'approve' && res.is_update) {
        message.warning(res.msg)
      } else {
        message.success(res.msg || '操作成功')
      }
    } else {
      message.success('操作成功')
    }

    fetchPending()
    fetchHistory()
  } catch (e: any) {
    message.error(e.message || '操作失败')
  }
}

// 历史记录逻辑
const fetchHistory = async () => {
  try {
    const res: any = await wsClient.call('admin.apps.history')
    console.info(res)
    appHistory.value = res
  } catch (e) {
  }
}

const getStatusText = (s: string) => {
  const map: any = {approved: '通过', rejected: '拒绝', cancelled: '取消'}
  return map[s] || s
}

const historyColumns = [
  {
    title: '目标',
    key: 'target_user_id',
    // 使用组件渲染
    render: (row: any) => h(QQUser, {qq: row.target_user_id})
  },
  {
    title: '类型',
    key: 'type',
    render: (row: any) => h(NTag, {
      type: row.type === 'ADD' ? 'error' : 'success',
      size: 'small',
      bordered: false
    }, () => row.type)
  },
  {
    title: '状态',
    key: 'status',
    render: (row: any) => h(NTag, {
      type: row.status === 'approved' ? 'success' : (row.status === 'rejected' ? 'error' : 'default'),
      bordered: false
    }, () => getStatusText(row.status))
  },
  {
    title: '处理人',
    key: 'processed_by',
    render: (row: any) => row.processed_by ? h(QQUser, {qq: row.processed_by}) : '-'
  },
  {
    title: '处理时间',
    key: 'processed_at',
    render: (row: any) => formatTime(row.processed_at)
  }
]

const handleAppEvent = (data: any, event?: string) => {
  if (event?.startsWith('app.')) {
    fetchPending();
    fetchHistory();
  }
}

const openEvidence = (app: any) => {
  try {
    const raw = app.evidence
    // 解析 JSON
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw

    // 兼容旧数据或空数据，确保是数组
    if (Array.isArray(parsed)) {
      evidenceList.value = parsed
    } else {
      // 这里的逻辑是为了兼容之前可能已经产生的脏数据
      evidenceList.value = []
    }
    showEvidenceModal.value = true
  } catch (e) {
    message.error('证据数据解析异常')
    evidenceList.value = []
  }
}

// 辅助函数：简单的图片URL判断 (Bot传来的 data 可能是纯文本也可能是 http 链接)
const isImageUrl = (str: string) => {
  return str.startsWith('http') && (str.includes('.jpg') || str.includes('.png') || str.includes('gchat.qpic.cn'))
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchPending()
  fetchHistory()
  wsClient.on('*', handleAppEvent) // 也可以精确监听 app.created 等
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleAppEvent)
})
</script>

<style scoped>
.text-gray {
  color: var(--n-text-color-3);
}

.text-xs {
  font-size: 12px;
}

/* 底部操作栏：移动端换行 */
.app-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  flex-wrap: wrap;
  gap: 8px;
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.footer-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 600px) {
  .hidden-xs {
    display: none;
  }

  .diff-old {
    border-right: none;
    border-bottom: 1px dashed var(--n-border-color);
    padding-bottom: 12px;
    margin-bottom: 12px;
    padding-right: 0;
  }

  .diff-new {
    padding-left: 0;
  }
}

/* Diff View */
.diff-view {
  background-color: rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 12px;
}

.diff-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.diff-old {
  border-right: 1px dashed var(--n-border-color);
  padding-right: 12px;
  opacity: 0.8;
}

.diff-new {
  padding-left: 12px;
}

.diff-label {
  font-size: 11px;
  color: var(--n-text-color-3);
  font-weight: bold;
  margin-bottom: 4px;
}

.diff-item {
  font-size: 13px;
  display: flex;
  align-items: center;
}

.diff-item .label {
  color: var(--n-text-color-3);
  margin-right: 6px;
  width: 32px;
  flex-shrink: 0;
}

.diff-item .value {
  flex: 1;
  word-break: break-all;
}

.ml-1 {
  margin-left: 4px;
}

/* 移动端历史卡片 */
.mobile-history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.history-card-body {
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>