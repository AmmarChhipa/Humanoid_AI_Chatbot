import google.generativeai as genai
import sqlite3
from datetime import datetime

# Initialize Gemini
genai.configure(api_key="AIzaSyCulA1fueRA6AyDjjg7Yvwu4b05Z4_gyU8")
model = genai.GenerativeModel("gemini-2.0-flash")

# Database setup
DB_PATH = "chat_history.db"

def initialize_database():
    """Initialize database with proper connection handling"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                user_id TEXT DEFAULT 'main_user',
                important_message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'main_session'
            )
        """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"[System] Database error: {e}")
    finally:
        if conn:
            conn.close()

def strict_importance_classifier(text):
    """Improved classifier with travel plan detection"""
    prompt = f"""Classify as IMPORTANT if:
    - Job changes (hiring/firing)
    - Relationship changes (marriage/breakup)
    - Health issues (diagnosis, accidents)
    - Financial changes (new house, big purchases)
    - current projects (work-related or personal)
    - personal achievements (graduation, awards)
    - significant life events (birth, death)
    - personal interests (hobbies, passions)
    - personal information (address, phone number, name, age)
    - travel plans (destinations, dates, activities)  # Added line
    
    NOT important:
    - Temporary emotional states
    - Technical discussions
    - Casual conversation
    
    Return ONLY 'IMPORTANT' or 'NOT_IMPORTANT'
    
    Examples:
    "I got promoted" → IMPORTANT
    "My dog died" → IMPORTANT
    "I am working on a project" → IMPORTANT
    "This code is buggy" → NOT_IMPORTANT
    "I'm feeling sad today" → NOT_IMPORTANT
    
    Message: "{text}"
    """
    try:
        response = model.generate_content(prompt)
        classification = response.text.strip().upper().replace(".", "")
        print(f"[Debug] Classified '{text[:20]}...' as {classification}")
        return classification == "IMPORTANT"
    except Exception as e:
        print(f"Classification error: {e}")
        return False

class ConversationManager:
    def __init__(self):
        self.session_memory = []
        self.current_topic = None
        self.current_subtopic = None
        self.topic_history = []
        self.user_mood = "neutral"
        self.session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.user_name = None
        self.current_project = None
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def _analyze_mood(self, text):
        """Real-time mood analysis with history context"""
        mood_prompt = f"""Analyze the emotional state through this conversation:
        Previous messages: {[msg['text'] for msg in self.session_memory[-3:]]}
        Latest message: "{text}"
        
        Detect CURRENT mood from: happy, sad, angry, anxious, neutral
        Return ONLY the mood word:"""
        try:
            response = model.generate_content(mood_prompt)
            self.user_mood = response.text.strip().lower()
            print(f"[Debug] Mood detected: {self.user_mood}")
        except:
            self.user_mood = "neutral"
    
    def _store_memory(self, text):
        """Enhanced memory storage with entity detection"""
        # Directly store names and projects
        if "my name is" in text.lower():
            self.user_name = text.split("is")[-1].strip()
        if "working on" in text.lower() or "project" in text.lower():
            self.current_project = text
        
        try:
            self.cursor.execute(
                """INSERT INTO history 
                (important_message, session_id) VALUES (?,?)""",
                (text, self.session_id)
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"[System] Storage error: {e}")
            return False

    def _get_contextual_memories(self):
        """Retrieve memories with conversation context"""
        try:
            self.cursor.execute("""
                SELECT important_message FROM history
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """, (self.session_id,))
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"[System] Memory error: {e}")
            return []
        
    def _analyze_topic_flow(self, text):
        """Optimized single-call topic analysis"""
        if not text.strip():
            return None

        prompt = f"""Analyze this conversation flow and return:
        Flow Type (1-4) | New Topic (if 3) | New Subtopic (if 2/3)
        
        Previous: {self.current_topic or 'None'} - {self.current_subtopic or 'None'}
        New Message: "{text[:300]}"
        
        Options:
        1. Continue current topic+subtopic
        2. New subtopic (provide) under current topic
        3. Completely new topic (provide)
        4. Return to previous topic
        
        Format: "flow_type|new_topic|new_subtopic"
        Example: "3|Vacation plans|Beach destinations"
        
        Your analysis:"""
        
        try:
            response = model.generate_content(prompt)
            parts = response.text.strip().split('|')
            parts = [p.strip() for p in parts]
            
            # Ensure we have 3 components
            while len(parts) < 3:
                parts.append('None')
                
            flow_type = int(parts[0])
            new_topic = parts[1] if parts[1].lower() != 'none' else None
            new_subtopic = parts[2] if parts[2].lower() != 'none' else None

            if flow_type == 3:  # New topic
                if self.current_topic:
                    self.topic_history = [(self.current_topic, self.current_subtopic)] + self.topic_history[:2]
                self.current_topic = new_topic or "General discussion"
                self.current_subtopic = new_subtopic
                
            elif flow_type == 2:  # New subtopic
                self.current_subtopic = new_subtopic or None
                
            elif flow_type == 4 and self.topic_history:  # Return previous
                self.current_topic, self.current_subtopic = self.topic_history[0]
                self.topic_history = self.topic_history[1:]
                
            return flow_type
            
        except Exception as e:
            print(f"[Error] Topic analysis failed: {e}")
            return None
    
    def process_message(self, text):
        # Force-store critical information
        if any(keyword in text.lower() for keyword in ["my name is", "i'm called", "call me"]):
            strict_importance_classifier(text)
            self._store_memory(text)
        elif any(keyword in text.lower() for keyword in ["project", "working on", "developing"]):
            strict_importance_classifier(text)
            self._store_memory(text)
        else:
            if strict_importance_classifier(text):
                self._store_memory(text)
        
        self._analyze_mood(text)
        self._analyze_topic_flow(text)
        if not self.current_topic:
            self.current_topic = "Initial conversation"
            
        self.session_memory.append({
            "text": text,
            "mood": self.user_mood,
            "time": datetime.now().strftime("%H:%M")
        })
        if len(self.session_memory) > 15:
            self.session_memory.pop(0)

    def generate_response(self, user_input):
        self.process_message(user_input)
    
        context = {
            "current_mood": self.user_mood,
            "last_3_moods": [msg["mood"] for msg in self.session_memory[-3:]],
            "memories": self._get_contextual_memories(),
            "user_name": self.user_name,
            "project": self.current_project,
            "history": [msg["text"] for msg in self.session_memory[-9:]],
            # NEW: Add topic context
            "current_topic": self.current_topic,
            "current_subtopic": self.current_subtopic,
            "topic_history": self.topic_history[-3:]  # Last 3 topic changes
        }
    
        response_prompt = f"""You're an empathetic friend. Respond considering:
        CURRENT TOPIC: {context['current_topic']}
        {"CURRENT SUBTOPIC: " + context['current_subtopic'] if context['current_subtopic'] else ""}
        MOOD: {context['current_mood']}
        USER NAME: {context['user_name'] or 'Not provided'}
        
        Response rules:
        1. Stay focused on current topic{" and subtopic" if context['current_subtopic'] else ""}
        2. Acknowledge mood naturally
        3. Use name if known (but not forced)
        4. Keep responses 1-2 sentences
        5. Never say "as we discussed" or similar
        
        Craft response for: "{user_input}"
        Response:"""
        
        try:
            response = model.generate_content(response_prompt)
            return response.text
        except Exception as e:
            print(f"[System] Response error: {e}")
            return "Let me think differently about that. Could you elaborate?"

def main_chat_loop():
    print("""
    ====================================
    Empathic Chat Assistant (v5.0)
    Commands:
    - 'exit' to end
    - 'reset' to clear history
    ====================================
    """)
    
    initialize_database()
    
    bot = ConversationManager()
    
    try:
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() == 'exit':
                print("\nBot: Our conversation is saved. Until next time!")
                break
                
            if user_input.lower() == 'reset':
                bot = ConversationManager()
                print("\nBot: Fresh start! Previous session cleared.\n")
                continue
            temp = bot._analyze_topic_flow(user_input)    
            response = bot.generate_response(user_input)
            print(f"[Debug] flow type: {temp}")
            print(f"\nBot: {response}\n")
            
    except KeyboardInterrupt:
        print("\n\nBot: Session saved. Come back anytime!")
    finally:
        if hasattr(bot, 'conn'):
            bot.conn.close()

if __name__ == "__main__":
    main_chat_loop()