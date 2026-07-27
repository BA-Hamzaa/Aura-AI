"""
Minimal test server to isolate the 500 error on port 8002.
Runs the same logic as ask_question endpoint but with full error visibility.
"""
import os, sys
os.environ['PYTHONUTF8'] = '1'
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from gemini_client import GeminiClient
from automation import parse_and_execute_actions, strip_action_tags
import traceback

app = FastAPI()
api_key = os.getenv('GEMINI_API_KEY', '')
ai = GeminiClient(api_key)
print(f"[TEST] GeminiClient ready, model={ai.active_model}", flush=True)

class AskReq(BaseModel):
    question: str = 'hi'
    speak: bool = False

@app.post('/api/ask')
def ask(req: AskReq):
    try:
        raw_answer = ai.ask(req.question)
        print(f"[TEST] raw_answer={repr(raw_answer[:80])}", flush=True)
        action_results = parse_and_execute_actions(raw_answer, callback=lambda r: None)
        visible_answer = strip_action_tags(raw_answer)
        return {"answer": visible_answer, "actions_triggered": len(action_results)}
    except Exception as e:
        print(f"[TEST] EXCEPTION: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=200)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8002, log_level='debug')
