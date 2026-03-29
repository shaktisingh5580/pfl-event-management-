"use client";
import { useState, useEffect } from "react";
import Editor from "@monaco-editor/react";
import { Globe, Code2, Rocket, RotateCcw } from "lucide-react";

export default function WebsiteEditorPage() {
    const [code, setCode] = useState(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sample Event Website</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
  <h1 class="text-5xl font-black bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">Autoevent Live</h1>
  <!-- Edit this code to see updates -->
</body>
</html>`);

    const [activeTab, setActiveTab] = useState("index.html");
    const [isDeploying, setIsDeploying] = useState(false);

    const handleDeploy = () => {
        setIsDeploying(true);
        setTimeout(() => {
            setIsDeploying(false);
            alert("Deployed to Vercel successfully!");
        }, 2000);
    };

    return (
        <div className="flex flex-col h-screen p-6">

            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-black flex items-center gap-2"><Globe className="text-blue-400" /> Web Deployer & Editor</h1>
                    <p className="text-sm text-gray-400">Review the AI-generated code, make manual adjustments, and deploy to production.</p>
                </div>
                <div className="flex gap-3">
                    <button className="flex items-center gap-2 bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl transition text-sm font-semibold">
                        <RotateCcw size={16} /> Regenerate
                    </button>
                    <button onClick={handleDeploy} disabled={isDeploying} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-2 rounded-xl transition text-sm font-bold shadow-lg shadow-blue-500/20 disabled:opacity-50">
                        {isDeploying ? "Deploying..." : <><Rocket size={16} /> Deploy to Vercel</>}
                    </button>
                </div>
            </div>

            {/* Editor Layout */}
            <div className="flex-1 flex gap-6 min-h-0">

                {/* File Explorer (Left) */}
                <div className="w-48 flex flex-col gap-2">
                    <FileTab name="index.html" active={activeTab === 'index.html'} onClick={() => setActiveTab('index.html')} />
                    <FileTab name="style.css" active={activeTab === 'style.css'} onClick={() => setActiveTab('style.css')} />
                    <FileTab name="wall.html" active={activeTab === 'wall.html'} onClick={() => setActiveTab('wall.html')} />
                    <FileTab name="verify.html" active={activeTab === 'verify.html'} onClick={() => setActiveTab('verify.html')} />
                </div>

                {/* Monaco Editor (Right) */}
                <div className="flex-1 rounded-2xl overflow-hidden glass-card border border-white/10 relative">
                    <Editor
                        height="100%"
                        defaultLanguage={activeTab.endsWith(".css") ? "css" : "html"}
                        language={activeTab.endsWith(".css") ? "css" : "html"}
                        theme="vs-dark"
                        value={code}
                        onChange={(val) => setCode(val || "")}
                        options={{
                            minimap: { enabled: false },
                            fontSize: 14,
                            fontFamily: "'JetBrains Mono', 'Courier New', monospace",
                            padding: { top: 16 }
                        }}
                    />
                </div>

            </div>
        </div>
    )
}

function FileTab({ name, active, onClick }: { name: string, active: boolean, onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition ${active ? 'bg-white/10 text-white font-semibold' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}`}
        >
            <Code2 size={16} className={active ? "text-blue-400" : "text-gray-500"} /> {name}
        </button>
    )
}
