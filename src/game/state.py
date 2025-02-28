# filepath: /game-backend/game-backend/src/game/state.py

class GameState:
    def __init__(self):
        self.players = {}
        self.status = "not started"

    def add_player(self, player_id):
        if player_id not in self.players:
            self.players[player_id] = {"progress": 0}
    
    def update_progress(self, player_id, progress):
        if player_id in self.players:
            self.players[player_id]["progress"] = progress

    def start_game(self):
        self.status = "in progress"

    def end_game(self):
        self.status = "finished"

    def get_state(self):
        return {
            "players": self.players,
            "status": self.status
        }