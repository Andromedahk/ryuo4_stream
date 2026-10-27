// Stream-compress an ext4 image to brotli (system.new.dat.br) for the OTA zip.
// usage: node brotli_stream.js <input> <output> [quality]
const fs = require('fs');
const zlib = require('zlib');

const inp = process.argv[2];
const out = process.argv[3];
const q = parseInt(process.argv[4] || '9', 10);
const size = fs.statSync(inp).size;

const src = fs.createReadStream(inp);
const dst = fs.createWriteStream(out);
const br = zlib.createBrotliCompress({
  params: {
    [zlib.constants.BROTLI_PARAM_QUALITY]: q,
    [zlib.constants.BROTLI_PARAM_LGWIN]: 22,
    [zlib.constants.BROTLI_PARAM_SIZE_HINT]: size,
  }
});
let read = 0;
src.on('data', d => { read += d.length; });
src.on('error', e => { console.error('read error', e); process.exit(1); });
br.on('error', e => { console.error('brotli error', e); process.exit(1); });
dst.on('error', e => { console.error('write error', e); process.exit(1); });
dst.on('finish', () => {
  const osz = fs.statSync(out).size;
  console.log(JSON.stringify({ input: inp, input_bytes: size, output: out, output_bytes: osz, quality: q, read_bytes: read }));
});
src.pipe(br).pipe(dst);
