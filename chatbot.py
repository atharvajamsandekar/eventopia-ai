from mongodb_connection import get_db
from flask import jsonify, session
import os

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Configure Gemini AI gracefully
api_key = os.getenv("GEMINI_API_KEY")
model = None

try:
    import google.generativeai as genai
    print(f"DEBUG: Loaded API Key from env: {api_key}")
    if api_key and api_key != "YOUR_API_KEY_HERE":
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')  # Switched to 2.5 flash as 1.5 is no longer supported
        print("DEBUG: Gemini model successfully initialized! (Ignore the deprecation warning above)")
    else:
        print("DEBUG: Condition failed! Either no api key or it's YOUR_API_KEY_HERE")
except Exception as e:
    print(f"DEBUG: Failed to initialize Google Generative AI: {e}")

def get_bot_response(user_message):
    message = user_message.strip()
    username = session.get("user", "Guest")
    db = get_db()

    try:
        # FETCH ALL EVENTS AS CONTEXT
        # Using aggregation or simple find(). In MySQL it was a complex join.
        # We'll just fetch related collections and combine.
        events_list = list(db.events.find({}))
        competitions = list(db.competitions.find({}))
        tech_fests = list(db.tech_fests.find({}))
        
        # If API KEY is missing, fallback to a simple manual response so the app doesn't crash
        if model is None:
            return jsonify({
                "response": "⚠️ **System Notice**: The Chatbot is currently in minimal mode because the `GEMINI_API_KEY` is missing in the `.env` file! Please ask the administrator to configure it."
            })

        # BUILD SYSTEM PROMPT CONTEXT
        context_str = f"You are the official AI Assistant for 'Eventopia', a college event portal. You are talking to user: {username}.\n"
        context_str += "Here is the live database of all upcoming events, tech fests, and competitions:\n"
        
        if not events_list and not competitions and not tech_fests:
            context_str += "Currently, there are no upcoming events or competitions scheduled.\n"
        else:
            if tech_fests:
                context_str += "--- DEPARTMENT TECH FESTS ---\n"
                for t in tech_fests:
                    context_str += f"- {t['name']} (Dept: {t['department']}): {t['description']} | Venue: {t['venue']} | Date: {t['fest_date']}\n"

            if events_list:
                context_str += "--- EVENTS & SUB-EVENTS ---\n"
                for e in events_list:
                    price_str = "Free" if e.get('price', 0) == 0 else f"₹{e.get('price', 0)}"
                    sub_cats = f" | Sub-Categories: {e.get('sub_categories', '')}" if e.get('sub_categories') else ""
                    parent_fest = f" [Part of Tech Fest: {e.get('tech_fest_name', '')}]" if e.get('tech_fest_name') else ""
                    context_str += f"- {e['name']}{parent_fest} ({e['category']} / {e['department']}): {e['description']} | Venue: {e['venue']} | Time: {e['event_date']} at {e['event_time']} | Price: {price_str}{sub_cats}\n"
            
            if competitions:
                context_str += "--- COMPETITIONS ---\n"
                for c in competitions:
                    context_str += f"- {c['name']} (Type: {c['type']}): {c['description']} | Venue: {c['venue']} | Date: {c['competition_date']}\n"

        context_str += "\nInstructions: Answer the user's question clearly and conversationally. If they ask about events, tech fests, or competitions, reference the provided list. "
        context_str += "If they ask about sub-events, explicitly list the events marked as '[Part of Tech Fest: ...]', or mention the 'Sub-Categories'. "
        context_str += "If they explicitly ask to 'go to home page', 'navigate to home', or 'take me home', do NOT write any conversational text. Instead, respond EXACTLY with: [NAVIGATE_HOME] "
        context_str += "If they ask you to 'create a notification', 'send a notification', or 'announce something' to the notification panel, respond EXACTLY with the format: [CREATE_NOTIFICATION] Title | Message (replace Title and Message with a catchy title and message based on their request). Do not include any other text. "
        context_str += "If they ask a general knowledge question... answer it brilliantly but concisely. "
        context_str += "Always be polite and helpful. format your response in plain text (can use emojis). Do NOT hallucinate events that aren't in the list."

        prompt = f"{context_str}\n\nUser Question: {message}\nAssistant:"

        response = model.generate_content(prompt)
        ai_text = response.text.replace('\n', '<br>')
        
        return jsonify({"response": ai_text})

    except Exception as e:
        print("Chatbot Error:", e)
        return jsonify({
            "response": "Oops! I encountered an error connecting to my neural network. Please try again later."
        })