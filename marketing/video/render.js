// Render promo.html to MP4: pause every CSS animation, step time frame by frame, pipe PNG frames to ffmpeg.
//   node render.js [seconds=62] [fps=30] [out=back-office-promo.mp4] [src=promo.html]
const { chromium } = require('playwright'); const { spawn } = require('child_process'); const path = require('path');
(async () => {
  const secs = Number(process.argv[2] || 62), fps = Number(process.argv[3] || 30), out = process.argv[4] || path.join(__dirname, 'back-office-promo.mp4');
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })).newPage();
  await p.goto('file://' + path.join(__dirname, process.argv[5] && !process.argv[5].startsWith('--') ? process.argv[5] : 'promo.html')); await p.evaluate(() => document.fonts.ready);
  await p.evaluate(() => document.getAnimations().forEach(a => a.pause()));
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const frames = secs * fps;
  for (let i = 0; i < frames; i++) {
    await p.evaluate(t => document.getAnimations().forEach(a => { a.currentTime = t; }), (i / fps) * 1000);
    const buf = await p.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (process.argv.includes('--stills') && [3.5, 10.2, 17, 26.5, 36, 44.8, 52.5, 60.5].some(s => Math.round(s * fps) === i)) require('fs').writeFileSync(path.join(process.env.STILLS || __dirname, `still_${String(Math.round(i / fps)).padStart(2, '0')}.jpg`), buf);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close(); console.log('wrote', out, frames, 'frames');
})().catch(e => { console.error(e); process.exit(1); });
