// frontend/src/utils/date.ts
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

/**
 * 格式化时间
 * @param date 时间字符串 (ISO) 或 时间戳
 * @param format 目标格式，默认为 'YYYY-MM-DD HH:mm:ss'
 * @returns 本地时区的时间字符串
 */
export const formatTime = (date: string | number | Date | null | undefined, format = 'YYYY-MM-DD HH:mm:ss') => {
    if (!date) return '-'
    // dayjs 默认会将输入的时间（如果是 UTC ISO 字符串）转换为浏览器所在的本地时区
    return dayjs(date).format(format)
}

/**
 * 格式化为相对时间 (例如: "3小时前")
 * @param date
 * @returns
 */
export const formatToNow = (date: string | number | Date) => {
    if (!date) return '-'
    return dayjs(date).fromNow()
}
