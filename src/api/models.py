class GameModel:
    def __init__(self, name, players):
        self.name = name
        self.players = players
        self.state = "waiting"  # Possible states: waiting, in_progress, finished

    def start_game(self):
        if self.state == "waiting":
            self.state = "in_progress"
            return True
        return False

    def end_game(self):
        if self.state == "in_progress":
            self.state = "finished"
            return True
        return False

    def get_game_info(self):
        return {
            "name": self.name,
            "players": self.players,
            "state": self.state
        }