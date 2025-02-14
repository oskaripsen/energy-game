import pandas as pd
import random
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from fuzzywuzzy import process

def load_data(file_path):
    """Load the energy dataset."""
    return pd.read_csv(file_path)

def get_country_coordinates(country):
    """Get latitude and longitude of a country."""
    geolocator = Nominatim(user_agent="energy_game")
    location = geolocator.geocode(country)
    if location:
        return (location.latitude, location.longitude)
    return None

def get_direction_hint(guess_coords, correct_coords):
    """Determine the directional hint based on coordinates and calculate distance."""
    lat_diff = correct_coords[0] - guess_coords[0]
    lon_diff = correct_coords[1] - guess_coords[1]
    
    direction = ""
    if lat_diff > 0:
        direction += "North"
    elif lat_diff < 0:
        direction += "South"
    
    if lon_diff > 0:
        direction += "East"
    elif lon_diff < 0:
        direction += "West"
    
    distance = geodesic(guess_coords, correct_coords).kilometers
    return direction or "Unknown direction", distance

def get_best_match(user_input, country_list):
    """Suggest the closest matching country name."""
    match, score = process.extractOne(user_input, country_list)
    return match if score > 80 else None

def filter_countries(df):
    """Filter out non-country regions and aggregations."""
    exclusions = ["World", "Europe", "Asia", "Africa", "OECD", "G20", "G7", "Non-OECD", "OPEC", "Middle East", "North America", "South America", "Central America", "Ember", "EIA", "EI"]
    return df[~df['country'].str.contains('|'.join(exclusions), na=False)]

def get_random_country_energy(df, year=2020):
    """Select a random country and provide energy split and total energy usage."""
    df_year = df[df['year'] == year]
    df_year = filter_countries(df_year)
    df_year['total_energy'] = df_year[['biofuel_consumption', 'coal_consumption', 'gas_consumption', 
                                       'oil_consumption', 'hydro_consumption', 'nuclear_consumption',
                                       'solar_consumption', 'wind_consumption', 'other_renewable_consumption']].sum(axis=1)
    df_year = df_year[df_year['total_energy'] > 0]
    fuel_columns = ['biofuel_consumption', 'coal_consumption', 'gas_consumption', 'oil_consumption',
                    'hydro_consumption', 'nuclear_consumption', 'solar_consumption', 'wind_consumption',
                    'other_renewable_consumption']
    df_year = df_year.dropna(subset=fuel_columns, how='all')
    
    random_country = random.choice(df_year['country'].dropna().unique())
    country_data = df_year[df_year['country'] == random_country]
    energy_sources = {
        "Biofuel": 'biofuel_share_energy',
        "Coal": 'coal_share_energy',
        "Gas": 'gas_share_energy',
        "Oil": 'oil_share_energy',
        "Hydro": 'hydro_share_energy',
        "Nuclear": 'nuclear_share_energy',
        "Solar": 'solar_share_energy',
        "Wind": 'wind_share_energy',
        "Other Renewables": 'other_renewables_share_energy'
    }
    energy_split = {source: country_data[col].values[0] for source, col in energy_sources.items() if col in country_data}
    return random_country, country_data['total_energy'].values[0], energy_split

def play_game(df, year=2020):
    """Game where user guesses the country based on energy data, with 5 attempts and directional hints."""
    country, total_energy, energy_split = get_random_country_energy(df, year)
    correct_coords = get_country_coordinates(country)
    country_list = filter_countries(df)['country'].dropna().unique()
    
    print("Guess the country based on the following energy data:")
    print(f"Total Energy Consumption: {total_energy:.2f} TWh")
    print("Energy Split:")
    for source, share in energy_split.items():
        print(f"  {source}: {share:.2f}%")
    
    attempts = 5
    while attempts > 0:
        user_guess = input(f"Enter your guess ({attempts} attempts left): ")
        best_match = get_best_match(user_guess, country_list)
        if best_match:
            user_guess = best_match
        
        if user_guess.lower() == country.lower():
            print("Correct! Well done!")
            return
        else:
            guess_coords = get_country_coordinates(user_guess)
            if guess_coords and correct_coords:
                hint, distance = get_direction_hint(guess_coords, correct_coords)
                print(f"Wrong guess. Hint: Move {hint}. Distance to correct location: {distance:.2f} km.")
            else:
                print(f"Wrong guess. Couldn't determine location for hint. Did you mean {best_match}?")
        attempts -= 1
    
    print(f"Out of attempts! The correct answer was {country}.")

# Example usage
if __name__ == "__main__":
    file_path = "owid-energy-data.csv"  # Adjust if needed
    df = load_data(file_path)
    play_game(df)

