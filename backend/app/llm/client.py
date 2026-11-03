"""大模型客户端：OpenAI 接口封装（/chat/completions；换其他 OpenAI 兼容服务只需改 BASE_URL/MODEL）。

用途（用户已确认）：模型只做"解读"，不编数字——
1. 吃瓜栏目：厂商高管动态下方的分析解读文字；
2. 本月政策解释的撰写辅助；
3. 竞品对比结论生成。
价格等数字一律以爬到的数据为准。
"""
import logging

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """调用 OpenAI 兼容的 /chat/completions 接口，返回模型回复文本。"""
        if not self.api_key:
            raise RuntimeError("未配置 LLM_API_KEY，无法调用大模型")
        resp = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def analyze(self, text: str) -> str:
        """通用解读：对一段情报文本输出分析（供吃瓜栏目等调用）。"""
        system = (
            "你是手机行业的情报分析师。请用简洁中文分析下面这条情报，"
            "重点说清：对我方在售机型报价的影响、建议的应对动作。"
            "不要编造价格数字，没有数据就明说。"
        )
        try:
            return self.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ]
            )
        except Exception as exc:  # 网络/配额问题不阻断主流程
            logger.warning("大模型解读失败：%s", exc)
            return ""


# 全局单例，方便各处直接调用
llm_client = LLMClient()
