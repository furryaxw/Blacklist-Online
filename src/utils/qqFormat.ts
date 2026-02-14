export function formatUserData(data: any): string {
    const lines: string[] = [];

    // 工具函数：格式化时间戳
    const formatDate = (timestamp: number): string => {
        if (!timestamp || timestamp <= 0) return '未知';
        return new Date(timestamp * 1000).toLocaleString('zh-CN', {
            timeZone: 'Asia/Shanghai',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    // ===== 基础身份信息 =====
    lines.push(`👤 昵称：${data.nick || '未设置'}`);
    if (data.longNick?.trim()) {
        lines.push(`📝 个性签名：${data.longNick.trim()}`);
    }
    lines.push(`🆔 QQ号：${data.uin}`);
    if (data.qid) {
        lines.push(`🔗 自定义ID（QID）：${data.qid}`);
    }
    // UID 通常不展示给用户，可选
    lines.push(`🔐 UID：${data.uid}`);

    // ===== 性别 =====
    const sexMap: Record<string, string> = {male: '男', female: '女', unknown: '未知'};
    lines.push(`🚻 性别：${sexMap[data.sex] || '未设置'}`);

    // ===== 生日与年龄 =====
    const hasFullBirthday = data.birthday_year > 0 && data.birthday_month > 0 && data.birthday_day > 0;
    if (hasFullBirthday) {
        lines.push(`🎂 生日：${data.birthday_year}年${data.birthday_month}月${data.birthday_day}日`);
    } else if (data.birthday_year > 0) {
        lines.push(`🎂 生日：${data.birthday_year}年`);
    } else {
        lines.push(`🎂 生日：未填写`);
    }
    lines.push(`🔢 年龄：${data.age || '未知'}`);

    // ===== 星座 =====
    const constellationMap: Record<number, string> = {
        1: '白羊座', 2: '金牛座', 3: '双子座', 4: '巨蟹座',
        5: '狮子座', 6: '处女座', 7: '天秤座', 8: '天蝎座',
        9: '射手座', 10: '摩羯座', 11: '水瓶座', 12: '双鱼座'
    };
    const constellationStr = data.constellation > 0 && data.constellation <= 12
        ? constellationMap[data.constellation]
        : '未知';
    lines.push(`⭐ 星座：${constellationStr}`);

    // ===== 生肖 =====
    const shengXiaoMap: Record<number, string> = {
        1: '鼠', 2: '牛', 3: '虎', 4: '兔',
        5: '龙', 6: '蛇', 7: '马', 8: '羊',
        9: '猴', 10: '鸡', 11: '狗', 12: '猪'
    };
    const shengXiao = shengXiaoMap[data.shengXiao] || '未知';
    lines.push(`🐶 生肖：${shengXiao}`);

    // ===== 血型 =====
    const bloodTypeMap: Record<number, string> = {
        1: 'A型', 2: 'B型', 3: 'O型', 4: 'AB型'
    };
    const blood = data.kBloodType >= 1 && data.kBloodType <= 4
        ? bloodTypeMap[data.kBloodType]
        : '未填写';
    lines.push(`🩸 血型：${blood}`);

    // ===== 地区信息 =====
    let location = '';
    if (data.country) {
        if (['香港', '澳门', '台湾'].includes(data.province)) {
            location = `中国 ${data.province}`;
        } else {
            location = [data.country, data.province, data.city].filter(Boolean).join(' ');
        }
    }
    lines.push(`📍 所在地：${location || '未填写'}`);

    // ===== 账号注册与活跃 =====
    lines.push(`📅 注册时间：${formatDate(data.regTime)}`);

    // ===== QQ等级 =====
    const levelDisplay = data.isHideQQLevel
        ? '（已隐藏）'
        : (data.qqLevel > 0 ? `${data.qqLevel}` : '0');
    lines.push(`🏆 QQ等级：${levelDisplay}`);

    // ===== VIP状态 =====
    if (data.is_vip) {
        const vipType = data.is_years_vip ? '年费VIP' : '普通VIP';
        lines.push(`💎 VIP状态：${vipType}（等级 ${data.vip_level}）`);
    } else {
        lines.push(`💎 VIP状态：否`);
    }

    // ===== 联系方式 =====
    if (data.eMail && data.eMail !== '-' && data.eMail !== '') {
        lines.push(`📧 邮箱：${data.eMail}`);
    }
    // 手机号通常不可见，除非有特殊权限
    if (data.phoneNum && !['-', ''].includes(data.phoneNum)) {
        lines.push(`📱 手机号：${data.phoneNum}`);
    }

    // ===== 兴趣与标签 =====
    if (data.interest?.trim()) {
        lines.push(`🎯 兴趣爱好：${data.interest.trim()}`);
    }
    if (Array.isArray(data.labels) && data.labels.length > 0) {
        lines.push(`🏷️ 个人标签：${data.labels.join('、')}`);
    }

    return lines.join('\n');
}