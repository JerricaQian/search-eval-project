"""Helper: run a single browser-action via catdesk, avoiding shell/JSON escaping issues.
Usage:
  python imd_eval.py eval '<js expression>'
  python imd_eval.py action '<json obj>'
"""
import json, subprocess, sys

def run(cmd_obj):
    cmd_str = json.dumps(cmd_obj, ensure_ascii=False)
    result = subprocess.run(['catdesk', 'browser-action', cmd_str],
                            capture_output=True, text=True)
    return result.stdout + result.stderr

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'eval':
        script = sys.argv[2]
        print(run({"action": "evaluate", "script": script}))
    elif mode == 'action':
        obj = json.loads(sys.argv[2])
        print(run(obj))
