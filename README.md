# PDF OCR DeepSeek Translator

一个适合课程作业展示的桌面小工具：把本地 PDF 逐页渲染成图片，调用百度智能云 OCR 识别英文文献，再通过 DeepSeek 翻译成简体中文，并导出文本、Markdown 和 Word 文件。

本项目是一个简化版 PDF 文献 OCR 翻译工具，主要用于课程作业展示。它不追求复杂的 PDF 版面还原，而是完成从 PDF 页面图像化、OCR 文本识别、LLM 翻译到结果文件导出的完整流程。

## 功能特点

- tkinter 桌面 GUI，可选择或手动输入 PDF 绝对路径
- 后台线程执行耗时任务，处理期间界面保持响应
- PyMuPDF 逐页生成 PNG，默认 200 DPI
- 图片超过 4 MB 时自动以 150 DPI 重渲染该页
- 百度通用文字识别（高精度版）逐页 OCR
- 保留 `===== Page N =====` 页码标记
- DeepSeek 按页优先、超长页按自然边界分块翻译
- DeepSeek 请求失败最多尝试 3 次，间隔 2 秒
- 输出 OCR 原文、纯文本译文、Markdown、运行日志及 Word 文档
- 所有路径使用 `pathlib.Path`，输出文本统一为 UTF-8
- API Key 只从 `.env` 读取，不写入源代码

## 项目结构

```text
pdf_ocr_deepseek_translator/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── pdf_processor.py
│   ├── baidu_ocr.py
│   ├── deepseek_translator.py
│   ├── output_writer.py
│   └── utils.py
└── samples/
    └── README.md
```

## 环境要求

- Python 3.10 或更高版本
- Windows、macOS 或带有图形桌面的 Linux
- 可访问百度智能云和 DeepSeek API 的网络
- 已开通百度智能云 OCR 服务和 DeepSeek API

> tkinter 通常随 Windows/macOS 的 Python 安装提供。部分 Linux 发行版需要另行安装 `python3-tk`。

## 安装步骤

在项目根目录打开 PowerShell 或终端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux 激活命令为：

```bash
source .venv/bin/activate
```

## API Key 配置

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

也可使用课程要求中的 Windows 命令：

```bat
copy .env.example .env
```

编辑 `.env`：

```dotenv
BAIDU_OCR_API_KEY=你的百度_API_Key
BAIDU_OCR_SECRET_KEY=你的百度_Secret_Key

DEEPSEEK_API_KEY=你的_DeepSeek_API_Key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com

OCR_RENDER_DPI=200
TRANSLATION_CHUNK_SIZE=2500
```

百度的 API Key 与 Secret Key 来自百度智能云应用；DeepSeek API Key 来自 DeepSeek 开放平台。`.gitignore` 已忽略 `.env`，请不要删除该规则，也不要把真实密钥复制到截图、日志、Issue 或提交记录中。

## 运行方式

```powershell
python app.py
```

然后：

1. 点击“选择 PDF”，或在输入框中粘贴本地 PDF 的绝对路径，例如 `D:\paper\example.pdf`。
2. 点击“开始处理”。
3. 在日志框和进度条中查看处理状态。
4. 完成后，弹窗会显示输出目录。

## 输出文件

假设输入为 `D:\paper\example.pdf`，程序会创建：

```text
D:\paper\example_translated_output\
├── images\
│   ├── page_001.png
│   ├── page_002.png
│   └── ...
├── ocr_raw.txt
├── translated.txt
├── translated.md
├── translated.docx
└── run_log.txt
```

- `images/`：用于 OCR 的逐页 PNG 图片
- `ocr_raw.txt`：带页码标记的 OCR 原文
- `translated.txt`：纯文本中文译文
- `translated.md`：适合 GitHub 或 Markdown 阅读器查看的结果
- `translated.docx`：简单排版的 Word 译文；若未安装 `python-docx`，程序会跳过它
- `run_log.txt`：开始时间、PDF 路径、页数、逐页 OCR 状态、翻译块数、输出路径或错误信息

如果同名输出目录已经存在，程序会覆盖同名结果文件和页面图片，不会主动删除目录中的其他文件。

## 异常处理

程序会在 GUI 日志框和弹窗中报告常见问题，包括：空路径、文件不存在、非 PDF 文件、缺少 API Key、输出目录无写权限、页面渲染失败、百度认证/OCR 错误、网络超时和 DeepSeek 翻译失败。详细堆栈会写入已创建输出目录中的 `run_log.txt`。

## 注意事项

- OCR 与翻译均会调用计费 API，请先查看账户余额和当前服务价格。
- 建议先用页数较少、版式简单的论文测试。
- 输出目录与源 PDF 位于同一位置，因此源 PDF 所在目录必须可写。
- 单页 PNG 的大小上限在本项目中保守设为 4 MB；超过后会降至 150 DPI，再超限则停止并给出错误。
- 不要在处理期间移动源 PDF 或删除输出目录。
- `.env` 仅供本机使用，提交 GitHub 前可执行 `git status` 再次确认密钥未被跟踪。

## 局限性

- OCR 质量依赖百度 OCR API。
- 扫描质量差、双栏论文、公式密集论文可能出现识别顺序或字符错误。
- 当前版本不做复杂版面还原，也不把译文覆盖回原 PDF。
- 当前版本不支持批量 PDF。
- 当前版本只支持百度 OCR 和 DeepSeek API。
- API 调用会产生费用。
- 大 PDF 的渲染、OCR 和分块翻译耗时较长。
- OCR 文本的断行和表格结构可能影响译文质量。

## 课程作业说明

项目刻意保持最小范围：没有 Web、App、登录、数据库、Docker 或复杂的 PDF 回填。模块分别负责配置、渲染、OCR、翻译、输出和 GUI 调度，便于在课程答辩中解释从输入到输出的完整数据流，也便于后续替换提示词或调整渲染参数。

请勿在仓库中提交真实论文样本或 API Key。`samples/` 只保留说明文件，测试材料由使用者自行准备。
