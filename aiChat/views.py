from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import StreamingHttpResponse

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from aiChat.models import ChatMessage
from aiChat.serializers import ChatMessageSerializer
from aiChat.utils import get_chat_context

from aiChat.tools import search_competitions,get_award_analysis_tool


class AIStreamChatView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user_input = request.data.get("message")
        llm = ChatOpenAI(model="qwen3.5-flash", streaming=True)

        # 实例化当前用户的专属工具
        my_award_tool = get_award_analysis_tool(request.user)

        # 将静态工具和动态工具组合
        current_tools = [search_competitions, my_award_tool]

        # 将工具绑定到大模型上，这样模型就知道自己拥有哪些技能了
        llm_with_tools = llm.bind_tools(current_tools)

        # 1. 获取历史上下文
        context_messages = get_chat_context(request.user)
        # 2. 保存用户的提问
        ChatMessage.objects.create(user=request.user, role='user', content=user_input)

        def stream_generator():
            # 3. 组装当前请求
            full_messages = [
                SystemMessage(content=f"你是竞赛助手。当前用户：{request.user.username}"),
                *context_messages,  # 展开历史消息
                HumanMessage(content=user_input)
            ]

            full_ai_response = ""  # 用于记录 AI 的完整回复
            # 监听模型的初步反应
            response_chunk_accumulator = None

            try:
                for chunk in llm_with_tools.stream(full_messages):
                    # 将所有流式块拼接到一起
                    if response_chunk_accumulator is None:
                        response_chunk_accumulator = chunk
                    else:
                        response_chunk_accumulator += chunk

                    # 如果此时模型直接输出了文本（没有调用工具），直接返给前端
                    if chunk.content and not chunk.tool_call_chunks:
                        full_ai_response += chunk.content
                        yield f"data: {chunk.content}\n\n"
                # 处理工具调用并进行二次生成
                if response_chunk_accumulator and response_chunk_accumulator.tool_calls:
                    # 把 AI 的"我想调用工具"这个消息加入对话历史
                    full_messages.append(response_chunk_accumulator)

                    # 映射工具名称到实际的 Python 函数
                    tool_map = {tool.name: tool for tool in current_tools}

                    for tool_call in response_chunk_accumulator.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]

                        # 执行 Python 函数，查询数据库
                        if tool_name in tool_map:
                            print(f"正在调用工具: {tool_name}, 参数: {tool_args}")
                            tool_output = tool_map[tool_name].invoke(tool_args)
                        else:
                            tool_output = f"未找到名为 {tool_name} 的工具。"

                        # 把数据库查到的结果包装成 ToolMessage，加进对话历史
                        full_messages.append(ToolMessage(
                            tool_call_id=tool_call["id"],
                            content=str(tool_output)
                        ))

                    # 带着工具返回的真实数据，再次向大模型请求生成最终的流式文本
                    for chunk in llm.stream(full_messages):
                        if chunk.content:
                            full_ai_response += chunk.content
                            yield f"data: {chunk.content}\n\n"
                # 保存最终数据
                print("开始保存助手消息")
                if full_ai_response:
                    ChatMessage.objects.create(
                        user=request.user,
                        role='assistant',
                        content=full_ai_response
                    )
                print(f"助手最终消息为:\n{full_ai_response}")
            except Exception as e:
                import traceback
                traceback.print_exc()  # 打印详细报错
                yield f"data: [Error] {str(e)}\n\n"

        return StreamingHttpResponse(stream_generator(), content_type='text/event-stream')

# 分页
class ChatHistoryPagination(PageNumberPagination):
    page_size = 20          # 每页显示多少条
    page_size_query_param = 'page_size' # 允许前端通过 ?page_size=50 自定义每页数量
    max_page_size = 100     # 最大允许每页多少条


class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    # 将分页类直接绑定到视图属性上（符合 DRF 标准写法）
    pagination_class = ChatHistoryPagination

    def get(self, request):
        # 1. 过滤并倒序排序
        messages = ChatMessage.objects.filter(
            user=request.user,
            is_summary=False
        ).order_by('-created_at')

        # 2. 实例化分页器
        paginator = self.pagination_class()

        # 3. 执行分页逻辑
        # 即使 messages 为空，这里也会返回一个空列表，而不是 None
        page_obj = paginator.paginate_queryset(messages, request, view=self)

        # 4. 统一序列化并返回分页响应
        serializer = ChatMessageSerializer(page_obj, many=True)
        return paginator.get_paginated_response(serializer.data)