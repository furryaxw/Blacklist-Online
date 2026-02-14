<template>
  <div class="layout">
    <n-card title="👥 系统用户管理" :bordered="false">
      <template #header-extra v-if="!isMobile">
        <div class="toolbar" v-if="['owner', 'super_admin'].includes(currentUser.role)">
          <n-input
              v-model:value="form.qq"
              placeholder="输入 QQ 号"
              size="small"
              style="width: 180px"
              :allow-input="onlyAllowNumber"
              :maxlength="11"
          />
          <n-select v-model:value="form.role" :options="createRoleOptions" size="small" style="width: 140px"/>
          <n-button type="primary" size="small" @click="createUser" :disabled="!form.qq">
            添加用户
          </n-button>
        </div>
      </template>

      <div v-if="isMobile && ['owner', 'super_admin'].includes(currentUser.role)" class="mobile-toolbar">
         <div class="mt-row">
           <n-input v-model:value="form.qq" placeholder="输入QQ号" :allow-input="onlyAllowNumber" :maxlength="11"/>
         </div>
         <div class="mt-row">
           <n-select v-model:value="form.role" :options="createRoleOptions" />
           <n-button type="primary" @click="createUser" :disabled="!form.qq" style="width: 80px">添加</n-button>
         </div>
      </div>

      <n-data-table
          v-if="!isMobile"
          :columns="columns"
          :data="users"
          :size="themeStore.density"
          :row-key="(row) => row.id"
      />

      <div v-else class="mobile-list">
        <n-card v-for="user in users" :key="user.id" size="small" class="user-card">
           <div class="card-header">
             <QQUser :qq="user.qq"/>
             <n-popconfirm v-if="canManage(user.role) && user.id !== currentUser.id" @positive-click="deleteUser(user.id)">
               <template #trigger>
                 <n-button size="tiny" type="error" secondary>删除</n-button>
               </template>
               确定删除？
             </n-popconfirm>
           </div>

           <div class="card-body">
             <div class="role-row">
               <span>当前角色: </span>
               <div v-if="canManage(user.role) && user.id !== currentUser.id" style="width: 120px">
                  <n-select
                    :value="user.role"
                    :options="getEditOptions(currentUser.role)"
                    size="small"
                    @update:value="(val) => switchRole(user.id, val)"
                  />
               </div>
               <n-tag v-else :type="getRoleTagType(user.role)" size="small" :bordered="false">
                 {{ getRoleLabel(user.role) }}
               </n-tag>
             </div>
           </div>
        </n-card>
      </div>

    </n-card>
  </div>
</template>

<script setup lang="ts">
import {computed, h, onMounted, onUnmounted, ref} from 'vue'
import {DataTableColumns, NButton, NCard, NDataTable, NInput, NPopconfirm, NSelect, NTag, useMessage} from 'naive-ui'
import {wsClient} from '../api/ws'
import {themeStore} from '../store/theme'
import type {User} from '../types'
import QQUser from "../components/QQUser.vue";
import {userStore} from "../store/user";

const message = useMessage()
// 1. 显式声明 ref 类型
const users = ref<User[]>([])
// 2. 断言本地存储的用户类型
const currentUser = computed(() => userStore.userInfo).value
const form = ref({qq: '', role: 'user'})

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => { isMobile.value = window.innerWidth <= 768 }

const onlyAllowNumber = (value: string) => !value || /^\d+$/.test(value)

// 定义角色映射类型，防止索引错误
const roleMap: Record<string, { type: 'error' | 'warning' | 'success' | 'default', label: string }> = {
  owner: {type: 'error', label: '所有者'},
  super_admin: {type: 'warning', label: '超管'},
  admin: {type: 'success', label: '管理员'},
  user: {type: 'default', label: '用户'}
}

const getRoleTagType = (role: string) => roleMap[role]?.type || 'default'
const getRoleLabel = (role: string) => roleMap[role]?.label || role

const createRoleOptions = computed(() => {
  const opts = [
    {label: '普通用户 (只读)', value: 'user'},
    {label: '管理员', value: 'admin'}
  ]
  if (currentUser.role === 'owner') {
    opts.push({label: '超级管理员', value: 'super_admin'})
  }
  return opts
})

// 3. 使用 DataTableColumns<User> 泛型
const columns: DataTableColumns<User> = [
  {
    title: 'QQ',
    key: 'qq',
    width: 150,
    render: (row) => h(QQUser, {qq: row.qq})
  },
  {
    title: '角色',
    key: 'role',
    render(row) {
      // row 自动被推断为 User 类型
      const canEdit = canManage(row.role) && row.id !== currentUser.id

      if (!canEdit) {
        const conf = roleMap[row.role] || {type: 'default', label: row.role}
        return h(NTag, {type: conf.type, bordered: false}, () => conf.label)
      }

      // 下拉切换逻辑
      return h(NSelect, {
        value: row.role,
        options: getEditOptions(currentUser.role),
        size: 'small',
        style: 'width: 130px',
        onUpdateValue: (val) => switchRole(row.id, val)
      })
    }
  },
  {
    title: '操作',
    key: 'action',
    render(row) {
      // 自己不能删自己，且只有有管理权限的才能删
      if (!canManage(row.role) || row.id === currentUser.id) return null
      return h(NPopconfirm, {onPositiveClick: () => deleteUser(row.id)}, {
        trigger: () => h(NButton, {size: 'small', type: 'error', secondary: true}, () => '删除'),
        default: () => '确定删除此用户？'
      })
    }
  }
]

// 权限判断辅助
const canManage = (targetRole: string) => {
  if (targetRole === 'owner') return false // 没人能动 Owner
  if (currentUser.role === 'owner') return true
  if (currentUser.role === 'super_admin') return ['admin', 'user'].includes(targetRole)
  return false
}

const getEditOptions = (myRole: string) => {
  const opts = [
    {label: '普通用户', value: 'user'},
    {label: '管理员', value: 'admin'}
  ]
  if (myRole === 'owner') opts.push({label: '超级管理员', value: 'super_admin'})
  return opts
}

// 4. 指定泛型返回值
const fetchUsers = () => wsClient.call<User[]>('admin.users.list').then(res => users.value = res)

const createUser = async () => {
  if (!form.value.qq) return
  await wsClient.call('admin.users.create', form.value)
  message.success('添加成功')
  form.value.qq = '' // 清空输入
  fetchUsers()
}

const switchRole = async (id: number, newRole: string) => {
  await wsClient.call('admin.users.set_role', {user_id: id, role: newRole})
  message.success('权限已更新')
  fetchUsers()
}

const deleteUser = async (id: number) => {
  await wsClient.call('admin.users.delete', {target_id: id})
  message.success('已删除')
  fetchUsers()
}

const handleUserEvent = (data: any, event?: string) => {
  if (event?.startsWith('user.')) {
    fetchUsers()
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchUsers()
  wsClient.on('*', handleUserEvent)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  wsClient.off('*', handleUserEvent)
})
</script>

<style scoped>
.layout {
  /* max-width: 1200px; */
  /* margin: 20px auto; */
  /* padding: 0 10px; */
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 移动端样式 */
.mobile-toolbar {
  background: var(--n-color-embedded);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.mt-row {
  display: flex;
  gap: 8px;
}

.mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.user-card {
  border: 1px solid var(--n-border-color);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--n-divider-color);
}
.role-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
</style>