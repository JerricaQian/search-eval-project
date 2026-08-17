"""IMD 在线标注（插件 API 版）
通过 window.mg.createRectangle / createText 直接在设计文件中新增
半透明矩形 + 文字标签图层，完成商卡识别标注。

坐标换算：每个场景画板本身是一张 scale=1 导出的页面截图矩形，
故 像素坐标 == 画板局部坐标，绝对设计坐标 = 画板偏移(frame_x,frame_y) + 像素坐标。

只做「新增图层」，不修改/删除原设计稿内容（非破坏性）。
所有新建图层名带前缀 [ANNO] 便于识别与整体撤销。
"""
import json, subprocess, sys, time

CATDESK = 'catdesk'

def action(obj):
    cmd = json.dumps(obj, ensure_ascii=False)
    r = subprocess.run([CATDESK, 'browser-action', cmd], capture_output=True, text=True)
    out = r.stdout + r.stderr
    if 'Full output saved to:' in out:
        path = out.split('Full output saved to:')[1].strip().split('\n')[0].strip()
        with open(path) as f:
            out = f.read()
    return out

def evaluate(script):
    out = action({"action": "evaluate", "script": script})
    try:
        return json.loads(out).get('data', {}).get('result')
    except Exception:
        return out

def hex_to_rgb01(h):
    h = h.lstrip('#')
    return round(int(h[0:2],16)/255,4), round(int(h[2:4],16)/255,4), round(int(h[4:6],16)/255,4)

# 配色（第六章 IMD 在线标注配色表 + 图筛/异构/侧边栏补充）
COLORS = {
    "状态栏":            ("C8D2DC", 20),
    "顶部导航搜索框":     ("6495ED", 22),
    "场次日期Tab":        ("40E0D0", 22),   # 日期/场次选择横滑条；须在「Tab」前，因"场次日期Tab"含"Tab"子串
    "Tab":              ("7B68EE", 22),
    "图筛":              ("DAA520", 20),   # 借用营销/异构金色系，区别于纯文字筛选器
    "快筛排序筛选器":     ("9370DB", 22),
    "营销横幅":          ("DAA520", 22),
    "品牌秀异构卡":       ("DAA520", 18),   # 列中异构卡，整体一个矩形
    "侧边栏":            ("787878", 40),
    "border":           ("787878", 80),
    "运营聚合卡":         ("DAA520", 18),   # 顶部并排聚合/榜单模块（异构）
    "头图区":            ("ADD8E6", 25),
    "副标题区":          ("B0C4DE", 22),   # 商品卡片 region③（标题下、价格上），灰色字为主；须在「标题区」前，因"副标题区"含"标题区"子串
    "标题区":            ("87CEFA", 24),
    "评分区":            ("F08080", 22),   # 评分/想看（房型卡底部评分+酒店名）
    "评分与推荐理由":      ("F08080", 22),   # 酒店商家卡 region③ 顶部（与评分区同色）
    "基础信息区":         ("DDA0DD", 24),
    "商家信息区":         ("DDA0DD", 24),   # 商家卡片官方名（文字/图文下挂 region③），与基础信息区同色
    "套餐概要":          ("DDA0DD", 24),   # 度假/酒店套餐卡 region③，信息行等价
    "演出信息区":         ("DDA0DD", 24),   # 演出卡 region④（日期/场次/场馆/地址），信息行等价
    "日期区":            ("40E0D0", 22),   # 演出日期行
    "标签区":            ("FFDAB9", 25),
    "AI推荐理由":        ("D8BFD8", 22),   # 商家卡-文字下挂 region⑤
    "价格区":            ("FF8C69", 24),   # 价格/销量
    "价格标签":          ("FF8C69", 24),   # 酒店卡 region⑥，与价格区同色
    "坑位":             ("CD5C5C", 28),   # 头图角标/标题后坑位（左上/右上/底部/标题后），可选子区
    "下挂区图文下挂":      ("98FB98", 22),
    "图文下挂区":         ("98FB98", 22),   # label 写法兼容（如 商卡_图文下挂区）
    "文字下挂区":         ("FFEC8B", 25),   # 纯文字型下挂（神券/满减券后价等），务必先于「标签区」匹配
    "下挂区文字下挂":      ("FFEC8B", 25),
    "相似推荐提示":       ("FFDAB9", 20),
}

def color_for(label):
    for key, val in COLORS.items():
        if key in label:
            return val
    return ("CCCCCC", 20)

def create_rect(abs_x, abs_y, w, h, hex_color, opacity_pct, name, is_border=False):
    r, g, b = hex_to_rgb01(hex_color)
    a = round(opacity_pct/100, 3)
    if is_border:
        # 描边：透明填充 + 深灰边框
        script = (
          "(() => { try { const n = window.mg.createRectangle(); "
          "n.x=%s; n.y=%s; n.width=%s; n.height=%s; "
          "n.name='[ANNO] %s'; "
          "n.fills=[]; "
          "n.strokes=[{type:'SOLID', color:{r:%s,g:%s,b:%s,a:1}, alpha:1, isVisible:true, blendMode:'PASS_THROUGH'}]; "
          "n.strokeWeight=4; "
          "return n.id; } catch(e){ return 'err:'+e.message; } })()"
        ) % (abs_x, abs_y, w, h, name, r, g, b)
    else:
        script = (
          "(() => { try { const n = window.mg.createRectangle(); "
          "n.x=%s; n.y=%s; n.width=%s; n.height=%s; "
          "n.name='[ANNO] %s'; "
          "n.fills=[{type:'SOLID', color:{r:%s,g:%s,b:%s,a:%s}, alpha:%s, isVisible:true, blendMode:'PASS_THROUGH'}]; "
          "return n.id; } catch(e){ return 'err:'+e.message; } })()"
        ) % (abs_x, abs_y, w, h, name, r, g, b, a, a)
    return evaluate(script)

def create_label(text, abs_x, abs_y, size=26):
    script = (
      "(() => { try { const t = window.mg.createText(); "
      "t.characters=%s; t.x=%s; t.y=%s; "
      "if(t.setRangeFontSize) t.setRangeFontSize(0, t.characters.length, %s); "
      "t.name='[ANNO-TXT] '+%s; "
      "t.fills=[{type:'SOLID', color:{r:0.85,g:0.1,b:0.1,a:1}, alpha:1, isVisible:true, blendMode:'PASS_THROUGH'}]; "
      "return t.id; } catch(e){ return 'err:'+e.message; } })()"
    ) % (json.dumps(text, ensure_ascii=False), abs_x, abs_y, size, json.dumps(text, ensure_ascii=False))
    return evaluate(script)

def run_scene(frame_x, frame_y, tasks, label_prefix):
    """tasks: list of dict {label, x, y, w, h, kind}
       kind: 'macro' | 'border' | 'part' | 'sidebar' | 'hetero'
       坐标为像素坐标(scale=1)，直接加 frame 偏移。
    """
    created = []
    for i, t in enumerate(tasks):
        ax = frame_x + t['x']
        ay = frame_y + t['y']
        name = label_prefix + '_' + t['label']
        hexc, op = color_for(t['label'])
        is_border = t.get('kind') == 'border'
        rid = create_rect(ax, ay, t['w'], t['h'], hexc, op, name, is_border=is_border)
        # 文字标签放在矩形左上角内 +8px
        tid = create_label(t['label'], ax + 8, ay + 6, size=t.get('fs', 24))
        created.append({'label': name, 'rect': rid, 'txt': tid,
                        'x': ax, 'y': ay, 'w': t['w'], 'h': t['h'],
                        'hex': hexc, 'op': op, 'border': is_border})
        print(f"[{i+1}/{len(tasks)}] {name} -> rect={rid} txt={tid}", flush=True)
        time.sleep(0.05)
    return created
