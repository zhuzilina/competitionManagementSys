import os
import re
from datetime import datetime

import django_filters
from celery.result import AsyncResult
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework import viewsets, filters
from django.db.models import Prefetch
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from competitionManagementSys import settings
from competitions.models import Competition
from .models import Award, AwardImportTask, AwardImportItem
from .serializers import AwardSerializer, AwardImportItemSerializer
from .serializers import AwardReportSerializer
from userManage.permissions import IsCompAdminOrReadOnly,IsCompAdmin
from django.db.models import Count,Q,F
from django.db.models.functions import ExtractYear
from .tasks import process_award_import_task

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
    queryset = AwardImportTask.objects.all()
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """
        第一步：上传 Excel，创建任务，触发异步解析
        """
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "请上传文件"}, status=400)

        # 1. 保存文件
        # 建议重命名文件防止冲突，例如加时间戳
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        save_path = f'imports/awards/{timestamp}_{file.name}'
        path = default_storage.save(save_path, file)
        full_path = os.path.join(settings.MEDIA_ROOT, path)  # 获取绝对路径供 pandas 读取

        # 2. 创建任务记录
        task_record = AwardImportTask.objects.create(
            creator=request.user,
            file_name=full_path,  # 存绝对路径方便读取，或存相对路径并在 Task 中处理
            status='pending'
        )

        # 3. 触发异步任务
        async_task = process_award_import_task.delay(task_record.id)
        # 保存id到数据库
        task_record.celery_task_id = async_task.id
        task_record.save()

        return Response({
            "id": task_record.id,
            "status": "pending",
            "message": "文件已上传，正在后台解析数据..."
        })

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        task = self.get_object()

        # 获取任务在数据库中的基础状态
        response_data = {
            "status": task.status,
            "progress": 0
        }

        # 如果任务有关联的 Celery ID，去查询实时进度
        if task.celery_task_id:
            res = AsyncResult(task.celery_task_id)

            if res.state == 'PROGRESS':
                # 正在处理中，获取 meta 里的进度
                response_data["progress"] = res.info.get('progress', 0)
            elif res.state == 'SUCCESS':
                # 任务成功
                response_data["progress"] = 100
            elif res.state == 'FAILURE':
                # 任务失败
                response_data["status"] = 'failed'
                response_data["error"] = str(res.info)

        return Response(response_data)

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """
        获取该任务下的所有解析项，支持过滤是否有效
        GET /award/import/1/items/?is_valid=false
        """
        task = self.get_object()
        items = task.items.all()

        # 可选：增加简单的过滤，方便前端只看错误项
        is_valid_filter = request.query_params.get('is_valid')
        if is_valid_filter is not None:
            is_valid_bool = is_valid_filter.lower() == 'true'
            items = items.filter(is_valid=is_valid_bool)

        serializer = AwardImportItemSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='update-item')
    def update_item(self, request, pk=None):
        """
        修正单条解析项数据
        URL: POST /award/import/{task_id}/update-item/
        Payload: { "item_id": 15, "competition_analysis": {...}, "participants_analysis": [...] }
        """
        task = self.get_object()
        item_id = request.data.get('id')
        item = get_object_or_404(AwardImportItem, id=item_id, task=task)

        # 1. 获取前端传回的修正后的解析内容
        # 前端通常会修改原始 JSON 中的 selected_id 后把整个对象/列表发回来
        comp_data = request.data.get('competition_analysis')
        part_data = request.data.get('participants_analysis')
        inst_data = request.data.get('instructors_analysis')

        # 2. 更新字段
        if comp_data is not None:
            item.competition_analysis = comp_data
        if part_data is not None:
            item.participants_analysis = part_data
        if inst_data is not None:
            item.instructors_analysis = inst_data

        # 3. 重新校验逻辑 (关键步骤)
        is_valid, error_msg = self._revalidate_item(item)
        item.is_valid = is_valid
        item.error_msg = error_msg

        item.save()

        return Response({
            "id": item.id,
            "is_valid": item.is_valid,
            "error_msg": item.error_msg,
            "message": "保存成功"
        })

    def _revalidate_item(self, item):
        """
        内部逻辑：检查 item 里的所有 selected_id 是否都已经填充
        """
        errors = []

        # 校验竞赛
        if not item.competition_analysis.get('selected_id'):
            errors.append("竞赛需确认")

        # 校验学生 (participants_analysis 是列表)
        missing_parts = [
            p.get('origin_name') for p in item.participants_analysis
            if not p.get('selected_id')
        ]
        if missing_parts:
            errors.append(f"学生需确认: {', '.join(missing_parts)}")

        # 校验老师
        missing_insts = [
            i.get('origin_name') for i in item.instructors_analysis
            if not i.get('selected_id')
        ]
        if missing_insts:
            errors.append(f"教师需确认: {', '.join(missing_insts)}")

        if errors:
            return False, "; ".join(errors)
        return True, ""

    @action(detail=True, methods=['post'])
    def commit(self, request, pk=None):
        """确认暂存数据并入库"""
        task = self.get_object()
        valid_items = task.items.filter(is_valid=True)

        # 只有在解析完成/待修正状态下才能提交
        if task.status not in ['correcting', 'finished']:
            return Response({"error": "解析尚未完成或任务已关闭"}, status=400)

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