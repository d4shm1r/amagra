import sys
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orchestration.coordinator import coordinator

print("""
╔══════════════════════════════════════════════╗
║        LOCAL AGENTIC AI — 9 AGENTS          ║
║   LangGraph v1.0 · phi4-mini · 100% Local      ║
╠══════════════════════════════════════════════╣
║  Agents: IT · Python · Blazor · AI/ML       ║
║          Docs · Projects · Research · Learn  ║
║  Type 'quit' to exit · 'agents' to list     ║
╚══════════════════════════════════════════════╝
""")

AGENT_LIST = """
Available specialist agents:
  🌐 IT & Networking    — network issues, Wi-Fi, routers
  🐍 Python Dev         — code, scripts, automation
  ⚡ Blazor Dev         — .NET, C#, Blazor components
  🤖 AI & ML            — AI concepts, frameworks, models
  📄 Documents          — reports, proposals, business writing
  🎯 Personal Projects  — project tracking, ideas, side hustles
  🔬 Research           — analysis, synthesis, fact-finding
  📚 Knowledge          — learning, explanations, study plans
"""

while True:
    try:
        user_input = input("\n🧠 You: ").strip()

        if not user_input:
            continue
        if user_input.lower() == 'quit':
            print("\n👋 Shutting down agents. Goodbye!")
            break
        if user_input.lower() == 'agents':
            print(AGENT_LIST)
            continue

        print("\n⏳ Thinking...\n")

        result = coordinator.invoke({
            "messages":       [{"role": "user", "content": user_input}],
            "active_agent":   "",
            "task":           user_input,
            "result":         "",
            "next_agent":     "",
            "memory":         {},
            "force_agent":    "",
            "brain_decision": {},
            "reflect":        False,
            "reflect_type":   "general",
        })

        agent_used = result.get("active_agent", "unknown")
        response   = result["messages"][-1].content

        print(f"🤖 [{agent_used.upper().replace('_',' ')}]:\n")
        print(response)
        print(f"\n{'─'*50}")

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
        break
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Try rephrasing your question.")
