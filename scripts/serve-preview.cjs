"use strict";
const http=require("node:http"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"..");
const types={".html":"text/html; charset=utf-8",".css":"text/css; charset=utf-8",".js":"text/javascript; charset=utf-8",".md":"text/plain; charset=utf-8"};
const allowed=/^\/(?:README\.md|VERIFICATION\.md|prototype\/(?:index\.html|styles\.css|app\.js|README\.md)|docs\/[a-z0-9-]+\.md)$/;
http.createServer((req,res)=>{
 if(req.method!=="GET"&&req.method!=="HEAD"){res.writeHead(405);return res.end();}
 let url;try{url=decodeURIComponent(new URL(req.url,"http://127.0.0.1:8788").pathname);}catch{res.writeHead(400);return res.end();}
 if(url==="/"){res.writeHead(302,{Location:"/prototype/index.html"});return res.end();}
 if(!allowed.test(url)){res.writeHead(404);return res.end("Not found");}
 fs.readFile(path.resolve(root,"."+url),(err,body)=>{if(err){res.writeHead(404);return res.end();}res.writeHead(200,{"Content-Type":types[path.extname(url)],"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"});res.end(req.method==="HEAD"?undefined:body);});
}).listen(8788,"127.0.0.1",()=>console.log("Design preview: http://127.0.0.1:8788"));
