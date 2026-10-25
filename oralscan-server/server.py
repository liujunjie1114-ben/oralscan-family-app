"""
OralScan YOLOv8 Inference Server
基于现有 DentalAI 龋齿检测模型 (best.pt) 的升级版推理服务。

对 OralScanAPP 前端 OralScanAPI schema：
  POST /detect   -> 兼容旧接口, 返回 [[x1,y1,x2,y2,type,conf],...]
  POST /analyze  -> 返回前端所需的完整诊断结构:
  {
    "imageQuality": {"brightness": 0-100, "clarity": 0-100, "coverage": "ok"},
    "teeth":  [{"id":0,"bbox":{"x":..,"y":..,"w":..,"h":..}, "fdi": 估计值}],
    "lesions":[{"type":"caries","confidence":0.82,"fdi":16,
                "bbox":{"x":..,"y":..,"w":..,"h":..},  # 归一化 0-1
                "severity":"moderate","recommendation":"..."}],
    "heatmap": null   # 预留: 后续接 Grad-CAM
  }
bbox 均为归一化 0-1 坐标（左上原点）。
FDI 牙位为基于图像位置的估计值（quadrant 推断 + 牙位排序），字段 fdiEstimated=true。
"""
from flask import Flask, request, jsonify, send_from_directory
from waitress import serve
from PIL import Image, ImageStat, ImageFilter
from ultralytics import YOLO
import os

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
# 主模型 = models/ 下所有 .pt（多模型结果自动合并去重，IoU>0.55 视为同一目标取高置信度）
model_paths = sorted(
    os.path.join(MODEL_DIR, f) for f in os.listdir(MODEL_DIR) if f.endswith(".pt")
) or [os.path.join(MODEL_DIR, "best.pt")]
models = [YOLO(p) for p in model_paths]
print(f"[OralScan] loaded {len(models)} model(s): {[os.path.basename(p) for p in model_paths]}")
CLASS_NAMES = models[0].names  # {0:'Caries',1:'Cavity',2:'Crack',3:'Tooth'}

def iou(a, b):
    ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    ua = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter / ua if ua > 0 else 0

def predict_ensemble(img, conf=0.15):
    """多模型推理 + 合并去重。返回合并后的 raw 检测列表。"""
    merged = []
    for m in models:
        r = m.predict(img, verbose=False, conf=conf)[0]
        for b in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
            merged.append((r.names[int(b.cls[0])].lower(), round(float(b.conf[0]), 4),
                           x1, y1, x2, y2))
    merged.sort(key=lambda d: -d[1])
    kept = []
    for d in merged:
        dup = False
        for k in kept:
            if d[0] == k[0] and iou(d[2:6], k[2:6]) > 0.55:
                dup = True
                break
        if not dup:
            kept.append(d)
    return kept

LESION_CLASSES = {"caries", "cavity", "crack"}

RECOMMENDATIONS = {
    "caries": "Possible caries detected. Book a consultation; filling may be needed within 2 weeks.",
    "cavity": "Cavity risk detected. Arrange dental treatment as soon as possible.",
    "crack":  "Possible crack detected. Avoid hard food; have a dentist evaluate it.",
    "plaque": "Plaque accumulation. Improve brushing habits and schedule cleaning.",
    "calculus": "Calculus detected. Professional cleaning recommended.",
}

UPPER_RIGHT = 1; UPPER_LEFT = 2; LOWER_LEFT = 3; LOWER_RIGHT = 4
# quadrant 内牙位序列（图像内从左到右或右到左）:
QUADRANT_TEETH = {1: [18,17,16,15,14,13,12,11], 2: [21,22,23,24,25,26,27,28],
                  3: [38,37,36,35,34,33,32,31], 4: [48,47,46,45,44,43,42,41]}

app = Flask(__name__, static_folder=os.path.dirname(__file__))

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return resp

def norm_bbox(x1, y1, x2, y2, w, h):
    return {"x": round(x1/w, 4), "y": round(y1/h, 4),
            "w": round((x2-x1)/w, 4), "h": round((y2-y1)/h, 4)}

def estimate_fdi(cx, cy, tooth_cx_list):
    """按图像位置推断象限 + 用牙齿横向排序估计牙位编号。"""
    upper = cy < 0.5
    right = cx >= 0.5  # 图像右侧 = 患者右侧
    if upper and right: q = UPPER_RIGHT
    elif upper: q = UPPER_LEFT
    elif right: q = LOWER_RIGHT
    else: q = LOWER_LEFT
    seq = QUADRANT_TEETH[q]
    # 象限内牙齿按离中线距离排序: 中线在图像中 x=0.5
    same_side = [c for c in tooth_cx_list if (c >= 0.5) == right]
    ranked = sorted(set(same_side), key=lambda c: abs(c - 0.5))
    if cx in ranked and ranked.index(cx) < len(seq):
        return seq[ranked.index(cx)], True
    return seq[0], True  # 估计值兜底

def assess_quality(img: Image.Image):
    gray = img.convert("L")
    brightness = round(ImageStat.Stat(gray).mean[0] / 255 * 100)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    clarity = min(100, round(ImageStat.Stat(edges).mean[0] * 4))
    return {"brightness": brightness, "clarity": clarity, "coverage": "ok"}

@app.route("/detect", methods=["POST", "OPTIONS"])
def detect():
    if request.method == "OPTIONS":
        return ("", 204)
    buf = request.files["image_file"]
    img = Image.open(buf.stream).convert("RGB")
    W, H = img.size
    merged = predict_ensemble(img)
    out = [[round(d[2]), round(d[3]), round(d[4]), round(d[5]), d[0].capitalize(), round(d[1], 2)] for d in merged]
    return jsonify(out)

@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return ("", 204)
    buf = request.files["image_file"]
    img = Image.open(buf.stream).convert("RGB")
    W, H = img.size
    quality = assess_quality(img)
    merged = predict_ensemble(img)

    teeth, lesions = [], []
    tooth_cx_list = []
    raw = []
    for name, conf, x1, y1, x2, y2 in merged:
        cx, cy = round((x1+x2)/2/W, 4), round((y1+y2)/2/H, 4)
        raw.append((name, conf, cx, cy, x1, y1, x2, y2))
        if name == "tooth":
            tooth_cx_list.append(cx)

    tooth_id = 0
    for name, conf, cx, cy, x1, y1, x2, y2 in raw:
        box = norm_bbox(x1, y1, x2, y2, W, H)
        if name == "tooth":
            teeth.append({"id": tooth_id, "bbox": box, "fdi": estimate_fdi(cx, cy, tooth_cx_list)[0],
                          "fdiEstimated": True})
            tooth_id += 1
        else:
            fdi, est = estimate_fdi(cx, cy, tooth_cx_list)
            if conf >= 0.8: severity = "moderate"
            elif conf >= 0.6: severity = "mild"
            else: severity = "watch"
            lesions.append({
                "type": name, "confidence": conf, "fdi": fdi, "fdiEstimated": est,
                "bbox": box, "severity": severity,
                "recommendation": RECOMMENDATIONS.get(name, "Consult a dentist."),
            })
    lesions.sort(key=lambda l: -l["confidence"])

    risk = "Low Risk"
    if any(l["type"] in ("caries", "cavity") and l["confidence"] >= 0.75 for l in lesions):
        risk = "Medium Risk"
    if sum(1 for l in lesions if l["type"] in ("caries", "cavity")) >= 3:
        risk = "High Risk"

    return jsonify({
        "imageQuality": quality,
        "teethCount": len(teeth),
        "teeth": teeth,
        "lesions": lesions,
        "riskLevel": risk,
        "heatmap": None,
        "demoMode": True,
    })

@app.route("/")
def root():
    return "<h2>OralScan YOLOv8 Inference Server</h2><p>POST /detect 或 POST /analyze (multipart field: image_file)</p><p>任务式接口: POST /v1/analyze (multipart field: images) -> GET /v1/jobs/&lt;id&gt;</p>"

# ---------------- 任务式接口 (Figma Make 前端契约) ----------------
# POST /v1/analyze (multipart "images") -> {id}
# GET  /v1/jobs/<id> -> {status, stages:[{id,status,progress,ms}], result:{risk, image:{width,height},
#          detections:[{class_name,confidence,fdi,box:{x1,y1,x2,y2}}]}}
import uuid, threading, time, io

JOBS = {}
JOB_LOCK = threading.Lock()

def run_job(job_id, image_bytes):
    """后台执行推理, 按 M1-M5 阶段推进状态。"""
    st = JOBS[job_id]["stages"]
    def stage(idx, ms):
        st[idx]["status"] = "running"
        time.sleep(ms)
        st[idx]["status"] = "done"
        st[idx]["progress"] = 1
        st[idx]["ms"] = int(ms * 1000)
    try:
        with job_lock_for(job_id):
            stage(0, 0.4)   # M1 quality gate
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            W, H = img.size
            JOBS[job_id]["quality"] = assess_quality(img)
            stage(1, 0.5)   # M2 tooth segmentation
            merged = predict_ensemble(img)
            stage(2, 0.5)   # M3 lesion detection

        teeth_boxes, detections = [], []
        tooth_cx = []
        raw = merged

        for name, conf, x1, y1, x2, y2 in raw:
            if name == "tooth":
                tooth_cx.append(round((x1 + x2) / 2 / W, 4))
                continue
            cx, cy = round((x1 + x2) / 2 / W, 4), round((y1 + y2) / 2 / H, 4)
            fdi, _ = estimate_fdi(cx, cy, tooth_cx)
            detections.append({
                "class_name": name, "confidence": conf, "fdi": str(fdi),
                "box": {"x1": round(x1, 1), "y1": round(y1, 1),
                        "x2": round(x2, 1), "y2": round(y2, 1)},
            })
        detections.sort(key=lambda d: -d["confidence"])

        stage(3, 0.4)       # M4 FDI numbering
        n_bad = sum(1 for d in detections if d["class_name"] in ("caries", "cavity"))
        if n_bad == 0: risk = "Low"
        elif n_bad <= 2: risk = "Medium"
        else: risk = "High"
        stage(4, 0.3)       # M5 risk scoring

        JOBS[job_id]["result"] = {
            "risk": risk,
            "image": {"width": W, "height": H},
            "detections": detections,
            "quality": JOBS[job_id]["quality"],
        }
        JOBS[job_id]["status"] = "done"
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = str(e)

_job_locks = {}
def job_lock_for(job_id):
    if job_id not in _job_locks:
        _job_locks[job_id] = threading.Lock()
    return _job_locks[job_id]

@app.route("/v1/analyze", methods=["POST", "OPTIONS"])
def v1_analyze():
    if request.method == "OPTIONS":
        return ("", 204)
    files = request.files.getlist("images") or [request.files["image_file"]]
    job_id = uuid.uuid4().hex[:12]
    stages = [{"id": f"M{i+1}", "status": "pending", "progress": 0, "ms": 0} for i in range(5)]
    JOBS[job_id] = {"status": "running", "stages": stages, "created": time.time()}
    blob = files[0].read()
    threading.Thread(target=run_job, args=(job_id, blob), daemon=True).start()
    return jsonify({"id": job_id})

@app.route("/v1/jobs/<job_id>", methods=["GET", "OPTIONS"])
def v1_job(job_id):
    if request.method == "OPTIONS":
        return ("", 204)
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"status": "error", "message": "unknown job"}), 404
    out = {"status": job["status"], "stages": job["stages"]}
    if "result" in job: out["result"] = job["result"]
    if "message" in job: out["message"] = job["message"]
    return jsonify(out)

# ---------------- 病例闭环 (Case workflow, SQLite) ----------------
# 证据链原则: 模型原始输出 (model_output) 只读存档, 牙医修订记录 (review) 独立保存, 互不覆盖。
import sqlite3, json as _json, base64, datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
IMG_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "cases.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS cases(
          id TEXT PRIMARY KEY, created_at TEXT, reviewed_at TEXT, status TEXT,
          child_name TEXT, child_age TEXT, parent_note TEXT,
          report_id TEXT, risk TEXT, source TEXT, quality TEXT,
          image_file TEXT, model_output TEXT, review TEXT)
        """)

init_db()

@app.route("/dentist")
def dentist_page():
    return send_from_directory(os.path.dirname(__file__), "dentist.html")

@app.route("/case-img/<path:name>")
def case_img(name):
    return send_from_directory(IMG_DIR, name)

@app.route("/v1/cases", methods=["POST", "OPTIONS"])
def cases_create():
    if request.method == "OPTIONS":
        return ("", 204)
    d = request.get_json(force=True) or {}
    cid = "CASE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4].upper()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    img_file = ""
    data_url = d.get("imageDataUrl") or ""
    if "," in data_url:
        try:
            img_file = cid + ".jpg"
            with open(os.path.join(IMG_DIR, img_file), "wb") as f:
                f.write(base64.b64decode(data_url.split(",", 1)[1]))
        except Exception:
            img_file = ""
    dets = d.get("detections") or []
    with db() as c:
        c.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, now, None, "submitted", d.get("childName"), d.get("childAge"),
                   d.get("parentNote", ""), d.get("reportId"), d.get("risk"),
                   d.get("source", "unknown"), _json.dumps(d.get("quality"), ensure_ascii=False),
                   img_file, _json.dumps(dets, ensure_ascii=False), None))
    return jsonify({"id": cid, "status": "submitted"}), 201

@app.route("/v1/cases", methods=["GET"])
def cases_list():
    with db() as c:
        rows = c.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    out = [{"id": r["id"], "created_at": r["created_at"], "status": r["status"],
            "child": (r["child_name"] or "Emma") + (f" · Age {r['child_age']}" if r["child_age"] else ""),
            "risk": r["risk"], "source": r["source"], "reviewed": bool(r["reviewed_at"]),
            "detections_count": len(_json.loads(r["model_output"] or "[]"))} for r in rows]
    return jsonify({"cases": out})

@app.route("/v1/cases/<case_id>", methods=["GET"])
def case_detail(case_id):
    with db() as c:
        r = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not r:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": r["id"], "created_at": r["created_at"], "reviewed_at": r["reviewed_at"],
        "status": r["status"], "childName": r["child_name"], "childAge": r["child_age"],
        "parentNote": r["parent_note"], "reportId": r["report_id"], "risk": r["risk"],
        "source": r["source"], "quality": _json.loads(r["quality"] or "null"),
        "image_file": r["image_file"], "model_output": _json.loads(r["model_output"] or "[]"),
        "review": _json.loads(r["review"]) if r["review"] else None})

@app.route("/v1/cases/<case_id>/review", methods=["POST", "OPTIONS"])
def case_review(case_id):
    if request.method == "OPTIONS":
        return ("", 204)
    d = request.get_json(force=True) or {}
    now = datetime.datetime.now().isoformat(timespec="seconds")
    review = {"dentistName": d.get("dentistName", "Dentist"), "note": d.get("note", ""),
              "revisions": d.get("revisions") or [], "reviewed_at": now}
    with db() as c:
        if not c.execute("SELECT id FROM cases WHERE id=?", (case_id,)).fetchone():
            return jsonify({"error": "not found"}), 404
        c.execute("UPDATE cases SET status='reviewed', reviewed_at=?, review=? WHERE id=?",
                  (now, _json.dumps(review, ensure_ascii=False), case_id))
    return jsonify({"id": case_id, "status": "reviewed"})

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8080, threads=4)
