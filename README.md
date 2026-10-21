# 羽约 · 西电 / 羽毛球预约助手 v2.1.1

v2.1.1 修复一键登录误报窗口关闭：Edge 兼容模式可能重新启动浏览器，原启动进程退出不代表登录窗口关闭。现在以专属 CDP 连接中的真实页面判断窗口存活，容忍短暂断连，并通过 Browser.close 关闭重新启动后的登录浏览器。新增启动进程退出、短暂断连与真实关闭场景的回归测试。

登录浏览器的临时配置改存本机临时目录，减少程序放在移动盘时的大量小文件读写；本机 HTTP 调试轮询也不再反复加载证书文件。场馆 HTTPS 请求仍照常验证证书。

西安电子科技大学远望谷体育馆羽毛球预约工具。FastAPI 后端、React 前端、Windows WebView2 桌面窗口。

## 使用修复版

Windows 10/11 64 位用户可从 [GitHub Releases](https://github.com/nknknk3/badminton-booking/releases/latest) 下载完整便携压缩包。请先全部解压，再运行其中的 exe；单独发送 exe 会缺少 `_internal` 运行依赖。GitHub 的源码压缩包需要自行构建，不能直接作为桌面版运行。

双击项目目录中的 `BadmintonBooking.exe`。请保留同目录下的 `_internal/`，里面是程序运行依赖。新版本采用目录打包，避免单文件版每次启动都先解压依赖。

- 默认只显示原生桌面窗口，不会自动打开浏览器，也不再在窗口打开失败时回退到浏览器。
- 关闭窗口右上角的 ×，即停止后台并退出程序。
- 侧栏底部或顶栏的「退出整个服务」可同时退出界面和后台；确认框会提示正在运行的任务将停止。
- 本地任务、预约记录与登录文件保存在程序目录，重启后保留。
- 如提示窗口初始化失败，请检查 Microsoft Edge WebView2 运行时是否已安装，查看 `logs/app.log` 和 `logs/console.log`。

首次使用打开「设置 → 一键登录」。登录时会单独打开学校认证窗口，账号密码与滑块由你在该窗口完成。如果出现「用户类型选择」，请继续完成选择。程序只有在场馆接口确认登录有效后才保存会话并关闭登录窗口；中途取消或验证未通过不会覆盖已有会话。登录有效期由学校系统决定。

仍支持在设置中导入 `venue_session.json`。校园网络不通时会显示连接错误；不会把没有通过认证的会话显示为登录成功。

## 本次修复

1. 登录检测改为检查实际页面的主机名，避免将认证 URL 查询参数中的场馆地址误判为已进入场馆。
2. 等待场馆会话验证成功，随后原子保存 cookie 并热更新所有预约服务；支持父域 cookie，兼容带 UTF-8 BOM 的状态响应；取消登录时等待清理结束，避免影响下一次登录。
3. 统一窗口与服务退出信号，停止调度器、登录窗口、HTTP 客户端、数据库；提供完整退出按钮。
4. 使用原生 WebView2 替代 Edge 应用模式，移除默认浏览器回退与无限等待循环。
5. 采用 exe + `_internal` 目录打包，首页立即渲染，本地数据与远程查询分开加载；没有 cookie 时不再请求场馆验证接口。
6. 更新森林绿侧栏、球场线条主视觉、统计与快捷操作卡片，保留窄窗口布局。

## 源码运行

建议使用 Python 3.11 或 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
cd frontend
npm install
npm run build
cd ..
.\.venv\Scripts\python.exe run.py
```

可选参数：

```powershell
python run.py --port 8080
python run.py --headless       # 只运行服务
python run.py --no-browser     # 同 --headless
python run.py --browser        # 仅显式指定此参数时打开系统浏览器
python run.py --token mypass
python run.py --tunnel
```

`--window-mode auto` 和 `--window-mode window` 都使用原生窗口。`--reload` 用于后端开发，默认不打开浏览器。`OPEN_BROWSER=false` 兼容旧配置，表示只运行后台服务。

## 构建与验证

```powershell
python -m unittest discover -s tests -v
python build_exe.py
```

构建总是重新编译前端，避免把旧界面打进新 exe。完整产物在 `dist/BadmintonBooking/`，也会复制到项目根目录的 `BadmintonBooking.exe` 与 `_internal/`。首次替换时保留原来的单文件版为 `BadmintonBooking.previous.exe`。分发时必须同时复制 exe 与 `_internal/`。

回归测试覆盖认证重定向识别、等待 cookie 生效、取消登录清理、父域 cookie、BOM 状态响应、无 cookie 快速返回与本地退出接口限制。真实校园账号登录需要使用者完成认证后验证。

## 配置与数据

复制 `config.example.json` 为 `config.json` 后按需修改，环境变量优先。默认监听 `127.0.0.1:8000`，端口占用时自动顺延。

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| PORT | 8000 | 本地监听端口 |
| HOST | 127.0.0.1 | 监听地址 |
| OPEN_BROWSER | true | 是否显示桌面界面，旧名称保留兼容 |
| ACCESS_TOKEN | 空 | 可选 API 访问令牌 |
| DEFAULT_POLL_INTERVAL | 3 | 任务默认轮询间隔（秒） |
| BOOKING_OPEN_LEAD_MINUTES | 150 | 最早目标时段前多久启动任务 |
| MAX_RUNTIME_HOURS | 4 | 单次任务最长运行时间 |
| PUSHPLUS_TOKEN | 空 | 可选微信推送 |

`data/booking.db` 保存任务与预约记录，`venue_session.json` 保存登录会话，`logs/` 保存日志。账号密码仅在学校登录窗口中输入，程序不保存密码。工具只代下单，不绕过场馆系统校验。
