// Markdown.jsx — rendered markdown (the doc reader, agent responses).
// The prose styles are a stylesheet, not inline styles, because they target
// tags produced at runtime. They live here — in the kit — so no tab ships its
// own <style> block full of hex ever again.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { T, TYPE, SPACE, RADIUS } from "@/styles/theme";

export function Markdown({ children, maxHeight }) {
  return (
    <div className="md-prose" style={{
      ...TYPE.caption, color: T.text, lineHeight: 1.7,
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: RADIUS.md - 2, padding: `${SPACE[4]}px ${SPACE[5]}px`,
      ...(maxHeight ? { maxHeight, overflowY: "auto", overflowX: "auto" } : null),
    }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
