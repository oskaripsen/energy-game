import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import random
from geopy.geocoders import Nominatim
from fuzzywuzzy import process
import numpy as np
import math  # new import
from functools import lru_cache  # new import

DEBUG = False  # disable debug logs in production

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

app = Flask(__name__)
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
COUNTRY_COORDINATES = {row['country']: (row['latitude'], row['longitude']) for _, row in coords_df.iterrows()}

# Helper functions
def get_country_coordinates(country):
    coords = COUNTRY_COORDINATES.get(country)
    if coords:
        try:
            # cast values to float to ensure numerical operations work
            lat, lon = float(coords[0]), float(coords[1])
            debug_print(f"get_country_coordinates for {country}: ({lat}, lon)")
            return (lat, lon)
        except Exception as e:
            debug_print(f"Error casting coordinates for {country}: {e}")
            return None
    debug_print(f"get_country_coordinates for {country}: {coords}")
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
    # Calculate differences
    lat_diff = correct_coords[0] - guess_coords[0]  # Positive = target is North
    lon_diff = correct_coords[1] - guess_coords[1]  # Positive = target is East
    
    debug_print(f"Guessed coords: {guess_coords}")
    debug_print(f"Correct coords: {correct_coords}")
    debug_print(f"Lat diff: {lat_diff} (+ = North, - = South)")
    debug_print(f"Lon diff: {lon_diff} (+ = East, - = West)")

    # Determine primary direction based on which difference is larger
    if abs(lat_diff) > abs(lon_diff):
        primary = "North" if lat_diff > 0 else "South"
        secondary = "East" if lon_diff > 0 else "West"
        direction = f"{primary}-{secondary}" if lon_diff != 0 else primary
    else:
        primary = "East" if lon_diff > 0 else "West"
        secondary = "North" if lat_diff > 0 else "South"
        direction = f"{primary}-{secondary}" if lat_diff != 0 else primary

    distance = haversine_distance(guess_coords, correct_coords)  # use custom function
    debug_print(f"Final direction: {direction}, Distance: {distance:.2f} km")
    
    return direction, distance

def get_best_match(user_input, country_list):
    match, score = process.extractOne(user_input, country_list)
    return match if score > 80 else None

def filter_countries(df):
    exclusions = [
        "World", "Europe", "Asia", "Africa", "OECD", "G20", "G7",
        "Non-OECD", "OPEC", "Middle East", "North America", "South America",
        "Central America", "Ember", "EIA", "EI" , "Oceania", "Lower-middle-income countries", "Latin America and Caribbean (Ember)",
        "Low-income countries", "Antarctica" ,"High-income countries", "Netherlands Antilles", "Upper-middle-income countries"


    ]
    return df[~df['country'].str.contains('|'.join(exclusions), na=False)]

def get_random_country_energy():
    debug_print("Available columns:", df.columns.tolist())  # Debug print
    
    df_year = df[df['year'] == 2020]
    df_year = filter_countries(df_year)
    
    # Update column names to match the CSV file
    energy_columns = [
        'country',
        'primary_energy_consumption',
        'coal_share_elec',
        'gas_share_elec',
        'oil_share_elec',
        'hydro_share_elec',
        'nuclear_share_elec',
        'solar_share_elec',
        'wind_share_elec',
        'biofuel_share_elec',
        'renewables_share_elec'
    ]
    
    # Check that all required columns exist
    available_columns = df_year.columns.tolist()
    for col in energy_columns:
        if col not in available_columns:
            debug_print(f"Missing column: {col}")
    
    df_year = df_year[energy_columns]
    df_year = df_year.dropna(subset=['primary_energy_consumption'])
    
    random_country = random.choice(df_year['country'].dropna().unique())
    country_data = df_year[df_year['country'] == random_country].iloc[0].to_dict()
    
    # Prepare the cleaned data for the frontend
    cleaned_data = {
        'country': str(country_data['country']),
        'total_energy_consumption': float(country_data['primary_energy_consumption']),
        'energy_shares': {
            'Coal': float(country_data['coal_share_elec'] if pd.notna(country_data['coal_share_elec']) else 0),
            'Gas': float(country_data['gas_share_elec'] if pd.notna(country_data['gas_share_elec']) else 0),
            'Oil': float(country_data['oil_share_elec'] if pd.notna(country_data['oil_share_elec']) else 0),
            'Hydro': float(country_data['hydro_share_elec'] if pd.notna(country_data['hydro_share_elec']) else 0),
            'Nuclear': float(country_data['nuclear_share_elec'] if pd.notna(country_data['nuclear_share_elec']) else 0),
            'Solar': float(country_data['solar_share_elec'] if pd.notna(country_data['solar_share_elec']) else 0),
            'Wind': float(country_data['wind_share_elec'] if pd.notna(country_data['wind_share_elec']) else 0),
            'Biofuel': float(country_data['biofuel_share_elec'] if pd.notna(country_data['biofuel_share_elec']) else 0)
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
    country, country_data = get_random_country_energy()
    
    # Store in our global state
    current_game['country'] = country
    current_game['data'] = country_data
    
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

@app.route('/guess', methods=['POST'])
def guess():
    try:
        debug_print("Guess endpoint called")
        correct_country = current_game.get('country')
        debug_print(f"Current game state: {current_game}")
        
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
        if not is_valid_country(user_guess):
            return jsonify({
                "message": "Invalid country. Please select from the suggestions.",
                "error": True,
                "target": correct_country
            }), 400

        debug_print(f"User guess: {user_guess}")
        guess_coords = get_country_coordinates(user_guess)
        correct_coords = get_country_coordinates(correct_country)
        debug_print(f"Retrieved guess_coords: {guess_coords}, correct_coords: {correct_coords}")
        
        if guess_coords and correct_coords:
            hint, distance = get_direction_hint(guess_coords, correct_coords)
            return jsonify({
                "message": f"Try looking {hint}. Distance: {distance:.2f} km.",
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
        debug_print(f"Error in /guess endpoint: {e}")
        return jsonify({
            "message": "An unexpected error occurred.",
            "error": True,
            "detail": str(e)
        }), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)