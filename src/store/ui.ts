// src/store/ui.ts
import {reactive} from 'vue'

export const uiStore = reactive({
    showProfileModal: false,
    currentQq: '',
    initialBlacklistData: null as any,

    openProfile(qq: string | number, data?: any) {
        if (!qq) return
        this.currentQq = String(qq)
        this.initialBlacklistData = data
        this.showProfileModal = true
    }
})