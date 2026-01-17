import re
import datetime
from thefuzz import process, fuzz
from django.db.models import Q


def clean_names(name_str):
    """
    将 '张三, 李四、王五 赵六' 切割成列表 ['张三', '李四', '王五', '赵六']
    """
    if not name_str:
        return []
    # 匹配逗号、顿号、空格
    names = re.split(r'[，,、\s]+', str(name_str).strip())
    return [n for n in names if n]


def parse_excel_date(date_val):
    """
    将 Excel 中的 2024.10 或 datetime 对象转为 date
    """
    if isinstance(date_val, datetime.datetime):
        return date_val.date()
    if isinstance(date_val, str):
        # 尝试处理 2024.10 这种格式，默认为该月1号
        try:
            if '.' in date_val:
                parts = date_val.split('.')
                if len(parts) == 2:
                    return datetime.date(int(parts[0]), int(parts[1]), 1)
                elif len(parts) == 3:
                    return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except:
            pass
    return None


def guess_competition_scale(award_level_str):
    """
    从获奖等级字符串中猜测竞赛规模，用于缩小竞赛匹配范围
    例如：'国家级三等奖' -> '国家级'
    """
    if not award_level_str:
        return None

    mapping = {
        "国际": "国际级",
        "国家": "国家级",
        "全国": "国家级",
        "省": "省级",
        "市": "市级",
        "校": "校级",
        "院": "院级"
    }
    for key, val in mapping.items():
        if key in award_level_str:
            print(f"推测出竞赛规模{val}")
            return val
    return None