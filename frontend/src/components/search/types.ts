export type Paper = {
  id: string;
  title: string;
  authors: string[];
  year: number;
  venue: string;
  abstract: string;
  doi?: string;
  pdfUrl?: string;
  url?: string;
  source: "Semantic Scholar" | "arXiv" | "URL Import";
};

/** Build the best available link for a paper */
export function getPaperLink(paper: Paper): string | null {
  if (paper.pdfUrl) return paper.pdfUrl;
  if (paper.url) return paper.url;
  if (paper.doi) return `https://doi.org/${paper.doi}`;
  if (paper.source === "Semantic Scholar" && paper.id) {
    return `https://www.semanticscholar.org/paper/${paper.id}`;
  }
  return null;
}
