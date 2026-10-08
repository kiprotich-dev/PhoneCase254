const http = require('http');
const fs = require('fs');
const path = require('path');
const root = __dirname;
const types = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.png':'image/png','.jpg':'image/jpeg'};
http.createServer((req,res)=>{
  const requested = req.url === '/' ? '/preview.html' : req.url;
  const file = path.join(root, decodeURIComponent(requested));
  if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end('Not found'); }
  res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'});
  fs.createReadStream(file).pipe(res);
}).listen(4173, '127.0.0.1', ()=>console.log('phoneCase254 preview: http://127.0.0.1:4173/'));
