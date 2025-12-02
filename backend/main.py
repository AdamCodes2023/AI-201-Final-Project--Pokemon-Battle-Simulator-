import os
import random
import json
import uuid
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from battle_engine import Battle, Pokemon, Move
from rag_chat import Oracle

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

active_battles = {}
oracle = None

def load_pokemon(name):
    with open("pokemon_db.json") as f: data = json.load(f)
    p = next(x for x in data if x['name'] == name)
    moves = [Move(**m) for m in p['moves'][:4]]
    return Pokemon(p['name'], p['types'], p['stats'], moves, p['sprite_front'], p['sprite_back'])

class StartReq(BaseModel): user_team: List[str]
class TurnReq(BaseModel): battle_id: str; action_type: str; action_value: int
class ChatReq(BaseModel): question: str

@app.get("/pokemon/list")
def list_poke():
    with open("pokemon_db.json") as f: return [{"name": p['name'], "types": p['types']} for p in json.load(f)]

@app.post("/battle/start")
def start(req: StartReq):
    user_team = [load_pokemon(n) for n in req.user_team]
    with open("pokemon_db.json") as f: all_p = json.load(f)
    ai_team = [load_pokemon(n) for n in random.sample([x['name'] for x in all_p], 3)]
    
    bid = str(uuid.uuid4())
    active_battles[bid] = Battle(user_team, ai_team)
    return get_state(bid)

@app.post("/battle/turn")
def turn(req: TurnReq):
    b = active_battles[req.battle_id]
    b.play_turn({"type": req.action_type, "value": req.action_value})
    return get_state(req.battle_id)

@app.post("/chat")
def chat(req: ChatReq):
    global oracle
    if not oracle: oracle = Oracle()
    return {"answer": oracle.ask(req.question)}

def get_state(bid):
    b = active_battles[bid]
    def s_p(p): 
        return {
            "name": p.name, "current_hp": p.current_hp, "max_hp": p.max_hp,
            "status": p.status, "sprite_front": p.sprite_front, "sprite_back": p.sprite_back,
            "is_fainted": p.is_fainted,
            "moves": [{"name": m.name, "type": m.type, "pp": m.pp} for m in p.moves]
        } if p else None
    
    return {
        "battle_id": bid, "winner": b.winner, "turn_log": b.turn_log,
        "user_pokemon": s_p(b.user_active),
        "opponent_pokemon": s_p(b.ai_active),
        "user_team_status": [p.name for p in b.user_team],
        "ai_team_status": [p.name for p in b.ai_team]
    }

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
