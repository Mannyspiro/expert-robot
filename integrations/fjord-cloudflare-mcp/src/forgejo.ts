export const ORIGIN = "https://commons.fjord.host";
const slug = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$/;
const safePart = (part: string): boolean =>
  slug.test(part) && part !== ".." && part !== "." && !part.includes("..");
export function makeApiPath(
  kind: "userRepos"|"repository"|"issues"|"pulls"|"contents",
  owner?: string, repo?: string, filepath?: string,
): string {
  if(kind === "userRepos") return "/api/v1/user/repos?limit=25&page=1";
  if(!owner || !repo || !safePart(owner) || !safePart(repo)) throw new Error("invalid repository identifier");
  const root = "/api/v1/repos/"+encodeURIComponent(owner)+"/"+encodeURIComponent(repo);
  if(kind === "repository") return root;
  if(kind === "issues") return root+"/issues?state=open&limit=25&page=1";
  if(kind === "pulls") return root+"/pulls?state=open&limit=25&page=1";
  if(kind === "contents") {
    if (!filepath || filepath.length > 300 || filepath.startsWith("/") ||
        filepath.includes("\\") || filepath.includes("%") || filepath.includes("?") ||
        filepath.split("/").some(p=> !safePart(p))) throw new Error("invalid file path");
    return root+"/contents/"+filepath.split("/").map(encodeURIComponent).join("/");
  }
  throw new Error("unapproved operation");
}
export function authorizedOwner(owner: string, allowlist: string): boolean {
  return allowlist.split(",").map(x=>x.trim()).filter(Boolean).includes(owner) && safePart(owner);
}
export function safeForgejoUrl(path: string): string {
  if (!path.startsWith("/api/v1/") || path.includes("://")) throw new Error("untrusted API path");
  const result = new URL(path, ORIGIN);
  if (result.origin !== ORIGIN || !result.pathname.startsWith("/api/v1/"))
    throw new Error("cross-origin request rejected");
  return result.toString();
}
export async function fetchForgejo(
  bearer: string, path: string, fetchImpl: typeof fetch = fetch
): Promise<string> {
  if (!bearer || bearer.length > 4096) throw new Error("authentication unavailable");
  const response = await fetchImpl(safeForgejoUrl(path), {
    method:"GET",redirect:"manual",
    headers:{"Authorization":"Bearer "+bearer,"Accept":"application/json"},
  });
  if(!response.ok || response.status >= 300) throw new Error("Forgejo API request failed");
  const reader = response.body?.getReader();
  if(!reader) throw new Error("empty upstream response");
  const pieces:Uint8Array[]=[]; let total=0;
  for(;;){
    const {value,done}=await reader.read();
    if(done)break;
    total+=value.length;
    if(total>65536){await reader.cancel();throw new Error("API report size limit exceeded");}
    pieces.push(value);
  }
  const bytes=new Uint8Array(total);let index=0;
  for(const piece of pieces){bytes.set(piece,index);index+=piece.length;}
  return new TextDecoder("utf-8",{fatal:true}).decode(bytes);
}
