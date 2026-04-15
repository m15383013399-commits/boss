# Job Apply Assistant

一个面向招聘网站半自动投递流程的 Codex skill 项目。当前重点是：

- 从 `Boss直聘`、`猎聘` 等页面采集岗位信息
- 将岗位数据标准化
- 用当前简历对岗位做匹配评分
- 输出岗位评估卡、优势/风险分析和问候语
- 为后续“用户确认后发送”保留待发送任务结构

当前版本更适合回复率优先的精投，而不是海投。

## 当前能力

- `run_phase1.py`
  - 读取简历
  - 读取标准化岗位 JSON
  - 生成匹配评分、岗位评估卡、问候语
  - 生成待发送任务

- `collect_jobs.py`
  - 从 HTML 快照解析岗位
  - 通过 `requests` 抓公开页面
  - 通过 Selenium 附着到已登录浏览器，抓 Boss 结果页和右侧 JD 详情

## 当前限制

- 真实站点采集目前优先支持 `Boss直聘`
- `猎聘` 解析器还没有按真实页面做足够调优
- 不会自动发送消息，当前只生成待发送任务
- 薪资文本在 Boss 上存在字体混淆，严格薪资过滤仍需继续完善

## 目录结构

```text
job-apply-assistant/
  README.md
  requirements.txt
  .gitignore
  job-apply-assistant/
    SKILL.md
    agents/
    references/
    scripts/
```

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 准备你的简历

把你的简历放到仓库根目录，文件名可以是：

- `resume.pdf`

或者直接修改：

- `job-apply-assistant/scripts/default_config.json`

中的 `resume_source`。

## 运行方式

### 1. 直接用样例岗位测试

```powershell
python "./job-apply-assistant/scripts/run_phase1.py" `
  --jobs "./job-apply-assistant/scripts/sample_jobs.json" `
  --config "./job-apply-assistant/scripts/default_config.json"
```

### 2. 先采集 Boss 页面，再做评分

先启动一个可见 Chrome，会话独立存在：

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

最后做评分：

```powershell
python "./job-apply-assistant/scripts/run_phase1.py" `
  --jobs "./job-apply-assistant/output/boss-jobs-live.json" `
  --config "./job-apply-assistant/scripts/default_config.json" `
  --output-json "./job-apply-assistant/output/boss-live-assessments.json" `
  --output-text "./job-apply-assistant/output/boss-live-assessments.txt"
```

## 如何安装成 Codex skill

把仓库里的：

- `job-apply-assistant/SKILL.md`
- `job-apply-assistant/agents`
- `job-apply-assistant/references`
- `job-apply-assistant/scripts`

复制到你本机的：

- `~/.codex/skills/job-apply-assistant`

然后就可以在 Codex 里通过 `$job-apply-assistant` 使用。

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
