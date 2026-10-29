// Usage: node render.js [out.mp4] [fps]  — renders scene.html frame-by-frame and muxes music
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');

const out = path.resolve(process.argv[2] || 'guzor-ads-motion.mp4');
const fps = +(process.argv[3] || 30);
const dir = __dirname;

function writeMusic(file, dur) {
  const sr = 44100, n = Math.floor(sr * dur), bpm = 120, beat = 60 / bpm;
  const buf = Buffer.alloc(44 + n * 2);
  const chords = [[220, 277.18, 329.63], [174.61, 220, 261.63], [261.63, 329.63, 392], [196, 246.94, 293.66]];
  const bass = [110, 87.31, 130.81, 98];
  for (let i = 0; i < n; i++) {
    const t = i / sr, bt = t % beat, bar = Math.floor(t / (beat * 4)) % 4;
    let s = 0;
    s += Math.sin(2 * Math.PI * (50 + 90 * Math.exp(-bt * 30)) * bt) * Math.exp(-bt * 7) * 0.55;       // kick
    const ht = (t + beat / 2) % beat;
    s += (Math.random() * 2 - 1) * Math.exp(-ht * 45) * 0.08;                                          // hat
    if (Math.floor(t / beat) % 2 === 1) s += (Math.random() * 2 - 1) * Math.exp(-bt * 18) * 0.12;      // clap
    const duck = 1 - 0.6 * Math.exp(-bt * 8);
    for (const f of chords[bar]) s += (Math.sin(2 * Math.PI * f * t) + 0.3 * Math.sin(4 * Math.PI * f * t)) * 0.045 * duck;
    s += Math.sin(2 * Math.PI * bass[bar] * t) * 0.18 * duck;
    const env = Math.min(1, t / 1.0, (dur - t) / 1.5);
    buf.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(Math.tanh(s * 1.2) * env * 26000))), 44 + i * 2);
  }
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sr, 24); buf.writeUInt32LE(sr * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
  buf.write('data', 36); buf.writeUInt32LE(n * 2, 40);
  fs.writeFileSync(file, buf);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.join(dir, 'scene.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  const dur = await page.evaluate(() => window.DURATION);
  const wav = path.join(dir, 'music.wav');
  writeMusic(wav, dur);

  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', '-i', wav,
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '18', '-c:a', 'aac', '-b:a', '192k',
    '-shortest', '-movflags', '+faststart', out], { stdio: ['pipe', 'ignore', 'inherit'] });
  const total = Math.round(dur * fps);
  for (let f = 0; f < total; f++) {
    await page.evaluate(t => window.seek(t), f / fps);
    const img = await page.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(img)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 150 === 0) console.log(`frame ${f}/${total}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  fs.unlinkSync(wav);
  console.log('done', out);
})();
