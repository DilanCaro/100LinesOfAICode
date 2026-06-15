from flask import Flask, request, jsonify, render_template_string
from pathlib import Path
from werkzeug.utils import secure_filename
import os, sys
BASE = Path(__file__).parent
env = BASE.parents[1] / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
sys.path.append(str(BASE.parent))
from rag import MiniRAG
app = Flask(__name__)
UPLOADS = BASE / "uploads"
KB = BASE / "knowledge_base.json"
UPLOADS.mkdir(exist_ok=True)
rag = MiniRAG()
if KB.exists():
    rag.load(KB)
HTML = """
<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script><title>Mini RAG</title></head>
<body class="bg-slate-950 text-slate-100 min-h-screen grid place-items-center p-4">
<main class="w-full max-w-3xl bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl p-6">
  <h1 class="text-3xl font-bold mb-1">Mini RAG</h1>
  <p class="text-slate-400 mb-6">Upload docs, index them, then ask questions.</p>
  <section class="mb-5 p-4 rounded-xl bg-slate-950 border border-slate-800">
    <label class="block text-sm mb-2 text-slate-300">Add .txt or .md files</label>
    <div class="flex gap-2">
      <input id="files" type="file" multiple accept=".txt,.md" class="flex-1 text-sm">
      <button onclick="upload()" class="px-4 py-2 rounded-lg bg-indigo-500 hover:bg-indigo-400 font-semibold">Index</button>
    </div>
    <p id="status" class="text-sm text-slate-400 mt-2">Ready.</p>
  </section>
  <section class="space-y-3">
    <div id="chat" class="h-80 overflow-y-auto rounded-xl bg-slate-950 border border-slate-800 p-4 space-y-3"></div>
    <div class="flex gap-2">
      <input id="q" onkeydown="if(event.key==='Enter') ask()" placeholder="Ask about your documents..."
        class="flex-1 rounded-lg bg-slate-800 border border-slate-700 px-4 py-3 outline-none focus:ring-2 focus:ring-indigo-500">
      <button onclick="ask()" class="px-5 py-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold">Ask</button>
    </div>
  </section>
</main>
<script>
const chat = document.getElementById('chat'), q = document.getElementById('q'), status = document.getElementById('status');
function bubble(text, who){
  const div = document.createElement('div');
  div.className = who==='me' ? 'ml-auto max-w-[85%] bg-indigo-500 rounded-xl p-3' : 'max-w-[85%] bg-slate-800 rounded-xl p-3 whitespace-pre-wrap';
  div.textContent = text; chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
}
async function upload(){
  const data = new FormData();
  [...document.getElementById('files').files].forEach(f => data.append('files', f));
  status.textContent = 'Indexing...';
  const res = await fetch('/upload', {method:'POST', body:data});
  const out = await res.json(); status.textContent = out.message || out.error;
}
async function ask(){
  const question = q.value.trim(); if(!question) return;
  bubble(question, 'me'); q.value = ''; bubble('Thinking...', 'bot');
  const res = await fetch('/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question})});
  const out = await res.json(); chat.lastChild.textContent = out.answer || out.error;
}
</script></body></html>
"""

@app.get("/")
def home():
    return render_template_string(HTML)

@app.post("/upload")
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify(error="No files uploaded."), 400
    for f in files:
        name = secure_filename(f.filename)
        if not name.endswith((".txt", ".md")):
            continue
        path = UPLOADS / name
        f.save(path)
        rag.add_file(str(path))
    rag.save(KB)
    return jsonify(message=f"Indexed {len(rag.documents)} chunks.")

@app.post("/ask")
def ask():
    question = (request.json or {}).get("question", "").strip()
    if not question:
        return jsonify(error="Question is empty."), 400
    if not os.getenv("ANTHROPIC_API_KEY"):
        return jsonify(error="ANTHROPIC_API_KEY not set. Add it to .env and restart."), 500
    try:
        return jsonify(answer=rag.query(question))
    except Exception as e:
        return jsonify(error=str(e)), 500
if __name__ == "__main__":
    app.run(debug=True, port=5000)