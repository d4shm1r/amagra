# Mission Control (Amagra UI)

The Amagra dashboard. Built with [React 19](https://react.dev/) and
[Vite](https://vite.dev/) (migrated off Create React App).

## Available scripts

Run these from the `ui/` directory.

### `npm start` (alias: `npm run dev`)

Starts the Vite dev server at [http://localhost:3000](http://localhost:3000)
with hot module replacement. The dashboard expects the API on
`http://localhost:8000` — start it separately (or use `start-agents.sh`, which
launches Ollama, the API, and this UI together).

### `npm run build`

Builds the production bundle to the `build/` folder — minified, with hashed
filenames. Static assets in `public/` (including `landing.html`) are copied to
the build root.

### `npm run preview`

Serves the production `build/` locally to sanity-check a build before shipping.

## Project layout

- `index.html` — Vite entry (at the project root, not in `public/`).
- `src/index.jsx` — React bootstrap.
- `src/App.jsx` — Mission Control shell; owns navigation and global state.
- `src/*.jsx` — one component per dashboard tab.
- `public/` — static assets served at `/` (favicon, manifest, `landing.html`).
- `vite.config.js` — build config; output dir is `build/` to match the old CRA path.

## Notes

JSX may live in `.jsx` files only. The two former CRA entry points
(`index.js`, `App.js`) were renamed to `.jsx` during the Vite migration so the
production build's import analysis parses them correctly.
