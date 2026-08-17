"""Export an IMD node (by id) to PNG via plugin API mg.getNodeById(id).exportAsync(),
retrieve as base64 through the browser, and save to a local file.
Usage: python imd_export_node.py <nodeId> <outPath> [scale]
"""
import json, subprocess, sys, base64, time

def action(obj):
    cmd = json.dumps(obj, ensure_ascii=False)
    r = subprocess.run(['catdesk', 'browser-action', cmd], capture_output=True, text=True)
    return r.stdout + r.stderr

def evaluate(script):
    out = action({"action": "evaluate", "script": script})
    # catdesk persists very large outputs to a file; detect and read it back
    if 'Full output saved to:' in out:
        path = out.split('Full output saved to:')[1].strip().split('\n')[0].strip()
        with open(path) as f:
            out = f.read()
    try:
        return json.loads(out).get('data', {}).get('result')
    except Exception:
        return out

node_id = sys.argv[1]
out_path = sys.argv[2]
scale = sys.argv[3] if len(sys.argv) > 3 else "1"

# Kick off export; store base64 on window.__exp
kick = ("(async () => { try { const n = window.mg.getNodeById('%s'); "
        "const bytes = await n.exportAsync({format:'PNG', constraint:{type:'SCALE', value:%s}}); "
        "let bin=''; const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes); "
        "for(let i=0;i<arr.length;i++) bin += String.fromCharCode(arr[i]); "
        "window.__exp = btoa(bin); window.__expLen = arr.length; return JSON.stringify({ok:true, len:arr.length}); "
        "} catch(e){ window.__exp='ERR'; return 'err:'+e.message; } })()") % (node_id, scale)
print("kick:", evaluate(kick), flush=True)

# poll for completion
for _ in range(60):
    st = evaluate("(() => window.__exp === undefined ? 'pending' : (window.__exp==='ERR'?'err':'done:'+window.__expLen))()")
    print("status:", st, flush=True)
    if isinstance(st, str) and (st.startswith('done') or st == 'err'):
        break
    time.sleep(1)

# fetch base64 in chunks to avoid huge single output
lenr = evaluate("(() => window.__exp ? window.__exp.length : 0)()")
total = int(lenr)
print("b64 total chars:", total, flush=True)
CHUNK = 60000
parts = []
i = 0
while i < total:
    part = evaluate("(() => window.__exp.substring(%d,%d))()" % (i, i+CHUNK))
    if not part or 'err' in part[:10].lower() or ' ' in part or '\n' in part:
        print('BAD CHUNK at', i, repr(part[:80]))
        break
    parts.append(part)
    i += CHUNK
b64 = ''.join(parts)
print('assembled b64 chars:', len(b64), flush=True)
with open(out_path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("SAVED", out_path, flush=True)
