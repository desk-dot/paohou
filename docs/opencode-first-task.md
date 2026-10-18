# 首次 OpenCode 编程实践：增加命令行复盘入口

你已说明 OpenCode 配置完成，但还没有完成实际编程实践。下面的任务是待执行的练习，不是已经发生的过程记录。当前网页原型由 Codex 辅助搭建；请在报告中分别说明两个工具的作用。

## 1. 打开项目并记录环境

在 OpenCode 中打开当前 `project` 文件夹。记录软件实际版本、所选服务商和模型名称、配置成功的截图或脱敏日志；不要根据课程示例填写版本。模型名称可以从 OpenCode 界面查看。

## 2. 粘贴下面的提示词

```text
我正在做 Keep 跑步复盘 Agent。请先阅读 README.md、analysis_tools.py 和 examples/demo.json，解释 validate_record、calculate_metrics、local_review 的输入输出。

请帮我新增一个小型命令行入口 review_file.py，要求：
1. 用 Python 标准库 argparse 接收 JSON 文件路径，以及可选 --output 报告路径。
2. 复用现有三个函数，不重复实现分析公式，不调用任何模型接口。
3. 未指定 --output 时把 Markdown 复盘打印到终端；指定时以 UTF-8 保存。输入无效时打印清楚的错误，并以非零状态退出，不能写出误导性报告。
4. 输入和输出路径不能相同；目标文件已存在时拒绝覆盖。
5. 用现有 examples/demo.json 验证 2.5 km、930 秒和 6:12/km；再验证不存在的文件、无效 JSON 和零距离的错误处理。
6. 补充 README 中的运行命令，并给出你执行的命令与结果。先说明改动计划，改动保持小而清楚。
```

如果 OpenCode 选择了错误的 Python，告诉它：当前虚拟环境解释器为 `.venv\Scripts\python.exe`。不要把“它说成功”直接当作自己的验证。

## 3. 亲自运行并核对

功能完成后，在 `project` 的终端执行：

```powershell
.\.venv\Scripts\python.exe review_file.py examples/demo.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git diff
```

人工核对：`360 + 380 + 0.5×380 = 930 秒`，`930÷2.5 = 372 秒/km = 6:12/km`。再实际检查至少一种错误输入和覆盖保护。记录自己是否发现问题、接受或修改了什么建议。

## 4. 保存完整交互，补全报告

用当前 OpenCode 版本支持的导出功能导出完整会话；若没有导出功能，则保存完整对话文本，包含提示、回答、工具执行及迭代。放到上一级 `ai-records/`。导出方式以实际版本界面为准，避免假定某个命令存在。

共享前检查密钥和个人信息，脱敏处明确写 `[已脱敏]`。截图和过程摘要不能代替完整记录。

## 5. 提交自己的实践改动

检查 `git diff` 和 `git status` 后，只暂存本次代码、文档及测试，例如：

```powershell
git add review_file.py README.md
git status
git commit -m "Add CLI running review and verify sample metrics"
git log --oneline -3
```

如新增测试，也明确加入相应文件。不要加入 API Key、真实截图、虚拟环境。将真实提交情况、运行结果及自己的体会补入上一级 `report.md`。
