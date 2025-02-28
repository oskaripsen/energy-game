from flask import request, jsonify, current_app, Blueprint
import random, math

def register_endpoints(app):
    bp = Blueprint('main', __name__)

    @bp.route('/')
    def index():
        return "Welcome to the Game API!"

    @bp.route("/game/start", methods=["GET"])
    def start_game():
        config = current_app.config
        energy_data = config.get('ENERGY_DATA')
        countries = config.get('COUNTRIES')
        country_coords = config.get('COUNTRY_COORDS')
        game_state = config.get('game_state')
        
        valid_countries = [c for c in countries if c in country_coords]
        target = random.choice(valid_countries)
        game_state.clear()
        game_state["target"] = target
        game_state["attempts"] = 0
        game_state["max_attempts"] = 5

        row = energy_data[energy_data['country'] == target].iloc[0]
        energy_info = {col: row[col] for col in energy_data.columns if "consumption" in col.lower()}

        return jsonify({
            "message": "Game started",
            "energy_data": energy_info, 
            "attempts_left": game_state["max_attempts"]
        })

    @bp.route("/game/guess", methods=["POST"])
    def guess_country():
        config = current_app.config
        game_state = config.get('game_state')
        country_coords = config.get('COUNTRY_COORDS')
        target = game_state.get("target")
        if not target:
            return jsonify({"error": "Game not started. Go to /game/start first."}), 400

        data = request.get_json()
        guess = data.get("guess")
        if not guess:
            return jsonify({"error": "No guess provided"}), 400

        game_state["attempts"] += 1
        attempts_left = game_state["max_attempts"] - game_state["attempts"]

        if guess.lower() == target.lower():
            game_state.clear()
            return jsonify({"message": "Correct! You win!"})

        if guess not in country_coords:
            return jsonify({"error": f"Coordinates for '{guess}' not available."}), 400

        guess_coord = country_coords[guess]
        target_coord = country_coords[target]
        distance = haversine_distance(guess_coord, target_coord)
        direction = get_direction(guess_coord, target_coord)

        response = {
            "message": "Incorrect guess",
            "distance_km": round(distance, 2),
            "direction": direction,
            "attempts_left": attempts_left
        }
        if attempts_left <= 0:
            response["game_over"] = True
            response["target"] = target
            game_state.clear()
        return jsonify(response)

    def haversine_distance(coord1, coord2):
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def get_direction(guess_coord, target_coord):
        lat_guess, lon_guess = guess_coord
        lat_target, lon_target = target_coord
        directions = []
        if lat_target > lat_guess:
            directions.append("north")
        elif lat_target < lat_guess:
            directions.append("south")
        if lon_target > lon_guess:
            directions.append("east")
        elif lon_target < lon_guess:
            directions.append("west")
        return " & ".join(directions) if directions else "here"

    app.register_blueprint(bp)