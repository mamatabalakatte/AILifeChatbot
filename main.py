import os
import base64
from fastapi import FastAPI, HTTPException, Request, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Import local modules
from agents import get_groq_client, get_agent_model, generate_response, route_query, parse_chat_history
from database import init_db, save_quiz_score, get_progress, record_mistake
from pdf_generator import create_pdf_bytes

load_dotenv()

# Initialize Database
init_db()

app = FastAPI(title="Universal Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_ai_client():
    return get_groq_client()

MAX_UPLOAD_BYTES = 8 * 1024 * 1024

async def image_upload_to_data_url(file: Optional[UploadFile]) -> Optional[str]:
    if not file:
        return None

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported right now.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large. Please upload an image under 8 MB.")

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    agent_type: Optional[str] = "auto"

class QuizRequest(BaseModel):
    topic: str

class QuizSubmitRequest(BaseModel):
    user_id: str
    topic: str
    score: int
    total: int

class MistakeRequest(BaseModel):
    question: str
    wrong_answer: str

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(...),
    agent_type: str = Form("auto"),
    history: str = Form("[]"),
    file: Optional[UploadFile] = File(None)
):
    import json
    try:
        chat_history = json.loads(history)
        image_data_url = await image_upload_to_data_url(file)
        
        # Routing logic
        if agent_type == "auto":
            active_agent = route_query(message)
        else:
            active_agent = agent_type
            
        if active_agent == "maps":
            from maps_agent import process_maps_query
            response_json_str = process_maps_query(message)
            import json
            try:
                maps_data = json.loads(response_json_str)
                return {
                    "response": maps_data.get("text", ""),
                    "graph_data": maps_data.get("graph_data", None),
                    "route_data": maps_data.get("route_data", None),
                    "agent_used": active_agent,
                    "status": "success"
                }
            except:
                return {
                    "response": response_json_str,
                    "agent_used": active_agent,
                    "status": "success"
                }
            
        model_config = get_agent_model(active_agent)
        gemini_history = parse_chat_history(chat_history)
        
        try:
            client_obj = get_ai_client()
            response_text = generate_response(client_obj, model_config, message, gemini_history, image_data_url=image_data_url)
            return {
                "response": response_text,
                "agent_used": active_agent,
                "status": "success"
            }
        except Exception as gemini_err:
            if "quota" in str(gemini_err).lower() or "429" in str(gemini_err):
                return {
                    "response": "I'm sorry, my daily AI quota has been reached! Please try again later or ask a map-related question which has a fallback mode.",
                    "agent_used": active_agent,
                    "status": "success"
                }
            raise gemini_err
    except HTTPException:
        raise
    except Exception as e:
        print(f"Chat Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quiz")
async def generate_quiz(request: QuizRequest):
    try:
        model_config = get_agent_model("quiz")
        client_obj = get_ai_client()
        response_text = generate_response(client_obj, model_config, f"Generate a quiz about: {request.topic}")
        import json
        quiz_data = json.loads(response_text)
        return {"quiz": quiz_data, "status": "success"}
    except Exception as e:
        print(f"Quiz Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quiz/submit")
async def submit_quiz(request: QuizSubmitRequest):
    try:
        save_quiz_score(request.user_id, request.topic, request.score, request.total)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mistake")
async def analyze_mistake(request: MistakeRequest):
    try:
        model_config = get_agent_model("mistake")
        client_obj = get_ai_client()
        prompt = f"Question: {request.question}\nMy Wrong Answer: {request.wrong_answer}"
        response_text = generate_response(client_obj, model_config, prompt)
        # We can also track mistakes
        record_mistake("demo_user", "general") # Hardcoded user for hackathon
        return {"response": response_text, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notes")
async def generate_notes(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    try:
        model_config = get_agent_model("notes")
        client_obj = get_ai_client()
        
        image_data_url = await image_upload_to_data_url(file)
        prompt = "Generate notes from this content."
        if text:
            prompt = f"Generate notes for: {text}"
        elif image_data_url:
            prompt = "Generate concise, well-structured study notes from the uploaded image."
            
        response_text = generate_response(client_obj, model_config, prompt, image_data_url=image_data_url)
        return {"notes": response_text, "status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MapsRequest(BaseModel):
    query: str

@app.post("/api/maps/search")
async def maps_search(request: MapsRequest):
    try:
        from maps_agent import process_maps_query
        import json
        res = json.loads(process_maps_query(request.query))
        return {"data": res, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress")
async def user_progress(user_id: str = "demo_user"):
    try:
        data = get_progress(user_id)
        return {"data": data, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PDFRequest(BaseModel):
    text: str

@app.post("/api/pdf/generate")
async def generate_pdf(request: PDFRequest):
    try:
        pdf_bytes = create_pdf_bytes(request.text)
        return StreamingResponse(
            pdf_bytes, 
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=AI_Life_Dashboard_Export.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def serve_index():
    if not os.path.exists("index.html"):
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse("index.html")

@app.get("/{asset_path:path}")
async def serve_frontend_asset(asset_path: str):
    allowed_assets = {"style.css", "script.js"}
    if asset_path in allowed_assets and os.path.exists(asset_path):
        return FileResponse(asset_path)
    raise HTTPException(status_code=404, detail="Not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
