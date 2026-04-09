import sys
import os
# Add root directory to python path so it can find agent.py, env.py etc.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import uvicorn
from engine.main import app  # Assuming your FastAPI app is in engine/main.py

def main():
    uvicorn.run("engine.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
