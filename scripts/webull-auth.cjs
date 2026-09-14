"use strict";
/*
 * Reuse a valid Webull access token, or create a replacement when none is
 * configured or the account API reports INVALID_TOKEN. This script never
 * prints credential values.
 */
const crypto = require("node:crypto");
const fs = require("node:fs");
const https = require("node:https");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const envPath = path.join(root, ".env");
const HELP = `Usage: node scripts/webull-auth.cjs [--dry-run]\n\nChecks WEBULL_ACCESS_TOKEN with Webull's read-only account-list API. It creates\na replacement only when the value is blank or Webull returns INVALID_TOKEN.\nA production replacement requires confirmation in the Webull mobile app.`;

function parseEnv(source) {
  const values = {};
  for (const line of source.split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!match || match[1] in values) continue;
    let value = match[2];
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    values[match[1]] = value;
  }
  return values;
}

function updateEnv(source, key, value) {
  const newline = source.includes("\r\n") ? "\r\n" : "\n";
  const lines = source.split(/\r?\n/);
  const index = lines.findIndex((line) => new RegExp(`^\\s*${key}\\s*=`).test(line));
  const replacement = `${key}=${value}`;
  if (index === -1) lines.push(replacement);
  else lines[index] = replacement;
  return lines.join(newline);
}

function request({ hostname, method, requestPath, appKey, appSecret, token }) {
  const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const nonce = crypto.randomUUID().replace(/-/g, "");
  const signing = {
    host: hostname,
    "x-app-key": appKey,
    "x-signature-algorithm": "HMAC-SHA1",
    "x-signature-nonce": nonce,
    "x-signature-version": "1.0",
    "x-timestamp": timestamp,
  };
  const parameterString = Object.keys(signing).sort().map((key) => `${key}=${signing[key]}`).join("&");
  const signatureInput = encodeURIComponent(`${requestPath}&${parameterString}`);
  const signature = crypto.createHmac("sha1", `${appSecret}&`).update(signatureInput).digest("base64");
  const headers = { ...signing, "x-signature": signature, "x-version": "v2" };
  if (token) headers["x-access-token"] = token;
  if (method === "POST") headers["content-type"] = "application/json";
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname, method, path: requestPath, headers, timeout: 15_000 }, (res) => {
      let raw = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { raw += chunk; });
      res.on("end", () => {
        let body;
        try { body = raw ? JSON.parse(raw) : {}; } catch { body = { raw }; }
        resolve({ status: res.statusCode || 0, body });
      });
    });
    req.on("timeout", () => req.destroy(new Error("Webull request timed out")));
    req.on("error", reject);
    req.end();
  });
}

function apiCode(body) {
  return String(body?.code ?? body?.error_code ?? body?.data?.code ?? "").toUpperCase();
}

function tokenFrom(body) {
  const candidates = [body?.token, body?.access_token, body?.data?.token, body?.data?.access_token];
  return candidates.find((candidate) => typeof candidate === "string" && candidate.trim().length >= 16)?.trim();
}

async function main() {
  const args = new Set(process.argv.slice(2));
  if (args.has("--help") || args.has("-h")) return console.log(HELP);
  if ([...args].some((arg) => arg !== "--dry-run")) throw new Error(HELP);
  if (!fs.existsSync(envPath)) throw new Error("Missing .env. Copy example.env to .env and configure the Webull values.");
  const source = fs.readFileSync(envPath, "utf8");
  const env = parseEnv(source);
  const appKey = env.WEBULL_APP_KEY?.trim();
  const appSecret = env.WEBULL_APP_SECRET?.trim();
  if (!appKey || !appSecret) throw new Error("WEBULL_APP_KEY and WEBULL_APP_SECRET must be set in .env.");
  const environment = (env.WEBULL_ENV || "production").trim().toLowerCase();
  const hostname = ["production", "prod"].includes(environment) ? "api.webull.com" : ["uat", "sandbox", "test"].includes(environment) ? "api.sandbox.webull.com" : null;
  if (!hostname) throw new Error("WEBULL_ENV must be production, prod, uat, sandbox, or test.");
  const dryRun = args.has("--dry-run");
  const existingToken = env.WEBULL_ACCESS_TOKEN?.trim();
  let create = !existingToken;
  if (existingToken) {
    process.stdout.write("Checking the configured Webull access token... ");
    const result = await request({ hostname, method: "GET", requestPath: "/openapi/account/list", appKey, appSecret, token: existingToken });
    if (result.status === 200) return console.log("accepted. No replacement was created.");
    if (result.status === 401 && apiCode(result.body) === "INVALID_TOKEN") {
      console.log("invalid. A replacement is required.");
      create = true;
    } else {
      throw new Error(`Token check stopped with HTTP ${result.status}${apiCode(result.body) ? ` (${apiCode(result.body)})` : ""}; the script will not create a replacement.`);
    }
  }
  if (!create) return;
  if (dryRun) return console.log("Dry run: a new token would be requested, but .env was not changed.");
  console.log("Requesting a new Webull token; no order or order preview will be sent.");
  const created = await request({ hostname, method: "POST", requestPath: "/auth/tokens/create", appKey, appSecret });
  const newToken = tokenFrom(created.body);
  if (created.status !== 200 || !newToken) throw new Error(`Token creation stopped with HTTP ${created.status}${apiCode(created.body) ? ` (${apiCode(created.body)})` : ""}; .env was not changed.`);
  fs.writeFileSync(envPath, updateEnv(source, "WEBULL_ACCESS_TOKEN", newToken), { encoding: "utf8", mode: 0o600 });
  const status = String(created.body?.status ?? created.body?.data?.status ?? "PENDING").toUpperCase();
  console.log(`New token saved locally with status ${status}.`);
  if (hostname === "api.webull.com") console.log("In the Webull app: Menu > Messages > OpenAPI Notifications > latest message > Check Now, then enter the SMS code within 5 minutes.");
}

main().catch((error) => { console.error(`Webull token helper: ${error.message}`); process.exitCode = 1; });