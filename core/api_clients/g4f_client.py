# core/api_clients/g4f_client.py
import logging

log = logging.getLogger(__name__)


class G4FClient:
    """封装与 g4f (GPT4Free) 的交互，无需 API Key。"""

    def __init__(self, provider_name=None):
        """
        Args:
            provider_name (str, optional): g4f Provider 名称（如 "Copilot"、"DeepSeek"）。
                                           None 或空字符串表示自动选择。
        """
        try:
            from g4f.client import Client
            import g4f as _g4f

            self._g4f = _g4f
            if provider_name:
                provider = getattr(_g4f.Provider, provider_name, None)
                if provider is None:
                    log.warning(f"未找到 g4f Provider '{provider_name}'，将使用自动选择。")
                    self.client = Client()
                    self.provider_name = "auto"
                else:
                    self.client = Client(provider=provider)
                    self.provider_name = provider_name
            else:
                self.client = Client()
                self.provider_name = "auto"

            log.info(f"g4f 客户端初始化成功（Provider: {self.provider_name}）。")
        except ImportError:
            raise ImportError("未安装 g4f 模块，请执行: pip install g4f")
        except Exception as e:
            log.exception(f"初始化 g4f 客户端失败: {e}")
            raise ConnectionError(f"初始化 g4f 客户端失败: {e}") from e

    def chat_completion(self, model_name, messages, temperature=0.7, max_tokens=None, **kwargs):
        """
        调用 g4f Chat Completion，接口与 DeepSeekClient 相同。

        Returns:
            tuple: (success, result_content, error_message)
        """
        if not model_name:
            return False, None, "模型名称不能为空。"
        if not messages:
            return False, None, "消息列表不能为空。"

        try:
            log.debug(f"向 g4f 模型 '{model_name}' 发送请求（Provider: {self.provider_name}）...")
            response = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            if (response and response.choices
                    and response.choices[0].message
                    and response.choices[0].message.content):
                content = response.choices[0].message.content
                log.debug("g4f Chat Completion 成功返回响应内容。")
                return True, content, None
            return False, None, "g4f 未返回有效内容。"
        except Exception as e:
            error_msg = f"g4f 调用失败: {e}"
            log.exception(error_msg)
            return False, None, error_msg

    def test_connection(self, model_name):
        """
        测试 g4f 连接。

        Returns:
            tuple: (success, message)
        """
        log.info(f"测试 g4f 连接（模型: {model_name}，Provider: {self.provider_name}）...")
        test_messages = [{"role": "user", "content": "reply with 'ok'"}]
        success, content, error = self.chat_completion(model_name, test_messages)
        if success and content:
            msg = f"g4f 连接测试成功！响应: {content[:80]}"
            log.info(msg)
            return True, msg
        msg = f"g4f 连接测试失败: {error}"
        log.error(msg)
        return False, msg
