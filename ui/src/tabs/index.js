// tabs/ — every routed view in the app, registered in one place.
//
// Naming rule: a routed view is `tabs/XxxTab.jsx`, default-exported. If it is
// not routed, it is not a tab — it belongs in components/panels/.
//
// Chunking rule (unchanged from before the split):
//   eager — Chat (the default view), Home (the pre-nav landing)
//   lazy  — everything else, one chunk per tab, fetched on first visit. This
//           keeps the initial bundle to Chat/Home instead of parsing ~30 heavy
//           tab trees (charts, graphs, Monaco) up front.
import { lazy } from "react";

export { default as ChatTab } from "./ChatTab";
export { default as HomeTab } from "./HomeTab";

export const AboutTab            = lazy(() => import("./AboutTab"));
export const CognitionTab        = lazy(() => import("./CognitionTab"));
export const CognitiveOSTab      = lazy(() => import("./CognitiveOSTab"));
export const ConsensusTab        = lazy(() => import("./ConsensusTab"));
export const ContextInspectorTab = lazy(() => import("./ContextInspectorTab"));
export const DataTab             = lazy(() => import("./DataTab"));
export const DecisionTimelineTab = lazy(() => import("./DecisionTimelineTab"));
export const DiagnosticsTab      = lazy(() => import("./DiagnosticsTab"));
export const ExplainProjectTab   = lazy(() => import("./ExplainProjectTab"));
export const GoalsTab            = lazy(() => import("./GoalsTab"));
export const GuideTab            = lazy(() => import("./GuideTab"));
export const KnowledgeGraphTab   = lazy(() => import("./KnowledgeGraphTab"));
export const LibraryTab          = lazy(() => import("./LibraryTab"));
export const LogTab              = lazy(() => import("./LogTab"));
export const MemoryBrowserTab    = lazy(() => import("./MemoryBrowserTab"));
export const MindMapTab          = lazy(() => import("./MindMapTab"));
export const PreferencesTab      = lazy(() => import("./PreferencesTab"));
export const ProjectStateTab     = lazy(() => import("./ProjectStateTab"));
export const PromptEditorTab     = lazy(() => import("./PromptEditorTab"));   // carries Monaco (~3.7 MB)
export const ProviderSettingsTab = lazy(() => import("./ProviderSettingsTab"));
export const ResearchTab         = lazy(() => import("./ResearchTab"));
export const RunsTab             = lazy(() => import("./RunsTab"));
export const ShortcutsTab        = lazy(() => import("./ShortcutsTab"));
export const SkillsTab           = lazy(() => import("./SkillsTab"));
export const TasksTab            = lazy(() => import("./TasksTab"));
export const TimelineTab         = lazy(() => import("./TimelineTab"));
export const VersionHistoryTab   = lazy(() => import("./VersionHistoryTab"));
