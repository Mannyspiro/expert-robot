import assert from "node:assert/strict";
import {test} from "node:test";
import {makeApiPath,authorizedOwner,safeForgejoUrl,fetchForgejo} from "../src/forgejo.ts";
import {readFileSync} from "node:fs";

test("allowlisted fixed-origin read-only paths",()=>{
  assert.equal(makeApiPath("userRepos"),"/api/v1/user/repos?limit=25&page=1");
  assert.equal(makeApiPath("repository","morganaspiro","sample"),"/api/v1/repos/morganaspiro/sample");
  assert.equal(makeApiPath("contents","morganaspiro","sample",".github/workflows/ci.yml"),
    "/api/v1/repos/morganaspiro/sample/contents/.github/workflows/ci.yml");
  for(const bad of ["../private","%2e%2e/foo","//evil","file?redirect=true","file\\evil"]){
    assert.throws(()=>makeApiPath("contents","morganaspiro","sample",bad));
  }
  for(const bad of ["https://evil.example/api/v1/repo","//evil/api/v1/repo"]){
    assert.throws(()=>safeForgejoUrl(bad));
  }
  assert.equal(authorizedOwner("morganaspiro","morganaspiro,p-123"),true);
  assert.equal(authorizedOwner("someoneelse","morganaspiro,p-123"),false);
});
test("network call is GET-only, manual redirect, fixed host, capped payload",async()=>{
  let seen;
  const stub=async (url,opts)=>{
    seen={url,opts};
    return new Response(JSON.stringify({ok:true}),{status:200});
  };
  const result=await fetchForgejo("TESTTOKEN","/api/v1/user/repos?limit=25",stub);
  assert.equal(JSON.parse(result).ok,true);
  assert.equal(seen.url,"https://commons.fjord.host/api/v1/user/repos?limit=25");
  assert.equal(seen.opts.method,"GET");
  assert.equal(seen.opts.redirect,"manual");
  const redirect=async()=>new Response(null,{status:302,headers:{Location:"https://evil.test/"}});
  await assert.rejects(fetchForgejo("TESTTOKEN","/api/v1/user/repos",redirect));
  const oversized=async()=>new Response("x".repeat(70000),{status:200});
  await assert.rejects(fetchForgejo("TESTTOKEN","/api/v1/user/repos",oversized));
});
test("OAuth helpers and identity restriction wired",()=>{
  const handler=readFileSync(new URL("../src/forgejo-handler.ts",import.meta.url),"utf8");
  const tools=readFileSync(new URL("../src/index.ts",import.meta.url),"utf8");
  assert.match(handler,/validateOAuthState/);
  assert.match(handler,/validateCSRFToken/);
  assert.match(handler,/ALLOWED_FORGEJO_LOGIN/);
  assert.match(handler,/completeAuthorization/);
  const names=[...tools.matchAll(/this\.server\.tool\("([^"]+)"/g)].map(m=>m[1]);
  assert.deepEqual(names,["list_repositories","get_repository","list_open_issues","list_open_pull_requests","read_file"]);
  assert.doesNotMatch(tools,/\b(delete|push|merge|issue_write)\b/);
});
