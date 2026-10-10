import type { AuthRequest, OAuthHelpers } from "@cloudflare/workers-oauth-provider";
import { Hono } from "hono";
import {
  addApprovedClient,bindStateToSession,createOAuthState,generateCSRFProtection,
  isClientApproved,OAuthError,renderApprovalDialog,validateCSRFToken,validateOAuthState,
} from "./workers-oauth-utils";
import {ORIGIN} from "./forgejo";

type Props = { login:string; accessToken:string };
type Bindings = {
  OAUTH_PROVIDER: OAuthHelpers; OAUTH_KV: KVNamespace;
  FORGEJO_CLIENT_ID: string; FORGEJO_CLIENT_SECRET: string;
  COOKIE_ENCRYPTION_KEY: string; ALLOWED_FORGEJO_LOGIN:string;
};
const app = new Hono<{Bindings:Bindings}>();
function redirectToForgejo(request:Request,env:Bindings,state:string,headers:Headers=new Headers()):Response{
  const url=new URL(ORIGIN+"/login/oauth/authorize");
  url.searchParams.set("response_type","code");
  url.searchParams.set("client_id",env.FORGEJO_CLIENT_ID);
  url.searchParams.set("redirect_uri",new URL("/callback",request.url).toString());
  url.searchParams.set("state",state);
  // Forgejo 15 OAuth scope behavior must be verified against your instance before
  // claiming the upstream OAuth grant itself is restricted to read-only operations.
  url.searchParams.set("scope","read:user read:repository");
  headers.set("Location",url.toString());
  return new Response(null,{status:302,headers});
}
app.get("/authorize",async c=>{
  const info=await c.env.OAUTH_PROVIDER.parseAuthRequest(c.req.raw);
  if(!info.clientId) return c.text("Invalid OAuth client",400);
  if(await isClientApproved(c.req.raw,info.clientId,c.env.COOKIE_ENCRYPTION_KEY)){
    const {stateToken}=await createOAuthState(info,c.env.OAUTH_KV);
    const {setCookie}=await bindStateToSession(stateToken);
    return redirectToForgejo(c.req.raw,c.env,stateToken,new Headers({"Set-Cookie":setCookie}));
  }
  const {token:csrfToken,setCookie}=generateCSRFProtection();
  return renderApprovalDialog(c.req.raw,{
    client:await c.env.OAUTH_PROVIDER.lookupClient(info.clientId),
    csrfToken,setCookie,
    server:{name:"Fjord Commons Read-Only MCP",description:"Allows read-only MCP tools for approved repository owners. Forgejo OAuth authorization must be reviewed separately."},
    state:{oauthReqInfo:info},
  });
});
app.post("/authorize",async c=>{
  try{
    const form=await c.req.raw.formData();
    validateCSRFToken(form,c.req.raw);
    const encoded=form.get("state");
    if(typeof encoded!=="string"||encoded.length>8192)return c.text("Invalid state",400);
    const json=JSON.parse(atob(encoded)) as {oauthReqInfo?:AuthRequest};
    if(!json.oauthReqInfo?.clientId)return c.text("Invalid state",400);
    const approved=await addApprovedClient(c.req.raw,json.oauthReqInfo.clientId,c.env.COOKIE_ENCRYPTION_KEY);
    const {stateToken}=await createOAuthState(json.oauthReqInfo,c.env.OAUTH_KV);
    const {setCookie}=await bindStateToSession(stateToken);
    const hdr=new Headers();hdr.append("Set-Cookie",approved);hdr.append("Set-Cookie",setCookie);
    return redirectToForgejo(c.req.raw,c.env,stateToken,hdr);
  }catch{return c.text("Authorization could not be completed",400);}
});
app.get("/callback",async c=>{
  let info:AuthRequest, clearCookie:string;
  try {
    const state=await validateOAuthState(c.req.raw,c.env.OAUTH_KV);
    info=state.oauthReqInfo;clearCookie=state.clearCookie;
    if(!info.clientId) return c.text("Invalid client",400);
  }catch{return c.text("Invalid or expired authorization state",400);}
  const code=c.req.query("code");
  if(!code || code.length>4096)return c.text("Invalid authorization code",400);
  // Fixed remote origin and no redirect forwarding of credentials.
  const exchange=await fetch(ORIGIN+"/login/oauth/access_token",{
    method:"POST",redirect:"manual",
    headers:{"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"},
    body:new URLSearchParams({
      client_id:c.env.FORGEJO_CLIENT_ID,client_secret:c.env.FORGEJO_CLIENT_SECRET,
      code,redirect_uri:new URL("/callback",c.req.url).toString(),
      grant_type:"authorization_code",
    }),
  });
  if(!exchange.ok || exchange.status>=300)return c.text("Forgejo authorization failed",502);
  const payload=await exchange.json() as {access_token?:string};
  const token=payload.access_token;
  if(typeof token!=="string" || token.length<10 || token.length>4096)
    return c.text("Forgejo authorization returned no usable token",502);
  const who=await fetch(ORIGIN+"/api/v1/user",{
    method:"GET",redirect:"manual",
    headers:{"Authorization":"Bearer "+token,"Accept":"application/json"},
  });
  if(!who.ok)return c.text("Unable to verify Forgejo identity",403);
  const user=await who.json() as {login?:string};
  if(user.login!==c.env.ALLOWED_FORGEJO_LOGIN)return c.text("Forgejo account not approved",403);
  const {redirectTo}=await c.env.OAUTH_PROVIDER.completeAuthorization({
    request:info,userId:user.login,scope:info.scope,
    metadata:{label:"Fjord Commons - "+user.login},
    props:{login:user.login,accessToken:token} satisfies Props,
  });
  const hdr=new Headers({"Location":redirectTo});
  hdr.append("Set-Cookie",clearCookie);
  return new Response(null,{status:302,headers:hdr});
});
export {app as ForgejoHandler};
