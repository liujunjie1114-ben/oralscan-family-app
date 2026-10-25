# OralScan 亲子口腔检查应用

**在线体验：https://liujunjie1114-ben.github.io/oralscan-family-app/**

根据「OralScan-完整项目包.zip」更新，包含家长端、儿童 Pad、YOLO 推理、病例提交、医生复核和训练脚本。

## 在线版与本地版

GitHub Pages 只托管静态网页，在线版默认演示分析，顶部显示 Demo Mode。真实推理、病例存储和医生复核需要 Python 服务；该服务尚未部署到公网。

本地 localhost 自动连接 http://localhost:8080。若已有 HTTPS 后端，可打开 `https://liujunjie1114-ben.github.io/oralscan-family-app/?api=https://你的后端域名`。远程服务需要自行配置访问控制后再开放。

## Windows 本地启动

安装 Python 3.12 后，在项目目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

脚本创建虚拟环境、安装依赖并启动后端与网页。首次安装模型依赖可能较慢。

手动运行（两个终端）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r oralscan-server/requirements.txt
.\.venv\Scripts\python.exe oralscan-server/server.py
```

```powershell
py -m http.server 8090 --bind 127.0.0.1 --directory docs
```

家长端：http://localhost:8090/ ，医生端：http://localhost:8080/dentist 。

## 目录

- `public/oralscan.html`：家长端与儿童 Pad，新增病例提交、记录与医生反馈。
- `docs/`：GitHub Pages 发布文件，图片直接存储。
- `src/`：React/Vite 容器，保留 Figma Make 项目结构。
- `oralscan-server/`：Flask/YOLO 推理与 SQLite 病例服务，`requirements.txt` 为依赖。
- `oralscan-server/models/best.pt`：完整包内的推理权重，通过 Git LFS 管理。克隆后运行 `git lfs pull`。
- `oralscan-train/`：数据准备与训练脚本；训练数据需另行下载。
- `oralscan-functional-plan.md`：原始功能方案，部分内容为早期规划。

病例数据库与上传影像在本地首次运行时生成，已排除提交。完整包中的历史病例数据库没有发布。

## 更新网站

修改 `public/oralscan.html` 后同步到 `docs/index.html`，静态资源同步到 `docs/assets/`，推送 main 后 GitHub Pages 自动发布。

当前权重类别以实际模型输出为准；FDI 牙位为位置估计，热力图为预留功能。在线演示不代表已连接真实模型或牙医。
