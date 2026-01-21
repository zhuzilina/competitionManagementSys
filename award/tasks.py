import re
import pandas as pd
import numpy as np
from celery import shared_task
from django.db import transaction
from fuzzywuzzy import fuzz

from competitions.models import Competition
from userProfile.models import Profile
from .models import AwardImportTask, AwardImportItem
from .utils import clean_names, parse_excel_date, guess_competition_scale

# --- 1. 配置项 ---
NOISE_WORDS = ["四川省", "四川轻化工大学", "大学生", "竞赛", "比赛", "大赛", "项目", "活动"]
MIN_SCORE_THRESHOLD = 65  # 硬阈值：低于此分数的匹配结果将被舍弃


def clean_comp_name(name):
    """清洗竞赛名称：去除年份、届数、括号及高频噪声词"""
    if not name: return ""
    name = str(name)
    # 移除年份 (2023年), 届数 (第十届), 括号内容 (A类)
    name = re.sub(r'\d{4}年|第.*?届|[\(（].*?[\)）]', '', name)
    for word in NOISE_WORDS:
        name = name.replace(word, "")
    return name.strip()


def calculate_match_score(query_clean, target_clean, query_raw, target_raw):
    """评分逻辑：优先使用清洗后的核心词进行 token_set_ratio 匹配"""
    if len(query_clean) < 2:
        return fuzz.token_set_ratio(query_raw, target_raw)
    return fuzz.token_set_ratio(query_clean, target_clean)


@shared_task(bind=True)
def process_award_import_task(self, task_id):
    try:
        task_record = AwardImportTask.objects.get(id=task_id)
        task_record.status = 'pending'
        task_record.save()

        # 读取 Excel
        df = pd.read_excel(task_record.file_name)
        df = df.replace({np.nan: None, "": None})
        data_list = df.to_dict(orient='records')
        total = len(data_list)

        # --- 性能优化：预处理竞赛数据池 ---
        all_competitions = Competition.objects.values('id', 'title', 'scale')

        # 按规模分组并预清洗标题
        comp_groups = {}
        for c in all_competitions:
            scale = c['scale']
            if scale not in comp_groups:
                comp_groups[scale] = []
            comp_groups[scale].append({
                'id': c['id'],
                'title': c['title'],
                'clean_title': clean_comp_name(c['title']),
                'scale': c['scale']
            })

        # 内部工具函数：解析人员
        def analyze_users(names_str):
            results = []
            names = clean_names(names_str)
            for name in names:
                analysis = {"origin_name": name, "status": "not_found", "selected_id": None, "options": []}
                profiles = Profile.objects.filter(real_name=name).select_related('user')
                opts = [{
                    "user_id": p.user.user_id, "real_name": p.real_name,
                    "college": p.college, "major": p.major or p.department, "clazz": p.clazz
                } for p in profiles]
                analysis['options'] = opts
                if len(opts) == 1:
                    analysis['status'], analysis['selected_id'] = 'success', opts[0]['user_id']
                elif len(opts) > 1:
                    analysis['status'] = 'multiple'
                results.append(analysis)
            return results

        # 内部工具函数：搜索逻辑
        def perform_search(pool, query_raw):
            query_clean = clean_comp_name(query_raw)
            results = []
            for item in pool:
                score = calculate_match_score(query_clean, item['clean_title'], query_raw, item['title'])
                if score >= MIN_SCORE_THRESHOLD:
                    results.append({
                        "id": item['id'], "title": item['title'],
                        "scale": item['scale'], "score": score
                    })
            # 仅保留匹配度最高的前3个
            return sorted(results, key=lambda x: x['score'], reverse=True)[:3]

        items_to_create = []

        # --- 主循环 ---
        for index, row in enumerate(data_list):
            raw_comp_name = str(row.get('奖项名称') or '').strip()
            raw_level = str(row.get('奖级') or '').strip()

            if not raw_comp_name and not row.get('学生'):
                continue

            guessed_scale = guess_competition_scale(raw_level)

            # --- 优化后的竞赛匹配逻辑 ---
            comp_analysis = {"status": "not_found", "selected_id": None, "options": []}

            if raw_comp_name:
                # 仅从推测的规模池中获取候选
                current_pool = comp_groups.get(guessed_scale, [])

                if current_pool:
                    matches = perform_search(current_pool, raw_comp_name)
                    # 如果有达标的结果
                    if matches:
                        comp_analysis['options'] = matches
                        comp_analysis['selected_id'] = matches[0]['id']
                        comp_analysis['status'] = 'success'

                # 如果 pool 为空或没有匹配上，comp_analysis 保持初始的 not_found 状态

            # 构建 Item 对象
            item = AwardImportItem(
                task=task_record,
                raw_competition=raw_comp_name,
                award_level=raw_level,
                award_date=parse_excel_date(row.get('获奖时间')),
                raw_participants=str(row.get('学生') or ''),
                raw_instructors=str(row.get('指导老师') or ''),
                competition_analysis=comp_analysis,
                participants_analysis=analyze_users(str(row.get('学生') or '')),
                instructors_analysis=analyze_users(str(row.get('指导老师') or ''))
            )

            # 校验有效性逻辑
            is_comp_ok = comp_analysis['status'] == 'success'
            is_part_ok = all(u['status'] == 'success' for u in item.participants_analysis)
            is_inst_ok = all(u['status'] == 'success' for u in item.instructors_analysis)

            if is_comp_ok and is_part_ok and is_inst_ok:
                item.is_valid, item.error_msg = True, ""
            else:
                item.is_valid = False
                err_s = []
                if not is_comp_ok:
                    scale_msg = f"[{guessed_scale}]" if guessed_scale else "[未知规模]"
                    err_s.append(f"未在{scale_msg}池中匹配到竞赛")
                if not is_part_ok: err_s.append("学生需核实")
                if not is_inst_ok: err_s.append("老师需核实")
                item.error_msg = "; ".join(err_s)

            items_to_create.append(item)

            # 更新任务进度
            if (index + 1) % 10 == 0 or (index + 1) == total:
                self.update_state(state='PROGRESS', meta={'current': index + 1, 'total': total})

        # 批量持久化
        with transaction.atomic():
            AwardImportItem.objects.bulk_create(items_to_create)
            task_record.status = 'correcting'
            task_record.save()

        return {"message": f"解析完成，共生成 {len(items_to_create)} 条暂存记录。"}

    except Exception as e:
        # 错误回退
        task_record = AwardImportTask.objects.get(id=task_id)
        task_record.status = 'failed'
        task_record.save()
        raise e