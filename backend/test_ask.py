
import os, time, sys
os.environ['PYTHONUTF8'] = '1'
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv(r'c:\Users\Hamza\OneDrive\Desktop\project ai\backend\.env')

print('Before', flush=True)
from gemini_client import GeminiClient

api_key = os.getenv('GEMINI_API_KEY')
print('Got Key', flush=True)

t = time.time()
ai = GeminiClient(api_key)
print('After init in', time.time() - t, flush=True)

t = time.time()
ans = ai.ask('hi')
print('After ask in', time.time() - t, flush=True)
print(ans, flush=True)
