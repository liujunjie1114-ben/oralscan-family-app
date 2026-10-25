# OralScan APP 功能实现方案（基于服务蓝图 PDF）

## 目标
在 Figma Make 中把设计稿变成"可实现功能"的动态 APP 原型：图片上传 → AI 诊断管线（模拟）→ 分层诊断 → 报告生成。

## 架构原则
- **AI 管线用模拟层**：检测框/热力图/诊断结果先用预设 JSON 数据（mock）驱动，Canvas 绘制在用户上传的图片上
- **数据结构按真实模型输出设计**，后端（YOLOv8）就绪后只替换数据来源，UI 不用改
- **双屏边界**：儿童 PAD 只显示提示/奖励/游戏，医疗结果只出现在家长手机端

## 核心数据结构（模拟模型输出）
```js
const mockDetection = {
  imageQuality: { brightness: 82, clarity: 91, coverage: "all-quadrants" },
  lesions: [
    { id: 1, fdi: 46, quadrant: 4, level: "L3",
      type: "caries", confidence: 0.87,
      bbox: { x: 412, y: 288, w: 96, h: 72 },   // 归一化 0-1 也可以
      severity: "moderate", recommendation: "Fill within 2 weeks" },
    { id: 2, fdi: 26, quadrant: 2, type: "calculus", confidence: 0.74,
      bbox: { x: 128, y: 310, w: 80, h: 60 }, severity: "mild" },
    { id: 3, fdi: 36, quadrant: 3, type: "plaque", confidence: 0.69,
      bbox: { x: 520, y: 350, w: 110, h: 64 }, severity: "mild" }
  ],
  heatmap: "attention_map_url_or_data",  // M4 可解释性
  report: { patient: "Emma · Age 9", date: "2026.10.25",
            riskLevel: "Low Risk", trend: "Improving",
            nextCheck: "12 days" }
}
```

## 页面清单（家长手机端，对应蓝图 6 阶段）
1. **Pair Device** — 设备配对：蓝牙搜索动画、连接状态、电量显示
2. **Prepare Child** — 姿势引导图示 + "Start Scan" 启动
3. **Live Screening** — 实时扫描：调取摄像头/相册上传图片 → 质量检测（亮度/清晰度评分条）→ 8 分区进度环 → 重扫提示
4. **Analyzing**（上传后）— 上传与 AI 分析进度：逐模块显示 M1→M5 处理动画
5. **Summary** — 风险等级卡 + 病灶数统计 + 趋势（Improving）
6. **Report** — 完整报告：原图 + Canvas 检测框叠加（FDI 标注）+ 热力图层切换 + 逐病灶卡片（类型/置信度/建议）+ 预约看诊按钮

## 儿童 PAD 端（独立页面组）
Mission Start（游戏化开场）→ Scan-synced View（牙弓图高亮当前扫描区）→ Hold Still 引导（倒计时）→ Mission Complete（奖励贴纸）。**不显示任何诊断结果。**

---

## Figma Make 提示词（按阶段粘贴）

### Prompt 1 — 图片上传 + 质量检测（Live Screening 功能化）
```text
Make the "Live Screening" screen functional:
1. Add an image upload feature: user can take a photo or pick from album; show the uploaded image in the screening view with the tooth-arch overlay guide.
2. Simulate image quality assessment on upload: animate progress rings for Brightness, Clarity, and Coverage (use values 80-95%). If brightness < 70 show a "Too dark, retake" prompt with a Retake button.
3. After quality check passes, show a "Zone Progress" ring filling across 8 mouth zones with playful micro-animations, then auto-navigate to the Analyzing screen after 2 seconds.
```

### Prompt 2 — AI 分析动画（M1→M5 管线可视化）
```text
Create an "Analyzing" screen that visualizes the 5-module AI pipeline as a vertical stepper with progress animations:
Module 1 Preprocessing (White balance / CLAHE / Brightness), Module 2 Lesion Detection (show the uploaded image with a scanning line animation), Module 3 Hierarchical Reasoning (Quadrant → Tooth ID (FDI) → Condition, animate through 3 levels), Module 4 Explainability (fade in a semi-transparent teal-red heatmap overlay on the image), Module 5 Report Generation.
Each step takes ~1.5s with a checkmark when done, then navigate to the Summary screen. Use mock data only — no backend.
```

### Prompt 3 — 诊断结果 + 检测框叠加（核心功能）
```text
Build the Report screen with a real functional overlay:
1. Render the uploaded photo on a <canvas> and draw detection boxes from this mock data: [{fdi:46,type:"caries",conf:87,bbox:{x:41,y:38,w:10,h:8}},{fdi:26,type:"calculus",conf:74,bbox:{x:12,y:40,w:8,h:6}},{fdi:36,type:"plaque",conf:69,bbox:{x:52,y:45,w:11,h:6}}] — coordinates are percentages of image size.
2. Color-code boxes: caries red, calculus orange, plaque teal, crack purple. Label each box with the FDI number and type. Clicking a box highlights the matching lesion card in the list below, and vice versa.
3. Add a "Heatmap" toggle that fades an attention-map overlay (radial teal→red gradient) over the boxes.
4. Show the hierarchical diagnosis path for each lesion: Level 1 Quadrant → Level 2 Tooth ID (FDI) → Level 3 Condition, with confidence bars.
5. End with risk level badge, "Book a Consultation" button, and Share/Export PDF buttons.
```

### Prompt 4 — 儿童 PAD 联动（双屏体验）
```text
Create the Child PAD companion screens as a separate tablet-size view (landscape, 1024x768): 01 Mission Start (tap to begin), 02 Scan-synced PAD View (cute tooth-arch map that highlights the currently scanned zone in sync with the parent app state), 03 Hold Still Guidance (2-second countdown with mascot, shows "keep still" when scanner moves), 04 Mission Complete (stars + sticker rewards).
Important: PAD shows ONLY prompts, games and rewards — never show diagnosis results or medical data on the PAD. Add a shared state object so the PAD zone highlight follows the parent screening progress.
```

### Prompt 5 — 数据接入预留（对接真实模型）
```text
Refactor all mock diagnosis data into a single `window.OralScanAPI` object with methods: uploadImage(), analyze(image) -> Promise<detectionResult>, getReport(). Keep the canvas rendering and UI driven entirely by this API's return values, so a real YOLOv8 backend can be plugged in later without changing the UI code. Add a visible "Demo Mode" badge while mock data is in use.
```

## 后续对接真实模型（毕业设计主线）
- 前端只认 `OralScanAPI.analyze()` 的返回结构（上面 mockDetection 的 schema）
- 后端 YOLOv8 推理服务按同一 schema 返回 JSON： lesions[]（fdi/type/confidence/bbox/severity）+ heatmap
- bbox 建议统一归一化 0-1 坐标，前端按图片实际尺寸换算
