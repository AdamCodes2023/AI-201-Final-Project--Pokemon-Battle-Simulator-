import os

# Define the file structure and content
project_files = {
    # ---------------------------------------------------------
    # ROOT FILES
    # ---------------------------------------------------------
    ".env": """OPENAI_API_KEY=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
PORT=8000
""",

    "Dockerfile": """# --- STAGE 1: Build Frontend (Node) ---
FROM node:18-alpine as frontend_builder
WORKDIR /frontend_build
COPY ./frontend/package.json ./frontend/package-lock.json ./
RUN npm install
COPY ./frontend ./
RUN npm run build

# --- STAGE 2: Setup Backend (Python) ---
FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential
COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./backend .

# --- STAGE 3: Merge ---
COPY --from=frontend_builder /frontend_build/build ./static
RUN chmod +x start.sh
ENV PORT=8000
CMD ["./start.sh"]
""",

    # ---------------------------------------------------------
    # BACKEND FILES
    # ---------------------------------------------------------
    "backend/requirements.txt": """fastapi
uvicorn
pydantic
requests
aiohttp
langchain
langchain-community
langchain-openai
chromadb
tiktoken
""",

    "backend/start.sh": """#!/bin/bash
if [ ! -f "pokemon_db.json" ]; then
    echo "--- Scraping PokeAPI... ---"
    python ingest_data.py
fi
if [ ! -d "chroma_db" ]; then
    echo "--- Building Vector DB... ---"
    python rag_builder.py
fi
echo "--- Starting Server ---"
uvicorn main:app --host 0.0.0.0 --port 8000
""",

    "backend/ingest_data.py": """import asyncio
import aiohttp
import json
import random

POKEMON_COUNT = 1010  # Gen 9 support

async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200: return await response.json()
    except: pass
    return None

async def get_pokemon_data(session, pid):
    url = f"https://pokeapi.co/api/v2/pokemon/{pid}"
    data = await fetch_url(session, url)
    if not data: return None
    
    print(f"Fetching {data['name']}...")
    stats = {s['stat']['name']: s['base_stat'] for s in data['stats']}
    types = [t['type']['name'].capitalize() for t in data['types']]
    
    # Randomly pick 10 moves to keep DB size manageable
    move_urls = [m['move']['url'] for m in data['moves']]
    if len(move_urls) > 10: move_urls = random.sample(move_urls, 10)
    
    moves_data = await asyncio.gather(*[fetch_url(session, m) for m in move_urls])
    valid_moves = []
    for m in moves_data:
        if m and m.get('power'):
            valid_moves.append({
                "name": m['name'],
                "type": m['type']['name'].capitalize(),
                "category": m['damage_class']['name'].capitalize(),
                "power": m['power'],
                "accuracy": m['accuracy'] or 100,
                "pp": m['pp']
            })
            
    return {
        "id": data['id'], "name": data['name'].capitalize(),
        "types": types, "stats": stats, "moves": valid_moves,
        "sprite_front": data['sprites']['front_default'],
        "sprite_back": data['sprites']['back_default']
    }

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [get_pokemon_data(session, i) for i in range(1, POKEMON_COUNT + 1)]
        results = await asyncio.gather(*tasks)
        db = [p for p in results if p]
        with open("pokemon_db.json", "w") as f: json.dump(db, f)

if __name__ == "__main__":
    asyncio.run(main())
""",

    "backend/battle_engine.py": """import random
import copy
from typing import List, Optional

class Weather:
    NONE, SUN, RAIN, SAND, HAIL = "Clear", "Sun", "Rain", "Sandstorm", "Hail"

def get_weather_modifier(weather, move_type):
    if weather == Weather.SUN: return 1.5 if move_type == "Fire" else 0.5 if move_type == "Water" else 1.0
    if weather == Weather.RAIN: return 1.5 if move_type == "Water" else 0.5 if move_type == "Fire" else 1.0
    return 1.0

class Move:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class Pokemon:
    def __init__(self, name, types, stats, moves, sprite_front, sprite_back):
        self.name = name
        self.types = types
        self.sprite_front = sprite_front
        self.sprite_back = sprite_back
        self.max_hp = stats.get('hp', 100)
        self.attack = stats.get('attack', 100)
        self.defense = stats.get('defense', 100)
        self.sp_attack = stats.get('special-attack', 100)
        self.sp_defense = stats.get('special-defense', 100)
        self.speed = stats.get('speed', 100)
        self.current_hp = self.max_hp
        self.moves = moves
        self.status = None
        self.sleep_turns = 0
        self.is_fainted = False

    def copy(self): return copy.deepcopy(self)

    @property
    def effective_speed(self):
        return int(self.speed * 0.5) if self.status == "PAR" else self.speed

    def check_can_move(self):
        if self.status == "SLP":
            self.sleep_turns -= 1
            if self.sleep_turns <= 0:
                self.status = None
                return {'can_move': True, 'log': f"{self.name} woke up!"}
            return {'can_move': False, 'log': f"{self.name} is fast asleep."}
        if self.status == "PAR" and random.random() < 0.25:
            return {'can_move': False, 'log': f"{self.name} is paralyzed!"}
        return {'can_move': True, 'log': None}
    
    def take_damage(self, amount):
        self.current_hp = max(0, self.current_hp - amount)
        if self.current_hp == 0: self.is_fainted = True

    def apply_status(self, code):
        if self.status: return False
        self.status = code
        if code == "SLP": self.sleep_turns = random.randint(1, 3)
        return True

    def apply_end_turn_effects(self):
        if self.status == "BRN" or self.status == "PSN":
            dmg = max(1, int(self.max_hp / (16 if self.status == "BRN" else 8)))
            self.take_damage(dmg)
            return f"{self.name} is hurt by its {self.status}!"
        return None

def calculate_damage(attacker, defender, move, weather=Weather.NONE):
    if move.category == "Physical": a, d = attacker.attack, defender.defense
    else: a, d = attacker.sp_attack, defender.sp_defense
    if attacker.status == "BRN" and move.category == "Physical": a = int(a * 0.5)
    
    base = ((2 * 50 / 5 + 2) * move.power * (a / d)) / 50 + 2
    stab = 1.5 if move.type in attacker.types else 1.0
    weather_mod = get_weather_modifier(weather, move.type)
    return int(base * stab * weather_mod * random.uniform(0.85, 1.0))

class Battle:
    def __init__(self, user_team, ai_team):
        self.user_team = user_team
        self.ai_team = ai_team
        self.weather = Weather.NONE
        self.turn_log = []
        self.winner = None
        self.user_active_idx = 0
        self.ai_active_idx = 0

    @property
    def user_active(self): return self.user_team[self.user_active_idx]
    @property
    def ai_active(self): return self.ai_team[self.ai_active_idx]

    def ai_choose_move(self, ai_poke, user_poke):
        best, max_dmg = None, -1
        for m in ai_poke.moves:
            dmg = calculate_damage(ai_poke, user_poke, m, self.weather)
            if dmg > max_dmg: max_dmg = dmg; best = m
        return best

    def play_turn(self, action):
        self.turn_log = []
        if action['type'] == "switch":
            self.user_active_idx = action['value']
            self.turn_log.append(f"Go {self.user_active.name}!")
        
        ai_move = self.ai_choose_move(self.ai_active, self.user_active)
        
        # Determine order
        user_move = self.user_active.moves[action['value']] if action['type'] == 'attack' else None
        user_goes_first = True
        if user_move and self.ai_active.effective_speed > self.user_active.effective_speed:
            user_goes_first = False

        participants = []
        if user_move: participants.append((self.user_active, user_move, self.ai_active))
        if not self.ai_active.is_fainted: participants.append((self.ai_active, ai_move, self.user_active))
        
        if not user_goes_first and len(participants) == 2: participants.reverse()
        if action['type'] == 'switch': participants = [(self.ai_active, ai_move, self.user_active)]

        for att, move, defe in participants:
            if att.is_fainted or defe.is_fainted: continue
            
            check = att.check_can_move()
            if check['log']: self.turn_log.append(check['log'])
            if not check['can_move']: continue

            dmg = calculate_damage(att, defe, move, self.weather)
            defe.take_damage(dmg)
            self.turn_log.append(f"{att.name} used {move.name}! (Dmg: {dmg})")
            
            # Status Chance (Simplified)
            if move.type == "Fire" and random.random() < 0.1: 
                if defe.apply_status("BRN"): self.turn_log.append(f"{defe.name} was burned!")
            
            if defe.is_fainted: self.turn_log.append(f"{defe.name} fainted!")

        # End Turn
        for p in [self.user_active, self.ai_active]:
            if not p.is_fainted:
                log = p.apply_end_turn_effects()
                if log: self.turn_log.append(log)
        
        if not any(not p.is_fainted for p in self.user_team): self.winner = "AI"
        if not any(not p.is_fainted for p in self.ai_team): self.winner = "User"
""",

    "backend/main.py": """import os
import random
import json
import uuid
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from battle_engine import Battle, Pokemon, Move, load_pokemon_from_db_util_wrapper_placeholder
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
""",

    "backend/rag_builder.py": """import json, os
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

def build():
    with open("pokemon_db.json") as f: data = json.load(f)
    docs = []
    for p in data:
        content = f"Name: {p['name']}. Type: {p['types']}. Stats: {p['stats']}."
        docs.append(Document(page_content=content, metadata={"name": p['name']}))
    
    Chroma.from_documents(docs, OpenAIEmbeddings(), persist_directory="./chroma_db")
    print("DB Built")

if __name__ == "__main__": build()
""",

    "backend/rag_chat.py": """from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA

class Oracle:
    def __init__(self):
        self.db = Chroma(persist_directory="./chroma_db", embedding_function=OpenAIEmbeddings())
        self.llm = ChatOpenAI(model_name="gpt-3.5-turbo")
        self.qa = RetrievalQA.from_chain_type(llm=self.llm, retriever=self.db.as_retriever())

    def ask(self, q): return self.qa.run(q)
""",

    # ---------------------------------------------------------
    # FRONTEND FILES
    # ---------------------------------------------------------
    "frontend/package.json": """{
  "name": "pokemon-ai",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "axios": "^1.4.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build"
  },
  "eslintConfig": { "extends": ["react-app"] },
  "browserslist": { "production": [">0.2%", "not dead", "not op_mini all"], "development": ["last 1 chrome version"] }
}
""",

    "frontend/public/index.html": """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Pokemon AI</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
""",

    "frontend/src/index.js": """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
""",

    "frontend/src/api.js": """import axios from 'axios';
const API = ""; 
export const getList = () => axios.get(`${API}/pokemon/list`);
export const start = (team) => axios.post(`${API}/battle/start`, {user_team: team});
export const turn = (bid, type, val) => axios.post(`${API}/battle/turn`, {battle_id: bid, action_type: type, action_value: val});
export const chat = (q) => axios.post(`${API}/chat`, {question: q});
""",

    "frontend/src/App.js": """import React, { useState, useEffect, useRef } from 'react';
import { getList, start, turn, chat } from './api';

const Health = ({ cur, max }) => {
  const p = Math.max(0, (cur/max)*100);
  const c = p < 20 ? 'bg-red-500' : p < 50 ? 'bg-yellow-400' : 'bg-green-500';
  return <div className="w-full h-4 bg-gray-700 rounded-full overflow-hidden border border-gray-600"><div className={`h-full ${c}`} style={{width: `${p}%`}}/></div>;
};

export default function App() {
  const [view, setView] = useState('select');
  const [allP, setAllP] = useState([]);
  const [team, setTeam] = useState([]);
  const [bState, setB] = useState(null);
  const [logs, setLogs] = useState([]);
  const [msg, setMsg] = useState("");
  const [hist, setHist] = useState([]);
  const [showSwitch, setShowSwitch] = useState(false);
  const logRef = useRef(null);

  useEffect(() => { getList().then(r => setAllP(r.data)); }, []);
  useEffect(() => { logRef.current?.scrollIntoView({behavior:'smooth'}); }, [logs]);

  const toggle = (n) => team.includes(n) ? setTeam(team.filter(x=>x!==n)) : team.length<3 && setTeam([...team, n]);
  
  const goBattle = async () => {
    const res = await start(team);
    setB(res.data); setLogs(res.data.turn_log); setView('battle');
  };

  const doTurn = async (type, val) => {
    const res = await turn(bState.battle_id, type, val);
    setB(res.data); setLogs(prev => [...prev, "---", ...res.data.turn_log]);
    setShowSwitch(false);
  };

  const sendChat = async (e) => {
    e.preventDefault();
    if(!msg) return;
    setHist(h => [...h, {u:'You', t:msg}]);
    const q = msg; setMsg("");
    const res = await chat(q);
    setHist(h => [...h, {u:'Oracle', t:res.data.answer}]);
  };

  if(view === 'select') return (
    <div className="p-8 bg-gray-900 min-h-screen text-white text-center">
      <h1 className="text-4xl text-yellow-400 font-bold mb-4">BUILD YOUR TEAM</h1>
      <div className="mb-4">
        {team.map(t=><span key={t} className="px-2 py-1 bg-blue-600 rounded m-1">{t}</span>)}
      </div>
      <button onClick={goBattle} disabled={team.length!==3} className="bg-green-500 px-6 py-2 rounded font-bold disabled:opacity-50">START</button>
      <div className="grid grid-cols-4 gap-2 mt-4">
        {allP.map(p=><div key={p.name} onClick={()=>toggle(p.name)} className={`p-2 border rounded cursor-pointer ${team.includes(p.name)?'border-yellow-400 bg-gray-800':'border-gray-700'}`}>{p.name}</div>)}
      </div>
    </div>
  );

  const usr = bState?.user_pokemon;
  const ai = bState?.opponent_pokemon;

  return (
    <div className="flex flex-col md:flex-row h-screen bg-gray-800 text-white font-mono">
      <div className="flex-1 p-4 relative">
        {/* AI */}
        <div className="absolute top-10 right-10 flex flex-col items-end">
            <div className="bg-gray-200 text-black p-3 rounded w-64 mb-2">
                <div className="flex justify-between font-bold"><span>{ai?.name}</span><span>{ai?.status}</span></div>
                <Health cur={ai?.current_hp} max={ai?.max_hp}/>
            </div>
            <img src={ai?.sprite_front} className="w-40 h-40 object-contain" alt="ai"/>
        </div>
        
        {/* USER */}
        <div className="absolute bottom-10 left-10 flex flex-col items-start">
            <img src={usr?.sprite_back} className="w-40 h-40 object-contain" alt="user"/>
            <div className="bg-yellow-100 text-black p-3 rounded w-64 mt-2">
                <div className="flex justify-between font-bold"><span>{usr?.name}</span><span>{usr?.status}</span></div>
                <Health cur={usr?.current_hp} max={usr?.max_hp}/>
            </div>
        </div>

        {/* CONTROLS */}
        <div className="absolute bottom-4 right-4 w-96 bg-gray-900 p-4 border border-gray-600 rounded">
            {bState?.winner ? 
                <div className="text-center font-bold text-2xl">{bState.winner} WINS! <button onClick={()=>window.location.reload()} className="block mx-auto mt-2 text-sm bg-blue-500 px-2 py-1 rounded">Reset</button></div> :
                <div className="grid grid-cols-2 gap-2">
                    {usr?.moves.map((m,i)=><button key={i} onClick={()=>doTurn('attack',i)} className="bg-gray-700 p-2 rounded hover:bg-gray-600 text-left"><div>{m.name}</div><div className="text-xs text-gray-400">{m.type}</div></button>)}
                    <button onClick={()=>setShowSwitch(true)} className="col-span-2 bg-blue-600 p-2 rounded font-bold">SWITCH</button>
                </div>
            }
        </div>

        {/* LOGS */}
        <div className="absolute top-4 left-4 w-80 h-48 bg-black opacity-80 overflow-y-auto text-sm p-2 text-green-400 border border-green-800 rounded">
            {logs.map((l,i)=><div key={i}>{l}</div>)} <div ref={logRef}/>
        </div>

        {/* SWITCH MODAL */}
        {showSwitch && <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
            <div className="bg-gray-800 p-6 rounded w-80">
                <h3 className="font-bold mb-4">Switch Pokemon</h3>
                {bState.user_team_status.map((n,i)=><button key={n} onClick={()=>doTurn('switch',i)} disabled={n===usr?.name} className="block w-full text-left p-2 hover:bg-gray-700 disabled:opacity-50">{n}</button>)}
                <button onClick={()=>setShowSwitch(false)} className="mt-4 w-full bg-red-600 py-1 rounded">Cancel</button>
            </div>
        </div>}
      </div>

      {/* CHAT */}
      <div className="w-full md:w-80 bg-gray-900 border-l border-gray-700 flex flex-col">
        <div className="flex-1 p-4 overflow-y-auto space-y-2">
            {hist.map((x,i)=><div key={i} className={`p-2 rounded text-sm ${x.u==='You'?'bg-gray-700 ml-4':'bg-blue-900 mr-4'}`}><b>{x.u}:</b> {x.t}</div>)}
        </div>
        <form onSubmit={sendChat} className="p-2 border-t border-gray-700"><input value={msg} onChange={e=>setMsg(e.target.value)} className="w-full bg-gray-800 border border-gray-600 rounded p-2" placeholder="Ask Oracle..."/></form>
      </div>
    </div>
  );
}
"""
}

# Execution
for path, content in project_files.items():
    # Ensure directory exists
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    
    # Write file
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        print(f"Created: {path}")

print("\n--- Project Created Successfully! ---")
print("1. Update the .env file with your OpenAI Key.")
print("2. Run: docker-compose up --build")