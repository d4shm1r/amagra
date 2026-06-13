import os as _os
path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "ui", "src", "App.js")
with open(path) as f:
    content = f.read()

# Fix 1: Quick Start command block
OLD1 = '''              <div style={{fontFamily:"monospace",fontSize:12,color:"#00FF88",background:"#051A0D",borderRadius:8,padding:"12px 16px",marginBottom:14}}>
                ~/start-agents.sh
              </div>'''
NEW1 = '''              <div style={{fontFamily:"monospace",fontSize:12,color:"#00FF88",background:"#051A0D",borderRadius:8,padding:"12px 16px",marginBottom:14}}>
                <div>Tab 1: <span style={{color:"#FFD700"}}>ai-ui</span> &nbsp;→ starts React on localhost:3000</div>
                <div style={{marginTop:6}}>Tab 2: <span style={{color:"#FFD700"}}>ai-start</span> &nbsp;→ starts backend on port 8000</div>
                <div style={{marginTop:6,color:"#8B949E"}}>ai-stop &nbsp;· &nbsp;ai-logs &nbsp;(also available)</div>
              </div>'''

assert OLD1 in content, "Fix 1 not found"
content = content.replace(OLD1, NEW1, 1)
print("✓ Fix 1: Quick Start commands updated to aliases")

# Fix 2: Model info
OLD2 = '                  {label:"Model",value:"Llama3 8B via Ollama"},'
NEW2 = '                  {label:"Model",value:"Llama3 q3_K_M · RTX 2050"},'
assert OLD2 in content, "Fix 2 not found"
content = content.replace(OLD2, NEW2, 1)
print("✓ Fix 2: Model info updated to q3_K_M + GPU")

# Fix 3: Recommended Daily Workflow steps
OLD3 = '                  {["1. Run ~/start-agents.sh","2. Open localhost:3000","3. Pin current project context","4. Queue background tasks","5. Chat for immediate questions","6. Check Knowledge tab for growth"].map((step,i)=>('
NEW3 = '                  {["1. Tab 1: ai-ui","2. Tab 2: ai-start","3. Pin current project context","4. Force-route to specific agent if needed","5. Use Task Queue for background jobs","6. Check Traces tab to see routing decisions"].map((step,i)=>('
assert OLD3 in content, "Fix 3 not found"
content = content.replace(OLD3, NEW3, 1)
print("✓ Fix 3: Daily workflow updated to aliases")

# Fix 4: Quick Start steps
OLD4 = '                {["1. Run start-agents.sh","2. Open localhost:3000","3. Pin current project context","4. Use Chat for quick questions","5. Use Task Queue for background jobs","6. Edit user_profile.py to steer agent tone"].map((step,i)=>('
NEW4 = '                {["1. Tab 1: ai-ui","2. Tab 2: ai-start","3. Pin context for your current task","4. Chat for quick questions","5. Task Queue for background jobs","6. Edit user_profile.py to steer tone"].map((step,i)=>('
assert OLD4 in content, "Fix 4 not found"
content = content.replace(OLD4, NEW4, 1)
print("✓ Fix 4: Quick Start steps updated")

# Fix 5: "5 phases completed" subtitle
OLD5 = '              <div style={{fontSize:12,color:"#8B949E",marginBottom:16}}>5 phases completed — built from scratch using LangGraph v1.0 + Llama3 on Ubuntu Linux.</div>'
NEW5 = '              <div style={{fontSize:12,color:"#8B949E",marginBottom:16}}>8 phases completed — built from scratch using LangGraph v1.0 + Llama3 q3_K_M on Ubuntu Linux · RTX 2050 GPU active.</div>'
assert OLD5 in content, "Fix 5 not found"
content = content.replace(OLD5, NEW5, 1)
print("✓ Fix 5: Phase count updated to 8")

# Fix 6: Header subtitle
OLD6 = '            <div style={{fontSize:11,color:"#8B949E",marginTop:1}}>LangGraph v1.0 · Llama3 8B · Ubuntu · 100% Local</div>'
NEW6 = '            <div style={{fontSize:11,color:"#8B949E",marginTop:1}}>LangGraph v1.0 · Llama3 q3_K_M · RTX 2050 · Ubuntu · 100% Local</div>'
assert OLD6 in content, "Fix 6 not found"
content = content.replace(OLD6, NEW6, 1)
print("✓ Fix 6: Header subtitle updated with GPU info")

# Fix 7: Tech stack - update model reference
OLD7 = '"LangGraph v1.0.8","Llama3 8B via Ollama"'
NEW7 = '"LangGraph v1.0.8","Llama3 q3_K_M via Ollama","RTX 2050 GPU"'
assert OLD7 in content, "Fix 7 not found"
content = content.replace(OLD7, NEW7, 1)
print("✓ Fix 7: Tech stack updated")

# Fix 8: Add Phase 9 to BUILD_PHASES
OLD8 = '];'
NEW8 = '''  { id:9, label:"Phase 9", title:"Performance + Machine",   color:"#00BFFF", steps:["GPU driver installed (RTX 2050)","LLM fallback removed from router — 17/17 keyword tests pass","Model switched to llama3:8b-instruct-q3_K_M (4GB fits VRAM)","OLLAMA_MAX_LOADED_MODELS=1 prevents VRAM conflict","Response time: 361s → 56s (6x improvement)","Aliases added: ai-start · ai-ui · ai-stop · ai-logs","mission-control merged into agentic-ai/ui/","Unnecessary services disabled (cups, avahi, ModemManager)"] },
];'''
# Only replace the first occurrence after BUILD_PHASES
idx = content.find('  { id:8, label:"Phase 8"')
end_idx = content.find('];', idx)
assert end_idx > 0, "BUILD_PHASES end not found"
content = content[:end_idx] + NEW8 + content[end_idx+2:]
print("✓ Fix 8: Phase 9 added to BUILD_PHASES")

with open(path, "w") as f:
    f.write(content)
print("\nAll fixes applied.")
