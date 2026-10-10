import OAuthProvider from "@cloudflare/workers-oauth-provider";
import {McpServer} from "@modelcontextprotocol/sdk/server/mcp.js";
import {McpAgent} from "agents/mcp";
import {z} from "zod";
import {ForgejoHandler} from "./forgejo-handler";
import {authorizedOwner,fetchForgejo,makeApiPath} from "./forgejo";
type Props={login:string;accessToken:string};
export class FjordMCP extends McpAgent<Env,Record<string,never>,Props> {
 server=new McpServer({name:"fjord-commons-readonly",version:"0.1.0"});
 async init(){
  const respond=(s:string)=>({content:[{type:"text" as const,text:s}]});
  const authorized=(owner:string)=>{
    if(!authorizedOwner(owner,this.env.ALLOWED_REPO_OWNERS))
      throw new Error("Repository owner not in trusted allowlist");
  };
  this.server.tool("list_repositories","List signed-in user's accessible repositories (read-only)",{},async()=>{
    const raw=await fetchForgejo(this.props!.accessToken,makeApiPath("userRepos"));
    const repos=JSON.parse(raw) as Array<{owner?:{login?:string}}>;
    if(!Array.isArray(repos))throw new Error("invalid Forgejo repository listing");
    return respond(JSON.stringify(repos.filter(r=>r.owner?.login &&
      authorizedOwner(r.owner.login,this.env.ALLOWED_REPO_OWNERS))));
  });
  this.server.tool("get_repository","Read repository metadata",{
    owner:z.string().min(1).max(100),repo:z.string().min(1).max(100)
  },async({owner,repo})=>{
    authorized(owner);
    return respond(await fetchForgejo(this.props!.accessToken,makeApiPath("repository",owner,repo)));
  });
  this.server.tool("list_open_issues","Read open repository issues",{
    owner:z.string().min(1).max(100),repo:z.string().min(1).max(100)
  },async({owner,repo})=>{
    authorized(owner);
    return respond(await fetchForgejo(this.props!.accessToken,makeApiPath("issues",owner,repo)));
  });
  this.server.tool("list_open_pull_requests","Read open pull requests",{
    owner:z.string().min(1).max(100),repo:z.string().min(1).max(100)
  },async({owner,repo})=>{
    authorized(owner);
    return respond(await fetchForgejo(this.props!.accessToken,makeApiPath("pulls",owner,repo)));
  });
  this.server.tool("read_file","Read repository file metadata and base64 content; max 64 KiB API response",{
    owner:z.string().min(1).max(100),repo:z.string().min(1).max(100),
    path:z.string().min(1).max(300)
  },async({owner,repo,path})=>{
    authorized(owner);
    return respond(await fetchForgejo(this.props!.accessToken,makeApiPath("contents",owner,repo,path)));
  });
 }
}
export default new OAuthProvider({
 apiHandler:FjordMCP.serve("/mcp"),apiRoute:"/mcp",
 defaultHandler:ForgejoHandler as any,
 authorizeEndpoint:"/authorize",tokenEndpoint:"/token",clientRegistrationEndpoint:"/register",
});
