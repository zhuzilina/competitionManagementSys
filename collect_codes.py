import os


def collect_django_code(project_root, output_file="codes.txt"):
    # 定义需要查找的目标文件名
    target_files = ['models.py', 'serializers.py', 'urls.py', 'views.py', 'settings.py']

    total_lines = 0
    all_content = []

    # 遍历项目目录
    for root, dirs, files in os.walk(project_root):
        # 排除常见的虚拟环境和缓存目录，提高效率
        if any(skip in root for skip in ['.git', '__pycache__', 'venv', '.venv', 'env']):
            continue

        for file in files:
            if file in target_files:
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        total_lines += line_count

                        # 构建文件头部标识，方便阅读
                        header = f"\n{'=' * 80}\n"
                        header += f"FILE: {file_path}\n"
                        header += f"LINES: {line_count}\n"
                        header += f"{'=' * 80}\n\n"

                        all_content.append(header)
                        all_content.extend(lines)
                        all_content.append("\n")  # 确保文件间有空行

                except Exception as e:
                    print(f"无法读取文件 {file_path}: {e}")

    # 将所有内容写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(all_content)

    print(f"处理完成！")
    print(f"合并后的文件已保存至: {os.path.abspath(output_file)}")
    print(f"总计读取代码行数: {total_lines}")


if __name__ == "__main__":
    # 获取当前脚本所在目录作为项目根目录
    current_dir = os.getcwd()
    collect_django_code(current_dir)