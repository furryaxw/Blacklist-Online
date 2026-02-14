import {reactive} from 'vue'

export const uiStore = reactive({
    showProfileModal: false,
    currentQq: '',

    openProfile(qq: string | number) {
        if (!qq) return
        this.currentQq = String(qq)
        this.showProfileModal = true
    }
})