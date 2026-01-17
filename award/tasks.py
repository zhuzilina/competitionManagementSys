from celery import shared_task
import pandas as pd
import numpy as np
from django.db import transaction

from competitions.models import Competition
from userProfile.models import Profile
from .models import (
    AwardImportTask, AwardImportItem
)
from .utils import clean_names, parse_excel_date, guess_competition_scale
# 引入 fuzzy match
from thefuzz import process


@shared_task(bind=True)
def process_award_import_task(self, task_id):
    """
    后台解析 Excel 并生成暂存记录 (AwardImportItem)
    优化项：
    1. 严格按规模（scale）预筛选池子
    2. 仅保留前 3 个模糊匹配结果
    3. 默认选中匹配度最高的一项
    """
    try:
        task_record = AwardImportTask.objects.get(id=task_id)
        # 更新状态为处理中
        task_record.status = 'pending'
        task_record.save()

        # 读取 Excel (建议生产环境使用 django default_storage.open)
        file_path = task_record.file_name
        df = pd.read_excel(file_path)
        df = df.replace({np.nan: None, "": None})
        data_list = df.to_dict(orient='records')

        total = len(data_list)
        items_to_create = []

        # --- 优化点：在内存中按规模对竞赛进行预分组 ---
        # 结构: {'国家级': {id: "标题", ...}, '省级': {...}}
        all_competitions = list(Competition.objects.values('id', 'title', 'scale'))
        comp_groups = {}
        for c in all_competitions:
            scale = c['scale']
            if scale not in comp_groups:
                comp_groups[scale] = {}
            comp_groups[scale][c['id']] = c['title']

        # 内部工具函数：人员分析逻辑
        def analyze_users(names_str):
            results = []
            names = clean_names(names_str)  # 假设已定义的清洗函数
            for name in names:
                analysis = {
                    "origin_name": name,
                    "status": "not_found",
                    "selected_id": None,
                    "options": []
                }

                # 查找 Profile，关联 User
                profiles = Profile.objects.filter(real_name=name).select_related('user')

                opts = []
                for p in profiles:
                    opts.append({
                        "user_id": p.user.user_id,
                        "real_name": p.real_name,
                        "college": p.college,
                        "major": p.major or p.department,
                        "clazz": p.clazz
                    })

                analysis['options'] = opts

                if len(opts) == 1:
                    analysis['status'] = 'success'
                    analysis['selected_id'] = opts[0]['user_id']
                elif len(opts) > 1:
                    analysis['status'] = 'multiple'
                else:
                    analysis['status'] = 'not_found'

                results.append(analysis)
            return results

        # --- 主循环处理每一行数据 ---
        for index, row in enumerate(data_list):
            raw_comp_name = str(row.get('奖项名称', '') or '')
            raw_level = str(row.get('奖级', '') or '')
            raw_date = row.get('获奖时间')
            raw_students = str(row.get('学生', '') or '')
            raw_instructors = str(row.get('指导老师', '') or '')

            # 初始化 Item 对象
            item = AwardImportItem(
                task=task_record,
                raw_competition=raw_comp_name,
                award_level=raw_level,
                award_date=parse_excel_date(raw_date),
                raw_participants=raw_students,
                raw_instructors=raw_instructors,
            )

            # --- 核心逻辑 A: 竞赛模糊匹配 (优化版) ---
            comp_analysis = {
                "status": "not_found",
                "selected_id": None,
                "options": []
            }

            # A.1 解析规模 (例如从 "国家级一等奖" 提取出 "国家级")
            guessed_scale = guess_competition_scale(raw_level)

            # A.2 仅获取相同规模的竞赛作为候选池
            # 如果猜不到规模，则无法精确匹配，保持 empty
            choices = comp_groups.get(guessed_scale, {})

            if raw_comp_name and choices:
                # A.3 使用 fuzzywuzzy 进行匹配，限制只取前 3 个
                matches = process.extract(raw_comp_name, choices, limit=3)

                options = []
                for title, score, comp_id in matches:
                    options.append({
                        "id": comp_id,
                        "title": title,
                        "scale": guessed_scale,
                        "score": score
                    })

                if options:
                    comp_analysis['options'] = options
                    # 默认选中第一个匹配结果（分值最高者）
                    comp_analysis['selected_id'] = options[0]['id']
                    # 只要池子里有结果，就标记为 success，让用户默认可以不用修改
                    comp_analysis['status'] = 'success'

            item.competition_analysis = comp_analysis

            # --- 核心逻辑 B: 人员匹配 ---
            item.participants_analysis = analyze_users(raw_students)
            item.instructors_analysis = analyze_users(raw_instructors)

            # --- 核心逻辑 C: 判定该行是否 Valid ---
            # 规则：竞赛有选中 + 所有学生已匹配 + 所有老师已匹配
            is_comp_ok = comp_analysis['status'] == 'success'
            is_part_ok = all(u['status'] == 'success' for u in item.participants_analysis)
            is_inst_ok = all(u['status'] == 'success' for u in item.instructors_analysis)

            if is_comp_ok and is_part_ok and is_inst_ok:
                item.is_valid = True
                item.error_msg = ""
            else:
                item.is_valid = False
                errs = []
                if not is_comp_ok: errs.append(f"未匹配到{guessed_scale or ''}竞赛")
                if not is_part_ok: errs.append("学生需核实")
                if not is_inst_ok: errs.append("老师需核实")
                item.error_msg = "; ".join(errs)

            items_to_create.append(item)

            # 更新任务进度
            if (index + 1) % 5 == 0 or (index + 1) == total:
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': index + 1,
                        'total': total,
                        'percent': round((index + 1) / total * 100, 2)
                    }
                )

        # 批量写入数据库
        with transaction.atomic():
            AwardImportItem.objects.bulk_create(items_to_create)

            # 任务处理完毕，状态改为 "待修正"
            task_record.status = 'correcting'
            task_record.save()

        return {"message": f"解析完成，共 {len(items_to_create)} 条，请核对。"}

    except Exception as e:
        # 异常捕获，确保任务状态能更新为失败
        task_record = AwardImportTask.objects.get(id=task_id)
        task_record.status = 'failed'
        task_record.save()
        raise e