# SceneProof 镜证

SceneProof 是面向 AI 视频生产链路的场景级质量验证与回归工具。

它不只检查接口是否成功，还会保存一次生成任务的输入、版本、日志、媒体产物和检查结果，用于：

- 验证视频是否可播放，以及时长、分辨率、帧率、编码和音轨是否符合要求
- 检查黑帧、冻结画面、缺失音频等确定性问题
- 为后续多模态质量评估保存关键帧、字幕和音频证据
- 比较不同平台版本或模型版本之间的回归差异
- 输出可以回溯到原始文件和日志的测试报告

当前里程碑是最小可用骨架：CLI 可以通过 `ffprobe` 读取真实视频信息。

## 环境要求

- Python 3.12 至 3.15
- uv 0.13 或更高版本
- FFmpeg 和 ffprobe
- Git

本机开发环境使用 Python 3.14.10 和 FFmpeg 9.0.2。

## 安装

```powershell
uv sync
```

## 使用

查看视频信息：

```powershell
uv run sceneproof probe "C:\path\to\video.mp4"
```

输出 JSON：

```powershell
uv run sceneproof probe "C:\path\to\video.mp4" --json
```

## 开发检查

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=sceneproof --cov-report=term-missing
```

## 数据安全

公开仓库和示例中不得包含公司代码、Token、内部接口、真实用户数据或未授权媒体。开发和生产环境的凭据必须通过环境变量或公司批准的密钥管理方式提供。

