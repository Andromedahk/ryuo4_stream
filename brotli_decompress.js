// Stream-decompress brotli for validation.
// usage: node brotli_decompress.js <input> <output>
const fs = require('fs');
const zlib = require('zlib');
const inp = process.argv[2], out = process.argv[3];
const src = fs.createReadStream(inp);
const dst = fs.createWriteStream(out);
const br = zlib.createBrotliDecompress();
src.on('error', e => { console.error(e); process.exit(1); });
br.on('error', e => { console.error(e); process.exit(1); });
dst.on('error', e => { console.error(e); process.exit(1); });
dst.on('finish', () => console.log(JSON.stringify({ input_bytes: fs.statSync(inp).size, output_bytes: fs.statSync(out).size })));
src.pipe(br).pipe(dst);
