import google.generativeai as genai
import sqlite3
from datetime import datetime
# from gtts import gTTS
# from playsound import playsound
# import os
import edge_tts
import asyncio
from playsound import playsound
import os
from html import escape

# Initialize Gemini
genai.configure(api_key="AIzaSyCulA1fueRA6AyDjjg7Yvwu4b05Z4_gyU8")
model = genai.GenerativeModel("gemini-2.0-flash")

# Database setup
DB_PATH = "chat_history.db"

# def speak(text):
#     """Convert text to speech with fast, natural-sounding voice"""
#     try:
#         # Use British English for more formal accent (can change to 'com' for American)
#         tts = gTTS(text=text, lang='en', tld='co.uk', slow=False)
        
#         # Save temporary audio file
#         audio_file = "temp_response.mp3"
#         tts.save(audio_file)
        
#         # Play the audio with cleaned-up delay
#         playsound(audio_file)
        
#         # Remove temporary file
#         os.remove(audio_file)
#     except Exception as e:
#         print(f"TTS Error: {e}")

async def generate_speech(text):
    """Generate natural-sounding speech using Edge TTS"""
    try:
        communicate = edge_tts.Communicate(text, "en-AU-NatashaNeural", rate="+20%")
        
        # Set output file
        output_file = "response.mp3"
        
        # Save audio with proper async handling
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# async def generate_speech(text):
#     """Generate natural-sounding speech with SSML processing"""
#     try:
#         ssml_text = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"><voice name="en-US-AriaNeural"><prosody rate="+15%" pitch="+5%">{text}</prosody></voice></speak>"""
#         # Reintroduce the voice parameter and add raw=True to indicate SSML input.
#         communicate = edge_tts.Communicate(
#             text=ssml_text,
#             voice="en-US-AriaNeural",
#             receive_timeout=30
#         ) 
#         output_file = "response.mp3"
#         await communicate.save(output_file)
#         return output_file
#     except Exception as e:
#         print(f"TTS Error: {e}")
#         return None


def speak(text):
    """Async wrapper for speech generation"""
    audio_file = asyncio.run(generate_speech(text))
    if audio_file:
        playsound(audio_file)
        os.remove(audio_file)

def initialize_database():
    """Initialize database with proper connection handling"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Remove user_info table and modify history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                user_id TEXT DEFAULT 'main_user',
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
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
    - travel plans (destinations, dates, activities)
    
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
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def _analyze_mood(self, text):
        """Real-time mood analysis with history context"""
        mood_prompt = f"""Analyze the emotional state through this conversation:
        These are the Previous messages: {[msg['text'] for msg in self.session_memory[-3:] if msg['sender'] == 'user']}
        This is the Latest message: "{text}"
        
        Detect CURRENT mood from: happy, sad, angry, anxious, neutral, curious, excited, bored, confused, or any other relevant mood.
        Return ONLY the mood word:"""
        try:
            response = model.generate_content(mood_prompt)
            self.user_mood = response.text.strip().lower()
            print(f"[Debug] Mood detected: {self.user_mood}")
        except:
            self.user_mood = "neutral"
    
    def _store_memory(self, text):
        """Enhanced memory storage with structured data"""
        try:
            # Extract structured information
            extraction_prompt = f"""Extract structured information from this message:
            "{text}"
            
            Return as:
            category|key|value
            
            Examples:
            "My name is Ammar" → personal_info|name|Ammar
            "I love pasta more than noodles" → preference|food|pasta > noodles
            "I'm working on a project about AI" → project|current|AI
            "I'm traveling to Paris next week" → travel_plan|destination|Paris
            """
            response = model.generate_content(extraction_prompt)
            parts = response.text.strip().split("|")
            if len(parts) == 3:
                category, key, value = parts
                self.cursor.execute(
                    """INSERT INTO history 
                    (category, key, value, session_id) VALUES (?,?,?,?)""",
                    (category, key, value, self.session_id)
                )
                self.conn.commit()
                return True
        except Exception as e:
            print(f"[System] Memory extraction error: {e}")
        return False

    def _get_contextual_memories(self):
        """Retrieve structured memories with conversation context"""
        try:
            self.cursor.execute("""
                SELECT category, key, value FROM history
                ORDER BY timestamp DESC
                LIMIT 15
            """)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"[System] Memory error: {e}")
            return []
        
    def _analyze_topic_flow(self, text):
        """Analyze conversation flow to detect topic changes"""
        if not text.strip():
            return
            
        prompt = f"""Analyze this conversation flow:
        Previous Topic: {self.current_topic or 'None'}
        Previous Subtopic: {self.current_subtopic or 'None'}
        New Message: "{text}"
        
        Should we:
        1. Continue current topic+subtopic
        2. New subtopic under current topic
        3. Completely new topic
        4. Return to previous topic
        
        Return ONLY the number:"""
        
        try:
            response = model.generate_content(prompt)
            flow_type = int(response.text.strip())
            
            if flow_type == 3:  # New main topic
                if self.current_topic:
                    self.topic_history.append((self.current_topic, self.current_subtopic))
                    if len(self.topic_history) > 3:
                        self.topic_history.pop(0) # del self.topic_history[0:2] can be used to remove first two elements
                
                new_topic_prompt = f"""What is the main topic of this message? 
                Return 3-5 words: "{text}" """
                self.current_topic = model.generate_content(new_topic_prompt).text.strip()
                self.current_subtopic = None
                
            elif flow_type == 2:  # New subtopic
                subtopic_prompt = f"""What specific aspect is this about? 
                Current Topic: {self.current_topic}
                Message: "{text}"
                Return 2-3 words:"""
                self.current_subtopic = model.generate_content(subtopic_prompt).text.strip()
                
            elif flow_type == 4:  # Return to previous topic
                if self.topic_history:
                    self.current_topic, self.current_subtopic = self.topic_history.pop()
                    
            return flow_type
        except Exception as e:
            print(f"[Debug] Topic analysis error: {e}")
            return 1

    def process_message(self, text):
        """Process and store user message"""
        if strict_importance_classifier(text):
            self._store_memory(text)
        
        self._analyze_mood(text)
        self._analyze_topic_flow(text)
        if not self.current_topic:
            self.current_topic = "Initial conversation"
            
        self.session_memory.append({
            "text": text,
            "mood": self.user_mood,
            "time": datetime.now().strftime("%H:%M"),
            "sender": "user"
        })
        if len(self.session_memory) > 15:
            self.session_memory.pop(0)

    def generate_response(self, user_input):
        """Generate and store bot response"""
        self.process_message(user_input)
    
        # Get relevant structured memories
        structured_memories = self._get_contextual_memories()
        memory_context = []
        used_categories = set()
        
        # Automatically include relevant memories without repetition
        for category, key, value in structured_memories:
            if category not in used_categories:
                memory_context.append(f"{category.replace('_', ' ')}: {value}")
                used_categories.add(category)
        
        context = {
            "current_mood": self.user_mood,
            "history": [msg["text"] for msg in self.session_memory[-5:]],
            "current_topic": self.current_topic,
            "current_subtopic": self.current_subtopic,
            "memories": "\n".join(memory_context) if memory_context else "None"
        }
    
        response_prompt = f"""you are my personal humanoid bot but you have to act like: You're a caring and empathetic friend who is also helpful in conversations. 
        Your job is to either:
        - Continue the conversation naturally, OR
        - Answer direct questions if asked
        CURRENT TOPIC: {context['current_topic']}
        {"CURRENT SUBTOPIC: " + context['current_subtopic'] if context['current_subtopic'] else ""}
        This are PREVIOUS CONVERSATION with user: {context['history']}
        This is user MOOD: {context['current_mood']}
        This are users RELEVANT MEMORIES: {context['memories']}
        
        Response rules:
        1. Stay focused on current topic{" and subtopic" if context['current_subtopic'] else ""}
        2. Acknowledge mood naturally
        3. Keep responses 1-2 sentences
        4. Use memories and personal information ONLY if directly relevant
        5. Never repeat the same information multiple times
        6. Never say "as we discussed" or similar phrases
        
        Craft response for: "{user_input}"
        Response:"""
        
        try:
            response = model.generate_content(response_prompt)
            
            self.session_memory.append({
                "text": response.text,
                "mood": "bot",
                "time": datetime.now().strftime("%H:%M"),
                "sender": "bot"
            })
            if len(self.session_memory) > 15:
                self.session_memory.pop(0)
            
            return response.text
        except Exception as e:
            print(f"[System] Response error: {e}")
            return "Let me think differently about that. Could you elaborate?"

def main_chat_loop():
    print("""
    ====================================
    Empathic Chat Assistant (v6.0)
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
                speak("Our conversation is saved. Until next time!")
                print("\nBot: Our conversation is saved. Until next time!")
                break
                
            if user_input.lower() == 'reset':
                print("\nBot: Fresh start! Previous session cleared.\n")
                continue
                
            response = bot.generate_response(user_input)
            print(f"\nBot: {response}\n")
            
            # Add TTS output here
            speak(response)
            
    except KeyboardInterrupt:
        speak("Session saved. Come back anytime!")
        print("\n\nBot: Session saved. Come back anytime!")
    finally:
        if hasattr(bot, 'conn'):
            bot.conn.close()

if __name__ == "__main__":
    main_chat_loop()