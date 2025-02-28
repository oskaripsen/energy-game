import os
import openai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    openai.api_key = api_key
else:
    print("Warning: OPENAI_API_KEY not found in environment variables")

def generate_hint(guess: str, correct_country: str) -> str:
    """
    Generates a hint using the OpenAI ChatCompletion API.
    """
    if not openai.api_key:
        return "API key not configured. Please check environment variables."
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a hint generator for an energy game."},
                {"role": "user", "content": f"Generate a hint about {correct_country} without revealing its name directly. Focus on its energy production or geographic location."},
            ],
            temperature=0.7,
            max_tokens=50,
            n=1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error: {str(e)}")
        return "Unable to generate hint at this time."
