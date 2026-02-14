<template>
  <div class="my-apps-page">
    <n-card title="📝 我的申请" :bordered="false">
      <n-grid x-gap="24" y-gap="16" cols="1 700:2">
        <n-grid-item>
          <n-card title="发起申请" size="small" class="mb-4">
            <n-form ref="formRef" :model="form" :rules="rules">
              <n-form-item label="类型" path="type">
                <n-radio-group v-model:value="form.type">
                  <n-radio-button value="ADD">请求拉黑</n-radio-button>
                  <n-radio-button value="REMOVE">请求移除</n-radio-button>
                </n-radio-group>
              </n-form-item>

              <n-form-item label="目标 QQ" path="target_user_id">
                <n-input
                    v-model:value="form.target_user_id"
                    placeholder="请输入目标 QQ 号"
                    :allow-input="onlyAllowNumber"
                    :maxlength="11"
                />
              </n-form-item>

              <n-form-item label="理由" path="reason">
                <n-input
                    v-model:value="form.reason"
                    type="textarea"
                    placeholder="请详细描述原因"
                    :maxlength="800"
                    show-count
                />
              </n-form-item>

              <n-form-item label="图片证据">
                <n-upload
                    action="/blacklist-api/upload"
                    list-type="image-card"
                    :max="9"
                    accept="image/*"
                    @finish="handleUploadFinish"
                    @remove="handleRemove"
                >
                  点击上传
                </n-upload>
              </n-form-item>

              <n-button type="primary" block @click="submit" :loading="submitting">
                提交申请
              </n-button>
            </n-form>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-card title="申请记录" size="small">
            <n-empty v-if="apps.length === 0" description="暂无记录"/>
            <n-scrollbar v-else style="max-height: 500px">
              <n-list hoverable>
                <n-list-item v-for="app in apps" :key="app.id">
                  <template #prefix>
                    <n-tag :type="getStatusType(app.status)" size="small" class="status-tag">
                      {{ getStatusText(app.status) }}
                    </n-tag>
                  </template>

                  <n-thing :title="`${app.type === 'ADD' ? '拉黑' : '移除'} ${app.target_user_id}`">
                    <template #description>
                      <span class="text-gray text-xs">{{ new Date(app.created_at).toLocaleString() }}</span>
                    </template>
                    <div class="mt-1 text-sm reason-text">{{ app.reason }}</div>
                  </n-thing>

                  <template #suffix>
                    <n-button
                        v-if="app.status === 'pending'"
                        size="tiny"
                        secondary
                        type="warning"
                        @click="cancelApp(app.id)"
                    >
                      撤销
                    </n-button>
                  </template>
                </n-list-item>
              </n-list>
            </n-scrollbar>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import {onMounted, onUnmounted, ref} from 'vue'
import {
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NList,
  NListItem,
  NRadioButton,
  NRadioGroup,
  NScrollbar,
  NTag,
  NThing,
  NUpload,
  UploadFileInfo,
  useMessage
} from 'naive-ui'
import {wsClient} from '../api/ws'

const message = useMessage()
const submitting = ref(false)
const apps = ref<any[]>([])

const form = ref({
  type: 'ADD',
  target_user_id: '',
  reason: '',
  images: <string[]>([])
})

const rules = {
  target_user_id: {required: true, message: '请输入目标QQ', trigger: 'blur'},
  reason: {required: true, message: '请输入理由', trigger: 'blur'}
}

const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

const fetchMyApps = async () => {
  try {
    const res: any = await wsClient.call('user.apps.list')
    apps.value = res
  } catch (e) {
    message.error('加载记录失败')
  }
}


const handleUploadFinish = ({file, event}: { file: UploadFileInfo, event?: ProgressEvent }) => {
  const res = JSON.parse((event?.target as XMLHttpRequest).response)
  file.url = res.url
  form.value.images.push(res.url)
}

const handleRemove = (data: { file: UploadFileInfo }) => {
  if (data.file.url) {
    form.value.images = form.value.images.filter(u => u !== data.file.url)
  }
}

const submit = async () => {
  if (!form.value.target_user_id || !form.value.reason) return message.warning('请填写完整')

  submitting.value = true
  try {
    await wsClient.call('user.apps.submit', form.value)
    message.success('申请已提交')

    // 3. 重置表单
    form.value.target_user_id = ''
    form.value.reason = ''
    form.value.images = []

    fetchMyApps()
  } catch (e: any) {
    message.error(e.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

const cancelApp = async (appId: string) => {
  try {
    await wsClient.call('admin.apps.cancel', {targetRequestId: appId})
    message.success('已撤销')
    fetchMyApps()
  } catch (e) {
    message.error('撤销失败')
  }
}

const getStatusType = (status: string) => {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'error'
  if (status === 'cancelled') return 'default'
  return 'warning'
}

const getStatusText = (status: string) => {
  const map: any = {approved: '已通过', rejected: '已驳回', pending: '审核中', cancelled: '已撤销'}
  return map[status] || status
}

// 监听申请状态变化
const handleEvent = (data: any, event?: string) => {
  // 无论是自己提交的(app.created)还是被处理的(app.handled)，都刷新列表
  if (event?.startsWith('app.')) fetchMyApps()
}

onMounted(() => {
  fetchMyApps()
  wsClient.on('*', handleEvent)
})

onUnmounted(() => {
  wsClient.off('*', handleEvent)
})
</script>

<style scoped>
.text-gray {
  color: var(--n-text-color-3);
}

.text-xs {
  font-size: 12px;
}

.text-sm {
  font-size: 13px;
}

.mt-1 {
  margin-top: 4px;
}

.mb-4 {
  margin-bottom: 16px;
}

/* 移动端间距微调 */
.status-tag {
  margin-right: 8px;
}

@media (max-width: 600px) {
  .reason-text {
    word-break: break-all;
  }
}
</style>