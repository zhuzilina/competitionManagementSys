# ai skills
from django.db.models import Q
from langchain_core.tools import tool

from award.models import Award
from competitions.models import Competition


@tool
def search_competitions(keyword: str = None, category_name: str = None, scale: str = None) -> str:
    """
    当用户询问竞赛信息（如查询某个竞赛、或者按类别/规模寻找竞赛）时，必须调用此工具。

    参数:
    - keyword: 竞赛的名称关键字（如"数学建模", "编程"）
    - category_name: 竞赛类别（如"创新", "算法"）
    - scale: 竞赛规模（如"院级", "校级", "市级", "省级", "国家级", "国际级"）
    注意：
    - 如果用户提到竞赛类型（如算法类、创新类），请填入 category_name。
    - 如果提到具体的竞赛名称，请填入 keyword。
    - 不要随意推测 scale（规模），除非用户明确说明。
    """

    # 1. 基础查询集
    qs = Competition.objects.all().select_related('category', 'level')

    # 2. 灵活构造过滤条件
    filters = Q()

    # 如果 AI 同时传了 keyword 和 category_name，且内容相似（比如都是"算法"）
    # 我们应该用 OR 逻辑，而不是 AND
    if keyword and category_name and (keyword in category_name or category_name in keyword):
        filters &= (Q(title__icontains=keyword) | Q(category__name__icontains=category_name))
    else:
        # 否则按常规处理
        if keyword:
            filters &= Q(title__icontains=keyword)
        if category_name:
            filters &= Q(category__name__icontains=category_name)

    # 规模通常比较明确，保留 AND 逻辑，但可以做个判空保护
    if scale:
        qs = qs.filter(scale=scale)

    # 执行第一次查询
    results = qs.filter(filters)[:5]

    # 3. 【降级策略】如果查不到，尝试放宽限制（去掉规模或关键词限制）
    if not results.exists() and (scale or keyword):
        # 比如去掉规模限制再查一次
        results = Competition.objects.filter(
            Q(title__icontains=keyword) | Q(category__name__icontains=category_name) if category_name else Q()
        )[:5]

    if not results.exists():
        return "数据库中未查找到符合条件的竞赛信息。建议换个关键词试试。"

    # 组装返回给 AI 的纯文本数据
    result_lines = []
    for comp in results:
        uri_text = f"官网: {comp.uri}" if comp.uri else "暂无官网"
        result_lines.append(
            f"- 【{comp.title}】 ({comp.year}年): 属于{comp.category.name}，级别为{comp.level.name}，"
            f"规模为{comp.scale}。简介: {comp.description} {uri_text}"
        )
    print("查询结果")
    print(*result_lines, sep="\n")
    return "\n".join(result_lines)


def get_award_analysis_tool(user):
    """
    动态生成工具的工厂函数。
    利用闭包特性，将当前的 request.user 锁定在工具内部，防止越权查询。
    """

    @tool
    def analyze_my_awards(year: int = None) -> str:
        """
        当用户要求：“查询我的获奖记录”、“分析我的竞赛情况”、“我适合参加什么竞赛”、“帮我做个竞赛总结”时，必须调用此工具。
        参数:
        - year: (可选) 如果用户指定了特定年份（如 2023），传入此参数。否则留空查询全部。
        """
        # 1. 核心过滤逻辑：RBAC 过滤逻辑
        queryset = Award.objects.filter(
            Q(participants=user) | Q(instructors=user)
        ).select_related(
            'competition',
            'competition__category',
            'competition__level'
        ).prefetch_related(
            'participants',
            'instructors'
        ).distinct().order_by('-award_date')

        if year:
            queryset = queryset.filter(award_date__year=year)

        if not queryset.exists():
            return "数据库中未查找到当前用户的任何获奖记录。请鼓励用户积极参赛。"

        # 2. 组装发给 AI 的数据
        result_lines = [f"【系统信息】已成功查询到用户 {user.username} 的获奖数据如下："]

        for award in queryset:
            comp = award.competition
            cat_name = comp.category.name if comp.category else "未知类别"
            level_name = comp.level.name if comp.level else "未知级别"

            # 判断用户的身份角色 (由于我们加了 prefetch_related，这里的 .all() 不会触发额外查库)
            role = "参赛学生" if user in award.participants.all() else "指导老师"

            result_lines.append(
                f"- {award.award_date.strftime('%Y-%m-%d')} | "
                f"【{comp.title}】(类别: {cat_name}, 级别: {level_name}, 规模: {comp.scale}) | "
                f"荣获：{award.award_level} (担任角色: {role})"
            )

        # 3. 关键魔法：在返回的数据末尾，直接给大模型下达“分析指令” (Prompt Engineering)
        result_lines.append(
            "\n【系统指令】请根据以上真实数据，以专业的竞赛助手身份为用户进行多维度分析：\n"
            "1. 优势总结：指出用户擅长的竞赛类别和已达到的最高规模。\n"
            "2. 短板与空间：指出用户在哪些类别或级别上还有空缺。\n"
            "3. 进阶建议：推荐用户下一步可以尝试什么类型/规模的竞赛，给出具体理由。"
        )

        return "\n".join(result_lines)

    return analyze_my_awards