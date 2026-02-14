import {createRouter, createWebHistory, RouteRecordRaw} from 'vue-router'
import {createDiscreteApi} from 'naive-ui'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css' // 引入样式
// 导入 Store
import {userStore} from '../store/user'

// 导入视图组件
import Login from '../views/Login.vue'
import Appeal from '../views/Appeal.vue'
import Dashboard from '../views/Dashboard.vue'
import MyApplications from '../views/MyApplications.vue'
import Blacklist from '../views/Blacklist.vue'
import Whitelist from '../views/Whitelist.vue'
import Approvals from '../views/Approvals.vue'
import Keys from '../views/Keys.vue'
import Users from '../views/Users.vue'
import Sessions from '../views/Sessions.vue'
import Logs from '../views/Logs.vue'
import Settings from '../views/Settings.vue'

// 配置 NProgress (去掉加载时的转圈圈，只留进度条)
NProgress.configure({showSpinner: false})

// 独立的 Message API，用于在路由文件中弹出提示
const {message} = createDiscreteApi(['message'])

// 定义路由并配置权限 Meta
const routes: Array<RouteRecordRaw> = [
    {
        path: '/',
        name: 'Login',
        component: Login,
        meta: {title: '登录'}
    },
    {
        path: '/appeal',
        name: 'Appeal',
        component: Appeal,
        meta: {title: '自助申诉'}
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: Dashboard,
        meta: {title: '控制台'}
    },
    {
        path: '/my-apps',
        name: 'MyApplications',
        component: MyApplications,
        meta: {
            title: '我的申请',
        }
    },
    {
        path: '/blacklist',
        name: 'Blacklist',
        component: Blacklist,
        meta: {title: '黑名单管理'}
    },
    {
        path: '/whitelist',
        name: 'Whitelist',
        component: Whitelist,
        meta: {title: '白名单管理'}
    },
    {
        path: '/sessions',
        name: 'Sessions',
        component: Sessions,
        meta: {title: '在线会话'}
    },
    {
        path: '/settings',
        name: 'Settings',
        component: Settings,
        meta: {title: '系统设置'}
    },
    // === 权限路由 ===
    {
        path: '/approvals',
        name: 'Approvals',
        component: Approvals,
        meta: {
            title: '审批管理',
            roles: ['owner', 'super_admin', 'admin']
        }
    },
    {
        path: '/keys',
        name: 'Keys',
        component: Keys,
        meta: {
            title: 'API 密钥',
            roles: ['owner', 'super_admin', 'admin']
        }
    },
    {
        path: '/users',
        name: 'Users',
        component: Users,
        meta: {
            title: '用户管理',
            roles: ['owner', 'super_admin']
        }
    },
    {
        path: '/logs',
        name: 'Logs',
        component: Logs,
        meta: {
            title: '操作日志',
            roles: ['owner', 'super_admin']
        }
    }
]

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes
})

// === 全局路由守卫 ===
router.beforeEach(async (to, from, next) => {
    // 1. 开启进度条
    NProgress.start()

    // 设置页面标题
    document.title = `${to.meta.title ? to.meta.title + ' - ' : ''}Shield Admin`

    const token = localStorage.getItem('token') || sessionStorage.getItem('token')

    // === 逻辑 A: 未登录拦截 ===
    if (to.path !== '/' && to.path !== '/appeal' && !token) {
        message.warning('请先登录')
        next('/')
        return
    }

    // === 逻辑 B: 已登录但在登录页 -> 跳控制台 ===
    if (to.path === '/' && token) {
        next('/dashboard')
        return
    }

    // === 逻辑 C: 页面刷新，状态丢失恢复 ===
    // 如果有 Token 但 userStore 里没有数据 (id === 0)，尝试重新获取
    if (token && userStore.userInfo.id === 0) {
        try {
            await userStore.fetchUser()
        } catch (e) {
            // 获取失败（Token 过期等），放行让后续逻辑或 Axios 拦截器处理，或者直接踢回
            // 这里 fetchUser 内部有错误处理，通常会清空 token
            if (!localStorage.getItem('token')) {
                next('/')
                return
            }
        }
    }

    // === 逻辑 D: 权限检查 ===
    const requiredRoles = to.meta.roles as string[] | undefined
    if (requiredRoles && requiredRoles.length > 0) {
        const userRole = userStore.userInfo.role
        if (!userRole || !requiredRoles.includes(userRole)) {
            message.error('权限不足，无法访问该页面')
            // 进度条结束
            NProgress.done()
            // 如果是从某个页面来的，中断跳转；如果是直接输 URL 进来的，去 Dashboard
            if (from.path !== '/') {
                next(false)
            } else {
                next('/dashboard')
            }
            return
        }
    }

    // 放行
    next()
})

router.afterEach(() => {
    // 关闭进度条
    NProgress.done()
})

export default router