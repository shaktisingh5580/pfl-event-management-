"use client";
import { useState } from "react";
import ReactMarkdown from 'react-markdown';
import { Send, UploadCloud, BrainCircuit } from 'lucide-react';

export default function PlannerPage() {
    const [messages, setMessages] = useState<any[]>([{
        role: "assistant",
        content: "Hi! I'm your AI Architect. Let's plan your event. What's the name and theme of the event?"
    }]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);

    // Simplified Chat function to talk to FastAPI
    const sendMessage = async () => {
        if (!input.trim()) return;
        const newMsg = { role: "user", content: input };
        setMessages(prev => [...prev, newMsg]);
        setInput("");
        setLoading(true);

        try {
            // In Phase 3 production, this would hit the FastAPI /api/architect/chat
            // For MVP UI, we'll mock the delay
            setTimeout(() => {
                setMessages(prev => [...prev, {
                    role: "assistant",
                    content: "Got it! How many participants are you expecting, and do you need any custom fields on the registration form (like T-shirt size)?"
                }]);
                setLoading(false);
            }, 1000);
        } catch (e) {
            console.error(e);
            setLoading(false);
        }
    };

    return (
        <div className="flex h-screen w-full">
            {/* LEFT: Chat Area */}
            <div className="w-2/3 flex flex-col p-6 border-r border-white/10">
                <div className="flex items-center gap-3 mb-6">
                    <BrainCircuit className="text-purple-400" size={28} />
                    <div>
                        <h1 className="text-2xl font-black">AI Event Architect</h1>
                        <p className="text-sm text-gray-400">Design your event timeline, rules, and layout</p>
                    </div>
                </div>

                <div className="flex-1 glass-card rounded-2xl p-6 overflow-y-auto mb-6 flex flex-col gap-4">
                    {messages.map((m, i) => (
                        <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] rounded-2xl px-5 py-3 ${m.role === 'user' ? 'bg-purple-600 text-white' : 'bg-white/10 text-gray-200'}`}>
                                <ReactMarkdown>{m.content}</ReactMarkdown>
                            </div>
                        </div>
                    ))}
                    {loading && (
                        <div className="flex justify-start">
                            <div className="bg-white/10 text-gray-400 rounded-2xl px-5 py-3 animate-pulse">
                                Architect is thinking...
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Box */}
                <div className="relative">
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                        placeholder="Type your event details here..."
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-4 pr-12 focus:outline-none focus:border-purple-500 transition"
                    />
                    <button onClick={sendMessage} className="absolute right-3 top-3.5 p-1 bg-purple-600 hover:bg-purple-500 rounded-lg transition">
                        <Send size={18} />
                    </button>
                </div>
            </div>

            {/* RIGHT: Knowledge Base Upload */}
            <div className="w-1/3 p-6 flex flex-col">
                <h2 className="text-xl font-bold mb-2">Knowledge Base</h2>
                <p className="text-sm text-gray-400 mb-6">Upload PDFs containing rules, coordinator lists, and venue details. The AI will read them instantly.</p>

                <div className="border-2 border-dashed border-white/20 rounded-2xl p-10 flex flex-col items-center justify-center text-center hover:border-purple-500/50 hover:bg-purple-500/5 transition cursor-pointer mb-6">
                    <UploadCloud size={40} className="text-purple-400 mb-3" />
                    <p className="font-semibold mb-1">Upload PDF Document</p>
                    <p className="text-xs text-gray-500">Drag & drop or click to browse</p>
                </div>

                <div className="flex-1">
                    <h3 className="text-sm font-bold text-gray-400 mb-3 uppercase tracking-wider">Processed Files</h3>
                    <div className="space-y-2">
                        <div className="glass-card px-4 py-3 rounded-xl flex items-center justify-between">
                            <span className="text-sm">Hackathon_Rules_2026.pdf</span>
                            <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-md">Vectorized</span>
                        </div>
                        <div className="glass-card px-4 py-3 rounded-xl flex items-center justify-between">
                            <span className="text-sm">Campus_Map.pdf</span>
                            <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-md">Vectorized</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
