// Resolve an asset reference to something Remotion's <Img>/<OffthreadVideo>/<Audio> can load.
// - http(s)/data URIs: pass through.
// - file:// URIs: pass through UNCHANGED (already absolute & valid). The previous
//   inline version stripped "file://" with /^file:\/\/\/?/, whose optional trailing
//   slash ate the leading "/" of Unix paths, demoting absolute paths to relative and
//   sending them through staticFile() -> served from /public/ -> 404.
// - bare absolute paths (Unix /… or Windows C:/…): wrap as a file:// URI.
// - everything else: treat as a public/-relative path via staticFile.
export function resolveAsset(src: string, staticFile: (p: string) => string): string {
  if (!src) return src;
  if (/^(https?:|data:)/.test(src)) return src;
  if (src.startsWith("file://")) return src;                 // already a valid file URI
  const norm = src.replace(/\\/g, "/");
  if (norm.startsWith("/")) return `file://${norm}`;          // Unix absolute -> file:///…
  if (/^[A-Za-z]:\//.test(norm)) return `file:///${norm}`;    // Windows absolute -> file:///C:/…
  return staticFile(norm);                                    // public/-relative
}
