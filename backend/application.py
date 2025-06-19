from flask import Flask, jsonify, request
from flask_cors import CORS
import chess
import threading

# Use application instead of app for AWS Elastic Beanstalk
application = Flask(__name__)
CORS(application) # Allow all origins for this challenge

# In-memory game state with a lock for thread safety
game_state = {}
game_lock = threading.Lock()

def initialize_game():
    """Sets the game to its initial state."""
    with game_lock:
        board = chess.Board()
        game_state['board'] = board
        game_state['moves_left'] = 1
        # The current turn is implicitly handled by board.turn
        # but we track captures to assign the next turn's move count.

def get_status_message():
    """Generates a user-friendly status message."""
    board = game_state['board']
    if board.is_game_over():
        result = board.result()
        if result == "1-0": return "Game Over: White wins!"
        if result == "0-1": return "Game Over: Black wins!"
        if result == "1/2-1/2": return "Game Over: Draw!"
        return f"Game Over! {result}"

    turn = "White" if board.turn == chess.WHITE else "Black"
    moves = game_state['moves_left']
    return f"{turn} to move ({moves} {'move' if moves == 1 else 'moves'} left)"

# Initialize the game on startup
initialize_game()

@application.route('/api/game_state', methods=['GET'])
def get_game_state():
    """Returns the current state of the game."""
    with game_lock:
        board = game_state['board']
        state = {
            "fen": board.fen(),
            "isGameOver": board.is_game_over(),
            "statusMessage": get_status_message()
        }
        return jsonify(state)

@application.route('/api/new_game', methods=['POST'])
def new_game():
    """Starts a new game."""
    initialize_game()
    return get_game_state()

@application.route('/api/move', methods=['POST'])
def make_move():
    """Handles a player's move and implements the two-move logic."""
    with game_lock:
        board = game_state['board']

        if board.is_game_over():
            return jsonify({"error": "Game is over"}), 400

        move_uci = request.json.get('move')
        if not move_uci:
            return jsonify({"error": "Move not provided"}), 400

        try:
            move = chess.Move.from_uci(move_uci)
            
            # This is the core logic
            if move in board.legal_moves:
                is_capture = board.is_capture(move)
                
                board.push(move)
                game_state['moves_left'] -= 1

                # If the player is out of moves, it's the next player's turn.
                if game_state['moves_left'] == 0:
                    # Determine how many moves the *next* player gets.
                    # This is based on the move that was just made.
                    if is_capture:
                        game_state['moves_left'] = 2
                    else:
                        game_state['moves_left'] = 1
                
                # If the current player has another move, the turn does not change.
                # The python-chess library handles board.turn automatically
                # ONLY when a full move (ply) is complete. Our logic sits on top of this.
                # When moves_left > 0, we are in a sub-turn.

                return get_game_state()
            else:
                return jsonify({"error": f"Illegal move: {move_uci}"}), 400

        except ValueError:
            return jsonify({"error": f"Invalid move format: {move_uci}"}), 400

# Entry point for running locally
if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5001, debug=True)