import json
import logging

import httpx

from desktop.config_manager import ConfigManager

LOGGER = logging.getLogger(__name__)


class LLMAdapter:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cfg = config.get_llm_config()

    def enhance(self, report_json: dict) -> str | None:
        if not self.cfg.get("enabled"):
            return None
        # The API key is never persisted to the database; it is read from
        # LLM_API_KEY in .env/.env.local at runtime. If it is missing, skip
        # the LLM call entirely rather than erroring.
        api_key = self.cfg.get("api_key", "")
        if not api_key:
            return None

        url = f"{self.cfg.get('base_url', 'https://api.deepseek.com/v1')}/chat/completions"
        prompt = self._build_prompt(report_json)

        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.cfg.get("model", "deepseek-chat"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是 A 股分析助手。请严格基于下面提供的事实数据生成解读，禁止编造价格、资金流或任何未提供的数据。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            LOGGER.error(f"LLM enhancement failed: {e}")
            return None

    def _build_prompt(self, report_json: dict) -> str:
        return f"""请基于以下已验证的分析报告生成一段简洁的增强解读（200字以内），说明核心逻辑和风险点：

```json
{json.dumps(report_json, ensure_ascii=False, indent=2)}
```
"""
