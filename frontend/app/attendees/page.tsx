"use client";
import { useState } from "react";
import { Users, Search, Filter } from "lucide-react";

export default function AttendeesPage() {
    const [searchTerm, setSearchTerm] = useState("");

    // Mock data representing Supabase attendee rows, including JSONB dynamic fields
    const mockAttendees = [
        { id: 1, name: "Alice Johnson", email: "alice@example.com", college: "MIT", status: "Checked In", dynamic: { tshirt: "M", dietary: "Vegan" } },
        { id: 2, name: "Bob Smith", email: "bob@example.com", college: "Stanford", status: "Registered", dynamic: { tshirt: "L", dietary: "None" } },
        { id: 3, name: "Charlie Davis", email: "charlie@example.com", college: "Harvard", status: "Registered", dynamic: { tshirt: "S", dietary: "Gluten-Free" } },
    ];

    return (
        <div className="p-10 max-w-6xl mx-auto">

            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-black flex items-center gap-3"><Users className="text-purple-400" /> Attendee Directory</h1>
                    <p className="text-gray-400 mt-1">Manage registrations, check-in status, and view dynamic custom fields.</p>
                </div>
                <div className="bg-purple-600/20 text-purple-400 px-4 py-2 rounded-xl font-bold">
                    Total: {mockAttendees.length}
                </div>
            </div>

            <div className="flex gap-4 mb-6">
                <div className="flex-1 relative">
                    <input
                        type="text"
                        placeholder="Search by name, email, or college..."
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pl-11 focus:outline-none focus:border-purple-500 transition"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                    <Search className="absolute left-4 top-3.5 text-gray-500" size={18} />
                </div>
                <button className="flex items-center gap-2 bg-white/5 hover:bg-white/10 px-6 py-3 rounded-xl transition font-semibold text-gray-300">
                    <Filter size={18} /> Filter Status
                </button>
            </div>

            <div className="glass-card rounded-2xl overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-white/5">
                        <tr>
                            <th className="px-6 py-4 font-semibold text-gray-300">Name</th>
                            <th className="px-6 py-4 font-semibold text-gray-300">Contact</th>
                            <th className="px-6 py-4 font-semibold text-gray-300">College</th>
                            <th className="px-6 py-4 font-semibold text-gray-300">Registration Fields (JSONB)</th>
                            <th className="px-6 py-4 font-semibold text-gray-300">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                        {mockAttendees.filter(a => a.name.toLowerCase().includes(searchTerm.toLowerCase())).map((a) => (
                            <tr key={a.id} className="hover:bg-white/5 transition">
                                <td className="px-6 py-4 font-medium text-white">{a.name}</td>
                                <td className="px-6 py-4 text-gray-400">{a.email}</td>
                                <td className="px-6 py-4 text-gray-400">{a.college}</td>
                                <td className="px-6 py-4">
                                    <div className="flex flex-wrap gap-2">
                                        {Object.entries(a.dynamic).map(([k, v]) => (
                                            <span key={k} className="bg-purple-900/40 text-purple-300 border border-purple-500/30 px-2 py-1 rounded-md text-xs">
                                                <span className="opacity-70 mr-1">{k}:</span>{v as string}
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${a.status === 'Checked In' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                                        }`}>
                                        {a.status}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

        </div>
    )
}
