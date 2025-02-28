import os
from flask import Flask, jsonify, request, session  # new import for session management
from flask_cors import CORS
import pandas as pd
import random
from geopy.geocoders import Nominatim
from fuzzywuzzy import process
import numpy as np
import math  # new import
from functools import lru_cache  # new import
import re  # new import for regular expression escaping
from openai_hint import generate_hint  # New import
from dotenv import load_dotenv
load_dotenv()  # Add this near the top of the file, after imports

DEBUG = False  # disable debug logs in production

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

app = Flask(__name__)
app.secret_key = "c183e021456dbfa985bb56650b28ecc490cd8f5bbcb0b8ce"  # new secret key for session usage
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5000",
            "https://oskaripsen.github.io",  # Make sure this matches exactly
            "https://oskaripsen.github.io/energy-game-UI",  # Add with path
            "https://oskaripsen.github.io/energy-game-UI/"  # Add with trailing slash
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Simple in-memory storage
current_game = {
    'country': None,
    'data': None
}

# Update CSV path handling
CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'owid-energy-data.csv')

# Load data
df = pd.read_csv(CSV_PATH)

# Load hardcoded coordinates CSV once at module level
COORDINATES_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'coordinates_all_countries.csv')
if not os.path.exists(COORDINATES_CSV):
    raise FileNotFoundError(f"File not found: {COORDINATES_CSV}. Please run collect_coordinates.py to generate it.")
coords_df = pd.read_csv(COORDINATES_CSV)
COUNTRY_COORDINATES = {row['country']: (float(row['latitude']), float(row['longitude'])) for _, row in coords_df.iterrows() if pd.notna(row['latitude']) and pd.notna(row['longitude'])}

# Helper functions
def get_country_coordinates(country):
    # Only return coordinates for an exact match
    coords = COUNTRY_COORDINATES.get(country)
    if coords is None:
        debug_print(f"No exact match found for {country}")
        return None
    try:
        lat, lon = float(coords[0]), float(coords[1])
        debug_print(f"get_country_coordinates for {country}: ({lat, lon})")
        return (lat, lon)
    except Exception as e:
        debug_print(f"Error casting coordinates for {country}: {e}")
        return None

def haversine_distance(coord1, coord2):
    # Coordinates in decimal degrees (lat, lon)
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    # convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    # haversine formula 
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) 
    r = 6371 # Radius of Earth in kilometers
    return c * r

def get_direction_hint(guess_coords, correct_coords):
    # Validate returned coordinates
    coord1 = validate_coordinates_from_coords(guess_coords)
    coord2 = validate_coordinates_from_coords(correct_coords)
    # Using bearing calculation for precision.
    bearing = get_bearing(coord1, coord2)
    cardinal = get_cardinal(bearing)
    distance = haversine_distance(coord1, coord2)
    debug_print(f"Bearing: {bearing:.2f}°, Direction: {cardinal}, Distance: {distance:.0f} km")
    return cardinal, distance

def get_best_match(user_input, country_list):
    match, score = process.extractOne(user_input, country_list)
    return match if score > 80 else None

def filter_countries(df):
    exclusions = [
        "World", "Europe", "Asia", "Africa", "OECD", "G20", "G7",
        "Non-OECD", "OPEC", "Middle East", "North America", "South America",
        "Central America", "Ember", "EIA", "EI", "Oceania", "Lower-middle-income countries",
        "Latin America and Caribbean (Ember)", "Low-income countries", "Palestine", 
        "Niue", "Antarctica", "High-income countries", "Netherlands Antilles", "Upper-middle-income countries"
    ]
    pattern = "|".join([re.escape(exclusion) for exclusion in exclusions])
    return df[~df['country'].str.contains(pattern, na=False)]

def get_random_country_energy():
    debug_print("Available columns:", df.columns.tolist())  # Debug print
    
    df_year = df[df['year'] == 2020]
    df_year = filter_countries(df_year)
    
    # Update column names to match the CSV file with new values
    energy_columns = [
        'country',
        'electricity_generation',
        'coal_electricity',
        'gas_electricity',
        'oil_electricity',
        'hydro_electricity',
        'nuclear_electricity',
        'solar_electricity',
        'wind_electricity',
        'biofuel_electricity',
        'other_renewable_electricity',  # new column added
    ]
    
    # Check that all required columns exist
    available_columns = df_year.columns.tolist()
    for col in energy_columns:
        if col not in available_columns:
            debug_print(f"Missing column: {col}")
    
    # Drop rows where electricity_generation is 0.000
    df_year = df_year[df_year['electricity_generation'] != 0.000]
    df_year = df_year[energy_columns]
    df_year = df_year.dropna(subset=['electricity_generation'])
    
    random_country = random.choice(df_year['country'].dropna().unique())
    country_data = df_year[df_year['country'] == random_country].iloc[0].to_dict()
    
    # Prepare the cleaned data for the frontend with updated column names
    # Compute Other Renewables = other_renewable_electricity - biofuel_electricity
    double_val = (
        (float(country_data['other_renewable_electricity']) if pd.notna(country_data['other_renewable_electricity']) else 0)
        - (float(country_data['biofuel_electricity']) if pd.notna(country_data['biofuel_electricity']) else 0)
    )
    other_renewables = max(0, double_val)
    
    cleaned_data = {
        'country': str(country_data['country']),
        # Use the original "electricity_generation" from the CSV
        'electricity_generation': float(country_data['electricity_generation']),
        'electricity_shares': {
            'Coal': float(country_data['coal_electricity'] if pd.notna(country_data['coal_electricity']) else 0),
            'Gas': float(country_data['gas_electricity'] if pd.notna(country_data['gas_electricity']) else 0),
            'Oil': float(country_data['oil_electricity'] if pd.notna(country_data['oil_electricity']) else 0),
            'Hydro': float(country_data['hydro_electricity'] if pd.notna(country_data['hydro_electricity']) else 0),
            'Nuclear': float(country_data['nuclear_electricity'] if pd.notna(country_data['nuclear_electricity']) else 0),
            'Solar': float(country_data['solar_electricity'] if pd.notna(country_data['solar_electricity']) else 0),
            'Wind': float(country_data['wind_electricity'] if pd.notna(country_data['wind_electricity']) else 0),
            'Biofuel': float(country_data['biofuel_electricity'] if pd.notna(country_data['biofuel_electricity']) else 0),
            'Geothermal': other_renewables,
        }
    }

    return cleaned_data['country'], cleaned_data

@lru_cache(maxsize=1)
def get_available_countries():
    """Get filtered list of valid countries"""
    df_year = df[df['year'] == 2020]
    df_year = filter_countries(df_year)
    return sorted(df_year['country'].unique().tolist())

@app.route('/debug/countries', methods=['GET'])
def list_countries():
    """Debug endpoint to view all available countries"""
    countries = get_available_countries()
    debug_print("Available countries:", countries)
    return jsonify({
        "count": len(countries),
        "countries": countries
    })

# Modified get_country_suggestions to use the same filtered list
def get_country_suggestions(prefix):
    if not prefix:
        return []
    valid_countries = get_available_countries()  # Use filtered list
    matching = [
        country for country in valid_countries 
        if country.lower().startswith(prefix.lower())
    ]
    return sorted(matching)[:3]

@app.route('/suggestions', methods=['GET'])
def suggestions():
    prefix = request.args.get('prefix', '')
    suggestions = get_country_suggestions(prefix)
    return jsonify(suggestions)

# API Endpoints
@app.route('/start_game', methods=['GET'])
def start_game():
    debug_print("Start game endpoint called")
    # Use session to isolate game state per user.
    session['guesses'] = []
    # Select and validate a target country.
    country, country_data = get_random_country_energy()  # existing random selection
    session['target_country'] = country  # Save target in session
    # Remove the country from the data to hide actual answer
    if 'country' in country_data:
        del country_data['country']
    debug_print(f"Selected country: {country}")
    return jsonify({
        "energy_data": country_data,
        "message": "Guess the country!"
    })

def is_valid_country(country):
    """Check if country is in the filtered list"""
    if not country:
        return False
    valid_countries = get_available_countries()  # Use same filtered list
    return country in valid_countries

# NEW: Coordinate validation helper
def validate_coordinates(country: str):
    coords = get_country_coordinates(country)
    if coords is None:
        raise ValueError(f"Coordinates not found for {country}")
    lat, lon = coords
    assert -90 <= lat <= 90, f"Invalid latitude for {country}"
    assert -180 <= lon <= 180, f"Invalid longitude for {country}"
    return (lat, lon)

# NEW: Bearing calculation helper
def get_bearing(coord1, coord2):
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)
    delta_lon = lon2 - lon1
    x = math.sin(delta_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360

def get_cardinal(bearing_degrees):
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    return directions[round(bearing_degrees / 45) % 8]

# Helper to ensure coordinates are tuples from validate_coordinates if already valid.
def validate_coordinates_from_coords(coords):
    if coords is None:
        return (0, 0)
    lat, lon = coords
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordinate out of bounds.")
    return (lat, lon)

@app.route('/guess', methods=['POST'])
def guess():
    try:
        debug_print("Guess endpoint called")
        correct_country = session.get('target_country')
        if not correct_country:
            return jsonify({
                "message": "No active game session. Please start a new game.",
                "error": True
            }), 400
        data = request.get_json()
        if not data or 'guess' not in data:
            return jsonify({
                "message": "Invalid guess format",
                "error": True,
                "target": correct_country
            }), 400
        user_guess = data['guess']
        if 'guesses' not in session:
            session['guesses'] = []
        if any(user_guess.lower() == g.lower() for g in session['guesses']):
            return jsonify({
                "message": "Country already guessed. Please select a new country.",
                "error": True,
                "target": correct_country
            }), 400
        session['guesses'].append(user_guess)
        session.modified = True
        if not is_valid_country(user_guess):
            return jsonify({
                "message": "Invalid country. Please select from the suggestions.",
                "error": True,
                "target": correct_country
            }), 400
        
        guess_coords = get_country_coordinates(user_guess)
        correct_coords = get_country_coordinates(correct_country)
        if guess_coords and correct_coords:
            hint, distance = get_direction_hint(guess_coords, correct_coords)
            if hint == "Correct":
                return jsonify({
                    "message": "Correct! You've guessed the country!",
                    "target": correct_country,
                    "game_over": True
                })
            else:
                return jsonify({
                    "message": f"Try looking {hint}. Distance: {distance:,.0f} km.",
                    "target": correct_country,
                    "game_over": False
                })
        else:
            return jsonify({
                "message": "Unable to determine direction. Please try another country.",
                "target": correct_country,
                "game_over": False
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        debug_print(f"Error in /guess endpoint: {e}")
        return jsonify({
            "message": "An unexpected error occurred.",
            "error": True,
            "detail": str(e)
        }), 500

@app.route('/hint', methods=['GET'])
def hint():
    guess = request.args.get('guess', '').strip()
    correct_country = session.get('target_country')
    if not correct_country:
        return jsonify({"message": "No active game session."}), 400
    if not guess:
        guess = f"Provide a hint on {correct_country}"
    debug_print(f"Using prompt: {guess}")
    ai_hint = generate_hint(guess, correct_country)
    debug_print(f"Generated hint: {ai_hint}")
    return jsonify({"message": ai_hint})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)