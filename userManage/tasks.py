import numpy as np
import pandas as pd
from celery import shared_task
from django.contrib.auth import get_user_model
from userManage.serializers import RegisterSerializer

User = get_user_model()


@shared_task(bind=True)
def import_users_task(self, file_path):
    df = pd.read_excel(file_path)
    df = df.replace({np.nan: None, "": None})
    data_list = df.to_dict(orient='records')

    total = len(data_list)
    success_count = 0
    errors = []

    column_mapping = {
        '姓名': 'real_name', '学工号': 'user_id', '密码': 'password',
        '角色': 'role_names', '部门': 'department', '学院': 'college',
        '手机号': 'phone', '邮箱': 'email', 'qq': 'qq',
        '专业': 'major', '班级': 'clazz', '职称': 'title'
    }

    # 建议不要在 Task 外层加 transaction.atomic，否则一个失败全部回滚
    # 如果需要部分成功，就在循环内处理事务
    for index, row in enumerate(data_list):
        mapped_data = {}
        # 1. 先完整提取该行的所有数据
        for chinese_key, english_key in column_mapping.items():
            val = row.get(chinese_key)
            if english_key == 'role_names' and val:
                # 关键：确保 val 是字符串且去除空格，转成列表
                mapped_data[english_key] = [str(val).strip()]
            else:
                mapped_data[english_key] = val

        # 2. 补充必要字段
        mapped_data['re_password'] = mapped_data.get('password')
        mapped_data['username'] = mapped_data.get('user_id')

        # 3. 校验并保存（在映射循环之外）
        serializer = RegisterSerializer(data=mapped_data)
        if serializer.is_valid():
            try:
                serializer.save()
                success_count += 1
            except Exception as e:
                errors.append({
                    "row": index + 2,
                    "user_id": mapped_data.get('user_id'),
                    "error": f"数据库写入失败: {str(e)}"
                })
        else:
            errors.append({
                "row": index + 2,
                "user_id": mapped_data.get('user_id'),
                "error": serializer.errors
            })

        # 更新进度
        self.update_state(
            state='PROGRESS',
            meta={'current': index + 1, 'total': total, 'percent': round((index + 1) / total * 100, 2)}
        )

    return {"total": total, "success_count": success_count, "errors": errors}