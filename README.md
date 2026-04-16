# Job Apply Assistant

一个面向招聘网站半自动投递流程的 Codex skill 项目。当前版本优先解决“高回复率的精投”，而不是海投。

当前支持的核心能力：
- 采集 `Boss直聘`、`猎聘` 等页面上的岗位信息
- 将岗位数据标准化为统一 JSON 结构
- 读取当前简历并对岗位做匹配评分
- 输出岗位评估卡、优势、风险和站内问候语
- 在 Boss 网页端打开聊天、填入问候语，并支持确认后发送

## 当前能力

### `run_phase1.py`
- 读取简历
- 读取标准化岗位 JSON
- 生成匹配评分、岗位评估卡、问候语
- 生成待发送任务

### `collect_jobs.py`
- 解析 HTML 快照
- 通过 `requests` 抓取公开页面
- 通过 Selenium 附着到已登录浏览器
- 支持从 `Boss直聘` 结果页实时点击岗位并读取右侧 JD 详情
- 支持持续滚动到页面没有新岗位为止，再停止抓取

## 当前限制

- 真实站点采集目前优先支持 `Boss直聘`
- `猎聘` 解析器仍以通用解析为主，真实页面还需要继续调优
- Boss 聊天执行目前依赖网页端现有结构，页面改版后可能需要同步调整选择器
- Boss 的薪资文本存在字体混淆，严格薪资过滤还需要继续完善

## 仓库结构

```text
job-apply-assistant/
  README.md
  requirements.txt
  .gitignore
  job-apply-assistant/
    SKILL.md
    agents/
    examples/
    references/
    scripts/
```

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 准备简历

把你的简历放到仓库根目录，文件名默认是：

- `resume.pdf`

如果你想用别的路径，可以改：

- `job-apply-assistant/scripts/default_config.json`

里的 `resume_source` 字段，或者在运行时通过 `--resume-source` 传入。

## 示例配置

仓库里提供了一个可直接复制修改的示例配置：

- `job-apply-assistant/examples/config.example.json`

建议复制成你自己的运行配置，例如：

```powershell
Copy-Item "./job-apply-assistant/examples/config.example.json" "./job-apply-assistant/examples/config.local.json"
```

## 运行方式

### 1. 直接用样例岗位测试

```powershell
python "./job-apply-assistant/scripts/run_phase1.py" `
  --jobs "./job-apply-assistant/scripts/sample_jobs.json" `
  --config "./job-apply-assistant/scripts/default_config.json"
```

### 2. 先采集 Boss 页面，再做评估

先启动一个可见 Chrome，会话单独存放：

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode browser `
  --session-launch `
  --browser chrome `
  --driver-path "./drivers/chromedriver.exe" `
  --browser-binary "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --user-data-dir "./job-apply-assistant/browser-profile" `
  --urls "https://www.bosszhipin.com/" `
  --output "./job-apply-assistant/output/browser-session.json"
```

然后在浏览器里登录并打开目标搜索结果页，再附着抓取：

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode browser `
  --live-extract `
  --browser chrome `
  --driver-path "./drivers/chromedriver.exe" `
  --debugger-address "127.0.0.1:9222" `
  --browser-binary "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --wait-seconds 1.2 `
  --max-jobs 10 `
  --output "./job-apply-assistant/output/boss-jobs-live.json"
```

如果你的 Boss 列表页是“滚动到底部后继续刷新新岗位”，可以把 `--max-jobs` 设成 `0`，
让脚本持续滚动直到连续几轮都没有新岗位出现：

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode browser `
  --live-extract `
  --browser chrome `
  --driver-path "./chromedriver-win64/chromedriver-win64/chromedriver.exe" `
  --debugger-address "127.0.0.1:9222" `
  --browser-binary "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --wait-seconds 1.2 `
  --max-jobs 0 `
  --idle-rounds 3 `
  --scroll-pause 1.2 `
  --scroll-timeout 8 `
  --output "./job-apply-assistant/output/boss-jobs-live.json"
```

最后做岗位评估：

```powershell
python "./job-apply-assistant/scripts/run_phase1.py" `
  --jobs "./job-apply-assistant/output/boss-jobs-live.json" `
  --config "./job-apply-assistant/scripts/default_config.json" `
  --output-json "./job-apply-assistant/output/boss-live-assessments.json" `
  --output-text "./job-apply-assistant/output/boss-live-assessments.txt"
```

### 3. 将问候语填入 Boss 聊天框

生成 `boss-live-assessments.json` 后，可以直接读取其中的 `delivery_tasks`，
自动在 Boss 网页端打开对应聊天，并把问候语填进去。

执行层默认会走一套更保守的低风控策略：

- 默认使用 `preserve_jobs_tab`，保留一个 Boss 列表页标签不动
- 每条沟通任务在临时标签页里完成，避免频繁从聊天页再返回列表页
- 每个关键动作之间都会加入随机停顿
- 每条任务之间也会加入更长一点的冷却时间
- 如果页面掉进 `browser-check` / `_security_check`，脚本会尽快停下来，不继续硬刷

默认推荐先用 `draft` 模式，只填入 1 条，不发送：

```powershell
python "./job-apply-assistant/scripts/execute_delivery_tasks.py" `
  --tasks "./job-apply-assistant/output/boss-live-assessments.json" `
  --driver-path "./chromedriver-win64/chromedriver-win64/chromedriver.exe" `
  --debugger-address "127.0.0.1:9222" `
  --send-mode draft `
  --output "./job-apply-assistant/output/delivery-execution.json"
```

如果你想自己在浏览器里逐条确认，就用 `confirm` 模式。
脚本会先填好当前消息，等你在 Boss 页面里手动点发送；
一旦检测到该条消息已发出，就会自动回到职位列表并切到下一条：

```powershell
python "./job-apply-assistant/scripts/execute_delivery_tasks.py" `
  --tasks "./job-apply-assistant/output/boss-live-assessments.json" `
  --driver-path "./chromedriver-win64/chromedriver-win64/chromedriver.exe" `
  --debugger-address "127.0.0.1:9222" `
  --send-mode confirm `
  --max-tasks 5 `
  --output "./job-apply-assistant/output/delivery-execution.json"
```

确认流程稳定后，再切到真正自动发送：

```powershell
python "./job-apply-assistant/scripts/execute_delivery_tasks.py" `
  --tasks "./job-apply-assistant/output/boss-live-assessments.json" `
  --driver-path "./chromedriver-win64/chromedriver-win64/chromedriver.exe" `
  --debugger-address "127.0.0.1:9222" `
  --send-mode send `
  --max-tasks 5 `
  --output "./job-apply-assistant/output/delivery-execution.json"
```

说明：

- `draft` 模式只会处理 1 条任务，并把内容留在聊天框里供你人工确认
- `confirm` 模式会逐条填入消息，等你在浏览器里手动点发送；发送成功后脚本会自动切到下一条
- `send` 模式会按当前筛出来的任务逐条进入聊天页并真实发送
- 默认 `navigation-mode` 是 `preserve_jobs_tab`，更适合降低“聊天页返回列表页”带来的不稳定
- `confirm` 模式下，如果你清空输入框而不是点击发送，脚本会把这一条视为跳过并继续后续任务
- 这一步默认依赖你当前打开的 Boss 结果页；如果你有固定搜索 URL，也可以通过 `--jobs-url` 传入
- 如果你想进一步放慢节奏，可以调大 `--action-pause-min/max` 和 `--between-task-pause-min/max`
- 如果只是稳妥精投，建议 `confirm` 或 `send` 时单次先跑 `3-5` 条，不要长批量连续执行

## 安装为 Codex skill

仓库里已经带了一个本地安装脚本：

```powershell
python "./job-apply-assistant/scripts/install_skill.py"
```

默认会把下面这些内容复制到你的本机 Codex skill 目录：

- `job-apply-assistant/SKILL.md`
- `job-apply-assistant/agents`
- `job-apply-assistant/examples`
- `job-apply-assistant/references`
- `job-apply-assistant/scripts`

目标目录默认是：

- Windows: `%USERPROFILE%\.codex\skills\job-apply-assistant`
- macOS/Linux: `~/.codex/skills/job-apply-assistant`

如果你想覆盖已存在的安装版本：

```powershell
python "./job-apply-assistant/scripts/install_skill.py" --force
```

如果你要安装到自定义的 Codex home：

```powershell
python "./job-apply-assistant/scripts/install_skill.py" --codex-home "D:\custom-codex-home"
```

## 不要提交到仓库的内容

这些目录或文件只属于本地运行环境，不应该公开：

- `resume.pdf`
- `base简历.pdf`
- `job-apply-assistant/browser-profile/`
- `job-apply-assistant/output/`
- `job-apply-assistant/snapshots/`
- `.selenium/`
- `chromedriver-win64/`

## 后续方向

- 完善 Boss 薪资解混
- 调优猎聘真实页面解析
- 让待发送任务进入“用户确认后发送”流程
- 加入多版本简历和简历适配建议
