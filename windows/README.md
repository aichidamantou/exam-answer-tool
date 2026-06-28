# 考试答题工具 - Windows 版

绍兴职业技术学院管理平台自动答题工具

## 启动方式

### 方式一：服务模式（推荐，无需安装）
双击 **server.bat**

```
server.bat
  → 自动检测 Python（系统 / 嵌入版）
  → 启动 HTTP 服务
  → 自动打开浏览器
  → 按 Ctrl+C 或关闭窗口退出
```

无需 pywebview，零依赖，直接跑。

### 方式二：原生窗口模式
双击 **start.bat**

```
start.bat
  → 自动检测/安装 Python（如需）
  → 安装 pywebview
  → 启动原生 GUI 窗口
```

需要 pywebview（首次运行自动安装）。

### 方式三：打包为 .exe
双击 **build.bat**

```
build.bat
  → 用 PyInstaller 打包成单文件 exe
  → 输出: windows\考试答题工具.exe
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | 主程序（HTTP API + 前端界面） |
| `modules/` | 核心模块（答案提取/提交/检测） |
| `server.bat` | 服务模式启动（推荐） |
| `start.bat` | 窗口模式启动 |
| `build.bat` | 打包 .exe |
| `config.example.json` | 配置模板 |
| `config.json` | 运行时配置（自动生成） |
| `cookie.txt` | Cookie 存储（自动生成） |
| `headers.txt` | 浏览器标头（导入生成） |
| `exam_tool.log` | 错误日志 |

## 操作流程

```
1. 双击 server.bat 启动
2. 浏览器自动打开
3. 在标头输入框粘贴 F12 复制的请求标头 → 点击"导入标头"
4. 输入 PID → "PID 检测"
5. "获取答案" → "提交(快速/逐题)"
6. 用完点击"关闭退出"停止服务
```

## 常见问题

**Q: 提示 Python 未找到？**
A: 安装 Python 3.9+（官网 https://www.python.org/downloads/），安装时勾选 "Add Python to PATH"
