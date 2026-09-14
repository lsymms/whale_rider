"use strict";
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const root=path.resolve(__dirname,"..");
let failures=[],markdownCount=0,jsonCount=0,links=0;
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entry=>{if([".git","node_modules"].includes(entry.name))return [];const file=path.join(dir,entry.name);return entry.isDirectory()?walk(file):[file];});}
for(const file of walk(root)){
 const rel=path.relative(root,file);
 if(file.endsWith(".md")){
  markdownCount++;const text=fs.readFileSync(file,"utf8");
  for(const match of text.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)){
   const raw=match[1].replace(/^<|>$/g,"");
   if(/^(https?:|mailto:|#)/.test(raw))continue;
   const target=decodeURIComponent(raw.split("#")[0]);
   if(!target)continue;links++;
   if(!fs.existsSync(path.resolve(path.dirname(file),target)))failures.push(rel+": missing link "+raw);
  }
  if((text.match(/^```/gm)||[]).length%2!==0)failures.push(rel+": unmatched fenced block");
 }
 if(file.endsWith(".json")){jsonCount++;try{JSON.parse(fs.readFileSync(file,"utf8"));}catch(err){failures.push(rel+": "+err.message);}}
}
for(const file of ["prototype/app.js","scripts/serve-preview.cjs"]){try{new vm.Script(fs.readFileSync(path.join(root,file),"utf8"),{filename:file});}catch(err){failures.push(file+": "+err.message);}}
const html=fs.readFileSync(path.join(root,"prototype/index.html"),"utf8");
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
if(new Set(ids).size!==ids.length)failures.push("Prototype contains duplicate IDs");
for(const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)){
 const target=match[1];if(/^https?:/.test(target)){failures.push("Unexpected external prototype asset: "+target);continue;}
 if(!fs.existsSync(path.resolve(root,"prototype",target)))failures.push("Missing prototype asset: "+target);
}
const js=fs.readFileSync(path.join(root,"prototype/app.js"),"utf8");
for(const match of js.matchAll(/\$\("([^"]+)"\)/g)){if(!ids.includes(match[1]))failures.push("Missing DOM ID: "+match[1]);}
if(/\bfetch\s*\(|XMLHttpRequest|WebSocket\s*\(/.test(js))failures.push("Prototype must not make network calls");
const rule=JSON.parse(fs.readFileSync(path.join(root,"examples/alert-rule.json"),"utf8"));
const event=rule.example_event;
if(Number(event.quantity)*Number(event.price)*Number(event.price_multiplier)!==Number(event.premium_usd))failures.push("Synthetic premium arithmetic mismatch");
const suggestion=JSON.parse(fs.readFileSync(path.join(root,"examples/suggestion.json"),"utf8"));
const a=suggestion.assumptions;
const delta=(Number(a.stock_shares)+Number(a.long_call_contracts)*Number(a.multiplier)*Number(a.call_delta))*Number(a.underlying_price_usd);
if(delta!==Number(suggestion.calculated.delta_dollars_before))failures.push("Synthetic exposure arithmetic mismatch");
if(failures.length){console.error(failures.join("\n"));process.exitCode=1;}else console.log("PASS: "+markdownCount+" Markdown files, "+links+" local links, "+jsonCount+" JSON examples; preview syntax/assets/IDs and sample arithmetic verified.");
