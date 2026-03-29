"use client"

import { useState, useEffect, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Send, Image as ImageIcon, Ticket, MessageSquare, LogOut, CheckCircle2 } from 'lucide-react'

type Message = { id: string; role: 'user' | 'assistant'; content: string; time: string }

export default function ParticipantDashboard() {
    const params = useParams()
    const eventId = params.eventId as string
    const router = useRouter()
    
    const [user, setUser] = useState<any>(null)
    const [activeTab, setActiveTab] = useState<'chat' | 'ticket' | 'wall'>('chat')
    
    // Chat state
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [isTyping, setIsTyping] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    // Wall state
    const [uploading, setUploading] = useState(false)
    const [uploadSuccess, setUploadSuccess] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    useEffect(() => {
        const stored = localStorage.getItem(`participant_${eventId}`)
        if (!stored) {
            router.push(`/p/${eventId}/login`)
            return
        }
        const parsedUser = JSON.parse(stored)
        setUser(parsedUser)
        
        // Initial greeting
        setMessages([
            {
                id: '1',
                role: 'assistant',
                content: `👋 Welcome to the Web Portal, ${parsedUser.name}!\n\nI'm your AI event assistant. You can ask me questions about the schedule, networking, or use me to report any issues (complaints).`,
                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
        ])
    }, [eventId, router])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, isTyping])

    const handleLogout = () => {
        localStorage.removeItem(`participant_${eventId}`)
        router.push(`/p/${eventId}/login`)
    }

    const sendMessage = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!input.trim() || !user) return

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim(),
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }

        setMessages(prev => [...prev, userMsg])
        setInput('')
        setIsTyping(true)

        try {
            const res = await fetch('http://localhost:8000/api/participant/chat', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMsg.content,
                    attendee_id: user.id,
                    event_id: eventId
                })
            })
            const data = await res.json()
            
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.reply || "Sorry, I had trouble processing that.",
                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }])
        } catch (error) {
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: "Network error trying to reach the event AI.",
                time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }])
        } finally {
            setIsTyping(false)
        }
    }

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file || !user) return

        setUploading(true)
        setUploadSuccess(false)

        try {
            const reader = new FileReader()
            reader.readAsDataURL(file)
            reader.onload = async () => {
                const base64string = (reader.result as string).split(',')[1]

                const res = await fetch('http://localhost:8000/api/participant/upload_wall', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image_base64: base64string,
                        attendee_id: user.id,
                        sender_name: user.name,
                        event_id: eventId
                    })
                })
                
                if (!res.ok) {
                    const err = await res.json()
                    throw new Error(err.detail || "Upload failed")
                }

                setUploadSuccess(true)
                setTimeout(() => setUploadSuccess(false), 5000)
            }
        } catch (error: any) {
            alert(`Error: ${error.message}`)
        } finally {
            setUploading(false)
            if (fileInputRef.current) fileInputRef.current.value = ''
        }
    }

    if (!user) return <div className="min-h-screen bg-background flex items-center justify-center">Loading...</div>

    return (
        <div className="min-h-screen bg-background text-white flex flex-col md:flex-row max-w-7xl mx-auto">
            
            {/* Nav Sidebar / Bottom Bar */}
            <nav className="w-full md:w-64 glass-card md:min-h-screen p-4 flex md:flex-col justify-between md:justify-start gap-2 border-b md:border-b-0 md:border-r border-white/10 shrink-0 sticky top-0 md:relative z-10">
                <div className="hidden md:block mb-8 px-4 py-2 mt-4">
                    <h1 className="text-xl font-black text-purple-400 truncate">Attendee Portal</h1>
                    <p className="text-xs text-gray-400 truncate">{user.name}</p>
                </div>

                <div className="flex md:flex-col gap-2 w-full justify-around md:justify-start">
                    <button onClick={() => setActiveTab('chat')} className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${activeTab === 'chat' ? 'bg-purple-600 font-bold text-white' : 'hover:bg-white/5 text-gray-400'}`}>
                        <MessageSquare size={20} /><span className="hidden md:inline">AI Chatbot</span>
                    </button>
                    <button onClick={() => setActiveTab('ticket')} className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${activeTab === 'ticket' ? 'bg-purple-600 font-bold text-white' : 'hover:bg-white/5 text-gray-400'}`}>
                        <Ticket size={20} /><span className="hidden md:inline">My Ticket</span>
                    </button>
                    <button onClick={() => setActiveTab('wall')} className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${activeTab === 'wall' ? 'bg-purple-600 font-bold text-white' : 'hover:bg-white/5 text-gray-400'}`}>
                        <ImageIcon size={20} /><span className="hidden md:inline">Live Wall</span>
                    </button>
                </div>

                <div className="mt-auto hidden md:block">
                    <button onClick={handleLogout} className="flex w-full items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/5 transition-colors text-red-400">
                        <LogOut size={20} /><span>Sign Out</span>
                    </button>
                </div>
            </nav>

            {/* Main Content Area */}
            <main className="flex-1 flex flex-col min-h-[calc(100vh-80px)] md:min-h-screen relative overflow-hidden bg-black/20">
                
                {activeTab === 'chat' && (
                    <div className="flex flex-col h-full w-full max-w-3xl mx-auto">
                        {/* Messages Area */}
                        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
                            {messages.map(msg => (
                                <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                    <div className="flex items-end gap-2 max-w-[85%]">
                                        {msg.role === 'assistant' && <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-blue-500 shrink-0 flex items-center justify-center text-sm">AI</div>}
                                        
                                        <div className={`p-4 rounded-2xl ${msg.role === 'user' ? 'bg-purple-600 text-white rounded-br-sm' : 'glass-card border border-white/10 text-gray-200 rounded-bl-sm whitespace-pre-wrap'}`}>
                                            {msg.content}
                                        </div>
                                    </div>
                                    <span className="text-xs text-gray-500 mt-1 mx-10">{msg.time}</span>
                                </div>
                            ))}
                            {isTyping && (
                                <div className="flex items-center gap-2 text-gray-400 text-sm ml-10">
                                    <div className="animate-pulse">Bot is thinking...</div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Input Area */}
                        <div className="p-4 md:p-6 glass-card border-t border-white/5 shrink-0 bg-background/80 backdrop-blur-xl">
                            <form onSubmit={sendMessage} className="flex gap-3 max-w-3xl mx-auto">
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Need help? Ask the AI or report an issue..."
                                    className="flex-1 bg-white/5 border border-white/10 rounded-full px-6 py-4 text-white focus:outline-none focus:border-purple-500 transition-colors placeholder-gray-500"
                                />
                                <button
                                    type="submit"
                                    disabled={!input.trim() || isTyping}
                                    className="w-14 h-14 bg-purple-600 hover:bg-purple-500 rounded-full flex items-center justify-center text-white transition-colors flex-shrink-0 disabled:opacity-50"
                                >
                                    <Send size={20} className="mr-1" />
                                </button>
                            </form>
                            <div className="text-center text-xs text-gray-600 mt-2">
                                For complaints, just type exactly what happened. The AI will categorize it.
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'ticket' && (
                    <div className="flex-1 p-6 flex flex-col items-center justify-center">
                        <div className="w-full max-w-md bg-gradient-to-b from-purple-900/40 to-black/80 border border-purple-500/30 rounded-3xl p-8 relative overflow-hidden backdrop-blur-xl shadow-2xl">
                             <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-purple-500 to-blue-500"></div>
                             <div className="text-center mb-8">
                                <h2 className="text-2xl font-black mb-1 text-white">{user.name}</h2>
                                <p className="text-gray-400">{user.email}</p>
                             </div>

                             <div className="bg-white p-4 rounded-2xl mb-8 flex justify-center">
                                {/* In a real app, generate the actual QR code image here */}
                                <div className="w-48 h-48 bg-gray-200 border-4 border-white flex items-center justify-center text-gray-400 font-mono text-xs text-center p-4">
                                    QR CODE DATA:<br/>{user.id}
                                </div>
                             </div>

                             <div className="space-y-4">
                                <div className="flex justify-between border-b border-white/10 pb-2">
                                    <span className="text-gray-400">Match Profile</span>
                                    <span className="font-semibold">{user.team_preference === 'looking_for_team' ? 'Looking for Team' : 'Complete'}</span>
                                </div>
                                <div className="flex justify-between border-b border-white/10 pb-2">
                                    <span className="text-gray-400">Status</span>
                                    <span className={user.checked_in ? 'text-green-400 font-bold' : 'text-yellow-400 font-bold'}>
                                        {user.checked_in ? 'Checked In' : 'Pending Gate Scan'}
                                    </span>
                                </div>
                             </div>
                        </div>
                        <p className="text-gray-500 mt-6 text-sm text-center">Show this QR code at the registration desk to enter the event.</p>
                    </div>
                )}

                {activeTab === 'wall' && (
                    <div className="flex-1 p-6 md:p-12 flex flex-col items-center justify-center">
                        <div className="text-center max-w-lg mb-8">
                            <div className="w-20 h-20 bg-gradient-to-tr from-purple-500/20 to-blue-500/20 rounded-full flex items-center justify-center text-4xl mx-auto mb-4 border border-purple-500/30">📸</div>
                            <h2 className="text-3xl font-black mb-3">Live Web Wall</h2>
                            <p className="text-gray-400">Snap a selfie or a picture of the event and upload it here. Approved photos will instantly appear on the giant screens across the venue!</p>
                        </div>

                        <div className="w-full max-w-md glass-card border border-white/10 border-dashed rounded-3xl p-10 flex flex-col items-center text-center transition-colors hover:bg-white/5 relative overflow-hidden group">
                           
                           {uploadSuccess ? (
                               <div className="text-green-400 flex flex-col items-center animate-pulse">
                                  <CheckCircle2 size={48} className="mb-4" />
                                  <span className="font-bold text-lg">Sent to Moderation!</span>
                                  <p className="text-sm mt-2 text-gray-500">Watch the big screens...</p>
                               </div>
                           ) : (
                               <>
                                <ImageIcon size={48} className="text-purple-400 mb-4 group-hover:scale-110 transition-transform" />
                                <span className="font-bold text-lg mb-2">{uploading ? 'Processing Image...' : 'Tap to Upload Photo'}</span>
                                <span className="text-sm text-gray-500 mb-6">JPG, PNG up to 5MB</span>
                                
                                <input 
                                    type="file" 
                                    accept="image/*" 
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                    onChange={handleFileUpload}
                                    disabled={uploading}
                                    ref={fileInputRef}
                                />
                                
                                <button className={`px-6 py-2 rounded-full font-bold transition-all ${uploading ? 'bg-gray-700 text-gray-400' : 'bg-white/10 text-white hover:bg-white/20'}`}>
                                    {uploading ? 'Uploading...' : 'Browse files'}
                                </button>
                               </>
                           )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    )
}
