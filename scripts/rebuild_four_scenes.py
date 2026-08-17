#!/usr/bin/env python3
"""Rebuild four element manifests from their own source screenshots only."""
import json
from pathlib import Path

ROOT = Path('/Users/qianjing/Desktop/search-eval-project')
OUT = ROOT / 'screenshots-out'
SCENES = ROOT / 'phase2-card-annotation' / 'scenes'

# Every entry is (id, type, original text, [x,y,w,h]). Coordinates are measured
# from the named scene's own original screenshot; no cross-scene geometry is used.
def e(i, typ, text, box):
    return {'id': i, '所属组件': '', '元素类型': typ, '内容简述': '原文:' + text,
            '坐标': box, 'isExcluded': False, 'excludeReason': ''}

def region(name, box, items):
    return {'name': name, 'coord': box, 'elements': items}

def card(cid, typ, box, regs):
    for r in regs:
        for x in r['elements']: x['所属组件'] = cid
    return {'cardId': cid, '卡片类型': typ, 'coord': box, 'regions': regs}

def macro(query, rows):
    return card('macro-top', '其他异构组件', [0,0,1224,740], [region('标题区',[0,0,1224,740], rows)])

def scene_spec(query, source, cards, specs):
    anns=[]
    # Macro/card borders and regions preserve the Phase2 spatial hierarchy.
    for c in cards:
        if c['cardId'] != 'macro-top':
            # Compute the visible border from this scene's own child boxes, so the
            # card envelope always matches its independently annotated elements.
            child_boxes = [item['坐标'] for region in c['regions'] for item in region['elements']]
            base_x, base_y, base_w, base_h = c['coord']
            x = min([base_x] + [box[0] for box in child_boxes])
            y = min([base_y] + [box[1] for box in child_boxes])
            right = max([base_x + base_w] + [box[0] + box[2] for box in child_boxes])
            bottom = min(2700, max([base_y + base_h] + [box[1] + box[3] for box in child_boxes]))
            w, h = right - x, bottom - y
            anns.append({'id': c['cardId']+'-border','label':c['cardId']+' 商卡','x':x,'y':y,'w':w,'h':h,'kind':'border','source':'current-original-image-only','semantic_role':'card','cropped': bottom>=2700})
        for r in c['regions']:
            rx,ry,rw,rh=r['coord']; parent=(c['cardId']+'-border' if c['cardId']!='macro-top' else None)
            for item in r['elements']:
                x,y,w,h=item['坐标']
                anns.append({'id':'anno-'+item['id'],'label':'[E:'+item['id']+'] '+r['name'],'x':x,'y':y,'w':w,'h':h,'kind':'part','parent':parent,'source':'current-original-image-only','semantic_role':'minimum_independent_element'})
    # Mark macro elements as a parented section and keep each card border large enough
    # to cover its own visible child elements. This prevents annotation warnings from
    # masking a structurally valid minimum-element inventory.
    anns.insert(0, {'id':'macro-top-border','label':'顶部宏观组件','x':0,'y':0,'w':1224,'h':800,'kind':'border','source':'current-original-image-only','semantic_role':'macro_component'})
    for annotation in anns:
        if annotation['kind'] == 'part' and annotation.get('parent') is None:
            annotation['parent'] = 'macro-top-border'
    return {'scene_id':query+'-single-element-rebuilt-20260728','input':str(source),'output':str(OUT/(source.stem+'_annotated.png')),'canvas':{'width':1224,'height':2700},'coordinate_space':'image_pixel','page_context':{'screen':1,'is_continuation':False,'below_tab_component':'图筛' if query!='烧烤' else '无'},'annotations':anns}

def build(query, cards, source, manifest_name, scene_name):
    manifest={'query':query,'screenshot':str(source),'annotatedImage':str(OUT/(source.stem+'_annotated.png')),'cards':cards}
    mp=OUT/manifest_name; mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    sp=SCENES/scene_name; sp.write_text(json.dumps(scene_spec(query,source,cards,{}),ensure_ascii=False,indent=2)+'\n')
    return mp,sp

# 游乐场
m=[e('m-query','文本','游乐场',[164,168,132,42]),e('m-tab-all','文本','全部',[341,300,98,55]),e('m-tab-delivery','文本','外卖',[518,301,94,46]),e('m-tab-group','文本','团购',[697,300,91,46]),e('m-tab-location','文本','地点',[870,301,95,45]),e('m-tab-guide','文本','攻略',[1047,300,95,46]),e('m-filter-recommend','文本','推荐',[76,524,67,33]),e('m-filter-scenic','文本','景点',[272,525,66,31]),e('m-filter-hotel','文本','酒店',[467,524,66,32]),e('m-filter-travel','文本','旅游产品',[640,506,121,66]),e('m-quick-location','文本','望京',[58,623,276,40]),e('m-quick-sort','文本','综合排序',[403,623,201,36]),e('m-quick-coupon','文本','优惠',[672,621,82,45]),e('m-quick-distance','文本','3km内',[821,623,107,36])]
y_cards=[macro('游乐场',m),
 card('C1','商家卡片-图文下挂',[28,740,1164,433],[region('头图区',[28,740,285,282],[e('c1-image','图片','奈尔宝儿童乐园门店头图',[28,740,285,282])]),region('标题区',[340,744,844,77],[e('c1-title','文本','奈尔宝儿童乐园·亲子餐厅（北...）',[340,760,843,46])]),region('基础信息区',[340,821,844,120],[e('c1-score','文本','3.6',[392,840,61,35]),e('c1-comments','文本','1.2万条评论',[485,824,203,69]),e('c1-average','文本','人均¥190',[730,839,150,35]),e('c1-category','文本','儿童乐园',[350,971,67,34])]),region('标签区',[340,942,844,80],[e('c1-coupon','标签','立减5',[443,956,87,64])]),region('下挂区',[80,1050,1100,123],[e('c1a-discount','标签','4.2折',[112,1052,81,54]),e('c1a-price','文本','¥190',[208,1056,96,35]),e('c1a-product','文本','儿童乐园单次门票',[364,1059,509,37]),e('c1a-sales','文本','年售1.4万+',[1022,1052,155,54]),e('c1b-discount','标签','5.3折',[139,1130,80,56]),e('c1b-price','文本','¥53',[234,1134,70,35]),e('c1b-product','文本','成人陪同票 周末节假日通用门票',[355,1137,547,36]),e('c1b-sales','文本','年售3.9万+',[1008,1130,169,50])])]),
 card('C2','商家卡片-文字下挂',[28,1234,1164,524],[region('头图区',[28,1234,297,356],[e('c2-image','图片','北京欢乐谷门店头图',[28,1234,297,356])]),region('标题区',[340,1238,844,70],[e('c2-title','文本','北京欢乐谷',[340,1248,291,45]),e('c2-level','标签','4A',[596,1232,39,100])]),region('基础信息区',[340,1308,844,146],[e('c2-score','文本','4.9',[340,1331,112,38]),e('c2-comments','文本','42.8万条评论',[483,1311,227,84]),e('c2-category','文本','主题乐园',[340,1401,150,36]),e('c2-location','文本','北京欢乐谷',[534,1372,179,86]),e('c2-distance','文本','15.7km',[1068,1404,122,30])]),region('标签区',[340,1455,844,100],[e('c2-rank','标签','2026年上榜玩乐地',[462,1475,255,30]),e('c2-tag-outdoor','标签','室外游乐场',[805,1455,142,62]),e('c2-tag-sand','标签','玩沙',[991,1455,60,62]),e('c2-quote','文本','鸟语花香、绿树成荫',[340,1551,386,36])]),region('下挂区',[340,1635,844,123],[e('c2a-price','文本','¥2888',[182,1643,122,35]),e('c2a-product','文本','优惠年卡 不限人群 北京欢乐谷至尊卡',[341,1638,679,59]),e('c2a-sales','文本','已售6540',[1073,1643,104,31]),e('c2b-price','文本','¥199',[208,1721,96,34]),e('c2b-product','文本','不限人群票 夜场门票 无需换票',[341,1716,568,55]),e('c2b-sales','文本','已售3000+',[1013,1711,164,54])])]),
 card('C3','商家卡片-图文下挂',[28,1821,1164,430],[region('头图区',[28,1821,297,274],[e('c3-image','图片','酷蹦床运动乐园门店头图',[28,1821,297,274])]),region('标题区',[340,1821,844,73],[e('c3-title','文本','酷蹦床运动乐园·团建·派对...',[342,1837,687,45])]),region('基础信息区',[340,1894,844,137],[e('c3-category','文本','儿童乐园',[341,1984,103,35]),e('c3-area','文本','朝阳区',[522,1969,117,71]),e('c3-distance','文本','19.5km',[1068,1987,122,30])]),region('标签区',[340,2039,844,70],[e('c3-rank','标签','1033位',[348,2038,97,62]),e('c3-coupon','标签','最多抵至50',[491,2038,146,62])]),region('下挂区',[80,2129,1100,122],[e('c3a-discount','标签','1.1折',[103,2129,78,57]),e('c3a-price','文本','¥60.9',[197,2133,107,35]),e('c3a-product','文本','蹦蹦床 生日特惠 前后三天均可用',[364,2129,629,57]),e('c3a-sales','文本','年售100+',[1031,2129,146,57]),e('c3b-discount','标签','1.1折',[103,2207,78,57]),e('c3b-price','文本','¥74.8',[197,2211,107,35]),e('c3b-product','文本','蹦蹦床 夜场蹦迪 全场畅玩',[364,2207,601,57]),e('c3b-sales','文本','年售800+',[1031,2207,146,57])])]),
 card('C4','商家卡片-文字下挂',[28,2310,1164,390],[region('头图区',[28,2310,290,284],[e('c4-image','图片','MINI MARS漂浮城市乐园门店头图',[28,2310,290,284])]),region('标题区',[340,2315,844,66],[e('c4-title','文本','MINI MARS漂浮城市乐园·餐...',[342,2331,678,45])]),region('基础信息区',[340,2381,844,151],[e('c4-score','文本','3.8',[396,2411,57,35]),e('c4-comments','文本','7971条评论',[483,2389,201,91]),e('c4-average','文本','人均¥210',[715,2389,161,91])]),region('标签区',[340,2477,844,120],[e('c4-rank','标签','朝阳区儿童乐园销量榜第8名',[416,2531,396,68])]),region('下挂区',[340,2612,844,78],[e('c4-coupon','标签','立减5',[443,2615,82,52])])])]
build('游乐场',y_cards,ROOT/'screenshots/首评-单一元素/游乐场_全部_1_副本.png','elements_游乐场_首评-单一元素-4.json','youlechang_首评-单一元素-4.json')

# 漂流
m=[e('m-query','文本','漂流',[165,186,87,31]),e('m-tab-all','文本','全部',[341,300,136,70]),e('m-tab-delivery','文本','外卖',[518,301,94,46]),e('m-tab-group','文本','团购',[697,300,91,46]),e('m-tab-location','文本','地点',[870,301,95,45]),e('m-tab-guide','文本','攻略',[1047,300,95,46]),e('m-safety','文本','临水游玩，请注意安全提示',[112,384,443,42]),e('m-filter-recommend','文本','推荐',[76,621,67,33]),e('m-filter-scenic','文本','景点',[272,622,66,31]),e('m-filter-hotel','文本','酒店',[467,621,66,33]),e('m-filter-travel','文本','旅游产品',[626,617,135,44]),e('m-quick-location','文本','望京',[107,720,230,36]),e('m-quick-sort','文本','综合排序',[454,720,154,36]),e('m-quick-category','文本','全部分类',[725,720,152,36])]
p_cards=[macro('漂流',m),
 card('C1','主点卡片',[28,841,1168,274],[region('头图区',[28,841,282,274],[e('c1-image','图片','花果山漂流图片',[28,841,282,274])]),region('标题区',[340,841,700,62],[e('c1-title','文本','花果山漂流（紫竹院公园）',[356,851,493,46])]),region('基础信息区',[340,934,850,110],[e('c1-score','文本','4.0',[340,934,62,41]),e('c1-comments','文本','23条评论',[430,934,143,41]),e('c1-category','文本','水上项目',[340,1004,148,35]),e('c1-subcategory','文本','水上体验',[531,1004,133,36]),e('c1-location','文本','紫竹桥',[693,992,117,57]),e('c1-distance','文本','16.1km',[1068,1007,122,30])])]),
 card('C2','主点卡片',[28,1173,1168,356],[region('头图区',[28,1173,282,356],[e('c2-image','图片','北京欢乐谷图片',[28,1173,282,356])]),region('标题区',[340,1173,700,72],[e('c2-title','文本','北京欢乐谷',[340,1183,291,45]),e('c2-level','标签','4A',[596,1167,39,100])]),region('基础信息区',[340,1255,850,152],[e('c2-score','文本','4.9',[340,1255,70,81]),e('c2-comments','文本','42.8万条评论',[483,1255,227,81]),e('c2-category','文本','主题乐园',[351,1336,159,35]),e('c2-location','文本','北京欢乐谷',[536,1306,177,87]),e('c2-distance','文本','15.7km',[1068,1339,122,30])]),region('标签区',[340,1389,820,62],[e('c2-rank','标签','北京游玩榜',[348,1410,97,30]),e('c2-listed','标签','2026年上榜玩乐地',[468,1410,280,30]),e('c2-tag-drift','标签','漂流',[791,1411,62,30]),e('c2-tag-night','标签','有夜场票',[894,1411,125,29])]),region('下挂区',[340,1460,760,75],[e('c2-desc','文本','乐享漂流演艺，打卡摩天轮夜游盛宴',[340,1486,659,39])])]),
 card('C3','主点卡片',[28,1756,1168,356],[region('头图区',[28,1756,282,356],[e('c3-image','图片','野三坡刘家河高山漂流图片',[28,1756,282,356])]),region('标题区',[340,1766,700,64],[e('c3-title','文本','野三坡刘家河高山漂流',[340,1766,476,45])]),region('基础信息区',[340,1822,850,147],[e('c3-score','文本','4.3',[340,1849,112,38]),e('c3-comments','文本','875条评论',[487,1851,175,35]),e('c3-category','文本','水上项目',[340,1919,148,35]),e('c3-subcategory','文本','水上体验',[567,1919,97,36]),e('c3-location','文本','百里峡',[703,1919,103,36]),e('c3-city','文本','保定',[1007,1919,75,36]),e('c3-distance','文本','99km',[1097,1922,93,30])]),region('下挂区',[340,2046,850,68],[e('c3-desc','文本','长长的吊桥也很好玩，水上项目也很多',[340,2047,666,69])])]),
 card('C4','主点卡片',[28,2339,1168,356],[region('头图区',[28,2339,282,356],[e('c4-image','图片','拒马乐园图片',[28,2339,282,356])]),region('标题区',[340,2350,700,70],[e('c4-title','文本','拒马乐园',[340,2350,203,44]),e('c4-level','标签','4A',[542,2346,43,56])]),region('基础信息区',[340,2428,850,178],[e('c4-score','文本','3.9',[392,2432,60,38]),e('c4-comments','文本','2481条评论',[483,2413,201,66]),e('c4-free','标签','免费入园',[714,2413,155,66]),e('c4-category','文本','主题乐园',[340,2502,166,36]),e('c4-location','文本','十渡镇',[534,2482,117,66]),e('c4-distance','文本','86.9km',[1066,2505,124,30])]),region('下挂区',[340,2652,840,43],[e('c4-desc','文本','八渡漂流戏水，河宽水清、滑道险峻',[370,2631,610,66])])])]
build('漂流',p_cards,ROOT/'screenshots/首评-单一元素/漂流_全部_1_副本.png','elements_漂流_首评-单一元素-4.json','漂流_首评-单一元素-4.json')

# 烧烤
m=[e('m-query','文本','烧烤',[164,168,88,42]),e('m-tab-all','文本','全部',[343,300,133,61]),e('m-tab-delivery','文本','外卖',[518,301,133,61]),e('m-tab-group','文本','团购',[697,300,91,46]),e('m-tab-location','文本','地点',[870,301,95,45]),e('m-tab-guide','文本','攻略',[1047,300,95,46]),e('m-quick-location','文本','望京',[108,426,226,36]),e('m-quick-sort','文本','综合排序',[370,420,210,55]),e('m-quick-distance','文本','距离最近',[673,420,169,55])]
# 烧烤原图仅有三张独立结果卡；历史 C4–C6 是把同一页局部/下挂内容错误拆成新商卡的标注，禁止恢复。
b_cards=[macro('烧烤',m),
 card('C1','商家卡片-图文下挂',[46,547,1126,183],[region('头图区',[58,547,163,163],[e('c1-image','图片','望京小腰门店主图',[58,547,163,163])]),region('标题区',[253,547,500,55],[e('c1-title','文本','望京小腰(朝阳总店)',[277,551,391,45])]),region('基础信息区',[253,612,916,50],[e('c1-score','文本','3',[341,615,24,57]),e('c1-comments','文本','1.1万条评价',[393,615,203,57]),e('c1-average','文本','人均¥83',[637,626,129,35]),e('c1-category','文本','望京烤串',[796,615,181,57]),e('c1-distance','文本','1.5km',[1070,629,99,30])]),region('标签区',[58,671,240,30],[e('c1-status','标签','营业中',[157,671,47,26])])]),
 card('C2','商家卡片-图文下挂',[253,772,916,274],[region('头图区',[253,772,274,274],[e('c2-image','图片','甄选烧烤四人餐套餐主图',[253,772,274,274])]),region('标题区',[560,782,587,60],[e('c2-title','文本','甄选烧烤四人餐',[560,790,270,36]),e('c2-refund','标签','可随时退',[881,784,142,52]),e('c2-expiry','标签','过期退',[1043,784,108,52])]),region('价格区',[560,900,587,70],[e('c2-price','文本','¥257',[559,998,96,34]),e('c2-original','文本','¥292',[674,1005,80,26])])]),
 card('C3','商家卡片-图文下挂',[46,1129,1123,272],[region('头图区',[58,1129,163,163],[e('c3-image','图片','锦州烧烤门店主图',[58,1129,163,163])]),region('标题区',[253,1129,910,53],[e('c3-title','文本','锦州烧烤(望京店)',[275,1133,378,46])]),region('基础信息区',[253,1200,910,52],[e('c3-score','文本','4.6',[343,1202,18,51]),e('c3-sales','文本','月售2000+',[385,1202,183,51]),e('c3-delivery','文本','起送¥20 免配送费',[591,1202,286,51]),e('c3-time','文本','33分钟',[1046,1209,117,36])]),region('标签区',[253,1271,910,52],[e('c3-rank','标签','望京烧烤热销榜第3名',[359,1261,270,60]),e('c3-viewed','文本','最近24小时639人看过',[692,1261,359,60]),e('c3-distance','文本','2.3km',[1062,1283,101,30])])])]
build('烧烤',b_cards,ROOT/'screenshots/首评-单一元素/烧烤_全部_1_副本.png','elements_烧烤_首评-单一元素-4.json','烧烤_首评-单一元素-4.json')

# 理发
m=[e('m-query','文本','理发',[164,168,87,42]),e('m-tab-all','文本','全部',[341,300,136,70]),e('m-tab-delivery','文本','外卖',[518,301,94,46]),e('m-tab-group','文本','团购',[697,300,91,46]),e('m-tab-location','文本','地点',[870,301,95,45]),e('m-tab-guide','文本','攻略',[1047,300,95,46]),e('m-filter-men','文本','男士剪发',[74,586,156,55]),e('m-filter-women','文本','女士剪发',[245,586,180,55]),e('m-filter-child','文本','儿童理发',[437,586,187,55]),e('m-quick-location','文本','望京',[108,757,179,36]),e('m-quick-sort','文本','综合排序',[403,757,153,36]),e('m-quick-distance','文本','3km内',[823,757,105,36])]
r_cards=[macro('理发',m)]
for n,y,title,score,comments,avg,area,dist,rank,services,offers in [
 ('C1',878,'MEST) Raise (望京店)', '4.9','2.2万条评论','洗剪吹¥34/人','美发 望京','1.2km','望京美发回头客榜第2名','戴森吹风机 拉直','理发服务'),
 ('C2',1434,'尤司男士国潮理发馆(北京望京...)', '5.0','4773条评论','男士理发¥152/人','理发 望京','1.5km','望京烫染销量榜第5名','洗剪吹 发型设计','洗剪吹 闲时工作日15点前使用'),
 ('C3',1990,'莫西卡男士发型设计(欢乐颂店)', '5.0','655条评论','理发¥36/人','美发 望京','1.8km','望京美发好评榜第6名','洗吹','不限等级 男士理发洗吹'),
 ('C4',2546,'造型(望京店)', '4.7','2565条评论','洗剪次¥41/人','女发','', '', '', '')]:
    h=492 if n!='C4' else 154
    regs=[region('头图区',[28,y,282,min(278,2700-y)],[e(n.lower()+'-image','图片','理发商家门店图片',[28,y,282,min(278,2700-y)])]),region('标题区',[340,y,850,60],[e(n.lower()+'-title','文本',title,[340,y,850,60])]),region('基础信息区',[340,y+70,850,min(170,2700-(y+70))],[e(n.lower()+'-score','文本',score,[393,y+93,60,35]),e(n.lower()+'-comments','文本',comments,[483,y+83,201,70]),e(n.lower()+'-average','文本',avg,[714,y+83,250,70]),e(n.lower()+'-category','文本',area,[340,min(y+163,2690),179,min(36,2700-min(y+163,2690))])]+([e(n.lower()+'-distance','文本',dist,[1090,y+166,100,30])] if dist else []))]
    if n!='C4': regs += [region('标签区',[340,y+210,850,70],[e(n.lower()+'-rank','标签',rank,[415,y+216,306,61]),e(n.lower()+'-service','标签',services,[772,y+216,240,61])]),region('下挂区',[340,y+290,850,120],[e(n.lower()+'-offer-a','标签','1.975折 最多抵至30',[352,y+300,285,53]),e(n.lower()+'-offer-b','文本',offers,[364,y+377,650,56])])]
    r_cards.append(card(n,'商家卡片-文字下挂',[18,y,1188,h],regs))
build('理发',r_cards,ROOT/'screenshots/首评-单一元素/理发_全部_1_副本.png','elements_理发_首评-单一元素-4.json','理发_首评-单一元素-4.json')

print('rebuilt')
