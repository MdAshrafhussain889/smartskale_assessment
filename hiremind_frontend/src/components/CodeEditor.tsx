"use client";

import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
      <div className="flex h-48 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
      Loading editor...
    </div>
  ),
});

const LANG_MAP: Record<string, string> = {
  python: "python",
  python3: "python",
  java: "java",
  cpp: "cpp",
  c: "c",
  js: "javascript",
  javascript: "javascript",
  sql: "sql",
};

export function CodeEditor({
  language,
  value,
  onChange,
}: {
  language: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const monacoLang = LANG_MAP[language.toLowerCase()] ?? "python";

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <MonacoEditor
      height="220px"
        language={monacoLang}
        theme="vs-dark"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          scrollBeyondLastLine: false,
          automaticLayout: true,
        }}
      />
    </div>
  );
}
