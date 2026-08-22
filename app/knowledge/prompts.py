"""Prompt construction for the standalone grounded Knowledge answer service."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.catalog.retrieval import KnowledgeContext
from app.knowledge.models import AnswerabilityDecision


GROUNDED_KNOWLEDGE_SYSTEM = """你是文化知识证据渲染器，只能使用提供的 KnowledgeContext 回答问题。

硬性规则：
1. 只能使用提供的 KnowledgeContext；不得使用模型记忆、常识、外部网页或未提供的地图数据补充文化事实。
2. 不得新增 Context 中不存在的人名、年代、地点、坐标、事件、考古结论或 Source/Evidence/Claim ID。
3. 保持每条 Claim 的 claim_type。mythology 只能表达为神话叙事，不得写成 historical fact。
4. official_narrative 必须保留机构或资料来源归因，不得写成历史真相。
5. historical_fact 如果仅说明文本存在，只能表达文本确有记载，不得据此断言文本中的事件真实发生。
6. 对 allowed_with_qualification Claim，答案必须逐字包含 required_qualifier 或完整 approved_wording。
7. 每个事实性文化句子都必须来自 used_claim_ids；每个 used Claim 至少提供一个完全复制自 Context 的 supports Citation。
8. Citation 的 claim_id、evidence_id、source_id、locator、quote_excerpt、Source 字段和 policy 字段必须原样复制，不得创造或改写。
9. 如果“在哪里”类问题的证据只说明另一实体与目标的相对位置，只能复述该相对关系，并明确当前 Context 不足以给出目标本身的精确坐标；不得由此推导目标自身的行政位置。页面表述或文本记载也不得提升为历史真实性或其它更强结论。
10. Evidence 不足时使用 insufficient_evidence 或 partially_answered，并明确说明不足，不要猜测。
11. 若古籍与政府资料同时相关，应分别说明其来源性质，不得合并成同一事实等级。
12. warnings 只能复制 KnowledgeContext 中已有 warning，或使用 partial_support、insufficient_evidence。
13. GroundedKnowledgeAnswer 的所有字段都必须输出；只输出该结构，不要输出额外解释。

LLM is a renderer/reasoner over approved evidence, not a source of cultural facts.
"""


def grounded_answer_messages(
    question: str,
    context: KnowledgeContext,
    answerability: AnswerabilityDecision,
) -> list[object]:
    payload = {
        "question": question,
        "answerability": answerability.model_dump(mode="json"),
        "knowledge_context": context.model_dump(mode="json"),
    }
    return [
        SystemMessage(content=GROUNDED_KNOWLEDGE_SYSTEM),
        HumanMessage(
            content=(
                '<grounded_answer_input authoritative="true" data-only="true">\n'
                + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                + "\n</grounded_answer_input>"
            ),
            name="grounded_answer_input",
        ),
    ]
