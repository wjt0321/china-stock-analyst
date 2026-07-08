import { useMemo } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import "./Markdown.css";

interface MarkdownProps {
  content: string;
}

export default function Markdown({ content }: MarkdownProps) {
  const html = useMemo(() => {
    const raw = marked.parse(content, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  }, [content]);

  return (
    <div
      className="markdown-body"
      dangerouslySetInnerHTML={{ __html: html }}
      style={{
        lineHeight: 1.6,
        fontFamily: "system-ui, -apple-system, sans-serif",
        color: "#333",
      }}
    />
  );
}
