export default function Home() {
    return (
        <div className="p-10 max-w-6xl mx-auto">
            <header className="mb-10">
                <h1 className="text-4xl font-black mb-2">Welcome to your Event Command Center</h1>
                <p className="text-gray-400">Monitor live metrics and manage your upcoming event built by AI.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                <MetricCard title="Total Registrations" value="342" subtitle="+12 today" color="from-purple-500/20 to-purple-500/5" border="border-purple-500/30" />
                <MetricCard title="Checked In" value="89" subtitle="Live tracking" color="from-blue-500/20 to-blue-500/5" border="border-blue-500/30" />
                <MetricCard title="Open Complaints" value="3" subtitle="Help Desk Active" color="from-red-500/20 to-red-500/5" border="border-red-500/30" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="glass-card p-6 rounded-2xl">
                    <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
                    <div className="space-y-3">
                        <button className="w-full bg-purple-600 hover:bg-purple-500 text-left px-6 py-4 rounded-xl font-bold transition">
                            1. Chat with AI to Plan Event →
                        </button>
                        <button className="w-full bg-white/5 hover:bg-white/10 text-left px-6 py-4 rounded-xl font-bold transition">
                            2. Upload Knowledge Base PDF →
                        </button>
                        <button className="w-full bg-white/5 hover:bg-white/10 text-left px-6 py-4 rounded-xl font-bold transition">
                            3. Deploy Website to Vercel →
                        </button>
                    </div>
                </div>

                <div className="glass-card p-6 rounded-2xl">
                    <h2 className="text-xl font-bold mb-4">Recent Server Activity</h2>
                    <div className="space-y-4 text-sm text-gray-300">
                        <div className="flex justify-between border-b border-white/5 pb-2">
                            <span>Database Sync</span><span className="text-green-400">Success (2 mins ago)</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-2">
                            <span>Social Wall Moderation</span><span className="text-yellow-400">14 Pending</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-2">
                            <span>Telegram Bot</span><span className="text-green-400">Online</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function MetricCard({ title, value, subtitle, color, border }: any) {
    return (
        <div className={`rounded-2xl p-6 bg-gradient-to-br ${color} border ${border} backdrop-blur-md`}>
            <h3 className="text-gray-400 font-medium mb-1 text-sm">{title}</h3>
            <div className="text-4xl font-black mb-1">{value}</div>
            <div className="text-sm text-gray-500">{subtitle}</div>
        </div>
    )
}
