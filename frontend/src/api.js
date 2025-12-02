import axios from 'axios';
const API = ""; 
export const getList = () => axios.get(`${API}/pokemon/list`);
export const start = (team) => axios.post(`${API}/battle/start`, {user_team: team});
export const turn = (bid, type, val) => axios.post(`${API}/battle/turn`, {battle_id: bid, action_type: type, action_value: val});
export const chat = (q) => axios.post(`${API}/chat`, {question: q});
