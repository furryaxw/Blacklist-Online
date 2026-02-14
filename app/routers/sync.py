import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.utils.database import get_session
from app.utils.deps import verify_bot_token
from app.utils.models import SyncEvent, BlacklistEntry, WhitelistEntry, ApiKey  # 修正类型注解

router = APIRouter(tags=["Sync"])


@router.post("/sync")
async def sync_data(
        payload: dict,
        session: Session = Depends(get_session),
        key: ApiKey = Depends(verify_bot_token)
):
    """
    Git-like 同步接口
    Payload: { "revision": 10, "instanceId": "uuid..." }
    """
    client_rev = int(payload.get("revision") or 0)
    client_instance_id = payload.get("instanceId")

    # 强制单实例绑定：一个 Key 只能对应一个 Bot Instance
    if client_instance_id:
        # 情况1: Key 已经绑定了实例，且与当前请求的不一致 -> 拒绝
        if key.instance_uuid and key.instance_uuid != client_instance_id:
            raise HTTPException(
                status_code=403,
                detail=f"Security Alert: This API Key is already bound to another Bot instance. "
                       f"Please use a new Key or reset the binding in the dashboard."
            )

        # 情况2: Key 未绑定 -> 执行首次绑定
        if not key.instance_uuid:
            key.instance_uuid = client_instance_id
            session.add(key)
            session.commit()
            # 刷新对象以获取最新状态
            session.refresh(key)

    # 获取服务器最新版本
    last_event = session.exec(select(SyncEvent).order_by(SyncEvent.revision.desc())).first()
    server_rev = last_event.revision if last_event else 0

    if client_rev >= server_rev:
        return {"strategy": "up-to-date", "newRevision": server_rev}

    # 如果落后超过 500 个版本，或者客户端是 0 (新初始化)，执行全量
    if server_rev - client_rev > 500 or client_rev == 0:
        bl_entries = session.exec(select(BlacklistEntry)).all()
        wl_entries = session.exec(select(WhitelistEntry)).all()
        return {
            "strategy": "full_replace",
            "newRevision": server_rev,
            "data": {
                "blacklist": [entry.model_dump() for entry in bl_entries],
                "whitelist": [entry.model_dump() for entry in wl_entries]
            }
        }

    # 增量同步
    events = session.exec(
        select(SyncEvent)
        .where(SyncEvent.revision > client_rev)
        .order_by(SyncEvent.revision.asc())
    ).all()

    upserts = []
    deletes = []

    whitelist_upserts = []
    whitelist_deletes = []

    for event in events:
        data = json.loads(event.payload)
        table = data.pop("table", "blacklist")

        if event.action == "upsert":
            if table == "whitelist":
                data.pop("disabled")
                whitelist_upserts.append(data)
            else:
                upserts.append(data)

        elif event.action == "delete":
            target_id = data.get("user_id")
            if table == "whitelist":
                data.pop("disabled")
                whitelist_deletes.append(target_id)
            else:
                deletes.append(target_id)

    return {
        "strategy": "incremental",
        "newRevision": server_rev,
        "data": {
            "upserts": upserts,
            "deletes": deletes,
            "whitelist_upserts": whitelist_upserts,
            "whitelist_deletes": whitelist_deletes
        }
    }
