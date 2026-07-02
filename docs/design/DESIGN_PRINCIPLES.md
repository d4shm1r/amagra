# Amagra — Experience Principles

> The **experience** contract. Where [`VISION.md`](../product/VISION.md) says *what Amagra is*
> (the AI operating layer above models, agents, and devices) and `ROADMAP.md` says
> *what we build next*, this document says *how it must feel*. It is a **filter**:
> every new feature, screen, and interaction is checked against these rules before it
> ships. Distilled from the founder's experience reflection (July 2026).

Amagra is not "a chatbot." It is an **AI operating layer** for the computer — a
persistent companion that treats natural language as the primary interface for getting
things done. Users remember how software *feels* more than how many options it has, so
the experience is the foundation, not a coat of paint.

---

## The principles

### 1. Instant continuity
The app is never "opened" — it is simply **there**, exactly where the user left it.

- No splash screen. No onboarding after first setup. No "How can I help you today?"
- The last conversation is already visible; the cursor is ready for typing.
- Reopening should feel like reopening a notebook, not launching an application.

### 2. Chat is the home
The chat is not one feature among many — it **is** the application. Everything else
exists to support it.

- The user thinks *"I need something,"* types it, and the system decides how to solve it.
- No hunting through menus first. If a task can be started from chat, it should not
  require its own entry point.

### 3. Long-running work is separated from the conversation
Starting work and watching work are two different spaces.

- The assistant acknowledges immediately (*"Working on it…"*) and the chat stays clean.
- A separate surface — **Tasks / Activity / Workspace** — carries the live steps,
  logs, commands, files affected, undo, and estimated time.
- A subtle indicator (`•••`) on the message shows there is active work; clicking it
  opens the execution view. The user can ignore the details or inspect every step.
- On completion the chat gets a single readable result (*"Desktop cleaned — 247 files
  organized."*); the mechanics live in the task, not the conversation.

### 4. Advanced tools stay out of the way
Models, MCP servers, agents, permissions, terminal commands, plugins — most users never
want to see these. They belong in an **advanced** section. The default interface stays
almost empty.

### 5. Luxury through restraint
"Luxurious" means *quiet*, not *expensive-looking*. Luxury is achieved by removing
things, not adding them.

- Almost no visual noise; consistent spacing; smooth, calm motion.
- Instant responses; every interaction feels intentional; no unnecessary dialogs.
- Brand rule (see [`theme.js`](../../ui/src/theme.js)): **gold is the signature, never the
  hierarchy system**; lead with the AMAGRA serif wordmark, never a glyph/monogram.

---

## Using this as a filter

When unsure about a new feature or screen, ask:

> *"Does this support the experience I'm trying to create, or does it add complexity
> that belongs somewhere else?"*

Concrete rules that fall out of the principles above — every screen must satisfy them:

- [ ] Chat remains the primary interface.
- [ ] The app resumes exactly where the user left off.
- [ ] No splash screens or onboarding after initial setup.
- [ ] Long-running actions never block the conversation.
- [ ] Technical details are available but hidden by default.
- [ ] Advanced configuration stays out of the main workflow.
- [ ] Every screen earns its place — if a feature can be initiated through chat, it
      does not get a separate entry point.

Distinguish **conversation** from **execution** in every design: the conversation
*starts* the work; the work has its own space.
