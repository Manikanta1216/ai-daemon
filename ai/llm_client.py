"""
JARVIS AI — LLM Client (Upgraded)
Provides unified access to Groq (Llama 3 / Mixtral) and Google Gemini APIs.
Falls back gracefully if one provider is unavailable.

NEW in v2:
  - _offline_fallback now distinguishes chat vs intent mode
  - Chat mode NEVER returns JSON — always plain text
  - Expanded offline knowledge base
  - Better JSON parsing recovery
"""

import json
import logging
import requests

logger = logging.getLogger("jarvis.ai")


class LLMClient:
    """
    Unified LLM interface.
    Supports Groq REST API and Google Generative AI (Gemini).
    """

    def __init__(self):
        from config import (
            LLM_PROVIDER, GROQ_API_KEY, GROQ_MODEL,
            GEMINI_API_KEY, GEMINI_MODEL,
        )
        self.provider = LLM_PROVIDER
        self.groq_key = GROQ_API_KEY
        self.groq_model = GROQ_MODEL
        self.gemini_key = GEMINI_API_KEY
        self.gemini_model = GEMINI_MODEL
        self._gemini_genai = None

        # Validate at least one key exists
        if not self.groq_key and not self.gemini_key:
            logger.warning(
                "No LLM API key configured. Set GROQ_API_KEY or GEMINI_API_KEY in .env"
            )

    # ====================================================
    # PUBLIC API
    # ====================================================

    def chat(self, prompt: str, system: str = None) -> str:
        """Send a chat prompt and return the response text."""
        if self.provider == "groq" and self.groq_key:
            return self._groq_chat(prompt, system)
        elif self.provider == "gemini" and self.gemini_key:
            return self._gemini_chat(prompt, system)
        elif self.groq_key:
            return self._groq_chat(prompt, system)
        elif self.gemini_key:
            return self._gemini_chat(prompt, system)
        else:
            # Check if this is an intent analysis call or chat call
            if system and "intent" in system.lower() and "json" in system.lower():
                return self._offline_intent_fallback(prompt)
            return self._offline_chat_response(prompt)

    def analyze_intent(self, command: str) -> dict:
        """
        Analyze user command and return structured intent.
        Returns: {"intent": str, "entities": dict, "confidence": float}
        """
        system_prompt = """You are JARVIS, an AI assistant intent analyzer.
Analyze the user's command and return ONLY valid JSON with these fields:
{
    "intent": "<one of: open_app, open_website, search, send_email, send_whatsapp, play_media, system_control, file_operation, get_info, weather, screenshot, volume_control, brightness, set_timer, chat, unknown>",
    "entities": {
        "app": "<application name if applicable>",
        "url": "<url if applicable>",
        "query": "<search query if applicable>",
        "recipient": "<email/phone if applicable>",
        "subject": "<email subject if applicable>",
        "body": "<message body if applicable>",
        "action": "<specific action like shutdown, restart, lock, sleep, mute, volume_up, volume_down>",
        "filename": "<file/folder name if applicable>",
        "target": "<target of action>"
    },
    "confidence": <0.0-1.0>,
    "task_plan": ["<step 1>", "<step 2>", "..."]
}
Only include entity fields that are relevant. Remove null/empty fields."""

        response = self.chat(command, system=system_prompt)
        return self._parse_json_response(response)

    def extract_entities(self, command: str) -> dict:
        """Extract named entities from a command string."""
        result = self.analyze_intent(command)
        return result.get("entities", {})

    def generate_task_plan(self, command: str) -> list:
        """Generate a step-by-step task plan for a command."""
        result = self.analyze_intent(command)
        return result.get("task_plan", [command])

    def chat_response(self, command: str) -> str:
        """Generate a conversational response (ALWAYS returns plain text, NEVER JSON)."""
        system = (
            "You are JARVIS, a helpful AI desktop assistant. "
            "Be concise, friendly, and direct. Keep responses under 3 sentences. "
            "IMPORTANT: Respond in plain natural language only. "
            "Do NOT return JSON, code blocks, or structured data."
        )
        if self.provider == "groq" and self.groq_key:
            try:
                return self._groq_chat(command, system=system)
            except Exception:
                pass
        if self.gemini_key:
            try:
                return self._gemini_chat(command, system=system)
            except Exception:
                pass
        if self.groq_key:
            try:
                return self._groq_chat(command, system=system)
            except Exception:
                pass
        # All LLMs failed — use offline chat responses
        return self._offline_chat_response(command)

    # ====================================================
    # GROQ (REST API — no SDK needed)
    # ====================================================

    def _groq_chat(self, prompt: str, system: str = None) -> str:
        """Call Groq API via REST."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API error: {e}")
            # Fallback to Gemini
            if self.gemini_key:
                logger.info("Falling back to Gemini...")
                return self._gemini_chat(prompt, system)
            # Check mode for offline fallback
            if system and "intent" in system.lower() and "json" in system.lower():
                return self._offline_intent_fallback(prompt)
            return self._offline_chat_response(prompt)

    # ====================================================
    # GEMINI (google-generativeai SDK)
    # ====================================================

    def _gemini_chat(self, prompt: str, system: str = None) -> str:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai

            if self._gemini_genai is None:
                genai.configure(api_key=self.gemini_key)
                self._gemini_genai = genai

            model = self._gemini_genai.GenerativeModel(
                self.gemini_model,
                system_instruction=system if system else None,
            )
            response = model.generate_content(prompt)
            return response.text.strip()

        except ImportError:
            logger.warning("google-generativeai not installed, using REST fallback")
            return self._gemini_rest(prompt, system)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            if self.groq_key:
                return self._groq_chat(prompt, system)
            if system and "intent" in system.lower() and "json" in system.lower():
                return self._offline_intent_fallback(prompt)
            return self._offline_chat_response(prompt)

    def _gemini_rest(self, prompt: str, system: str = None) -> str:
        """Gemini REST fallback (no SDK needed)."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_key}"
        )
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Gemini REST error: {e}")
            if system and "intent" in system.lower() and "json" in system.lower():
                return self._offline_intent_fallback(prompt)
            return self._offline_chat_response(prompt)

    # ====================================================
    # OFFLINE FALLBACK — INTENT MODE (returns JSON string)
    # ====================================================

    def _offline_intent_fallback(self, prompt: str) -> str:
        """
        Offline fallback for intent analysis only.
        Returns JSON string suitable for analyze_intent parsing.
        """
        logger.warning("LLM unavailable — using offline fallback (intent mode)")
        prompt_lower = prompt.lower()

        intent_map = {
            "open": "open_app",
            "search": "search",
            "email": "send_email",
            "whatsapp": "send_whatsapp",
            "play": "play_media",
            "screenshot": "screenshot",
            "weather": "weather",
            "volume": "volume_control",
            "shutdown": "system_control",
            "restart": "system_control",
            "time": "get_info",
            "date": "get_info",
            "battery": "get_info",
        }

        detected_intent = "chat"
        for keyword, intent in intent_map.items():
            if keyword in prompt_lower:
                detected_intent = intent
                break

        result = {
            "intent": detected_intent,
            "entities": {"query": prompt},
            "confidence": 0.4,
            "task_plan": [prompt],
        }
        return json.dumps(result)

    # ====================================================
    # OFFLINE CHAT RESPONSES (natural language — NEVER JSON)
    # ====================================================

    # Curated Q/A pairs for when no LLM is available
    OFFLINE_QA = {
        # General knowledge
        "who is the ceo of google": "The CEO of Google is Sundar Pichai.",
        "who is the ceo of microsoft": "The CEO of Microsoft is Satya Nadella.",
        "who is the ceo of apple": "The CEO of Apple is Tim Cook.",
        "who is the ceo of amazon": "The CEO of Amazon is Andy Jassy.",
        "who is the ceo of tesla": "The CEO of Tesla is Elon Musk.",
        "who is the ceo of meta": "The CEO of Meta is Mark Zuckerberg.",
        "who is the president of india": "The President of India is Droupadi Murmu.",
        "who is the prime minister of india": "The Prime Minister of India is Narendra Modi.",

        # Science
        "what is chandra grahan": "Chandra Grahan, or Lunar Eclipse, occurs when the Earth comes between the Sun and the Moon, blocking sunlight from reaching the Moon. The Moon appears reddish-brown during a total lunar eclipse.",
        "what is solar eclipse": "A solar eclipse occurs when the Moon passes between the Sun and the Earth, blocking the Sun's light. There are total, partial, and annular solar eclipses.",
        "what is gravity": "Gravity is a fundamental force that attracts objects with mass toward each other. On Earth, it gives weight to physical objects and causes objects to fall toward the ground.",
        "what is black hole": "A black hole is a region of spacetime where gravity is so strong that nothing, not even light, can escape from it. They form when massive stars collapse at the end of their lives.",
        "what is dna": "DNA, or deoxyribonucleic acid, is the molecule that carries the genetic instructions for all living organisms. It has a double helix structure.",

        # Technology
        "what is python": "Python is a popular, versatile programming language known for its readability and wide range of applications in web development, AI, data science, and automation.",
        "what is ai": "AI, or Artificial Intelligence, refers to computer systems designed to perform tasks that typically require human intelligence, like understanding language, recognizing images, and making decisions.",
        "what is machine learning": "Machine Learning is a subset of AI where systems learn from data to improve their performance without being explicitly programmed.",
        "what is blockchain": "Blockchain is a decentralized digital ledger technology that records transactions across multiple computers, making it secure and transparent.",
        "what is cloud computing": "Cloud computing is the delivery of computing services like storage, servers, and software over the internet, allowing on-demand access without owning physical hardware.",
        "what is iot": "IoT, or Internet of Things, refers to the network of physical devices connected to the internet that can collect and exchange data.",

        # Geography
        "andhra": "Andhra refers to Andhra Pradesh, a state in southeastern India. Its capital is Amaravati.",
        "andhra pradesh": "Andhra Pradesh is a state in southeastern India with its capital at Amaravati. It is known for its rich cultural heritage.",
        "telangana": "Telangana is a state in southern India with Hyderabad as its capital.",
        "hyderabad": "Hyderabad is the capital city of Telangana, India. It is known for its historic Charminar and IT industry.",
        "india": "India is the largest country in South Asia with a population of over 1.4 billion people. Its capital is New Delhi.",

        # Greetings
        "hello": "Hello! How can I help you today?",
        "hi": "Hi there! What can I do for you?",
        "hey": "Hey! How can I assist you?",
        "good morning": "Good morning! Hope you're having a great day. How can I help?",
        "good afternoon": "Good afternoon! What can I do for you?",
        "good evening": "Good evening! How can I assist you?",
        "good night": "Good night! Have a restful sleep.",
        "how are you": "I'm doing great, thank you for asking! How can I help you?",
        "what is your name": "I am JARVIS, your personal AI assistant.",
        "who are you": "I am JARVIS — Just A Rather Very Intelligent System. I'm here to help you.",
        "thank you": "You're welcome! Is there anything else I can help with?",
        "thanks": "You're welcome! Let me know if you need anything else.",

        # General
        "what can you do": "I can open apps, search the web, send messages, play media, control system settings, and have conversations. Just ask!",
        "help": "I can help with opening apps, web searches, messaging, media playback, and system controls. What would you like to do?",
        "who made you": "I was created as JARVIS, inspired by the AI assistant from Iron Man. I'm your personal desktop assistant.",
        "what is the meaning of life": "That's a deep philosophical question! Many would say it's about finding purpose, happiness, and making a positive impact on others.",
    }

    def _offline_chat_response(self, prompt: str) -> str:
        """Return a natural language response using the offline Q/A dictionary."""
        logger.info("Using offline chat response")
        prompt_lower = prompt.lower().strip()

        # 1. Try exact match first (after removing common punctuation)
        clean_prompt = prompt_lower.rstrip('?!. ')
        if clean_prompt in self.OFFLINE_QA:
            return self.OFFLINE_QA[clean_prompt]

        # 2. Try prefix matching
        for prefix in ["tell me ", "what is ", "who is ", "what are ", "explain "]:
            if prompt_lower.startswith(prefix):
                query = prompt_lower[len(prefix):].strip().rstrip('?!. ')
                # Check for exact query in values or partial keys
                if query in self.OFFLINE_QA:
                    return self.OFFLINE_QA[query]
                # Check if query is part of a key (e.g. "ceo of google" in "who is the ceo of google")
                for key, answer in self.OFFLINE_QA.items():
                    if query in key and len(query) > 5:
                        return answer

        # 3. Best substring match
        best_match = None
        best_length = 0
        for key, answer in self.OFFLINE_QA.items():
            if key in clean_prompt and len(key) > best_length:
                best_match = answer
                best_length = len(key)
        
        if best_match and best_length > len(clean_prompt) * 0.7:
            return best_match

        # 4. Word overlap with high threshold
        prompt_words = set(clean_prompt.split())
        if not prompt_words: return "I'm listening."
        
        best_overlap_pct = 0
        best_answer = None
        
        for key, answer in self.OFFLINE_QA.items():
            key_words = set(key.split())
            overlap = len(prompt_words & key_words)
            overlap_pct = overlap / len(key_words)
            
            # Require at least 60% overlap and at least 2 words
            if overlap >= 2 and overlap_pct > best_overlap_pct and overlap_pct >= 0.6:
                best_overlap_pct = overlap_pct
                best_answer = answer

        if best_answer:
            return best_answer

        # 5. Very basic fallback keywords
        if "time" in clean_prompt:
            import datetime
            return f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."
        if "date" in clean_prompt:
            import datetime
            return f"Today is {datetime.datetime.now().strftime('%B %d, %Y')}."
        if any(w in clean_prompt for w in ["hello", "hi", "hey"]):
            return "Hello! How can I help you today?"

        return (
            "I don't have detailed information on that right now, "
            "but I can help you search the web for it. "
            "Just say 'search' followed by your question."
        )

    # ====================================================
    # HELPERS
    # ====================================================

    def _parse_json_response(self, response: str) -> dict:
        """Safely parse JSON from LLM response."""
        try:
            # Try direct parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        if "```json" in response:
            start = response.index("```json") + 7
            end = response.index("```", start)
            try:
                return json.loads(response[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

        if "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            try:
                return json.loads(response[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # Try finding JSON object in response
        brace_start = response.find("{")
        brace_end = response.rfind("}") + 1
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(response[brace_start:brace_end])
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse LLM JSON response: {response[:200]}")
        return {
            "intent": "chat",
            "entities": {"query": response},
            "confidence": 0.3,
            "task_plan": [],
        }


# ============================================
# SINGLETON
# ============================================
_client = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
