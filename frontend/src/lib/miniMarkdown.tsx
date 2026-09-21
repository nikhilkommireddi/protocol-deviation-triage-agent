import type { ReactNode } from "react";

// A small, hand-rolled renderer for the specific markdown subset
// data/labels.md actually uses (#, ##, **bold**, *italic*, `code`, - bullets
// with wrapped continuation lines) -- not a general markdown parser. Adding
// a markdown library for one static reference file would be overkill for
// this project's minimal-dependency convention.

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const tokens: ReactNode[] = [];
  let remaining = text;
  let key = 0;
  const pattern = /(\*\*(.+?)\*\*|`(.+?)`|\*(.+?)\*)/;

  while (remaining.length > 0) {
    const match = pattern.exec(remaining);
    if (!match) {
      tokens.push(remaining);
      break;
    }
    if (match.index > 0) {
      tokens.push(remaining.slice(0, match.index));
    }
    if (match[2] !== undefined) {
      tokens.push(<strong key={`${keyPrefix}-${key++}`}>{match[2]}</strong>);
    } else if (match[3] !== undefined) {
      tokens.push(
        <code
          key={`${keyPrefix}-${key++}`}
          className="bg-slate-100 text-slate-700 px-1 py-0.5 rounded text-[0.85em] font-mono"
        >
          {match[3]}
        </code>,
      );
    } else if (match[4] !== undefined) {
      tokens.push(<em key={`${keyPrefix}-${key++}`}>{match[4]}</em>);
    }
    remaining = remaining.slice(match.index + match[0].length);
  }
  return tokens;
}

export function renderMiniMarkdown(markdown: string): ReactNode {
  const lines = markdown.split("\n");
  const blocks: ReactNode[] = [];
  let paragraphLines: string[] = [];
  let listItemTexts: string[] = [];
  let blockKey = 0;

  function flushParagraph() {
    if (paragraphLines.length > 0) {
      const text = paragraphLines.join(" ");
      blocks.push(
        <p key={`p-${blockKey}`} className="text-sm text-slate-700 my-2 leading-relaxed">
          {renderInline(text, `p-${blockKey++}`)}
        </p>,
      );
      paragraphLines = [];
    }
  }

  function flushList() {
    if (listItemTexts.length > 0) {
      const items = listItemTexts;
      blocks.push(
        <ul key={`ul-${blockKey}`} className="list-disc list-inside space-y-1.5 my-2 ml-1">
          {items.map((text, i) => (
            <li key={`li-${blockKey}-${i}`} className="text-sm text-slate-700">
              {renderInline(text, `li-${blockKey}-${i}`)}
            </li>
          ))}
        </ul>,
      );
      blockKey++;
      listItemTexts = [];
    }
  }

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();

    if (trimmed === "") {
      flushParagraph();
      continue;
    }

    if (trimmed.startsWith("# ")) {
      flushParagraph();
      flushList();
      blocks.push(
        <h1 key={`h1-${blockKey}`} className="text-xl font-bold text-slate-900 mt-6 mb-2 first:mt-0">
          {renderInline(trimmed.slice(2), `h1-${blockKey++}`)}
        </h1>,
      );
    } else if (trimmed.startsWith("## ")) {
      flushParagraph();
      flushList();
      blocks.push(
        <h2
          key={`h2-${blockKey}`}
          className="text-lg font-semibold text-slate-800 mt-5 mb-2 pb-1 border-b border-slate-200"
        >
          {renderInline(trimmed.slice(3), `h2-${blockKey++}`)}
        </h2>,
      );
    } else if (trimmed.startsWith("- ")) {
      flushParagraph();
      listItemTexts.push(trimmed.slice(2));
    } else if (listItemTexts.length > 0) {
      // A wrapped continuation line of the current bullet, not a new block.
      listItemTexts[listItemTexts.length - 1] += " " + trimmed;
    } else {
      paragraphLines.push(trimmed);
    }
  }
  flushParagraph();
  flushList();

  return <>{blocks}</>;
}
