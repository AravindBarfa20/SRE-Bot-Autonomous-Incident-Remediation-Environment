import uvicorn
from engine.main import app  # Assuming your FastAPI app is in engine/main.py

def main():
    uvicorn.run("engine.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
