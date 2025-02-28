import os
import pandas as pd
from geopy.geocoders import Nominatim
import time

# Define file paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

OWID_CSV = os.path.join(DATA_DIR, 'owid-energy-data.csv')
if not os.path.exists(OWID_CSV):
    print(f"Error: OWID CSV not found at {OWID_CSV}")
    exit(1)
else:
    print(f"Found energy data CSV at {OWID_CSV}")

OUTPUT_CSV = os.path.join(DATA_DIR, 'coordinates_all_countries.csv')

# Read energy data
df = pd.read_csv(OWID_CSV)

# Filter countries
exclusions = [
    "World", "Europe", "Asia", "Africa", "OECD", "G20", "G7",
    "Non-OECD", "OPEC", "Middle East", "North America", "South America",
    "Central America", "Ember", "EIA", "EI", "Oceania",
    "Lower-middle-income countries", "Latin America and Caribbean",
    "Low-income countries", "Antarctica", "High-income countries",
    "Netherlands Antilles", "Upper-middle-income countries"
]
df_2020 = df[df['year'] == 2020]
mask = ~df_2020['country'].isin(exclusions)
countries = df_2020[mask]['country'].unique()
print(f"Processing {len(countries)} countries...")

# Get coordinates with retries
geolocator = Nominatim(user_agent="energy_game", timeout=10)
results = []

try:
    for country in sorted(countries):
        print(f"Processing: {country}")
        lat, lon = None, None
        for attempt in range(3):
            try:
                location = geolocator.geocode(country, timeout=10)
                if location:
                    lat, lon = location.latitude, location.longitude
                    print(f"Found {country}: {lat}, {lon}")
                    break
            except Exception as e:
                print(f"Error processing {country} on attempt {attempt+1}: {e}")
            time.sleep(0.5)  # reduced sleep time
        if lat is None or lon is None:
            print(f"Warning: Coordinates not found for {country}")
        results.append([country, lat, lon])
except KeyboardInterrupt:
    print("Process interrupted by user. Saving partial results...")

# Save to CSV
coords_df = pd.DataFrame(results, columns=['country', 'latitude', 'longitude'])
coords_df.to_csv(OUTPUT_CSV, index=False)
print(f"Coordinates file generated at {OUTPUT_CSV}")
