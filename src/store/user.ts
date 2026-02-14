import {reactive} from 'vue'
import {wsClient} from '../api/ws'
import {User} from "../types";
import FingerprintJS from "@fingerprintjs/fingerprintjs";

export const userStore = reactive({
    // 默认空状态
    userInfo: {
        id: 0,
        qq: '',
        role: 'user'
    } as User,

    // 设置用户信息
    setUserInfo(user: any) {
        this.userInfo = user
    },

    // 核心：从后端拉取最新信息
    async fetchUser() {
        // 1. 获取本地 Token
        const token = localStorage.getItem('token') || sessionStorage.getItem('token')
        if (!token) return

        try {
            const fpPromise = await FingerprintJS.load()
            const result = await fpPromise.get()
            const fingerprint = result.visitorId

            // 2. 关键：调用 auth.login 而不是 get_current_user
            // 这样后端才会把当前 WebSocket 连接标记为 "属于这个 Token"
            // 从而实现精准踢人、排除当前设备发送通知等功能
            const res: any = await wsClient.call('auth.login', {token, fingerprint})

            // 后端返回结构: { user: {...}, access_token: "..." }
            // 注意：恢复登录时后端不一定返回 access_token，但一定返回 user
            if (res && res.user) {
                this.setUserInfo(res.user)
            }
        } catch (e) {
            console.error('Session restore failed', e)
            // Token 无效，清理本地状态
            this.clear()
        }
    },

    // 登出清理
    clear() {
        this.userInfo = {id: 0, qq: '', role: 'user'}
        localStorage.removeItem('token')
        sessionStorage.removeItem('token')
    }
})