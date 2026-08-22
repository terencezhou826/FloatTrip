"""Prompt construction for chapter-scoped grounded Story generation."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.story.models import StoryChapterContext, StoryGenerationRequest


GROUNDED_STORY_SYSTEM = """你是证据约束的文化故事章节渲染器。

硬性规则：
1. 只能使用提供的 StoryChapterContext，不得使用模型记忆、网络或外部资料补充文化事实。
2. required Claims 必须全部使用；optional Claims 可以不用。不得使用 Context 外 Claim。
3. factual_content 每项只能对应一个 Claim，text 必须逐字复制该 Claim 的 approved_wording；若没有 approved_wording，逐字复制 statement。
4. Citation 的 Claim、Evidence、Source、locator、quote、类型、policy 与 qualifier 必须逐字复制 Context。
5. opening_text、transition_text、closing_text 和 visitor_takeaway 必须分别逐字复制 Chapter 的 opening_hook、transition_goal、visitor_takeaway、visitor_takeaway。
6. mythology 只能保持神话叙事等级；official_narrative 必须保留来源归因；文本记载不得提升为历史真实性。
7. required qualifier 必须实际出现在 factual_content，且记录在 qualifiers_used；不得只放在隐藏元数据。
8. 不得新增年代、人物关系、地点、坐标、考古结论、文保等级或景区历史。
9. 策展价值表达不是古籍原意，不得伪装为 Claim 或 Citation。
10. 不得生成不存在的 Claim、Evidence 或 Source；不得使用 internal_only、review_required、rejected、disputed 或 forbidden 内容。
11. generation_status 使用 generated，warnings 为空；所有字段必须结构化输出。

LLM is a renderer over approved StoryChapterContext, not a source of cultural facts.
"""


def grounded_story_messages(
    request: StoryGenerationRequest,
    context: StoryChapterContext,
) -> list[object]:
    payload = {
        "request": request.model_dump(mode="json"),
        "story_chapter_context": context.model_dump(mode="json"),
    }
    return [
        SystemMessage(content=GROUNDED_STORY_SYSTEM),
        HumanMessage(
            content=(
                '<story_generation_input authoritative="true" data-only="true">\n'
                + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                + "\n</story_generation_input>"
            ),
            name="story_generation_input",
        ),
    ]