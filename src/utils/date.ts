// frontend/src/utils/date.ts
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

// Project timestamps are Unix seconds. Milliseconds and legacy ISO strings are
// accepted here only as compatibility fallbacks.
const toDayjs = (date: string | number | Date | null | undefined) => {
    if (!date) return '-'
    if (typeof date === 'number') {
        return dayjs(date < 1_000_000_000_000 ? date * 1000 : date)
    }
    if (typeof date === 'string' && /^\d+$/.test(date)) {
        const ts = Number(date)
        return dayjs(ts < 1_000_000_000_000 ? ts * 1000 : ts)
    }
    return dayjs(date)
}

export const toLocalDate = (date: string | number | Date | null | undefined) => {
    const parsed = toDayjs(date)
    if (parsed === '-') return null
    return parsed.toDate()
}

export const formatTime = (date: string | number | Date | null | undefined, format = 'YYYY-MM-DD HH:mm:ss') => {
    const parsed = toDayjs(date)
    if (parsed === '-') return '-'
    return parsed.format(format)
}

export const formatDate = (date: string | number | Date | null | undefined) => {
    return formatTime(date, 'YYYY-MM-DD')
}

/**
 * 格式化为相对时间 (例如: "3小时前")
 * @param date
 * @returns
 */
export const formatToNow = (date: string | number | Date) => {
    const parsed = toDayjs(date)
    if (parsed === '-') return '-'
    return parsed.fromNow()
}
