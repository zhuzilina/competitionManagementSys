from .models import ChatMessage
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


def get_chat_context(user, max_messages=6):
    """
    获取最近的上下文。
    """
    messages = []
    # 这里的 filter 确保不取正在生成的或摘要的消息
    history = ChatMessage.objects.filter(user=user, is_summary=False).order_by('-created_at')[:max_messages]
    print(f"提取到的历史消息数量为：{len(history)}")

    # 因为是 -created_at 取出的，需要反转回正序发给 AI
    history = reversed(history)

    for msg in history:
        if msg.role == 'user':
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == 'assistant':  # 对应数据库中的 role
            messages.append(AIMessage(content=msg.content))
    print(f"最终组成的历史消息为：{messages}")
    return messages