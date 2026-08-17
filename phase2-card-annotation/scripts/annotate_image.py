"""
本地图片标注库（PNG/JPG）——与 IMD 在线标注共用同一套识别规则与配色表。

用途：对本地整页截图（搜索结果页/信息页）直接绘制「宏观组件 + 商卡内部分区」两级
半透明矩形 + 红色文字标签，产出一张标注 PNG。无需浏览器/IMD，纯 Pillow 实现。

与 imd_annotate_api.py 的区别：
- IMD 版通过 window.mg 插件 API 在设计文件里新增图层（坐标 = 画板偏移 + 像素坐标）。
- 本地版直接在图片像素上绘制（坐标就是像素坐标，无偏移）。
- 两者配色表 COLORS 完全一致，任务表 tasks 结构 {label,x,y,w,h,kind} 也一致，可互相复用。

用法：
    from annotate_image import annotate_image
    annotate_image("in.png", "out.png", tasks)   # tasks: [{label,x,y,w,h,kind}, ...]
"""
import os
from PIL import Image, ImageDraw, ImageFont

# ---- 配色表：与 imd_annotate_api.py 的 COLORS 保持一致（HEX, 透明度%）----
COLORS = {
    "状态栏":            ("C8D2DC", 20),
    "顶部导航搜索框":     ("6495ED", 22),
    "Tab":              ("7B68EE", 22),
    "图筛":              ("DAA520", 20),
    "快筛排序筛选器":     ("9370DB", 22),
    "营销横幅":          ("DAA520", 22),
    "品牌秀异构卡":       ("DAA520", 18),
    "运营聚合卡":         ("DAA520", 18),
    "场次日期Tab":       ("40E0D0", 22),
    "日期区":            ("40E0D0", 22),
    "侧边栏":            ("787878", 40),
    "头图区":            ("ADD8E6", 25),
    "副标题区":          ("B0C4DE", 22),
    "标题区":            ("87CEFA", 24),
    "评分区":            ("F08080", 22),
    "基础信息区":         ("DDA0DD", 24),
    "商家信息区":         ("DDA0DD", 24),   # 商家卡片官方命名，与基础信息区同色
    "套餐概要":          ("DDA0DD", 24),   # 度假/酒店套餐卡 region③
    "演出信息区":         ("DDA0DD", 24),   # 演出卡 region④
    "位置信息区":         ("DDA0DD", 22),   # 景点票务卡：距离+近区位
    "营业时间区":         ("DDA0DD", 22),   # 景点票务卡：开园时间
    "标签区":            ("FFDAB9", 25),
    "AI推荐理由":        ("D8BFD8", 22),
    "价格区":            ("FF8C69", 24),
    "下挂区图文下挂":      ("98FB98", 22),
    "图文下挂区":         ("98FB98", 22),
    "文字下挂区":         ("FFEC8B", 25),   # 纯文字型下挂，须先于「标签区」匹配
    "下挂区文字下挂":      ("FFEC8B", 25),
    "相似推荐提示":       ("FFDAB9", 20),
}
BORDER_COLOR = "787878"   # 商卡整体边界（描边）
TEXT_COLOR   = (220, 30, 30)   # 红色文字标签

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def color_for(label):
    for key, val in COLORS.items():
        if key in label:
            return val
    return ("CCCCCC", 20)

def _load_font(size):
    for p in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def annotate_image(in_path, out_path, tasks, label_size=22, border_weight=4):
    """在 in_path 上按 tasks 绘制标注，输出到 out_path。
    tasks 每项 {label, x, y, w, h, kind[, elementId]}，kind ∈ macro|border|part|hetero。
    elementId 仅用于 SceneSpec/元素清单与 Phase3 结果的内部追溯，绝不渲染到标注图；
    标注图始终只展示原有的宏观组件、商卡边界与卡内分区标签，避免页面被最小元素编号淹没。
    绘制顺序即叠放顺序：先大后小，文字标签统一最后画，保证浮在最上层。
    """
    base = Image.open(in_path).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(label_size)

    labels = []  # 收集文字标签，最后统一画
    for t in tasks:
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        box = [x, y, x + w, y + h]
        kind = t.get("kind", "part")
        label = t["label"]
        # elementId 仅保留在任务数据/元素清单中供 Phase3 精确追溯，不显示在页面标注上。
        if kind == "border":
            # 商卡整体边界：只描边，不填充
            rgb = hex_to_rgb(BORDER_COLOR)
            draw.rectangle(box, outline=rgb + (255,), width=border_weight)
        else:
            hex_color, op = color_for(label)
            rgb = hex_to_rgb(hex_color)
            alpha = int(round(op / 100 * 255))
            draw.rectangle(box, fill=rgb + (alpha,), outline=rgb + (255,), width=1)
        labels.append((label, x + 8, y + 6))

    # 文字标签（带浅色描边增强可读性）统一最后画
    for text, tx, ty in labels:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((tx + dx, ty + dy), text, font=font, fill=(255, 255, 255, 220))
        draw.text((tx, ty), text, font=font, fill=TEXT_COLOR + (255,))

    out = Image.alpha_composite(base, overlay).convert("RGB")
    out.save(out_path)
    return out_path
