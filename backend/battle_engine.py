import random
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
        if self.is_fainted: return {'can_move': False, 'log': None} # Safety check
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
        if self.is_fainted: return None
        if self.status == "BRN" or self.status == "PSN":
            dmg = max(1, int(self.max_hp / (16 if self.status == "BRN" else 8)))
            self.take_damage(dmg)
            return f"{self.name} is hurt by its {self.status}!"
        return None

def calculate_damage(attacker, defender, move, weather=Weather.NONE):
    if move.category == "Physical": a, d = attacker.attack, defender.defense
    else: a, d = attacker.sp_attack, defender.sp_defense
    if attacker.status == "BRN" and move.category == "Physical": a = int(a * 0.5)
    
    # Avoid Division by Zero
    d = max(1, d)
    
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
        # If AI has no valid moves (struggle) or list is empty, handle safely
        if not ai_poke.moves: return None 
        
        for m in ai_poke.moves:
            dmg = calculate_damage(ai_poke, user_poke, m, self.weather)
            if dmg > max_dmg: max_dmg = dmg; best = m
        return best if best else ai_poke.moves[0]

    def handle_faint_switching(self):
        """Checks if active pokemon are fainted and swaps in the next available one."""
        
        # 1. Check AI
        if self.ai_active.is_fainted:
            # Look for a teammate that is alive
            found_replacement = False
            for i, p in enumerate(self.ai_team):
                if not p.is_fainted:
                    self.ai_active_idx = i
                    self.turn_log.append(f"Opponent sent out {p.name}!")
                    found_replacement = True
                    break
        
        # 2. Check User
        if self.user_active.is_fainted:
            found_replacement = False
            for i, p in enumerate(self.user_team):
                if not p.is_fainted:
                    self.user_active_idx = i
                    self.turn_log.append(f"Go {p.name}!")
                    found_replacement = True
                    break

    def play_turn(self, action):
        self.turn_log = []
        
        # --- PHASE 1: SWITCHING ---
        if action['type'] == "switch":
            self.user_active_idx = action['value']
            self.turn_log.append(f"Go {self.user_active.name}!")
        
        # --- PHASE 2: AI DECISION ---
        ai_move = self.ai_choose_move(self.ai_active, self.user_active)
        
        # --- PHASE 3: DETERMINE ORDER ---
        user_move = None
        if action['type'] == 'attack' and action['value'] < len(self.user_active.moves):
            user_move = self.user_active.moves[action['value']]
        
        participants = []
        
        # Add User to queue if they are attacking
        if user_move: 
            participants.append((self.user_active, user_move, self.ai_active))
        
        # Add AI to queue if they are alive
        if not self.ai_active.is_fainted and ai_move:
            participants.append((self.ai_active, ai_move, self.user_active))
        
        # Sort by speed: If AI is faster, swap the list order (AI becomes index 0)
        # Exception: If user switched, AI attacks alone (list length is 1), so no sort needed
        if len(participants) == 2:
            if self.ai_active.effective_speed > self.user_active.effective_speed:
                participants.reverse()

        # --- PHASE 4: EXECUTE ATTACKS ---
        for att, move, defe in participants:
            # Re-check fainted status (in case first attacker killed the second)
            if att.is_fainted or defe.is_fainted: continue
            
            check = att.check_can_move()
            if check['log']: self.turn_log.append(check['log'])
            if not check['can_move']: continue

            dmg = calculate_damage(att, defe, move, self.weather)
            defe.take_damage(dmg)
            self.turn_log.append(f"{att.name} used {move.name}! (Dmg: {dmg})")
            
            # Status Chance
            if move.type == "Fire" and random.random() < 0.1: 
                if defe.apply_status("BRN"): self.turn_log.append(f"{defe.name} was burned!")
            elif move.type == "Electric" and random.random() < 0.1:
                if defe.apply_status("PAR"): self.turn_log.append(f"{defe.name} was paralyzed!")
            
            if defe.is_fainted: self.turn_log.append(f"{defe.name} fainted!")

        # --- PHASE 5: END OF TURN EFFECTS ---
        for p in [self.user_active, self.ai_active]:
            if not p.is_fainted:
                log = p.apply_end_turn_effects()
                if log: self.turn_log.append(log)
        
        # --- PHASE 6: AUTO-SWITCH FAINTED MONS ---
        self.handle_faint_switching()

        # --- PHASE 7: CHECK WINNER ---
        if not any(not p.is_fainted for p in self.user_team): self.winner = "AI"
        if not any(not p.is_fainted for p in self.ai_team): self.winner = "User"