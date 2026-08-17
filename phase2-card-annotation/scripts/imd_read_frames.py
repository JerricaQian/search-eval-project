"""Read design-space X/Y/W/H for a list of artboard layer names by
searching each in the layer panel, native-clicking it, and reading the props panel.
"""
import json, subprocess, time, sys

def run(cmd_obj):
    cmd_str = json.dumps(cmd_obj, ensure_ascii=False)
    r = subprocess.run(['catdesk', 'browser-action', cmd_str], capture_output=True, text=True)
    return r.stdout + r.stderr

def evaluate(script):
    out = run({"action": "evaluate", "script": script})
    try:
        data = json.loads(out)
        return data.get('data', {}).get('result')
    except Exception:
        return out

names = sys.argv[1:]
result = {}
for name in names:
    run({"action": "fill", "selector": "[data-imd-tag=layer-search]", "value": name})
    time.sleep(1.8)
    # native click the single matched item
    run({"action": "click", "selector": ".item_container"})
    time.sleep(1.5)
    raw = evaluate('(() => { const p = document.querySelectorAll(".basic__props--item.position input"); const w = document.querySelectorAll(".basic__props--item.wh input"); return JSON.stringify({pos: Array.from(p).map(i=>i.value), wh: Array.from(w).map(i=>i.value)}); })()')
    try:
        vals = json.loads(raw)
        result[name] = {"x": float(vals['pos'][0]), "y": float(vals['pos'][1]),
                        "w": float(vals['wh'][0]), "h": float(vals['wh'][1])}
    except Exception as e:
        result[name] = {"error": str(e), "raw": raw}
    print(f"{name}: {result[name]}", flush=True)

with open('/tmp/imd_frames.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("SAVED /tmp/imd_frames.json", flush=True)
