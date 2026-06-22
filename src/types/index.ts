import type {DataTableColumn} from 'naive-ui'

// 通用 API 响应结构
export interface ApiResponse<T = any> {
    req_id: string
    code: number
    msg: string
    data: T
    type?: 'response' | 'broadcast'
    event?: string
}

// 分页响应结构
export interface PaginatedResponse<T> {
    items: T[]
    total: number
    page: number
    size: number
}

// 用户模型
export interface User {
    id: number
    qq: string
    role: 'owner' | 'super_admin' | 'admin' | 'user'
    created_at?: number
    subscriptions?: string
}

// 黑名单模型
export interface BlacklistEntry {
    user_id: string
    reason: string
    disabled: boolean
    operator_id?: string
    source_id?: string
    updated_at: number
}

// 白名单模型
export interface WhitelistEntry {
    user_id: string
    reason?: string
    operator_id: string
    created_at: number
}

// 申请单模型
export interface Application {
    id: string
    type: 'ADD' | 'REMOVE'
    applicant_id: string
    target_user_id: string
    reason: string
    status: 'pending' | 'approved' | 'rejected' | 'cancelled'
    created_at: number
    processed_by?: string
    processed_at?: number
}

// API Key 模型
export interface ApiKey {
    id: number
    key: string
    description: string
    permissions: string
    is_active: boolean
    created_by: number
    created_at: number
    created_by_qq?: string
}

// Dashboard 统计模型
export interface DashboardStats {
    counts: {
        blacklist: number
        whitelist: number
        users: number
        pending: number
    }
    trend: {
        dates: string[]
        values: number[]
    }
    distribution: Array<{ name: string; value: number }>
    top_operators: Array<{ name: string; value: number }>
}

// 操作日志模型
export interface OperationLog {
    id: number
    event: string
    operator: string
    details: string // JSON string
    created_at: number
}

// 扩展 Naive UI 的 Column 类型 (可选，方便后续扩展)
export type TableColumn = DataTableColumn
