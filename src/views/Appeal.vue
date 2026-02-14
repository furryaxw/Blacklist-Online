<template>
  <div class="appeal-container">
    <div class="appeal-bg"></div>

    <n-card class="appeal-card" title="📝 自助申诉" :bordered="false" size="large">
      <template #header-extra>
        <n-button text size="small" @click="$router.push('/')">
          <template #icon>↩️</template> 返回登录
        </n-button>
      </template>

      <n-alert type="info" style="margin-bottom: 20px" :bordered="false">
        如果不幸被误封，请在此提交申诉。<br>支持上传证据，管理员审核后会通过邮件通知您。
      </n-alert>

      <n-form size="medium" label-placement="left" label-width="80">
        <n-form-item label="QQ 号" required>
          <n-input
            v-model:value="appealForm.qq"
            placeholder="被拉黑的 QQ 号码"
            :allow-input="onlyAllowNumber"
            :maxlength="11"
          />
        </n-form-item>

        <n-form-item label="联系邮箱">
          <n-input v-model:value="appealForm.email" placeholder="默认 QQ 邮箱"/>
        </n-form-item>

        <n-form-item label="申诉理由" required>
          <n-input
              v-model:value="appealForm.reason"
              type="textarea"
              placeholder="请详细说明情况..."
              :rows="4"
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

        <div class="footer-actions">
           <n-button block type="primary" size="large" @click="submitAppeal" :loading="appealLoading">
             提交申诉
           </n-button>
        </div>
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  NButton, NCard, NForm, NFormItem, NInput, NUpload, NAlert,
  useMessage, UploadFileInfo
} from 'naive-ui'
import { wsClient } from '../api/ws'

const message = useMessage()
const appealLoading = ref(false)
const appealForm = ref({
  qq: '',
  email: '',
  reason: '',
  images: <string[]>([])
})

const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

const submitAppeal = async () => {
  if (!appealForm.value.qq || !appealForm.value.reason) {
    return message.warning('请填写 QQ 号和申诉理由')
  }

  appealLoading.value = true
  try {
    // 调用公开接口
    await wsClient.call('public.appeal.submit', appealForm.value)

    const targetEmail = appealForm.value.email || `${appealForm.value.qq}@qq.com`
    message.success(`申诉已提交，结果将发送至 ${targetEmail}`, { duration: 5000 })

    // 提交成功后清空
    appealForm.value = { qq: '', email: '', reason: '', images: [] }
  } catch (e: any) {
    message.error(e.message || '提交失败')
  } finally {
    appealLoading.value = false
  }
}

const handleUploadFinish = ({file, event}: { file: UploadFileInfo, event?: ProgressEvent }) => {
  try {
    const res = JSON.parse((event?.target as XMLHttpRequest).response)
    file.url = res.url
    appealForm.value.images.push(res.url)
  } catch (e) {
    message.error('上传响应解析失败')
  }
}

const handleRemove = (data: { file: UploadFileInfo }) => {
  if (data.file.url) {
    appealForm.value.images = appealForm.value.images.filter(u => u !== data.file.url)
  }
}
</script>

<style scoped>
/* 复用 Login.vue 的样式 */
.appeal-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
  background-color: #0f172a;
}

.appeal-bg {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 80% 20%, rgb(99, 102, 241) 0%, rgb(168, 85, 247) 90%);
  opacity: 0.8;
  z-index: 0;
  filter: blur(80px);
  transform: scale(1.2);
}

.appeal-card {
  width: 90%;
  max-width: 500px; /* 适配移动端宽度策略 */
  z-index: 1;
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(10px);
  background-color: rgba(255, 255, 255, 0.9);
}

.footer-actions {
  margin-top: 24px;
}

/* 暗黑模式适配 */
@media (prefers-color-scheme: dark) {
  .appeal-card {
    background-color: rgba(24, 24, 28, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
}
</style>