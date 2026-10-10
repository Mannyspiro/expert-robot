import assert from "node:assert/strict";
import {test} from "node:test";
import {readFileSync} from "node:fs";
const src=readFileSync(new URL("../src/forgejo.ts",import.meta.url),"utf8");
const mcp=readFileSync(new URL("../src/index.ts",import.meta.url),"utf8");
const h=readFileSync(new URL("../src/forgejo-handler.ts",import.meta.url),"utf8");
const cfg=readFileSync(new URL("../wrangler.jsonc",import.meta.url),"utf8");
test("fixed API host and no outbound user-controlled URL",()=>{
  assert.match(src,/https:\/\/commons\.fjord\.host/);
  assert.match(src,/redirect:"manual"/);
  assert.doesNotMatch(src,/POST\s*,/);
});
test("MCP declares read only tools",()=>{
  const names=[...mcp.matchAll(/this\.server\.tool\("([^"]+)"/g)].map(x=>x[1]);
  assert.deepEqual(names,["list_repositories","get_repository","list_open_issues","list_open_pull_requests","read_file"]);
  assert.doesNotMatch(mcp,/this\.server\.tool\("(push|delete|write|merge)/);
});
test("OAuth state, CSRF and user allowlist",()=>{
  assert.match(h,/validateOAuthState/);
  assert.match(h,/validateCSRFToken/);
  assert.match(h,/ALLOWED_FORGEJO_LOGIN/);
  assert.match(h,/completeAuthorization/);
});
test("No existing Forgejo access token or paid tier in sources",()=>{
  for (const data of [src,h,mcp,cfg]){
    assert.doesNotMatch(data,/775c52d63dba5b8e0c10f0763aa20306d29580cc/i);
    assert.doesNotMatch(data,/paid plan|plan upgrade|cloudflare turnstile secret/i);
  }
});
