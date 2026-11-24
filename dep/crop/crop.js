const { createCanvas, loadImage } = require('canvas');
const fs = require('fs');

async function autoCrop(input, output) {
  const img = await loadImage(input);

  const canvas = createCanvas(img.width, img.height);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);

  const { data } = ctx.getImageData(0, 0, img.width, img.height);

  let minX = img.width;
  let minY = img.height;
  let maxX = 0;
  let maxY = 0;

  // 🔍 scan completo
  for (let y = 0; y < img.height; y++) {
    for (let x = 0; x < img.width; x++) {
      const idx = (y * img.width + x) * 4;
      const alpha = data[idx + 3];

      if (alpha !== 0) {
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }
    }
  }

  // ⚠️ proteção (imagem vazia)
  if (minX > maxX || minY > maxY) {
    console.log("⚠️ Nenhum pixel visível encontrado");
    return;
  }

  const cropWidth = maxX - minX + 1;
  const cropHeight = maxY - minY + 1;

  const outCanvas = createCanvas(cropWidth, cropHeight);
  const outCtx = outCanvas.getContext('2d');

  outCtx.drawImage(
    canvas,
    minX,
    minY,
    cropWidth,
    cropHeight,
    0,
    0,
    cropWidth,
    cropHeight
  );

  fs.writeFileSync(output, outCanvas.toBuffer());

  console.log("✅ Crop automático (sem offset):");
  console.log({ minX, minY, maxX, maxY });
}

// 🧪 uso
autoCrop("map.png", "map-cropped.png");