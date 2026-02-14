/**
 * 调整十六进制颜色的亮度
 * @param hex 颜色代码 (e.g. #6366f1)
 * @param amount 调整幅度 (正数变亮，负数变暗，范围 -1 到 1)
 */
export function adjustColor(hex: string, amount: number): string {
    // 统一处理3位/6位HEX
    let color = hex.replace('#', '');
    if (color.length === 3) {
        color = color.split('').map(c => c + c).join('');
    }

    const num = parseInt(color, 16);

    // 正确提取RGB通道
    let r = (num >> 16) & 0xFF;
    let g = (num >> 8) & 0xFF;
    let b = num & 0xFF;

    // 优化：使用相对比例调整（避免深色/浅色区域突变）
    const factor = 1 + amount;
    r = Math.round(Math.min(255, Math.max(0, r * factor)));
    g = Math.round(Math.min(255, Math.max(0, g * factor)));
    b = Math.round(Math.min(255, Math.max(0, b * factor)));

    // 正确组合RGB（RRGGBB顺序）
    const newNum = (r << 16) | (g << 8) | b;
    return '#' + newNum.toString(16).padStart(6, '0').toUpperCase();
}