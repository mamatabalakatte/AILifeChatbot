import os
from groq import Groq
from typing import List, Dict, Optional
import json
import re

# Initialize the client once (singleton)
_client = None

def get_groq_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Try the key from GEMINI_API_KEY env var (which is actually the Groq key)
            api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise Exception("GROQ_API_KEY not configured")
        _client = Groq(api_key=api_key)
    return _client

SYSTEM_PROMPTS = {
    "subject": """You are a smart, practical Student Life Assistant chatbot designed to help young people improve their daily life, confidence, and productivity.

Your responsibilities include:
- Grooming and hygiene advice (simple, science-based)
- Fitness guidance (basic workouts, routines)
- Study and career advice (especially for students)
- Social skills and communication tips
- Mental well-being and motivation
- Daily routine optimization

Tone:
- Friendly but not childish
- Confident and clear
- No cringe, no over-motivation
- Give actionable advice (steps, not just theory)

Rules:
- Keep answers structured (steps, tips, examples)
- Be practical and realistic
- If unsure, say so instead of guessing
- Avoid unsafe or harmful advice

Always aim to:
→ Improve discipline
→ Build confidence
→ Solve real problems""",
    
    "career": """You are the Universal Bot Career Agent.
Your goal is to guide students on potential career paths based on their interests and academic strengths.
Provide actionable advice, suggest skills to learn, and be inspiring.""",

    "quiz": """You are the Universal Bot Quiz Generator.
Generate exactly 3 Multiple Choice Questions based on the user's topic.
Format your response as a valid JSON array of objects with the following keys:
"question", "options" (a list of 4 strings), "correct_answer" (the exact string from options), "explanation".""",
    
    "mistake": """You are the Universal Bot Mistake Analyzer.
The user will provide a Question and their Wrong Answer.
You must:
1. Explain exactly WHERE the mistake happened in their thought process.
2. Provide the CORRECT method to solve it step-by-step.
3. Be supportive and constructive.""",
    
    "notes": """You are the Universal Bot Notes Generator.
Convert the provided text or image content into highly structured, easy-to-read bullet point notes.
Extract only the key points, formulas, or critical concepts."""
}

def get_agent_model(agent_type: str, temperature: float = 0.7):
    """Returns a config object for generating content"""
    prompt = SYSTEM_PROMPTS.get(agent_type, SYSTEM_PROMPTS["subject"])
    
    # Check if API key is configured
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY not configured")
    
    # Return a config object that can be used with the Groq API
    return {
        "model": "llama-3.3-70b-versatile",
        "vision_model": os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        "system_instruction": prompt,
        "temperature": temperature,
        "max_tokens": 1024,
        "agent_type": agent_type
    }

def generate_response(client_obj, model_config, message: str, history: List[Dict] = None, image_data_url: Optional[str] = None):
    """Generate a response using the Groq API"""
    
    # Build messages with history
    messages = []
    
    # Add system instruction
    messages.append({
        "role": "system",
        "content": model_config["system_instruction"]
    })
    
    # Add history as context
    if history:
        for msg in history:
            messages.append({
                "role": "user" if msg.get("role") == "user" else "assistant",
                "content": msg.get("content", "")
            })
    
    if image_data_url:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": message},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        })
    else:
        messages.append({
            "role": "user",
            "content": message
        })
    
    # Generate content
    response = client_obj.chat.completions.create(
        model=model_config["vision_model"] if image_data_url else model_config["model"],
        messages=messages,
        temperature=model_config["temperature"],
        max_tokens=model_config["max_tokens"],
    )
    
    return response.choices[0].message.content

def route_query(message: str) -> str:
    """Simple routing logic to decide which agent to use based on keywords."""
    lower_msg = message.lower()
    
    # Maps keywords
    route_like = re.match(r"^\s*(?:from\s+)?[a-z][a-z\s,.'-]{1,60}\s+(?:to|->|→)\s+[a-z][a-z\s,.'-]{1,60}\s*$", lower_msg)
    between_route = re.search(r"\bdistance\s+between\s+.+\s+and\s+.+", lower_msg)
    route_false_start = re.match(r"^\s*(i\s+want|i\s+need|how|what|when|where|why|learn|try|need|want)\s+to\b", lower_msg)
    if any(word in lower_msg for word in ["near", "restaurant", "hospital", "atm", "mall", "directions", "how to reach", "distance", "route", "trip", "place"]) or ((route_like or between_route) and not route_false_start):
        return "maps"
        
    if any(word in lower_msg for word in ["career", "job", "future", "college", "degree"]):
        return "career"
        
    return "subject"

def parse_chat_history(history: List[Dict]) -> List[Dict]:
    """Converts frontend history format to Groq format"""
    groq_history = []
    for msg in history:
        groq_history.append({
            "role": "user" if msg["role"] == "user" else "assistant",
            "content": msg["content"]
        })
    return groq_history
