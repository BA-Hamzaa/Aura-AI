"""Temporary debug script — finds the real 500 error in the ask endpoint."""
import sys, os

# Override sys.stdout/stderr BEFORE main.py overwrites them with devnull
# so we can see the real traceback
import io
_cap = io.StringIO()

# Prevent main.py from silencing output
import builtins
_orig_open = builtins.open
def _open_intercept(file, mode='r', **kwargs):
    if str(file) == os.devnull and 'w' in str(mode):
        return _orig_open(os.devnull, mode, **kwargs)
    return _orig_open(file, mode, **kwargs)

sys.path.insert(0, os.path.dirname(__file__))

# Patch dotenv and imports
os.environ.setdefault('PYTHONUTF8', '1')

# Simulate exactly what the ask endpoint does
from dotenv import load_dotenv
load_dotenv()

from gemini_client import GeminiClient
from automation import parse_and_execute_actions, strip_action_tags

api_key = os.getenv('GEMINI_API_KEY', '')
print(f"Key loaded: {api_key[:10]}...")

try:
    print("Creating GeminiClient...")
    ai = GeminiClient(api_key)
    print(f"GeminiClient created, model={ai.active_model}")
    
    print("Calling ai.ask('hi')...")
    raw_answer = ai.ask('hi')
    print(f"raw_answer type: {type(raw_answer)}")
    print(f"raw_answer bytes: {raw_answer.encode('utf-8')[:200]}")
    
    print("Calling parse_and_execute_actions...")
    action_results = parse_and_execute_actions(raw_answer, callback=lambda r: None)
    print(f"actions: {len(action_results)}")
    
    print("Calling strip_action_tags...")
    visible_answer = strip_action_tags(raw_answer)
    print(f"visible_answer bytes: {visible_answer.encode('utf-8')[:200]}")
    
    import json
    result = {"answer": visible_answer, "actions_triggered": len(action_results)}
    j = json.dumps(result, ensure_ascii=False)
    print(f"JSON serialization OK, length={len(j)}")
    print("SUCCESS - no errors!")
    
except Exception as e:
    import traceback
    print(f"EXCEPTION at step above: {type(e).__name__}: {e}")
    traceback.print_exc()
