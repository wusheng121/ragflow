from __future__ import annotations

# 该模块仅保留旧名兼容层：项目内部已将“coach”命名迁移为“assistant”。
# 为避免外部代码或历史引用中断，暴露 CoachService 作为 AssistantService 的别名。
from app.services.assistant_service import AssistantService


# 兼容旧名，外部仍可导入 app.services.coach_service.CoachService
CoachService = AssistantService

