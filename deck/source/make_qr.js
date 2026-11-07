// QR for the demo video on the cover: NODE_PATH=../../frontend/node_modules node make_qr.js <video url>
const QRCode = require('qrcode')
const path = require('path')
const url = process.argv[2]
if (!url) { console.error('usage: node make_qr.js <video url>'); process.exit(1) }
QRCode.toFile(path.join(__dirname, 'img', 'qr_video.png'), url, { margin: 1, width: 600 }).then(() => console.log('wrote img/qr_video.png'))
