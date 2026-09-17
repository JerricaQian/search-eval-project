"""Project the current q20 Phase-2 facts into the Phase-3 result contract."""
from pathlib import Path

ROOT = Path('/Users/qianjing/Documents/ChatGPT/workproject_3')
source = (ROOT / 'scripts/generate_q33_phase3_results.py').read_text(encoding='utf-8')
replacements = {
    "eval-20260913-09-1-next35-v1-q33-r2": "batch-09-1-20260915-a2-q20",
    "elements_网咖_全部_1_": "elements_霸王茶姬_全部_1_副本1_",
    "eval-20260913-09-1-next35-v1/{RUN}": "batch-09-1-20260915/{RUN}",
    "网咖_全部_1.png": "霸王茶姬_全部_1_副本1.png",
    "'网咖'": "'霸王茶姬'",
    "四张": "三张",
    "文字下挂区": "下挂商品区",
    "商家卡片_文字下挂": "商家卡片_图文下挂",
    "红、橙、绿": "红、橙、黄",
}
for before, after in replacements.items():
    source = source.replace(before, after)
# The third result card is naturally cropped and the selected component skills
# that require a complete component exclude it.  Page-level checks still use
# the page-wide manifest and the colour aggregation prepared for all cards.
source = source.replace("cards = m['cards']", "cards = [card for card in m['cards'] if card['cardId'] != 'C3']")
source = source.replace("colors = json.loads(next(MEASURE.glob('*.component-color-families.json')).read_text())['components']", "colors = [item for item in json.loads(next(MEASURE.glob('*.component-color-families.json')).read_text())['components'] if item['componentId'] != 'C3']")
source = source.replace("chosen=['标题区','基础信息区','下挂商品区','头图区']", "chosen=['基础信息区','下挂商品区','头图区']")
source = source.replace("['头图区','标题区','基础信息区','下挂商品区']", "['头图区','基础信息区','下挂商品区']")
source = source.replace("active = [e for c in cards for r in c['regions'] for e in r['elements']]", "active = [e for c in m['cards'] for r in c['regions'] for e in r['elements']]")
source = source.replace("members=[c['cardId'] for c in cards]", "members=['C1']")
source = source.replace("if (role=='promotion' or tf.get('rawText','').startswith('神券')) and color not in ('neutral','unknown',''):", "if tf.get('promotionPrefix','') == '神券' and color not in ('neutral','unknown',''):")
source = source.replace("'content':tf.get('rawText','')", "'content':tf.get('promotionPrefix','')")
exec(compile(source, 'q20_phase3_projection', 'exec'))
