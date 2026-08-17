"""Non-destructive visual verification:
clone the base screenshot rectangle + clone all [ANNO] layers of a scene,
group the clones, export the group PNG, then delete the group (originals untouched).
Usage: python imd_verify_export.py <baseNodeId> <scenePrefix> <outPath>
"""
import json, subprocess, sys, base64, time

def action(obj):
    cmd = json.dumps(obj, ensure_ascii=False)
    r = subprocess.run(['catdesk', 'browser-action', cmd], capture_output=True, text=True)
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

base_id = sys.argv[1]
prefix = sys.argv[2]
out_path = sys.argv[3]

# clone base + all [ANNO] layers whose name starts with '[ANNO] {prefix}' or '[ANNO-TXT] {prefix}'
build = ("(() => { try { const doc=window.mg.document; const page=doc.currentPage||doc.children[0]; "
         "const base=window.mg.getNodeById('%s'); const clones=[base.clone()]; "
         "const want='%s'; "
         "for (const n of page.children){ if(n.name && (n.name.indexOf('[ANNO] '+want)===0 || n.name.indexOf('[ANNO-TXT] '+want)===0)){ clones.push(n.clone()); } } "
         "const g=window.mg.group(clones, page); window.__vg=g.id; "
         "return JSON.stringify({count:clones.length, groupId:g.id}); "
         "} catch(e){ return 'err:'+e.message; } })()") % (base_id, prefix)
print("build:", evaluate(build), flush=True)
time.sleep(0.5)

kick = ("(async () => { try { const g=window.mg.getNodeById(window.__vg); "
        "const bytes = await g.exportAsync({format:'PNG', constraint:{type:'SCALE', value:1}}); "
        "const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes); "
        "let bin=''; for(let i=0;i<arr.length;i++) bin+=String.fromCharCode(arr[i]); "
        "window.__vexp=btoa(bin); window.__vlen=arr.length; return 'ok:'+arr.length; "
        "} catch(e){ window.__vexp='ERR'; return 'err:'+e.message; } })()")
print("kick:", evaluate(kick), flush=True)

for _ in range(60):
    st = evaluate("(() => window.__vexp===undefined?'pending':(window.__vexp==='ERR'?'err':'done:'+window.__vlen))()")
    if isinstance(st, str) and (st.startswith('done') or st=='err'):
        print("status:", st, flush=True); break
    time.sleep(1)

total = int(evaluate("(() => window.__vexp?window.__vexp.length:0)()"))
CHUNK=60000; parts=[]; i=0
while i<total:
    part = evaluate("(() => window.__vexp.substring(%d,%d))()" % (i, i+CHUNK))
    if not part or ' ' in part or '\n' in part:
        print('BAD CHUNK', i, repr(part[:60])); break
    parts.append(part); i+=CHUNK
with open(out_path,'wb') as f:
    f.write(base64.b64decode(''.join(parts)))
print("SAVED", out_path, flush=True)

# cleanup: delete the temp group (removes clones too)
print("cleanup:", evaluate("(() => { const g=window.mg.getNodeById(window.__vg); if(g)g.remove(); window.__vg=null; return 'removed'; })()"), flush=True)
