# 跑后 · Keep 跑步复盘 Agent

面向个人跑者：上传同一次 Keep 跑步的截图，确认识别数据，计算可复核的跑步指标，再生成有数据依据的复盘。

## 启动

在本目录的 PowerShell 中执行（首次安装需要联网）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

本机已创建 `.venv` 并安装依赖，直接执行第三条即可。页面地址为 `http://127.0.0.1:8501`。

先点击“体验示例数据”，核对后勾选确认，再点击“生成本地复盘”，不需要 API Key。

## 使用真实截图

1. 准备同一次跑步的总览、分段配速和步频/步幅截图，最多 6 张、合计 20 MB。建议裁掉头像、姓名和路线位置。
2. 在侧栏填写服务商的 API Base URL、API Key、截图模型和复盘模型。截图模型必须支持图片输入，复盘模型必须支持 Chat Completions 工具调用。使用服务商控制台提供的真实名称，不假定 OpenCode 中的模型一定具备这些能力。
3. 上传图片，确认允许发送到所填服务商，点击“识别截图”。Key 不需要发到聊天里。
4. 对照原图改正表格。段长是本段长度；最后 0.5 km 就填 0.5。未知值留空，爬升不等于海拔或起终点高差。
5. 勾选数据确认，再生成本地复盘或 AI 复盘。可以下载 Markdown、确认数据及工具执行记录。

也可设置环境变量 `RUN_BASE_URL`、`RUN_API_KEY`、`RUN_VISION_MODEL`、`RUN_REVIEW_MODEL`。程序不读取 OpenCode 配置、不自动读取 `.env`，不保存密钥或上传图片。数据和报告只存在会话内，需自行下载；当前没有历史数据库。工作目录位于 OneDrive，下载文件的同步行为由用户自己的系统设置决定。

## 已实现与待验证

- 已实现：图片上传、可配置视觉模型适配、识别后编辑确认、数据校验、指标计算、配速图、只读工具调用 Agent、调用上限、失败提示、本地规则降级、报告和执行记录导出。
- 本地可验证：固定样例、指标边界、Agent 调用控制（模拟模型）、页面确认和修改后失效。
- 尚未验证：真实 Keep 截图识别准确率、所选服务商兼容性及真实模型复盘质量。没有真实接口配置前，不把模拟测试算作真实模型调用成功。
- 后续范围：保存多次跑步记录、条件相近记录之间的比较，以及小型人工标注截图评测集。
- 本学期先保持单人本地使用、手动上传；不依赖 Keep 自动登录、抓取或未确认存在的导出 API。

## 为什么属于 Agent 应用

`model_client.extract_record` 提取截图字段，用户确认后 `agent.review_run` 将任务交给模型。模型调用白名单中的 `analyze_run` 工具，由 Python 校验并计算结果，再交给模型生成复盘。最多 4 轮，未知工具不执行，未调用分析工具的直接回答不予采用。界面保留执行步骤和工具结果，不展示模型隐式推理。

本地规则复盘只是离线演示与故障回退，不将其称为大模型 Agent 的实际运行结果。模型输出仍需评估，工具调用并不能保证每句话都正确。

## 指标口径

- 全程均配速 = 全程用时 / 全程距离；两者不齐全时，统一退回已录入分段的距离和估算用时，不混用不同范围的数据。
- 分段估算用时 = 段长 × 每公里配速。末段按实际段长计算。
- 前后半程按已录入距离等分，跨段边界按该段匀速估算；结果为后半程配速减前半程配速，正值表示更慢。这是描述值，不是疲劳或跑姿诊断。
- 距离差超过 `max(0.02 km, 全程距离 × 1%)`，或用时差超过 `max(5秒, 总用时 × 1%)` 时提示核对。这些是工程容差，不是运动科学阈值。
- 顶层步频、步幅和爬升只使用全程汇总；缺失时不以部分分段值冒充。每段的对应数据仍保留给用户和模型查看。
- 不从单次记录推断乳酸阈值、伤病、跑姿优劣，不要求统一的“180 步频”。缺少训练史和恢复信息时，不生成具体加量或高强度处方。

示例是人工构造的 2.5 km 记录：`1×360 + 1×380 + 0.5×380 = 930 秒`，均配速 `930÷2.5 = 372 秒/km = 6:12/km`。前半程用时 455 秒，后半程 475 秒，配速差 `20÷1.25 = 16 秒/km`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试中的 `FakeClient` 是确定性测试替身，不发送网络请求。真实模型评测需另行记录截图字段正确率、人工修正数量、是否忠实引用工具数值、是否保留数据限制，以及模型、耗时与失败情况。

## 命令行复盘

不打开页面、不调用模型，直接对一份记录 JSON 生成本地规则复盘：

```powershell
# 打印到终端
.\.venv\Scripts\python.exe review_file.py examples/demo.json

# 保存为 UTF-8 Markdown（目标已存在或与输入路径相同时拒绝执行）
.\.venv\Scripts\python.exe review_file.py examples/demo.json --output review.md
```

文件不存在、JSON 无法解析或记录校验失败时，打印错误并以非零状态退出，不写出报告。

## 文件

- `streamlit_app.py`：上传、确认、复盘页面。
- `analysis_tools.py`：校验及可重复计算的指标。
- `model_client.py`：模型接口及截图提取提示词。
- `agent.py`：受限工具调用循环及复盘提示词。
- `review_file.py`：命令行入口：校验 JSON 记录并输出本地复盘报告，不调用模型。
- `examples/demo.json`：明确标注的合成数据。
- `tests/`：数值、Agent 控制、页面交互测试。
- `docs/opencode-first-task.md`：学生在 OpenCode 中完成首次实践的独立小任务。

本项目从空目录启动；初始代码由 Codex 辅助生成，学生需阅读、亲自运行、核对并继续修改。没有采用第三方现成跑步项目；使用 Python、Streamlit 及其依赖。模型适配参考 [阿里云模型服务的图片输入文档](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/vision)，采用可配置的兼容接口，不预设账户权限。

课程依据：[检查点 1](https://edu.cs.tsinghua.edu.cn/ai-prog/course/checkpoint-1/)、[大作业说明](https://edu.cs.tsinghua.edu.cn/ai-prog/course/project/)。
