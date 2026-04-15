# Job Apply Assistant

一个面向招聘网站半自动投递流程的 Codex skill 项目。当前版本优先解决“高回复率的精投”，而不是海投。

当前支持的核心能力：
- 采集 `Boss直聘`、`猎聘` 等页面上的岗位信息
- 将岗位数据标准化为统一 JSON 结构
- 读取当前简历并对岗位做匹配评分
- 输出岗位评估卡、优势、风险和站内问候语
- 预留“用户确认后发送”的执行接口

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

## 当前限制

- 真实站点采集目前优先支持 `Boss直聘`
- `猎聘` 解析器仍以通用解析为主，真实页面还需要继续调优
- 当前不会自动发送消息，只生成待发送任务
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

最后做岗位评估：

```powershell
python "./job-apply-assistant/scripts/run_phase1.py" `
  --jobs "./job-apply-assistant/output/boss-jobs-live.json" `
  --config "./job-apply-assistant/scripts/default_config.json" `
  --output-json "./job-apply-assistant/output/boss-live-assessments.json" `
  --output-text "./job-apply-assistant/output/boss-live-assessments.txt"
```

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
