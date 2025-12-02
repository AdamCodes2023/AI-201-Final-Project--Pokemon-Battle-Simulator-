import React, { useState, useEffect, useRef } from 'react';
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
