<template>
  <n-modal
      v-model:show="uiStore.showProfileModal"
      :mask-closable="true"
      :auto-focus="false"
  >
    <n-card
        style="width: 600px; max-width: 90vw; border-radius: 16px; overflow: hidden"
        :bordered="false"
        content-style="padding: 0;"
        role="dialog"
        aria-modal="true"
    >
      <div class="profile-header" :class="{ 'mobile-header': isMobile }">
        <div class="bg-blur" :style="{ backgroundImage: `url(${avatarUrl})` }"></div>
        <div class="header-content">
          <n-avatar
              round
              :size="isMobile ? 64 : 80"
              :src="avatarUrl"
              class="main-avatar"
          />
          <div class="name-box">
            <h2 class="nickname">{{ profileData.nick || uiStore.currentQq }}</h2>
            <div class="tags">
              <n-tag size="small" :type="sexType" round :bordered="false" style="margin-right: 6px">
                {{ sexText }} {{ profileData.age ? `${profileData.age}岁` : '' }}
              </n-tag>
              <n-tag size="small" type="warning" round :bordered="false">
                等级：{{ profileData.qqLevel || '0' }}
              </n-tag>
            </div>
          </div>
        </div>
      </div>

      <div class="profile-body" :class="{ 'mobile-body': isMobile }">
        <n-spin :show="loading">
          <div v-if="error" class="error-box">
            <div class="icon">⚠️</div>
            <p>{{ error }}</p>
            <p class="sub">请检查 Bot 是否连接正常</p>
          </div>

          <div v-else>
            <n-descriptions :column="isMobile ? 1 : 2" label-placement="top" class="desc-grid">
              <n-descriptions-item label="QQ 号">
                <span class="mono">{{ uiStore.currentQq }}</span>
              </n-descriptions-item>

              <n-descriptions-item label="UID">
                <span class="mono">{{ profileData.uid || '-' }}</span>
              </n-descriptions-item>

              <n-descriptions-item label="注册时间">
                {{ formatDate(profileData.regTime) }}
              </n-descriptions-item>

              <n-descriptions-item label="所在地">
                {{ locationText }}
              </n-descriptions-item>

              <n-descriptions-item label="生日">
                {{ birthdayText }}
              </n-descriptions-item>

              <n-descriptions-item label="星座/生肖">
                {{ constellationText }}
              </n-descriptions-item>

              <n-descriptions-item label="手机号"
                                   v-if="!isMobile || (profileData.phoneNum && profileData.phoneNum !== '-')">
                <span v-if="profileData.phoneNum && !['-', ''].includes(profileData.phoneNum)">{{
                    profileData.phoneNum
                  }}</span>
                <span v-else class="text-gray">-</span>
              </n-descriptions-item>

              <n-descriptions-item label="邮箱" v-if="!isMobile || (profileData.eMail && profileData.eMail !== '-')">
                <span v-if="profileData.eMail && profileData.eMail !== '-'">{{ profileData.eMail }}</span>
                <span v-else class="text-gray">-</span>
              </n-descriptions-item>

              <n-descriptions-item label="VIP 状态" :span="isMobile ? 1 : 2">
                <n-tag v-if="profileData.is_vip" type="warning" size="small" round>
                  {{ profileData.is_years_vip ? '年费' : '' }}VIP {{ profileData.vip_level }}
                </n-tag>
                <span v-else class="text-gray">未开通</span>
              </n-descriptions-item>

              <n-descriptions-item label="兴趣爱好" :span="isMobile ? 1 : 2" v-if="profileData.interest">
                {{ profileData.interest }}
              </n-descriptions-item>

              <n-descriptions-item label="个人标签" :span="isMobile ? 1 : 2"
                                   v-if="profileData.labels && profileData.labels.length">
                <n-space size="small">
                  <n-tag v-for="label in profileData.labels" :key="label" size="small" :bordered="false">
                    {{ label }}
                  </n-tag>
                </n-space>
              </n-descriptions-item>

              <n-descriptions-item label="个性签名" :span="isMobile ? 1 : 2">
                <div class="long-text">
                  {{ profileData.longNick || profileData.signature || '这个人很懒，什么都没有写' }}
                </div>
              </n-descriptions-item>
            </n-descriptions>

            <div v-if="blacklistInfo" class="blacklist-warning">
              <n-alert :type="blacklistInfo.disabled ? 'warning' : 'error'" show-icon>
                <template #icon>
                  <span style="font-size: 20px">🚫</span>
                </template>
                <div class="warning-title">
                  该用户在黑名单中
                  <n-tag size="small" :type="blacklistInfo.disabled ? 'default' : 'error'" style="margin-left: 8px">
                    {{ blacklistInfo.disabled ? '已失效' : '生效中' }}
                  </n-tag>
                </div>
                <div class="warning-content">
                  <div><b>理由:</b> {{ blacklistInfo.reason }}</div>
                  <div class="sub-info">
                    操作人: {{blacklistInfo.operator_id}}
                    <br v-if="isMobile"/>
                    <span v-else> | </span>
                    时间: {{ new Date(blacklistInfo.updated_at).toLocaleDateString() }}
                  </div>
                </div>
              </n-alert>
            </div>
          </div>

        </n-spin>
      </div>

      <div class="profile-footer">
        <n-button block secondary @click="uiStore.showProfileModal = false">关闭</n-button>
      </div>
    </n-card>
  </n-modal>
</template>

<script setup lang="ts">
import {computed, onMounted, onUnmounted, ref, watch} from 'vue'
import {NAlert, NAvatar, NButton, NCard, NDescriptions, NDescriptionsItem, NModal, NSpace, NSpin, NTag} from 'naive-ui'
import {uiStore} from '../store/ui'
import {wsClient} from '../api/ws'

const loading = ref(false)
const error = ref('')
const profileData = ref<any>({})
const blacklistInfo = ref<any>(null)

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 600
}

const avatarUrl = computed(() =>
    `https://q1.qlogo.cn/g?b=qq&nk=${uiStore.currentQq}&s=640`
)

const sexType = computed(() => {
  if (profileData.value.sex === 'female') return 'error' // 粉色
  if (profileData.value.sex === 'male') return 'info'   // 蓝色
  return 'default'
})

const sexText = computed(() => {
  const map: any = {female: '♀', male: '♂', unknown: '?'}
  return map[profileData.value.sex] || '?'
})

const locationText = computed(() => {
  const {country, province, city} = profileData.value
  return [country, province, city].filter(Boolean).join(' · ') || '未知'
})

const birthdayText = computed(() => {
  const {birthday_year, birthday_month, birthday_day} = profileData.value
  if (!birthday_month) return '-'
  return `${birthday_year || ''}年${birthday_month}月${birthday_day}日`
})

const constellationText = computed(() => {
  const cMap: any = {
    1: '白羊',
    2: '金牛',
    3: '双子',
    4: '巨蟹',
    5: '狮子',
    6: '处女',
    7: '天秤',
    8: '天蝎',
    9: '射手',
    10: '摩羯',
    11: '水瓶',
    12: '双鱼'
  }
  const sMap: any = {
    1: '鼠',
    2: '牛',
    3: '虎',
    4: '兔',
    5: '龙',
    6: '蛇',
    7: '马',
    8: '羊',
    9: '猴',
    10: '鸡',
    11: '狗',
    12: '猪'
  }

  const c = cMap[profileData.value.constellation]
  const s = sMap[profileData.value.shengXiao]

  if (!c && !s) return '-'
  return `${c ? c + '座' : ''} ${s ? s + '年' : ''}`
})

const formatDate = (ts: number) => {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleDateString()
}

// 监听打开动作
watch(() => uiStore.showProfileModal, async (val) => {
  if (val && uiStore.currentQq) {
    loading.value = true
    error.value = ''
    // 先清空旧数据，保留默认头像
    profileData.value = {}
    blacklistInfo.value = null // 重置黑名单信息

    try {
      // 1. 并行请求：获取资料 + 查询黑名单
      // 注意：admin.blacklist.list 搜索是模糊匹配，需要二次确认精确匹配
      const [profileRes, blRes] = await Promise.all([
        wsClient.call('admin.system.get_qq_profile', {qq: uiStore.currentQq}),
        wsClient.call('admin.blacklist.list', {keyword: uiStore.currentQq, page: 1, size: 5})
      ])

      profileData.value = profileRes

      // 2. 筛选精确匹配的黑名单记录
      if (blRes && blRes.items) {
        const found = blRes.items.find((item: any) => String(item.user_id) === String(uiStore.currentQq))
        if (found) {
          blacklistInfo.value = found
        }
      }

    } catch (e: any) {
      error.value = e.message || '获取失败'
    } finally {
      loading.value = false
    }
  }
})

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.profile-header {
  position: relative;
  height: 140px;
  display: flex;
  align-items: flex-end;
  padding: 20px;
  background: var(--n-color-embedded);
}

/* 移动端头部高度减小 */
.mobile-header {
  height: 120px;
  padding: 16px;
}

.bg-blur {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-size: cover;
  background-position: center;
  filter: blur(20px) brightness(0.8);
  opacity: 0.5;
  z-index: 0;
}

.header-content {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.main-avatar {
  border: 4px solid var(--n-card-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  margin-right: 16px;
  margin-bottom: -10px;
  flex-shrink: 0;
}

.name-box {
  margin-bottom: 5px;
  color: var(--n-text-color);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  min-width: 0; /* Flex item truncation fix */
  flex: 1;
}

.nickname {
  margin: 0;
  font-size: 20px;
  font-weight: bold;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tags {
  margin-top: 6px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.profile-body {
  padding: 30px 24px 20px;
}

.mobile-body {
  padding: 24px 16px 16px;
}

.mono {
  font-family: monospace;
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
}

.long-text {
  background: var(--n-color-embedded);
  padding: 10px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--n-text-color-2);
}

.error-box {
  text-align: center;
  padding: 30px 0;
  color: var(--n-error-color);
}

.error-box .icon {
  font-size: 40px;
  margin-bottom: 10px;
}

.error-box .sub {
  font-size: 12px;
  opacity: 0.7;
  color: var(--n-text-color-3);
}

.profile-footer {
  padding: 0 24px 24px;
}

.text-gray {
  color: var(--n-text-color-3);
}

/* 警告样式 */
.blacklist-warning {
  margin-top: 24px;
  border-top: 1px dashed var(--n-border-color);
  padding-top: 16px;
}

.warning-title {
  font-weight: bold;
  font-size: 15px;
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.warning-content {
  font-size: 13px;
  color: var(--n-text-color-2);
}

.sub-info {
  margin-top: 2px;
  font-size: 12px;
  opacity: 0.8;
}
</style>