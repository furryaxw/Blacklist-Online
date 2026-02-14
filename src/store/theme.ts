import {reactive, watch} from 'vue'

// 读取本地存储
const savedTheme = localStorage.getItem('pref_theme') || 'auto'
const savedPrimary = localStorage.getItem('pref_primary_color') || '#6366f1'
const savedDensity = localStorage.getItem('pref_density') || 'medium'
const applyNotify = localStorage.getItem('pref_applyNotify') === 'true'

export const themeStore = reactive({
    mode: savedTheme, // 'light' | 'dark' | 'auto'
    primaryColor: savedPrimary,
    density: <"medium" | "small" | "large" | undefined>savedDensity, // 'small' | 'medium'
    notifyApply: applyNotify,

    setColor(color: string) {
        this.primaryColor = color
    }
})

// === 统一使用 Watch 监听变化并写入 localStorage ===
watch(() => themeStore.mode, (val) => localStorage.setItem('pref_theme', val))
watch(() => themeStore.primaryColor, (val) => localStorage.setItem('pref_primary_color', val))
watch(() => themeStore.density, (val) => localStorage.setItem('pref_density', val?.toString() || ""))
watch(() => themeStore.notifyApply, (val) => localStorage.setItem('pref_applyNotify', String(val)))

// 预设颜色
export const presetColors = [
    {name: '靛蓝', value: '#6366f1'},
    {name: '翠绿', value: '#10b981'},
    {name: '紫罗兰', value: '#8b5cf6'},
    {name: '玫瑰红', value: '#f43f5e'},
    {name: '天蓝', value: '#0ea5e9'}
]