import re

import django_filters
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework import viewsets, filters
from datetime import datetime
from django.db.models import Prefetch
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from competitions.models import Competition
from .models import Award
from .serializers import AwardSerializer
from .serializers import AwardReportSerializer
from userManage.permissions import IsCompAdminOrReadOnly,IsCompAdmin
from django.db.models import Count,Q,F
from django.db.models.functions import ExtractYear

User = get_user_model()


class AwardFilter(django_filters.FilterSet):
    # 1. 竞赛名称：模糊搜索
    competition_name = django_filters.CharFilter(
        field_name='competition__title',
        lookup_expr='icontains'
    )

    # 2. 类别与级别：精确匹配 (接受 ID)
    category = django_filters.NumberFilter(field_name='competition__category_id')
    level = django_filters.NumberFilter(field_name='competition__level_id')

    # 3. 获奖等级：模糊搜索
    award_level = django_filters.CharFilter(lookup_expr='icontains')

    # 4. 日期范围：使用 start_date 和 end_date 过滤
    date_min = django_filters.DateFilter(field_name='award_date', lookup_expr='gte')
    date_max = django_filters.DateFilter(field_name='award_date', lookup_expr='lte')

    # 5. 指导老师：搜索老师的姓名 (假设 Profile 中有 name 字段)
    instructor_name = django_filters.CharFilter(
        field_name='instructors__profile__real_name',
        lookup_expr='icontains'
    )

    # 6. 学院与专业：通过参与者(participants)关联的 Profile 过滤
    # 假设你的 Profile 模型中有 college 和 major 字段
    college = django_filters.CharFilter(
        field_name='participants__profile__college',
        lookup_expr='icontains'
    )
    major = django_filters.CharFilter(
        field_name='participants__profile__major',
        lookup_expr='icontains'
    )

    class Meta:
        model = Award
        fields = [
            'competition_name', 'category', 'level',
            'award_level', 'date_min', 'date_max',
            'instructor_name', 'college', 'major'
        ]

class AwardViewSet(viewsets.ModelViewSet):
    # 1. select_related 针对 ForeignKey 和 OneToOne
    # 2. prefetch_related 针对 ManyToMany，并使用 Prefetch 对象深入关联 profile
    queryset = Award.objects.all()
    serializer_class = AwardSerializer
    permission_classes = [IsCompAdminOrReadOnly]

    # 多维度搜索功能
    # 索引优化：
    # 由于你频繁对 award_date 进行范围查询，以及对 competition__title 进行搜索，
    # 建议在数据库模型层为 award_date 增加索引，并确保 competition.title 也有索引。
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AwardFilter

    # 设置默认排序字段
    ordering_fields = ['award_date', 'created_at']
    ordering = ['-award_date']

    def get_queryset(self):
        # 深度优化：一次性取出所有必要数据
        queryset = self.queryset.select_related(
            'competition',
            'competition__level',  # 深度预加载
            'competition__category',
            'certificate',
            'creator__profile'
        ).prefetch_related(
            'participants__profile',  # 预加载参与者的档案
            'participants__groups',  # 预加载组信息以便 ProfileSerializer 里的 get_role_name 使用
            'instructors__profile',  # 预加载老师的档案
            'instructors__groups'
        )

        user_query_id = self.request.query_params.get('user_id')

        if user_query_id == 'me':
            if self.request.user.is_authenticated:
                user_query_id = self.request.user.user_id
            else:
                return Award.objects.none()

        if user_query_id:
            queryset = queryset.filter(
                Q(participants__user_id=user_query_id) |
                Q(instructors__user_id=user_query_id)
            ).distinct()

        return queryset

    def perform_create(self, serializer):
        # 自动关联当前登录用户为录入人
        serializer.save(creator=self.request.user)

    def perform_destroy(self, instance):
        cert = instance.certificate
        instance.delete()  # 删除获奖记录
        if cert:
            cert.delete()

    @action(detail=False, methods=['post'], url_path='batch-import')
    def batch_import(self, request):
        file_data = request.data.get('data')  # 假设前端传回的是解析好的 JSON 列表
        if not file_data:
            return Response({"error": "无有效数据"}, status=400)

        results = {
            "success_count": 0,
            "error_count": 0,
            "errors": []  # 记录具体哪一行、因为什么报错
        }

        # 分隔符正则：中英文逗号、分号、顿号、空格
        delimiters = r'[，,；;、\s]+'

        with transaction.atomic():
            for index, item in enumerate(file_data):
                line_num = index + 1
                try:
                    # 1. 匹配竞赛
                    comp_name = item.get('competition_name', '').strip()
                    comp = Competition.objects.filter(title=comp_name).first()
                    if not comp:
                        raise ValueError(f"竞赛 '{comp_name}' 不存在")

                    # 2. 解析人员数据 (学生和老师)
                    student_ids = self._parse_users(item.get('participants', ''), delimiters)
                    teacher_ids = self._parse_users(item.get('instructors', ''), delimiters)

                    # 3. 创建获奖记录
                    award = Award.objects.create(
                        competition=comp,
                        award_level=item.get('award_level'),
                        award_date=item.get('award_date'),
                        creator=request.user
                    )
                    award.participants.set(student_ids)
                    award.instructors.set(teacher_ids)

                    results["success_count"] += 1

                except Exception as e:
                    results["error_count"] += 1
                    results["errors"].append({
                        "line": line_num,
                        "reason": str(e)
                    })
                    # 如果要求“原子性”，这里可以直接 raise 撤销全部；
                    # 如果要求“能导多少是多少”，则 continue

        return Response(results)

    def _parse_users(self, raw_str, delimiters):
        """
        解析人员字符串，支持：
        新版：张三23101100527
        旧版：张三
        """
        if not raw_str:
            return []

        # 按分隔符切分
        names = re.split(delimiters, str(raw_str))
        user_ids = []

        for part in names:
            part = part.strip()
            if not part: continue

            # 使用正则提取：末尾的连续数字作为 ID，前面的作为名字
            # 兼容：张三23101100527 或直接 张三
            match = re.match(r'^([^\d]+)(\d+)$', part)

            if match:
                # --- 新版逻辑：带学工号 ---
                name, uid = match.groups()
                user = User.objects.filter(user_id=uid).first()
                if not user:
                    raise ValueError(f"用户 ID '{uid}'({name}) 未在系统中找到")
                user_ids.append(user.id)
            else:
                # --- 旧版逻辑：纯名字 ---
                # 关联到 UserProfile 的 real_name
                users = User.objects.filter(profile__real_name=part)
                count = users.count()
                if count == 0:
                    raise ValueError(f"找不到名为 '{part}' 的用户")
                elif count > 1:
                    # 获取他们的部门信息以便提示
                    depts = [u.profile.department for u in users if hasattr(u, 'profile')]
                    raise ValueError(f"发现重名用户 '{part}' ({' / '.join(depts)})，请使用 '姓名+学号' 导入")
                user_ids.append(users.first().id)

        return user_ids


class AwardReportView(APIView):
    """
    获奖统计报表
    网页查看
    GET /award/report/?group_by=student&start_date=2025-01-01
    下载报表
    GET /award/report/?group_by=student&start_date=2025-01-01&format=excel
    """
    permission_classes = [IsCompAdmin]

    def get(self, request):
        group_by = request.query_params.get('group_by', 'student')
        # 获取日期范围参数
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # 1. 构建奖项的过滤基础查询集
        award_queryset = Award.objects.select_related('competition')

        if start_date:
            award_queryset = award_queryset.filter(award_date__gte=start_date)
        if end_date:
            award_queryset = award_queryset.filter(award_date__lte=end_date)

        report_data = []

        if group_by == 'student':
            # 使用 Prefetch 对象，将过滤后的奖项存入 'filtered_awards' 属性中
            users = User.objects.filter(
                student_awards__in=award_queryset
            ).distinct().prefetch_related(
                'profile',
                Prefetch('student_awards', queryset=award_queryset, to_attr='filtered_awards')
            )

            for user in users:
                # 注意这里使用 to_attr 指定的 'filtered_awards'
                report_data.append(self._format_user_data(user, user.filtered_awards))

        elif group_by == 'teacher':
            users = User.objects.filter(
                teacher_awards__in=award_queryset
            ).distinct().prefetch_related(
                'profile',
                Prefetch('teacher_awards', queryset=award_queryset, to_attr='filtered_awards')
            )

            for user in users:
                report_data.append(self._format_user_data(user, user.filtered_awards))

        serializer = AwardReportSerializer(report_data, many=True)
        return Response(serializer.data)

    def _generate_excel(self, data, group_by):
        """生成并返回 Excel 文件流"""
        wb = Workbook()
        ws = wb.active
        ws.title = "获奖报表"

        # 表头
        headers = ['学号/工号', '姓名', '院系', '专业/班级/职称', '获奖明细']
        ws.append(headers)

        # 设置表头样式
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        # 填充数据
        for item in data:
            # 将多条获奖信息合并为一个字符串
            awards_text = "\n".join([
                f"[{a.award_date}] {a.competition.title} - {a.award_level}"
                for a in item['awards']
            ])

            row = [
                item['user_id'],
                item['real_name'],
                item['department'],
                f"{item['major']}/{item['clazz']}/{item['title']}",
                awards_text
            ]
            ws.append(row)

            # 设置单元格换行（用于显示多条获奖）
            ws.cell(row=ws.max_row, column=5).alignment = Alignment(wrapText=True)

        # 设置列宽
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['E'].width = 60

        # 构建响应
        filename = f"award_report_{group_by}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    def _format_user_data(self, user, awards):
        # 保持不变，但传入的是过滤后的 awards 列表
        profile = getattr(user, 'profile', None)
        return {
            "user_id": user.user_id,
            "real_name": profile.real_name if profile else "未填写",
            "department": profile.department if profile else "-",
            "major": getattr(profile, 'major', '-'),
            "clazz": getattr(profile, 'clazz', '-'),
            "title": getattr(profile, 'title', '-'),
            "awards": awards
        }


class AwardStatisticsView(APIView):
    """
    获奖信息多维度统计API
    """
    permission_classes = [IsCompAdmin]

    def get(self, request):
        # 1. 基础总数统计
        total_awards = Award.objects.count()

        # 2. 按竞赛类别统计 (基于 CompetitionCategory)
        category_stats = Award.objects.values(
            name=F('competition__category__name')
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # 3. 按竞赛级别统计 (基于 CompetitionLevel)
        level_stats = Award.objects.values(
            name=F('competition__level__name')
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # 4. 按年度统计及环比计算
        # 提取日期中的年份进行分组
        yearly_stats_query = Award.objects.annotate(
            year=ExtractYear('award_date')
        ).values('year').annotate(
            count=Count('id')
        ).order_by('year')

        yearly_data = list(yearly_stats_query)
        # 计算变动率 (Growth Rate)
        for i in range(len(yearly_data)):
            if i > 0 and yearly_data[i - 1]['count'] > 0:
                prev = yearly_data[i - 1]['count']
                curr = yearly_data[i]['count']
                growth_rate = ((curr - prev) / prev) * 100
                yearly_data[i]['growth_rate'] = f"{round(growth_rate, 2)}%"
            else:
                yearly_data[i]['growth_rate'] = "0%"

        # 5. 按学院部门统计
        # 注意：这里需要跨两层：Award -> participants (User) -> profile (Profile)
        dept_stats = Award.objects.values(
            name=F('participants__profile__department')
        ).annotate(
            count=Count('id', distinct=True)  # 使用distinct防止一个奖项多个学生导致重复计算
        ).exclude(name__isnull=True).order_by('-count')

        # 6. 人员总数统计 (去重)
        total_students = Award.objects.aggregate(
            count=Count('participants', distinct=True)
        )['count']

        total_instructors = Award.objects.aggregate(
            count=Count('instructors', distinct=True)
        )['count']

        # 7. 获奖等级分布 (金奖、一等奖等)
        level_distribution = Award.objects.values('award_level').annotate(
            count=Count('id')
        ).order_by('-count')

        # 封装结果
        data = {
            "summary": {
                "total_awards": total_awards,
                "total_students": total_students,
                "total_instructors": total_instructors,
            },
            "by_category": category_stats,
            "by_level": level_stats,
            "by_department": dept_stats,
            "by_year": yearly_data,
            "by_award_rank": level_distribution
        }

        return Response(data)


class AwardImportViewSet(viewsets.ModelViewSet):

    @action(detail=True, methods=['post'])
    def commit(self, request, pk=None):
        """确认暂存数据并入库"""
        task = self.get_object()
        valid_items = task.items.filter(is_valid=True)

        if not valid_items.exists():
            return Response({"error": "没有可录入的有效记录"}, status=400)

        success_count = 0
        with transaction.atomic():
            for item in valid_items:
                # 1. 提取竞赛 ID
                comp_id = item.competition_analysis['selected_id']

                # 2. 提取人员。selected_id 存储的是 user_id (学号字符串)
                # 我们需要找到这些 user_id 对应的 User 实例
                p_uids = [u['selected_id'] for u in item.participants_analysis]
                i_uids = [u['selected_id'] for u in item.instructors_analysis]

                # 直接通过 user_id 批量查询 User
                participants = User.objects.filter(user_id__in=p_uids)
                instructors = User.objects.filter(user_id__in=i_uids)

                # 3. 创建正式获奖记录
                award = Award.objects.create(
                    competition_id=comp_id,
                    award_level=item.award_level,
                    award_date=item.award_date,
                    cert_no=item.cert_no,
                    creator=request.user
                )
                award.participants.set(participants)
                award.instructors.set(instructors)

                item.delete()  # 从暂存区移除
                success_count += 1

            # 更新任务状态
            if task.items.count() == 0:
                task.status = 'finished'
                task.save()

        return Response({"message": f"成功同步 {success_count} 条数据"})