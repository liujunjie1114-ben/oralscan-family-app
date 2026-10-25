"""
OralScan 扩展模型训练
- 基础权重: oralscan-server/models/best.pt (DentalAI: Caries/Cavity/Crack/Tooth, 迁移学习)
- 训练数据: Kaggle 口腔疾病 23k (Calculus/Caries/Gingivitis/Hypodontia/Discoloration/Ulcer)
- 产出: models/oral-extended/weights/best.pt -> 复制到 oralscan-server/models/ 即自动并入推理服务
用法: python train_oral.py [epochs]
"""
import os, sys, yaml
from ultralytics import YOLO

HERE = os.path.dirname(__file__)
BASE_WEIGHTS = os.path.join(HERE, "..", "oralscan-server", "models", "best.pt")
DATA_ROOT = os.path.join(HERE, "datasets", "oral-disease-23k")

def find_data_yaml(root):
    for root_, dirs, files in os.walk(root):
        for f in files:
            if f == "data.yaml":
                return os.path.join(root_, f)
    return None

def main():
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    data_yaml = find_data_yaml(DATA_ROOT)
    if not data_yaml:
        print("ERROR: data.yaml not found under", DATA_ROOT)
        print("先运行 prepare_dataset.py 下载数据集")
        sys.exit(1)
    # 校验/修正 data.yaml 的路径
    with open(data_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    print("original data.yaml:", cfg)
    base = os.path.dirname(data_yaml)
    for k in ("train", "val", "test"):
        if k in cfg and isinstance(cfg[k], str) and not os.path.isabs(cfg[k]):
            p = os.path.join(base, cfg[k])
            if os.path.exists(p):
                cfg[k] = p.replace("\\", "/")
    cfg["path"] = ""
    fixed = os.path.join(HERE, "data_fixed.yaml")
    with open(fixed, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)
    print("fixed data.yaml ->", fixed)

    model = YOLO(BASE_WEIGHTS)
    results = model.train(
        data=fixed,
        epochs=epochs,
        imgsz=640,
        batch=16,
        device=0,            # RTX 4060
        project=os.path.join(HERE, "runs"),
        name="oral-extended",
        patience=15,
        workers=4,
        plots=True,
    )
    best = os.path.join(results.save_dir, "weights", "best.pt")
    print("\n=== TRAINING DONE ===")
    print("best weights:", best)
    print("复制到 oralscan-server/models/ 后重启服务即自动生效:")
    print(f'  copy "{best}" "..\\oralscan-server\\models\\oral-extended.pt"')

if __name__ == "__main__":
    main()
