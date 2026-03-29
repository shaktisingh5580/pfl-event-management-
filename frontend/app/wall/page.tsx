"use client";
import { useState } from "react";
import { Check, X, ShieldAlert, Image as ImageIcon } from "lucide-react";

export default function SocialWallPage() {
    const [photos, setPhotos] = useState([
        { id: 1, sender: "AliceJohnson", url: "https://res.cloudinary.com/demo/image/upload/sample.jpg", status: "pending" },
        { id: 2, sender: "TechBro99", url: "https://res.cloudinary.com/demo/image/upload/cld-sample-2.jpg", status: "pending" },
        { id: 3, sender: "EventLover", url: "https://res.cloudinary.com/demo/image/upload/cld-sample-3.jpg", status: "pending" }
    ]);

    const handleAction = (id: number, action: 'approve' | 'reject') => {
        // In prod, this would hit the API which then triggers Cloudinary bot overlay
        setPhotos(prev => prev.filter(p => p.id !== id));
    };

    return (
        <div className="p-10 max-w-7xl mx-auto h-screen flex flex-col">
            <div className="mb-8">
                <h1 className="text-3xl font-black flex items-center gap-3"><ShieldAlert className="text-yellow-400" /> Social Wall Moderation Queue</h1>
                <p className="text-gray-400 mt-1">Review photos sent to the Telegram bot before they appear on the public live wall.</p>
            </div>

            <div className="flex-1 overflow-y-auto">
                {photos.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-500">
                        <ImageIcon size={64} className="mb-4 opacity-50" />
                        <p className="text-xl font-semibold">Queue is empty!</p>
                        <p>All photos have been moderated.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {photos.map(p => (
                            <div key={p.id} className="glass-card rounded-2xl overflow-hidden flex flex-col">
                                <div className="aspect-square relative group">
                                    <img src={p.url} alt="User submission" className="w-full h-full object-cover" />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent group-hover:from-black opacity-0 group-hover:opacity-100 transition duration-300 flex items-end p-4">
                                        <p className="text-gray-300 text-sm font-medium">Auto AI safety check passed</p>
                                    </div>
                                </div>
                                <div className="p-5 flex flex-col justify-between flex-1">
                                    <p className="text-gray-300 text-sm mb-4">
                                        Uploaded by <span className="font-bold text-white">@{p.sender}</span>
                                    </p>
                                    <div className="flex gap-3">
                                        <button
                                            onClick={() => handleAction(p.id, 'reject')}
                                            className="flex-1 flex items-center justify-center gap-2 bg-red-600/20 hover:bg-red-600/40 text-red-500 py-2.5 rounded-xl font-bold transition">
                                            <X size={18} /> Reject
                                        </button>
                                        <button
                                            onClick={() => handleAction(p.id, 'approve')}
                                            className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 text-white py-2.5 rounded-xl font-bold transition">
                                            <Check size={18} /> Approve
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
