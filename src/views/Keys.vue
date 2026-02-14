<template>
  <div class="keys-manage">
    <n-card title="🔑 API 密钥管理" :bordered="false">
      <div class="toolbar">
        <div class="toolbar-top">
          <n-input
              v-model:value="newDesc"
              placeholder="备注 (例如: 1群Bot)"
              class="desc-input"
              clearable
              :maxlength="20"
              show-count
          >
            <template #prefix>📝</template>
          </n-input>

          <n-button type="primary" @click="createKey" :disabled="loading" class="create-btn">
            {{ loading ? '...' : '新建' }}
          </n-button>
        </div>

        <div class="toolbar-bottom">
          <n-checkbox-group v-model:value="newPerms">
            <n-space item-style="display: flex; align-items: center;">
              <n-checkbox value="read" label="读权限 (同步)"/>
              <n-checkbox value="write" label="写权限 (申请)"/>
            </n-space>
          </n-checkbox-group>
        </div>
      </div>

      <n-alert v-if="currentUser.role === 'admin'" type="info" style="margin-bottom: 20px" :bordered="false" show-icon>
        普通管理员只能管理自己创建的 Key。
      </n-alert>

      <n-data-table
          v-if="!isMobile"
          :columns="columns"
          :data="keys"
          :loading="tableLoading"
          :size="themeStore.density" striped
      />

      <div v-else class="mobile-list">
        <n-card v-for="item in keys" :key="item.id" size="small" class="key-card">
          <div class="key-header">
            <span class="desc">{{ item.description }}</span>
            <n-popconfirm @positive-click="deleteKey(item.id)">
              <template #trigger>
                <n-button size="tiny" type="error" secondary>删除</n-button>
              </template>
              删除 Key?
            </n-popconfirm>
          </div>

          <div class="key-body">
            <div class="key-row">
              <span class="label">权限:</span>
              <n-space size="small">
                <n-tag v-for="p in (item.permissions||'').split(',')" :key="p" size="tiny" type="info"
                       :bordered="false">{{ p }}
                </n-tag>
              </n-space>
            </div>
            <div class="key-row" v-if="['owner', 'super_admin'].includes(currentUser.role)">
              <span class="label">创建者:</span>
              <QQUser :qq="item.created_by_qq" size="small" :show-tag="false"/>
            </div>
            <div class="key-token-box" @click="copyToClipboard(item.key)">
              <div class="token-val">{{ item.key }}</div>
              <div class="copy-hint">点击复制</div>
            </div>
            <div class="key-row" style="margin-top: 8px">
              <span class="label">实例:</span>
              <n-tag v-if="item.instance_uuid" size="tiny">{{ item.instance_uuid.substring(0, 8) }}</n-tag>
              <span v-else class="text-gray">未连接</span>
            </div>
          </div>
        </n-card>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import {computed, h, onMounted, onUnmounted, ref} from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NDataTable,
  NInput,
  NPopconfirm,
  NSpace,
  NTag,
  NTooltip,
  useMessage
} from 'naive-ui'
import {wsClient} from '../api/ws'
import {themeStore} from '../store/theme'
import QQUser from "../components/QQUser.vue";
import {userStore} from "../store/user";

const message = useMessage()
const keys = ref<any[]>([])
const newDesc = ref('')
const newPerms = ref<string[]>([])
const loading = ref(false)
const tableLoading = ref(false)

// 获取当前用户信息
const currentUser = computed(() => userStore.userInfo).value

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

// 动态定义表格列 (根据权限显示不同列)
const columns = computed(() => {
  const cols: any[] = [
    {title: 'ID', key: 'id', width: 60},
    {title: '备注', key: 'description'},
    {
      title: '权限',
      key: 'permissions',
      render: (row: any) => {
        const perms = (row.permissions || '').split(',')
        return h(NSpace, {size: 'small'}, () => perms.map((p: string) =>
            h(NTag, {size: 'small', type: 'info', bordered: false}, () => p)
        ))
      }
    }
  ]

  // 2. 动态列：仅超管和Owner显示“创建人”
  if (['owner', 'super_admin'].includes(currentUser.role)) {
    cols.push({
      title: '创建人',
      key: 'created_by_qq',
      render: (row: any) => h(QQUser, {qq: row.created_by_qq})
    })
  }

  // 继续拼接后续列 (Token, 实例, 操作...)
  cols.push(
      {
        title: 'API Token',
        key: 'key',
        width: 300,
        render: (row: any) => {
          return h(
              NTooltip,
              {trigger: 'hover', placement: 'top'},
              {
                trigger: () => h(
                    NTag,
                    {
                      type: 'warning',
                      bordered: false,
                      style: 'cursor: pointer; font-family: monospace; max-width: 280px; overflow: hidden; text-overflow: ellipsis;',
                      onClick: () => copyToClipboard(row.key)
                    },
                    () => row.key
                ),
                default: () => '点击复制'
              }
          )
        }
      },
      {
        title: '绑定实例',
        key: 'instance_uuid',
        render: (row: any) => row.instance_uuid ?
            h(NTag, {size: 'small'}, () => row.instance_uuid.substring(0, 8)) :
            h('span', {style: 'color: var(--n-text-color-3); font-size: 12px'}, '未连接')
      },
      {
        title: '操作',
        key: 'action',
        render(row: any) {
          return h(NPopconfirm, {
            onPositiveClick: () => deleteKey(row.id)
          }, {
            trigger: () => h(NButton, {size: 'small', type: 'error', secondary: true}, () => '删除'),
            default: () => '确定删除?'
          })
        }
      }
  )

  return cols
})

// 复制功能
const copyToClipboard = (text: string) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      message.success('Token 已复制')
    }).catch(() => {
      message.error('复制失败')
    })
  } else {
    message.warning('请手动复制')
  }
}

// 获取列表
const fetchKeys = async () => {
  tableLoading.value = true
  try {
    const res: any = await wsClient.call('admin.keys.list')
    keys.value = res
    fetchDefaultPerms()
  } catch (e) {
    // 错误由 request.ts 拦截器处理
  } finally {
    tableLoading.value = false
  }
}

// 创建 Key
const createKey = async () => {
  if (!newDesc.value) return message.warning('请输入备注')
  if (newPerms.value.length === 0) return message.warning('请至少选择一个权限')

  loading.value = true
  try {
    await wsClient.call('admin.keys.create', {
      description: newDesc.value,
      permissions: newPerms.value.join(',')
    })
    message.success('创建成功')
    newDesc.value = ''
    fetchKeys()
  } catch (e) {
  } finally {
    loading.value = false
  }
}

const fetchDefaultPerms = async () => {
  try {
    // 只有管理员才需要拉取这个配置
    if (['owner', 'super_admin', 'admin'].includes(currentUser.role)) {
      const res: any = await wsClient.call('admin.system.get_public')
      if (res.DEFAULT_KEY_PERMS) {
        // 数据库存的是字符串 "read,write"，转为数组
        newPerms.value = res.DEFAULT_KEY_PERMS.split(',')
      }
    }
  } catch (e) {
  }
}

// 删除 Key
const deleteKey = async (id: number) => {
  try {
    await wsClient.call('admin.keys.delete', {key_id: id})
    message.success('已删除')
    fetchKeys()
  } catch (e) {
  }
}

const handleKeyEvent = (data: any, event?: string) => {
  if (event?.startsWith('key.')) {
    fetchKeys()
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchKeys()
  wsClient.on('*', handleKeyEvent)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleKeyEvent)
})
</script>

<style scoped>
/* 简单的布局调整 */
.keys-manage {
  /* 移除原本的 max-width 限制，让其自适应 n-layout-content */
  width: 100%;
}

/* 响应式工具栏 */
.toolbar {
  margin-bottom: 20px;
  background-color: var(--n-color-embedded);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-top {
  display: flex;
  gap: 8px;
  width: 100%;
}

.desc-input {
  flex: 1;
}

.toolbar-bottom {
  display: flex;
  align-items: center;
}

@media (min-width: 600px) {
  .toolbar {
    flex-direction: row;
    justify-content: space-between;
  }

  .toolbar-top {
    width: auto;
  }
}

/* 移动端卡片 */
.mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.key-card {
  border: 1px solid var(--n-border-color);
}

.key-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  border-bottom: 1px dashed var(--n-divider-color);
  padding-bottom: 6px;
}

.desc {
  font-weight: bold;
  font-size: 14px;
}

.key-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.key-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.label {
  color: var(--n-text-color-3);
  min-width: 40px;
}

.text-gray {
  color: var(--n-text-color-3);
  font-size: 12px;
}

.key-token-box {
  background: var(--n-color-embedded);
  padding: 8px;
  border-radius: 4px;
  margin-top: 4px;
  cursor: pointer;
  position: relative;
}

.token-val {
  font-family: monospace;
  word-break: break-all;
  font-size: 12px;
  color: var(--n-warning-color);
}

.copy-hint {
  font-size: 10px;
  color: var(--n-text-color-3);
  text-align: right;
  margin-top: 2px;
}
</style>