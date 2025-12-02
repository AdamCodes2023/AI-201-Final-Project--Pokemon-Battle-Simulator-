import asyncio
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
