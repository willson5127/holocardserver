import uuid
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.matchmaking import Matchmaking
import app.message_types as message_types
from app.playermanager import PlayerManager, Player
from app.gameroom import GameRoom
from app.card_database import CardDatabase

app = FastAPI()

# Store connected clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message : message_types.Message):
        dict_message = message.as_dict()
        for connection in self.active_connections:
            try:
                await connection.send_json(dict_message)
            except:
                pass

manager = ConnectionManager()

player_manager : PlayerManager = PlayerManager()
game_rooms : List[GameRoom] = []
matchmaking : Matchmaking = Matchmaking()
card_db : CardDatabase = CardDatabase()

async def broadcast_server_info():
    message = message_types.ServerInfoMessage(
        message_type="server_info",
        queue_info=matchmaking.get_queue_info()
    )
    await manager.broadcast(message)

async def send_error_message(websocket: WebSocket, error_id, error_str : str):
    message = message_types.ErrorMessage(
        message_type="error",
        error_id = error_id,
        error_message=error_str,
    )
    await websocket.send_json(message.as_dict())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_id = str(uuid.uuid4())
    player = player_manager.get_player(player_id)
    if player:
        player.websocket = websocket
    else:
        player = player_manager.add_player(player_id, websocket)

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = message_types.parse_message(data)
            except Exception as e:
                print("Error in message parsing:", e, "\nMessage:", data)
                await send_error_message(websocket, "invalid_message", f"ERROR: Invalid JSON: {data}")
                continue

            print(f"MESSAGE:", message.message_type)
            if isinstance(message, message_types.JoinServerMessage):
                await broadcast_server_info()

            elif isinstance(message, message_types.JoinMatchmakingQueueMessage):
                # Ensure player is in a joinable state.
                if not can_player_join_queue(player):
                    await send_error_message(websocket, "joinmatch_invalid_alreadyinmatch", "Already in a match.")
                elif not matchmaking.is_game_type_valid(message.game_type):
                    await send_error_message(websocket, "joinmatch_invalid_gametype", "Invalid game type.")
                else:
                    is_valid = card_db.validate_deck(
                        oshi_id=message.oshi_id,
                        deck=message.deck,
                        cheer_deck=message.cheer_deck
                    )

                    if is_valid:
                        player.save_deck_info(
                            oshi_id=message.oshi_id,
                            deck=message.deck,
                            cheer_deck=message.cheer_deck
                        )
                        match = matchmaking.add_player_to_queue(
                            player=player,
                            queue_name=message.queue_name,
                            custom_game=message.custom_game,
                            game_type=message.game_type,
                        )
                        if match:
                            game_rooms.append(match)
                            await match.start(card_db)

                        await broadcast_server_info()
                    else:
                        await send_error_message(websocket, "joinmatch_invaliddeck", "Invalid deck list.")

            elif isinstance(message, message_types.LeaveMatchmakingQueueMessage):
                matchmaking.remove_player_from_queue(player)
                await broadcast_server_info()

            elif isinstance(message, message_types.LeaveGameMessage):
                player_room : GameRoom = player.current_game_room
                if player_room is not None:
                    await player_room.handle_player_quit(player)
                    check_cleanup_room(player_room)
                    await broadcast_server_info()
                else:
                    await send_error_message(websocket, "not_in_room", f"ERROR: Not in a game room to leave.")

            elif isinstance(message, message_types.GameActionMessage):
                print(f"GAMEACTION:", message.action_type)
                player_room : GameRoom = player.current_game_room
                if player_room and not player_room.is_ready_for_cleanup():
                    await player_room.handle_game_message(player.player_id, message.action_type, message.action_data)
                    check_cleanup_room(player_room)
                else:
                    await send_error_message(websocket, "not_in_room", f"ERROR: Not in a game room to send a game message.")
            else:
                await send_error_message(websocket, "invalid_game_message", f"ERROR: Invalid message: {data}")

    except WebSocketDisconnect:
        print("Client disconnected.")
        player.connected = False
        matchmaking.remove_player_from_queue(player)
        for room in game_rooms:
            if player in room.players:
                await room.handle_player_disconnect(player)
                check_cleanup_room(room)
                break

        player_manager.remove_player(player_id)
        manager.disconnect(websocket)
        await broadcast_server_info()

def check_cleanup_room(room: GameRoom):
    if room.is_ready_for_cleanup():
        game_rooms.remove(room)
        for player in room.players:
            player.current_game_room = None

def can_player_join_queue(player: Player):
    # If the player is in a queue or in a game room, then they can't join another queue.
    if player.current_game_room or matchmaking.get_player_queue(player):
        return False
    return True