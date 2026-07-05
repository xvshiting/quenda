"""
测试多模态（图片）支持。

使用 JD Cloud 的 Kimi-K2.5 模型测试视觉能力。
"""

import base64
import os
import sys
from quenda.kernel.types import Message, TextContent, ImageContent
from quenda.providers.builtins import JDCLOUD_SPEC
from quenda.providers.provider import Provider
from quenda.providers.auth import EnvAuthResolver
from quenda.providers.api.registry import get_api_registry


def test_multimodal(image_path: str | None = None):
    """测试多模态消息发送"""

    # 检查环境变量
    if not os.environ.get("JDCLOUD_API_KEY"):
        print("请设置环境变量 JDCLOUD_API_KEY")
        return

    # 创建 provider
    api_registry = get_api_registry()
    provider = Provider(JDCLOUD_SPEC, auth=EnvAuthResolver(), api_registry=api_registry)

    # 获取 Kimi-K2.5 模型
    model = provider.get_model("Kimi-K2.5")

    # 准备图片内容
    if image_path and os.path.exists(image_path):
        # 读取本地图片
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 推断媒体类型
        ext = os.path.splitext(image_path)[1].lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(ext, "image/png")

        image_content = ImageContent(media_type=media_type, data=image_data)
        print(f"图片: {image_path}")
    else:
        # 使用一个简单的测试图片
        RED_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        image_content = ImageContent(media_type="image/png", data=RED_PIXEL_PNG)
        print("图片: 1x1 红色像素 PNG (base64)")

    # 创建多模态消息
    messages = [
        Message(
            role="user",
            content=[
                TextContent(text="这张图片里有什么？请简要描述。"),
                image_content,
            ]
        )
    ]

    print("发送多模态消息...")
    print(f"模型: {model.id}")
    print()
    print()

    # 调用模型
    response = model.invoke(messages, tools=[])

    print("响应:")
    print(response.content)
    print()
    print(f"停止原因: {response.stop_reason}")
    if response.usage:
        print(f"Token 使用: 输入 {response.usage.input_tokens}, 输出 {response.usage.output_tokens}")


if __name__ == "__main__":
    # 可以通过命令行参数传入图片路径
    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    test_multimodal(image_path)
