import google.genai as genai
from google.genai import client
import requests
import json
import os
import re

# Initialize client
_maps_client = None

def get_maps_client():
    global _maps_client
    if _maps_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        _maps_client = client.Client(api_key=api_key)
    return _maps_client

UNIVERSAL_PROMPT = """
You are an advanced maps assistant chatbot.
Understand ANY location-based query and convert it into JSON.
Detect route queries such as "Bidar to Jalandhar", "Delhi to Mumbai",
"Plan trip from X to Y", "route from X to Y", or "distance between X and Y"
as get_directions. Extract the source and destination clearly.

User Query: "{user_input}"

Return ONLY valid JSON:
{
  "intent": "search_place | get_directions | explore_area",
  "place_type": "any (restaurant, hospital, ATM, mall, tourist place, etc)",
  "location": {
    "type": "current | city | specific_place",
    "value": "location or null"
  },
  "filters": {
    "price": "cheap | moderate | expensive | null",
    "rating": "number or null",
    "open_now": "true | false | null"
  },
  "route": {
    "origin": "if directions",
    "destination": "if directions",
    "mode": "driving | walking | transit | null"
  }
}
"""

ROUTE_PATTERNS = [
    r"\bfrom\s+(?P<origin>.+?)\s+to\s+(?P<destination>.+?)\s*$",
    r"\bbetween\s+(?P<origin>.+?)\s+and\s+(?P<destination>.+?)\s*$",
    r"^\s*(?P<origin>.+?)\s+(?:to|towards|->|→)\s+(?P<destination>.+?)\s*$",
]

def detect_route_query(user_input):
    """Fast local route extraction for common route formats."""
    cleaned = user_input.strip().rstrip(".?!")
    for pattern in ROUTE_PATTERNS:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            origin = match.group("origin").strip(" ,")
            destination = match.group("destination").strip(" ,")
            origin = re.sub(r"^(plan|show|find|give|calculate|get)\s+(a\s+)?(trip|route|directions|distance)\s+", "", origin, flags=re.IGNORECASE).strip()
            origin = re.sub(r"^from\s+", "", origin, flags=re.IGNORECASE).strip()
            destination = re.sub(r"\s+(by\s+car|driving|route|directions)$", "", destination, flags=re.IGNORECASE).strip()
            if origin and destination and origin.lower() != destination.lower():
                return {
                    "intent": "get_directions",
                    "place_type": None,
                    "location": {"type": "specific_place", "value": None},
                    "filters": {"price": None, "rating": None, "open_now": None},
                    "route": {
                        "origin": origin,
                        "destination": destination,
                        "mode": "driving"
                    }
                }
    return None

def parse_query(user_input):
    local_route = detect_route_query(user_input)
    if local_route:
        return local_route

    try:
        client_obj = get_maps_client()
        prompt = UNIVERSAL_PROMPT.replace("{user_input}", user_input)
        response = client_obj.models.generate_content(
            model="gemini-2.0-flash",
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        parsed = json.loads(response.text)
        if parsed.get("intent") == "get_directions":
            route = parsed.get("route", {})
            if route.get("origin") and route.get("destination"):
                return parsed
        return parsed
    except:
        return local_route or {"intent": "search_place", "place_type": user_input, "location": {"value": ""}}

# USING FREE OPENSTREETMAP API (Nominatim) INSTEAD OF GOOGLE MAPS
def search_places(query):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'UniversalBotHackathon/1.0'}
    params = {
        "q": query,
        "format": "json",
        "limit": 5
    }
    try:
        res = requests.get(url, params=params, headers=headers).json()
        places = []
        for p in res:
            places.append({
                "name": p.get("display_name", "").split(",")[0],
                "address": p.get("display_name"),
                "type": p.get("type", "place"),
                "lat": float(p.get("lat", 0)),
                "lon": float(p.get("lon", 0))
            })
        return places if places else [{"error": "No places found"}]
    except Exception as e:
        return [{"error": str(e)}]

def get_coordinates(place_name):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'UniversalBotHackathon/1.0'}
    params = {"q": place_name, "format": "json", "limit": 1}
    try:
        res = requests.get(url, params=params, headers=headers).json()
        if res:
            return float(res[0]["lon"]), float(res[0]["lat"])
    except:
        pass
    return None, None

# USING FREE OSRM API FOR DIRECTIONS
def get_directions(origin, destination):
    lon1, lat1 = get_coordinates(origin)
    lon2, lat2 = get_coordinates(destination)
    
    if not (lon1 and lat1 and lon2 and lat2):
        return {"error": "Could not find coordinates for route"}
        
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        res = requests.get(url).json()
        route = res["routes"][0]
        coordinates = route.get("geometry", {}).get("coordinates", [])
        route_path = [{"lat": lat, "lon": lon} for lon, lat in coordinates]
        return {
            "from": origin,
            "to": destination,
            "source": origin,
            "destination": destination,
            "source_coords": {"lat": lat1, "lon": lon1},
            "destination_coords": {"lat": lat2, "lon": lon2},
            "route_path": route_path,
            "distance_km": round(route["distance"] / 1000, 2),
            "time_mins": round(route["duration"] / 60)
        }
    except:
        return {"error": "Route calculation failed"}

def format_duration(minutes):
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"

def build_route_response(data):
    source = data.get("source") or data.get("from", "Source")
    destination = data.get("destination") or data.get("to", "Destination")
    distance = data.get("distance_km", "N/A")
    minutes = int(data.get("time_mins", 0) or 0)
    duration = format_duration(minutes) if minutes else "N/A"
    image_prompt = (
        f"Realistic cinematic road journey from {source} to {destination}, "
        "wide highway with cars and trucks, natural sky, roadside environment, "
        "regional cities and plains along the route, highly detailed, high-resolution, "
        "professional travel photography, natural colors, sharp focus"
    )

    return f"""**Route:** {source} → {destination}
**Distance:** {distance} km
**Time:** {duration}

**Explanation:** This driving route takes you from {source} to {destination}. The approximate road distance is {distance} km, and the estimated travel time is about {duration}, depending on traffic, road conditions, and stops. Follow the main available driving route shown on the live map for turn-by-turn planning.

**Map Data:**
**Source:** {source}
**Destination:** {destination}

**Image Prompt:**
"{image_prompt}"
"""

def format_response(data, user_input=""):
    if isinstance(data, dict) and "error" not in data and data.get("distance_km") is not None:
        return build_route_response(data)

    try:
        client_obj = get_maps_client()
        prompt = f"""You are an intelligent AI travel assistant that helps users plan routes between any two locations and presents both data and visual guidance.

First, understand the user's input and detect if it contains a route query, such as "Bidar to Jalandhar", "Delhi to Mumbai", or "Plan trip from X to Y". Extract the source and destination clearly.

For every valid route query:
- Identify the source and destination accurately
- Provide approximate distance in kilometers
- Provide estimated travel time
- Mention the most relevant route, major highways, or major cities if known
- Write a clear and friendly explanation in simple language
- Include map integration data with Source and Destination separately

Also generate a realistic image prompt that visually represents the journey.

Image Prompt Rules:
- Must be realistic (not cartoon)
- Reflect actual terrain where possible, such as highways, cities, mountains, plains, or coast
- Include road, vehicles, sky, and environment
- Cinematic, high-resolution, highly detailed

Output format:

**Route:** <source> → <destination>
**Distance:** <value in km>
**Time:** <estimated duration>

**Explanation:** <simple and natural explanation of the journey>

**Map Data:**
**Source:** <source>
**Destination:** <destination>

**Image Prompt:**
"<realistic detailed scene description>"

If the user input is not a route query, respond normally and guide them to enter routes in formats like "City A to City B".

---
Context Data from API (use this to help answer):
{data}

User Query: {user_input}
        """
        res = client_obj.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return res.text
    except:
        # Fallback if Gemini fails
        if isinstance(data, list):
            names = [p.get("name", "Place") for p in data if "name" in p]
            return "I found these places for you: " + ", ".join(names[:3]) + " 📍"
        return "Here is what I found for you! 📍"

def process_maps_query(user_input):
    parsed = parse_query(user_input)

    if parsed.get("intent") == "get_directions":
        origin = parsed["route"].get("origin", "current location")
        destination = parsed["route"].get("destination")
        if not destination:
            return json.dumps({"text": "Please provide a valid destination!", "graph_data": None})
        route_data = get_directions(origin, destination)
        text_response = format_response(route_data, user_input)
        
        graph_data = None
        route_map_data = None
        if "error" not in route_data:
            graph_data = {
                "type": "directions",
                "labels": ["Distance (km)", "Time (mins)"],
                "data": [route_data.get("distance_km", 0), route_data.get("time_mins", 0)],
                "title": f"Route to {destination}"
            }
            route_map_data = {
                "source": route_data.get("source", origin),
                "destination": route_data.get("destination", destination),
                "source_coords": route_data.get("source_coords"),
                "destination_coords": route_data.get("destination_coords"),
                "route_path": route_data.get("route_path", [])
            }
            
        return json.dumps({"text": text_response, "graph_data": graph_data, "route_data": route_map_data})
    else:
        place = parsed.get("place_type", "")
        loc = parsed.get("location", {}).get("value", "")
        query = f"{place} {loc}".strip()
        if not query:
            query = user_input
            
        places = search_places(query)
        text_response = format_response(places, user_input)
        
        # Generate graph data for places (random ratings since free API doesn't have it easily)
        graph_data = None
        if isinstance(places, list) and len(places) > 0 and "error" not in places[0]:
            import random
            labels = []
            distances = []
            for p in places[:3]:
                name = p.get("name", "Unknown")[:15]
                labels.append(name)
                distances.append(round(random.uniform(0.5, 5.0), 1)) # Mock distance for UI
                
            graph_data = {
                "type": "places",
                "labels": labels,
                "data": distances,
                "title": f"Distance Comparison (km)"
            }
            
        return json.dumps({"text": text_response, "graph_data": graph_data, "places": places})
