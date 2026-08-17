"""
逐卡分区扫描审计工具——支撑「禁止跨卡复用坐标，必须逐卡独立标定」。

给定一张整页截图和某张商卡的大致 y 范围，自动扫描出该卡：
  - 左侧头图区的真实 y 起止 + 左右缘 x
  - 右侧信息区每一行文字的真实 y 起止 + 文字左右缘 x
  - （可选）下挂区全宽文字行

据此填 annotate_image 的 tasks，而不是把第一张卡的坐标平移复用到后续卡。

用法：
    python3 scan_card_regions.py <图片> <卡y0> <卡y1> [信息区x0=385] [信息区x1=1200]
例：
    python3 scan_card_regions.py 迪士尼_全部_1.png 1150 1710
"""
import sys
import numpy as np
from PIL import Image


def load(path):
    return np.array(Image.open(path).convert("RGB"))


def head_image_span(img, y0, y1, x0=10, x1=410, thr=244, ratio=0.6):
    """头图真实矩形边界。头图是一整块照片，四周是白色卡片背景。
    用「整行/整列中图片像素(非近白)占比 >= ratio」来判定图片主体，
    避免把头图右侧白边、投影、旁侧文字误算进头图导致框偏大。
    （严格阈值：曾因用宽松的 >0.5 单像素判定把商卡2头图框宽 65px。）
    """
    sub = img[y0:y1, x0:x1]
    m = (sub.min(axis=2) < thr)
    rr = m.mean(axis=1)
    cc = m.mean(axis=0)
    ys = np.where(rr > ratio)[0]
    xs = np.where(cc > ratio)[0]
    if not len(ys) or not len(xs):
        return None
    yt, yb = int(y0 + ys[0]), int(y0 + ys[-1])
    xl, xr = int(x0 + xs[0]), int(x0 + xs[-1])
    return {"y": (yt, yb), "x": (xl, xr), "h": yb - yt, "w": xr - xl}


def text_rows(img, y0, y1, x0, x1, thr=120, min_ink=0.008, minh=8):
    """在 [y0,y1)×[x0,x1) 内找文字行，返回每行 y 起止 + 文字实际左右缘 x。"""
    rows = []
    run = None
    for y in range(y0, y1):
        band = img[y, x0:x1]
        on = (band.min(axis=1) < thr).mean() > min_ink
        if on:
            if run is None:
                run = y
        else:
            if run is not None:
                rows.append((run, y - 1))
            run = None
    if run is not None:
        rows.append((run, y1 - 1))
    out = []
    for (a, b) in rows:
        if b - a < minh:
            continue
        sub = img[a:b + 1, x0:x1]
        colink = (sub.min(axis=2) < thr).mean(axis=0)
        xs = np.where(colink > 0.02)[0]
        xspan = (int(x0 + xs[0]), int(x0 + xs[-1])) if len(xs) else (x0, x1)
        out.append({"y": (a, b), "h": b - a, "x": xspan, "w": xspan[1] - xspan[0]})
    return out


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    cy0, cy1 = int(sys.argv[2]), int(sys.argv[3])
    ix0 = int(sys.argv[4]) if len(sys.argv) > 4 else 385
    ix1 = int(sys.argv[5]) if len(sys.argv) > 5 else 1200
    img = load(path)

    print(f"# 卡片 y[{cy0},{cy1}] 逐区实测（据此逐卡填 tasks，勿复用其他卡坐标）")
    head = head_image_span(img, cy0, cy1)
    print("头图区:", head)
    print("信息区文字行（右侧）:")
    for r in text_rows(img, cy0, cy1, ix0, ix1):
        print("  ", r)
    print("下挂区候选（全宽 x60..1200）:")
    for r in text_rows(img, cy0, cy1, 60, 1200):
        # 只提示明显位于头图下方的行
        print("  ", r)


if __name__ == "__main__":
    main()
