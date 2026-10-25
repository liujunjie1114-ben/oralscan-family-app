# OralScan YOLOv8 推理服务

来源：`D:\.ps\` 现成 DentalAI 龋齿检测项目（模型 4 类：Caries / Cavity / Crack / Tooth），
已升级为符合 OralScanAPP 前端 `OralScanAPI` schema 的推理服务。

## 启动

```bash
cd oralscan-server
python server.py
# 服务地址: http://localhost:8080
```

## 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/analyze` | POST multipart `image_file` | 前端主接口：返回 imageQuality / teeth[] / lesions[] / riskLevel（bbox 归一化 0-1，FDI 为位置估计值 `fdiEstimated: true`） |
| `/detect` | POST multipart `image_file` | 兼容旧接口，返回 `[[x1,y1,x2,y2,type,conf],...]` |

测试：`curl -F "image_file=@caries.jpg" http://localhost:8080/analyze`

## 与前端对接

Figma Make 导出代码中，把 `OralScanAPI.analyze()` 实现为：

```js
async function analyze(file) {
  const fd = new FormData();
  fd.append("image_file", file);
  const r = await fetch("http://localhost:8080/analyze", { method: "POST", body: fd });
  return r.json();
}
```

## 已知边界

- 模型只有 4 类（无 plaque/calculus），后两类等扩展训练后自动生效（server.py 已写好 recommendation 映射）
- FDI 是基于图像位置的估计（象限推断 + 中线距离排序），后续可通过牙齿分割模型精确化
- heatmap 预留字段，待接 Grad-CAM
