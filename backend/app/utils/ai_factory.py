from typing import Any

from agno.agent import Agent
from agno.models.openai.like import OpenAILike
from agno.team import Team

from app.config.setting import settings


class AgnoFactory:
    """Agno 工厂类 - 统一管理 Agent、Team 创建逻辑"""

    # 配置常量
    AGENT_DESCRIPTION = "你是一个有用的AI助手，可以帮助用户回答问题和提供帮助。"
    AGENT_INSTRUCTIONS = ["保持回答简洁明了", "如果不确定，请说明"]
    AGENT_EXPECTED_OUTPUT = "中文回答"
    AGENT_TEMPERATURE = 0.7
    NUM_HISTORY_RUNS = 3
    REQUEST_TIMEOUT = 60.0  # LLM 请求总超时（秒），流式响应需放长
    CONNECT_TIMEOUT = 10.0  # TCP 连接超时（秒）

    def create_agent(
        self,
        user_id: str,
        team_id: str,
        session_id: str,
        db: Any | None = None,
        model_config: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
    ) -> Team:
        """创建带 Agent 的 Team 实例。

        参数:
        - user_id (str): 用户标识。
        - team_id (str): 团队标识。
        - session_id (str): 会话 ID。
        - db (Any | None): Agno 持久化数据库实例，可选。
        - model_config (dict | None): 运行时模型配置，覆盖系统默认。
            支持字段：base_url, api_key, model_id, temperature。
        - tools (list[Any] | None): 需要注入给 Agent 的工具（**只读工具**，由调用方按开关决定）。

        返回:
        - Team: 配置好的 Team。
        """
        # 优先使用运行时配置，否则 fallback 到系统 settings
        base_url = settings.OPENAI_BASE_URL
        api_key = settings.OPENAI_API_KEY
        model_id = settings.OPENAI_MODEL
        temperature = self.AGENT_TEMPERATURE

        if model_config:
            base_url = model_config.get("base_url") or base_url
            api_key = model_config.get("api_key") or api_key
            model_id = model_config.get("model_id") or model_id
            if isinstance(model_config.get("temperature"), (int, float)):
                temperature = float(model_config["temperature"])

        # 创建 Agent
        argus_agent = Agent(
            id=user_id,
            name="argus_agent",
            role="You are a helpful AI assistant",
            description=self.AGENT_DESCRIPTION,
            tools=list(tools or []),
        )

        # 创建 Team
        argus_team = Team(
            id=team_id,
            user_id=user_id,
            session_id=session_id,
            model=OpenAILike(
                id=model_id,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                timeout=self.REQUEST_TIMEOUT,
            ),
            members=[argus_agent],
            instructions=self.AGENT_INSTRUCTIONS,
            expected_output=self.AGENT_EXPECTED_OUTPUT,
            add_datetime_to_context=True,
            add_history_to_context=True,
            markdown=True,
            num_history_runs=self.NUM_HISTORY_RUNS,
            input_schema=None,
            output_schema=None,
            parse_response=True,
            read_chat_history=True,
            db=db,
        )

        return argus_team


    async def complete_json(self, system: str, message: str, model_config: dict[str, Any] | None = None) -> str:
        """无工具、无聊天历史的结构化业务提取，复用当前模型配置。"""
        import httpx
        from openai import AsyncOpenAI

        config = model_config or {}
        key = config.get("api_key") or settings.OPENAI_API_KEY
        if not key:
            raise RuntimeError("AI_MODEL_NOT_CONFIGURED")
        from urllib.parse import urlsplit

        base_url = config.get("base_url") or settings.OPENAI_BASE_URL
        options: dict[str, Any] = {}
        if urlsplit(base_url).hostname == "api.deepseek.com":
            # DeepSeek V4 默认高强度思考；业务字段提取使用非思考 JSON 模式。
            options = {"extra_body": {"thinking": {"type": "disabled"}}, "response_format": {"type": "json_object"}}
        async with AsyncOpenAI(api_key=key, base_url=base_url, timeout=httpx.Timeout(90, connect=self.CONNECT_TIMEOUT), max_retries=0) as client:
            response = await client.chat.completions.create(
                model=config.get("model_id") or settings.OPENAI_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
                temperature=0,
                max_tokens=10000,
                **options,
            )
            if not response.choices or response.choices[0].finish_reason == "length":
                raise ValueError("AI_OUTPUT_INCOMPLETE")
            content = response.choices[0].message.content
            if not content:
                raise ValueError("AI_OUTPUT_EMPTY")
            return content
