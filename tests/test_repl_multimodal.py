"""测试 REPL 多模态消息发送。"""

import os

# 在 convert_messages_to_openai 中添加日志
import quenda.providers.api.converters as converters

original_convert = converters.convert_messages_to_openai

def logged_convert(messages):
    result = original_convert(messages)
    print("\n[DEBUG] OpenAI messages:")
    for msg in result:
        if isinstance(msg.get("content"), list):
            print(f"  role={msg['role']}, content_type=list, len={len(msg['content'])}")
            for item in msg["content"]:
                if item.get("type") == "image_url":
                    url = item.get("image_url", {}).get("url", "")
                    if url.startswith("data:"):
                        print(f"    - image_url: data:image/...;base64,{len(url)} chars")
                    else:
                        print(f"    - image_url: {url[:50]}...")
                else:
                    print(f"    - {item}")
        else:
            print(f"  role={msg['role']}, content=str")
    return result

converters.convert_messages_to_openai = logged_convert

# 启动 REPL
from quenda.cli import main
import sys
sys.exit(main())
