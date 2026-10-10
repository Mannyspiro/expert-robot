interface Env {
  OAUTH_KV: KVNamespace;
  MCP_OBJECT: DurableObjectNamespace;
  FORGEJO_CLIENT_ID: string;
  FORGEJO_CLIENT_SECRET: string;
  COOKIE_ENCRYPTION_KEY: string;
  ALLOWED_FORGEJO_LOGIN: string;
  ALLOWED_REPO_OWNERS: string;
  FORGEJO_ORIGIN: string;
}
