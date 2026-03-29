"use client";
import { useState } from "react";
import { AlertCircle, Search, MessageSquareShare } from "lucide-react";

export default function ComplaintsPage() {
    const [complaints, setComplaints] = useState([
        { id: "C-101", user: "@shakti", category: "registration", severity: "high", status: "open", desc: "I paid for the VIP ticket but my confirmation email says General Admission. Please fix this.", time: "10 mins ago" },
        { id: "C-102", user: "@tech_geek", category: "technical", severity: "medium", status: "escalated", desc: "The website registration form is crashing when I select 'Looking for team'.", time: "1 hr ago" },
        { id: "C-103", user: "Anonymous", category: "harassment", severity: "critical", status: "open", desc: "Someone is spamming the Telegram group with inappropriate links.", time: "2 hrs ago" }
    ]);

    const resolveComplaint = (id: string) => {
        setComplaints(prev => prev.filter(c => c.id !== id));
        // Alert or Toast here
    };

    return (
        <div className="p-10 max-w-6xl mx-auto flex flex-col h-screen">

            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-black flex items-center gap-3"><AlertCircle className="text-red-400" /> AI Help Desk Console</h1>
                    <p className="text-gray-400 mt-1">Manage AI-escalated issues from Telegram attendees.</p>
                </div>
                <div className="bg-red-600/20 text-red-400 px-4 py-2 rounded-xl font-bold flex gap-2">
                    Open Issues: <span>{complaints.length}</span>
                </div>
            </div>

            <div className="flex gap-4 mb-6">
                <div className="flex-1 relative">
                    <input
                        type="text"
                        placeholder="Search by ID, username, or description..."
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pl-11 focus:outline-none focus:border-purple-500 transition"
                    />
                    <Search className="absolute left-4 top-3.5 text-gray-500" size={18} />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 flex-1 overflow-y-auto pb-10">
                {complaints.length === 0 ? (
                    <div className="col-span-full h-64 flex flex-col items-center justify-center text-gray-400">
                        <p className="text-2xl mb-2">🎉 All clear!</p>
                        <p className="text-sm">No open complaints to manage.</p>
                    </div>
                ) : (
                    complaints.map(c => (
                        <div key={c.id} className="glass-card rounded-2xl p-6 flex flex-col border border-white/5 relative hover:border-white/20 transition">

                            <div className="flex justify-between items-start mb-4">
                                <span className="font-mono text-sm text-purple-400 font-bold">{c.id}</span>
                                <span className={`text-xs px-2 py-1 rounded-md font-bold uppercase tracking-wider ${c.severity === 'critical' ? 'bg-red-500/20 text-red-500' :
                                        c.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                            'bg-yellow-500/20 text-yellow-500'
                                    }`}>
                                    {c.severity}
                                </span>
                            </div>

                            <p className="text-white text-sm mb-4 leading-relaxed flex-1">"{c.desc}"</p>

                            <div className="bg-white/5 rounded-xl p-3 mb-4 text-xs text-gray-400 flex justify-between items-center">
                                <span>By: <strong className="text-gray-200">{c.user}</strong></span>
                                <span>{c.time}</span>
                            </div>

                            <div className="flex gap-3 mt-auto">
                                <button
                                    className="flex-1 flex justify-center items-center gap-2 bg-white/5 hover:bg-white/10 text-gray-300 py-2.5 rounded-xl font-semibold transition text-sm">
                                    <MessageSquareShare size={16} /> Reply
                                </button>
                                <button
                                    onClick={() => resolveComplaint(c.id)}
                                    className="flex-1 flex justify-center items-center gap-2 bg-green-600 hover:bg-green-500 text-white py-2.5 rounded-xl font-bold transition text-sm shadow-lg shadow-green-900/30">
                                    Resolve
                                </button>
                            </div>

                        </div>
                    ))
                )}
            </div>

        </div>
    )
}
