// Local, CDN-free Monaco setup.
//
// @monaco-editor/react loads Monaco from a CDN (jsDelivr) by default — which
// would send a request off-machine every time the Prompt IDE opens, breaking
// Amagra's "nothing leaves your machine / no telemetry" promise. We point the
// loader at the bundled `monaco-editor` package and wire the base editor worker
// through Vite's `?worker` import, so the editor is fully offline and private.
import { loader } from "@monaco-editor/react";
// Core editor API only — NOT the full `monaco-editor` barrel, which drags in the
// JSON/HTML/CSS/TS language services and their multi-MB web workers (the TS worker
// alone is ~7 MB). A prompt editor only needs plain text + markdown coloring, so we
// pull the slim core and just the markdown basic-language contribution.
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/basic-languages/markdown/markdown.contribution";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

self.MonacoEnvironment = {
  getWorker() {
    return new EditorWorker();
  },
};

// "Gilded Calm" light theme — matches the dashboard's warm cream + gold palette
// (see theme.js) so the editor reads as part of Amagra, not a generic IDE.
monaco.editor.defineTheme("amagra", {
  base: "vs",
  inherit: true,
  rules: [
    { token: "",        foreground: "2E2010" },
    { token: "comment", foreground: "9A7A60", fontStyle: "italic" },
    { token: "keyword", foreground: "9A6C00" },
    { token: "string",  foreground: "0F766E" },
  ],
  colors: {
    "editor.background":                  "#F0E9DF",
    "editor.foreground":                  "#2E2010",
    "editorLineNumber.foreground":        "#C9B79B",
    "editorLineNumber.activeForeground":  "#9A6C00",
    "editor.lineHighlightBackground":     "#E9E0D2",
    "editor.lineHighlightBorder":         "#00000000",
    "editor.selectionBackground":         "#C4880833",
    "editorCursor.foreground":            "#1F1408",
    "editorIndentGuide.background":       "#E0D6C4",
    "editorIndentGuide.activeBackground": "#C9B79B",
    "scrollbarSlider.background":         "#D6C9B288",
    "scrollbarSlider.hoverBackground":    "#C9B79B",
  },
});

loader.config({ monaco });

export const MONACO_THEME = "amagra";
