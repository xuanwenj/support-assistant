import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Tailwind's preflight strips default element styles, so each one is restyled here.
// The answer is LLM output built from documents and customer data, so:
// - raw HTML is never rendered (no rehype-raw; react-markdown ignores it by default)
// - images render nothing (a markdown image would make the browser fetch any URL)
// - links open in a new tab without referrer/opener access
const components: Components = {
  p: ({ children }) => <p className="mt-3 first:mt-0">{children}</p>,
  h1: ({ children }) => <h3 className="mt-4 text-lg font-semibold">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-4 text-lg font-semibold">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-3 font-semibold">{children}</h4>,
  ul: ({ children }) => <ul className="mt-3 list-disc pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="mt-3 list-decimal pl-5">{children}</ol>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 underline dark:text-blue-400"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-zinc-100 px-1 py-0.5 text-sm dark:bg-zinc-800">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="mt-3 overflow-x-auto rounded bg-zinc-100 p-3 text-sm dark:bg-zinc-800">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="mt-3 overflow-x-auto">
      <table className="border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border px-3 py-1 text-left font-medium">{children}</th>
  ),
  td: ({ children }) => <td className="border px-3 py-1">{children}</td>,
  img: () => null,
};

export default function MarkdownAnswer({ children }: { children: string }) {
  return (
    <div>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
