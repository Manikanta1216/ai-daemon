import sys
import os
import win32com.client

print("Testing direct SAPI via win32com...")
try:
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    print("Speaker initialized.")
    
    # List voices
    voices = speaker.GetVoices()
    print(f"Number of voices: {voices.Count}")
    for i in range(voices.Count):
        print(f"Voice {i}: {voices.Item(i).GetDescription()}")
    
    print("Attempting to speak 'Hello, can you hear me?'...")
    speaker.Speak("Hello, can you hear me?")
    print("Speak command finished.")
except Exception as e:
    print(f"Error: {e}")
