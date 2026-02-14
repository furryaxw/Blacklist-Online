import {createDiscreteApi} from 'naive-ui'
import {reactive} from 'vue'
import type {ApiResponse} from '../types'
import router from "../router";
import {userStore} from "../store/user";

const {message} = createDiscreteApi(['message'])

// 定义 WS 消息结构
interface WsRequest {
    req_id: string
    action: string
    data: any
    token?: string | null
}

type EventHandler = (data: any, event?: string) => void

class NativeWsClient {
    private ws: WebSocket | null = null
    // Request Promise Map
    private pending = new Map<string, { resolve: (val: any) => void, reject: (err: any) => void }>()
    // Event Listeners Map: eventName -> Set<Callback>
    private listeners = new Map<string, Set<EventHandler>>()

    private reconnectTimer: any = null
    private connectPromise: Promise<void> | null = null
    private heartbeatTimer: any = null

    // === 响应式状态，供 Vue 组件直接使用 ===
    public status = reactive({
        connected: false,
        latency: 0,
        lastPingTime: 0
    })

    constructor() {
        this.connect()
    }

    // === 事件订阅机制 ===
    /**
     * 注册监听器
     * @param event 事件名称，支持 '*' 监听所有广播
     * @param callback 回调函数
     */
    public on(event: string, callback: EventHandler) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set())
        }
        this.listeners.get(event)!.add(callback)
    }

    /**
     * 移除监听器
     * @param event 事件名称
     * @param callback 原回调函数引用
     */
    public off(event: string, callback: EventHandler) {
        const handlers = this.listeners.get(event)
        if (handlers) handlers.delete(callback)
    }

    private connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return

        // 自动判断协议 (ws:// 或 wss://)
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
        // 假设后端 WS 挂载在 /blacklist-api/ws (对应 vite 代理配置) 或直接 /ws
        // 根据您的环境，这里使用相对路径以适配代理
        const url = `${protocol}//${location.host}/blacklist-api/ws`

        this.ws = new WebSocket(url)

        this.connectPromise = new Promise((resolve) => {
            if (!this.ws) return

            this.ws.onopen = () => {
                this.status.connected = true
                console.log('[WS] Connection Established')

                if (this.reconnectTimer) {
                    clearTimeout(this.reconnectTimer)
                    this.reconnectTimer = null
                }

                // 连接成功，立即启动心跳
                this.startHeartbeat()
                resolve()
            }

            this.ws.onclose = () => {
                this.status.connected = false
                this.connectPromise = null
                this.stopHeartbeat() // 停止心跳

                // 立即终止所有正在等待的请求
                this.pending.forEach(({reject}) => {
                    reject(new Error('Network Disconnected'))
                })
                this.pending.clear()

                console.warn('[WS] Disconnected. Retrying in 5s...')
                this.reconnectTimer = setTimeout(() => this.connect(), 5000)
            }

            this.ws.onerror = (error) => {
                console.error('[WS] Error:', error)
                this.status.connected = false
            }

            this.ws.onmessage = (event) => {
                try {
                    const response: ApiResponse = JSON.parse(event.data)

                    // 1. 处理广播消息
                    if (response.type === 'broadcast' && response.event) {
                        this.dispatchBroadcast(response.event, response.data)
                        return
                    }

                    // 2. 处理请求响应
                    const {req_id, code, data, msg} = response
                    if (req_id && this.pending.has(req_id)) {
                        const {resolve, reject} = this.pending.get(req_id)!
                        this.pending.delete(req_id)

                        if (code === 200) {
                            resolve(data)
                        } else {
                            // 增加对 401 和特定错误信息的判断
                            // "登录已过期" 是后端 deps.py 抛出的
                            // "无效的令牌或已过期" 是 ws_manager.py 抛出的
                            // "身份验证失败" 是旧逻辑
                            if (code === 401 || msg.includes('过期') || msg.includes('身份验证') || msg.includes('无效的令牌')) {
                                console.warn('[WS] Session expired or invalid')
                                userStore.clear()
                                router.push('/')
                                // 不弹窗报错，直接跳登录页体验更好
                                reject(new Error('Session Expired'))
                                return
                            }

                            console.error(`[WS] Request Failed: ${msg}`, response)
                            if (msg !== 'ok' && !req_id.startsWith('ping_')) {
                                message.error(msg || '操作失败')
                            }
                            reject(new Error(msg))
                        }
                    }
                } catch (e) {
                    console.error('[WS] Failed to parse message:', event.data)
                }
            }
        })
    }

    private dispatchBroadcast(event: string, data: any) {
        // 1. 触发精确匹配的监听器
        const specificHandlers = this.listeners.get(event)
        if (specificHandlers) specificHandlers.forEach(cb => cb(data, event))

        // 2. 触发通配符 '*' 监听器
        const globalHandlers = this.listeners.get('*')
        if (globalHandlers) globalHandlers.forEach(cb => cb(data, event))
    }

    /**
     * 核心调用方法
     * @param action 后端路由动作，例如 "auth/login"
     * @param payload 数据载荷
     */
    async call<T = any>(action: string, payload: any = {}): Promise<T> {
        // 确保连接已就绪
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            if (this.connectPromise) {
                await this.connectPromise
            } else {
                throw new Error('WebSocket Disconnected')
            }
        }

        // 如果是心跳包，使用特殊前缀方便过滤错误
        const isPing = action === 'system.ping'
        const reqId = (isPing ? 'ping_' : '') + Date.now().toString(36) + Math.random().toString(36).substr(2)

        const token = localStorage.getItem('token') || sessionStorage.getItem('token')

        const requestPacket: WsRequest = {
            req_id: reqId,
            action,
            data: payload,
            token
        }

        return new Promise<T>((resolve, reject) => {
            // 注册回调
            this.pending.set(reqId, {resolve, reject})

            // 发送消息
            this.ws!.send(JSON.stringify(requestPacket))

            // 10秒超时熔断
            setTimeout(() => {
                if (this.pending.has(reqId)) {
                    this.pending.delete(reqId)
                    const err = new Error('Request Timeout')
                    reject(err)
                    // 仅非心跳请求提示超时
                    if (!isPing) message.error('服务器响应超时')
                }
            }, 10000)
        })
    }

    // === 心跳逻辑 ===
    private startHeartbeat() {
        this.stopHeartbeat()
        // 立即发一次
        this.sendPing()
        // 每 5 秒发送一次心跳 (根据需要调整频率)
        this.heartbeatTimer = setInterval(() => {
            if (this.status.connected) this.sendPing()
        }, 5000)
    }

    private stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer)
            this.heartbeatTimer = null
        }
    }

    // 公开的手动测速方法
    public async sendPing() {
        try {
            const local_time = Date.now()
            await this.call<{ timestamp: number }>('system.ping')
            const now_time = Date.now()
            const rtt = now_time - local_time
            this.status.latency = rtt
            this.status.lastPingTime = Date.now()
            return rtt
        } catch (e) {
            console.warn('[WS] Heartbeat failed', e)
            return -1
        }
    }
}

// 导出单例
export const wsClient = new NativeWsClient()