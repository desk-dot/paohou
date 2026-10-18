"""命令行入口：读取跑步记录 JSON，复用 analysis_tools 生成本地规则复盘（Markdown）。

只使用 Python 标准库与 analysis_tools 中的确定性函数，不调用任何模型接口。
"""
import argparse
import json
import os
import sys
from pathlib import Path

from analysis_tools import calculate_metrics, local_review, validate_record


def build_parser():
    parser = argparse.ArgumentParser(
        description="校验 Keep 跑步记录 JSON 并生成本地规则复盘（Markdown），不调用模型。")
    parser.add_argument("json_path", help="跑步记录 JSON 文件路径")
    parser.add_argument("--output", metavar="报告路径",
                        help="Markdown 复盘保存路径（UTF-8）；缺省时打印到终端。"
                             "目标已存在或与输入路径相同时拒绝执行。")
    return parser


def fail(message):
    print(f"错误：{message}", file=sys.stderr)
    return 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    input_path = Path(args.json_path)
    output_path = Path(args.output) if args.output else None

    if not input_path.is_file():
        return fail(f"输入文件不存在或不是文件：{input_path}")
    if output_path is not None:
        same = (os.path.normcase(os.path.realpath(input_path))
                == os.path.normcase(os.path.realpath(output_path)))
        if same:
            return fail("输入和输出路径不能相同。")
        if output_path.exists():
            return fail(f"目标文件已存在，拒绝覆盖：{output_path}")

    try:
        raw = json.loads(input_path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError as exc:
        return fail(f"输入文件不是有效的 UTF-8 文本：{exc}")
    except json.JSONDecodeError as exc:
        return fail(f"JSON 解析失败（第 {exc.lineno} 行第 {exc.colno} 列）：{exc.msg}")
    except OSError as exc:
        return fail(f"无法读取输入文件：{exc}")

    try:
        record = validate_record(raw)
        metrics = calculate_metrics(record)
        report = local_review(metrics)
    except ValueError as exc:
        return fail(f"记录校验失败：{exc}")

    if output_path is None:
        print(report)
        return 0
    # 前置 exists 检查只是友好的快速失败；x 模式独占创建才是原子保证，
    # 即使检查后目标被其他进程创建，也拒绝覆盖。
    try:
        with open(output_path, "x", encoding="utf-8") as f:
            f.write(report + "\n")
    except FileExistsError:
        return fail(f"目标文件已存在，拒绝覆盖：{output_path}")
    except OSError as exc:
        return fail(f"无法写出报告：{exc}")
    print(f"已保存 Markdown 复盘：{output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
