"""
下载 Kaggle 口腔疾病检测数据集 (23,552 张, YOLO 格式)
类别: Calculus / Caries / Gingivitis / Hypodontia / Tooth Discoloration / Ulcer
许可: Apache 2.0
用法: python prepare_dataset.py
"""
import kagglehub, shutil, os, sys

DATASET = "faizan729/dental-cancer-and-abnormality-dataset"
DEST = os.path.join(os.path.dirname(__file__), "datasets")

def main():
    print("downloading via kagglehub (anonymous, public dataset)...")
    path = kagglehub.dataset_download(DATASET)
    print("downloaded to:", path)
    # 打印结构
    for root, dirs, files in os.walk(path):
        depth = root.replace(path, "").count(os.sep)
        if depth <= 2:
            print(" ", root.replace(path, "."), f"({len(files)} files)")
    if not os.path.exists(DEST):
        os.makedirs(DEST)
    link = os.path.join(DEST, "oral-disease-23k")
    if not os.path.exists(link):
        try:
            shutil.copytree(path, link)
        except Exception as e:
            print("copy failed, using original path:", e)
            link = path
    print("dataset ready at:", link)

if __name__ == "__main__":
    sys.exit(main())
