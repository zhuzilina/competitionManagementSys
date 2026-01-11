import re
from django.db.models import Q

from competitions.models import Competition
from .models import AwardImportItem
from userProfile.models import Profile

class ImportAnalyzer:
    def __init__(self):
        # 匹配 "姓名+学号" (如: 张三231001) 或 "纯姓名" (如: 张三)
        self.user_pattern = re.compile(r'^([^\d]+)(\d+)?$')
        self.split_pattern = re.compile(r'[，,、；;\s]+')

    def analyze_row(self, row_data) -> dict:
        """解析单行数据"""
        # 1. 竞赛解析逻辑 (同前)
        comp_raw = str(row_data.get('competition', '')).strip()
        comp_analysis = self._resolve_competition(comp_raw)

        # 2. 人员解析逻辑 (重点修改：基于 Profile)
        part_analysis = self._resolve_profiles_batch(row_data.get('participants', ''))
        inst_analysis = self._resolve_profiles_batch(row_data.get('instructors', ''))

        # 3. 校验逻辑
        is_comp_ok = comp_analysis['status'] == 'success'
        is_part_ok = all(u['status'] == 'success' for u in part_analysis)
        is_inst_ok = all(u['status'] == 'success' for u in inst_analysis)

        return {
            "raw_competition": comp_raw,
            "raw_participants": row_data.get('participants', ''),
            "raw_instructors": row_data.get('instructors', ''),
            "competition_analysis": comp_analysis,
            "participants_analysis": part_analysis,
            "instructors_analysis": inst_analysis,
            "is_valid": (is_comp_ok and is_part_ok and is_inst_ok),
            "error_msg": self._build_error_msg(is_comp_ok, is_part_ok, is_inst_ok)
        }

    def _resolve_competition(self, name):
        if not name:
            return {"status": "empty", "selected_id": None}

        comps = Competition.objects.filter(title__icontains=name)
        count = comps.count()

        if count == 0:
            return {"status": "not_found", "origin_text": name, "selected_id": None}
        elif count == 1:
            return {
                "status": "success",
                "origin_text": name,
                "selected_id": comps.first().id,
                "name": comps.first().title
            }
        else:
            # 模糊匹配找到多个，返回选项供用户选
            options = [{"id": c.id, "name": c.title} for c in comps[:10]]
            return {
                "status": "multiple",
                "origin_text": name,
                "selected_id": None,
                "options": options
            }

    def _resolve_profiles_batch(self, raw_str):
        if not str(raw_str).strip(): return []
        parts = re.split(self.split_pattern, str(raw_str).strip())
        return [self._resolve_single_profile(p) for p in parts if p]

    def _resolve_single_profile(self, text):
        match = self.user_pattern.match(text)
        if not match:
            return {"status": "error", "origin_text": text, "error": "格式错误"}

        name, uid = match.groups()
        name = name.strip()

        # 情况 A：带有明确的学工号 (精确匹配 Profile.user_id)
        if uid:
            profile = Profile.objects.filter(user_id=uid).first()
            if profile:
                return {
                    "status": "success",
                    "origin_text": text,
                    "selected_id": profile.user_id, # 这里的 selected_id 对应 Profile.user_id
                    "real_name": profile.real_name,
                    "dept": profile.department or profile.college
                }
            return {"status": "not_found", "origin_text": text, "error": "学号不存在"}

        # 情况 B：仅有姓名 (模糊匹配 Profile.real_name)
        else:
            profiles = Profile.objects.filter(real_name=name)
            count = profiles.count()

            if count == 0:
                return {"status": "not_found", "origin_text": text, "selected_id": None}
            elif count == 1:
                p = profiles.first()
                return {
                    "status": "success",
                    "origin_text": text,
                    "selected_id": p.user_id,
                    "real_name": p.real_name,
                    "dept": p.department or p.college
                }
            else:
                # 存在重名，构造选项供前端手动选择
                options = [{
                    "id": p.user_id,
                    "label": f"{p.real_name} ({p.department or p.college or '无单位'} - {p.user_id})"
                } for p in profiles]
                return {
                    "status": "multiple",
                    "origin_text": text,
                    "selected_id": None,
                    "options": options
                }

    def _build_error_msg(self, c, p, i):
        errs = []
        if not c: errs.append("竞赛未锁定")
        if not p: errs.append("学生信息有误")
        if not i: errs.append("导师信息有误")
        return " | ".join(errs)