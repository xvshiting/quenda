"""
调试多模态消息格式。
"""

import base64
import os
from quenda.kernel.types import Message, TextContent, ImageContent
from quenda.providers.api.converters import convert_messages_to_openai

# 读取测试图片
with open(os.path.expanduser("~/Downloads/test.jpg"), "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")

# 创建多模态消息
messages = [
    Message(
        role="user",
        content=[
            TextContent(text="这张图片是什么？"),
            ImageContent(media_type="image/jpeg", data=image_data[:100] + "..."),  # 截断显示
        ]
    )
]

# 转换为 OpenAI 格式
openai_messages = convert_messages_to_openai(messages)

print("OpenAI 消息格式:")
import json
print(json.dumps(openai_messages, indent=2, ensure_ascii=False))
