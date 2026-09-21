const landing=document.getElementById('landing'),scene=document.getElementById('scene');
const canvas=document.getElementById('code'),ctx=canvas.getContext('2d');
const monitor = document.getElementById('monitor');
const statusText=document.getElementById('status');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let w=0,h=0,cx=0,cy=0,screenW=0,screenH=0,frame=0,last=0,particles=[],entering=false,paused=reduced.matches,hover=false;
let timers=[];
let pointerNear=false;
const words = [
  '01111001', 
  '01110101', 
  '01101011', 
  '01110100', 
  '01100001'  
];
function resize(){
 w=landing.clientWidth;h=landing.clientHeight;
 const ratio=1672/941,scale=w<=600?h/941:Math.max(w/1672,h/941);
 const iw=1672*scale,ih=941*scale,ox=(w-iw)/2,oy=(h-ih)/2;
 cx=ox+iw*.5;cy=oy+ih*.565;screenW=iw*.136;screenH=ih*.168;
 Object.assign(monitor.style,{left:`${cx-screenW/2}px`,top:`${cy-screenH/2}px`,width:`${screenW}px`,height:`${screenH}px`});
 scene.style.setProperty('--origin-x',`${cx}px`);scene.style.setProperty('--origin-y',`${cy}px`);
 const d=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*d);canvas.height=Math.round(h*d);if(ctx)ctx.setTransform(d,0,0,d,0,0);
}
function particle(){return{side:Math.random()<.5?-1:1,spread:Math.random()*2-1,t:0,duration:3+Math.random()*5,word:words[Math.floor(Math.random()*words.length)]};}
function draw(now){frame=0;if(!ctx||paused||entering||document.hidden||!hover)return;
 const dt=Math.min((now-(last||now))/1000,.05);last=now;ctx.clearRect(0,0,w,h);
 const amount = entering ? 60 : hover ? 40 : 0;
 particles=particles.filter(p=>p.t<1);
 for(let i=0;i<3&&particles.length<amount;i++)particles.push(particle());
 const reach=Math.min(w*.18,300),spread=Math.min(h*.14,130);
 for(const p of particles){p.t+=dt/p.duration*(entering?3.4:hover?1.4:1);const t=Math.min(p.t,1),a=t*t;
 const x=cx+p.side*(screenW*.47+reach*(1-a));
 const y=cy+p.spread*spread*(1-a)+Math.sin(t*Math.PI)*p.spread*22;
 const alpha=Math.min(t*6,1)*(1-Math.pow(t,5));
 ctx.globalAlpha=alpha*(hover||entering?.95:.68);ctx.fillStyle='#52ff9a';ctx.shadowColor='#20ff6a';ctx.shadowBlur=hover?9:5;
 ctx.font=`${Math.max(9,Math.min(18,w*.012))*(1-t*.32)}px monospace`;ctx.textAlign=p.side<0?'right':'left';
 // Clip at the monitor edges so code never hides its central emblem.
 ctx.save();ctx.beginPath();if(p.side<0)ctx.rect(0,h*.36,cx-screenW*.46,h*.4);else ctx.rect(cx+screenW*.46,h*.36,w,h*.4);ctx.clip();
 ctx.fillText(p.word,x,y);ctx.strokeStyle='#47ff9638';ctx.beginPath();ctx.moveTo(x,y+4);ctx.lineTo(x+p.side*24*(1-t),y+4+p.spread*5);ctx.stroke();ctx.restore();
 }
 ctx.globalAlpha=1;ctx.shadowBlur=0;frame=requestAnimationFrame(draw);
}
function start(){if(!frame&&!paused&&!entering&&ctx&&hover){last=0;frame=requestAnimationFrame(draw);}}
function stopEffects(){cancelAnimationFrame(frame);frame=0;particles=[];if(ctx)ctx.clearRect(0,0,w,h);}
function setPaused(value){paused=value;if(paused)stopEffects();else start();}
function updateHover(){
  hover = pointerNear || document.activeElement === monitor;

  landing.classList.toggle('is-near', hover);

  if (hover || entering) {
    start();
  } else {
    stopEffects();
  }
}
// Start the binary effect when the pointer is near the monitor.
landing.addEventListener('pointermove', event => {

  if (event.pointerType === 'touch') return;

  const pc = monitor.getBoundingClientRect();

  const padding = 45;

  pointerNear =
    event.clientX >= pc.left - padding &&
    event.clientX <= pc.right + padding &&
    event.clientY >= pc.top - padding &&
    event.clientY <= pc.bottom + padding;

  updateHover();
});
landing.addEventListener('pointerleave',()=>{pointerNear=false;updateHover();});
// The only binary used in either effect is the UTF-8/ASCII encoding of "yukta".
// Change this value to adjust how long the patches take to cover the viewport.
const takeoverDuration = 2200;
const takeoverCanvas = document.getElementById('takeover');
const takeoverContext = takeoverCanvas.getContext('2d');
let takeoverFrame = 0, takeoverStart = 0, tiles = [];
let takeoverWidth = 0, takeoverHeight = 0;
const tileWidth = 80, tileHeight = 42;

function buildPatches() {
  takeoverWidth = innerWidth;
  takeoverHeight = innerHeight;
  const d = Math.min(devicePixelRatio || 1, 2);
  takeoverCanvas.width = Math.round(takeoverWidth * d);
  takeoverCanvas.height = Math.round(takeoverHeight * d);
  if (!takeoverContext) return;
  takeoverContext.setTransform(d, 0, 0, d, 0, 0);
  const cols = Math.ceil(takeoverWidth / tileWidth);
  const rows = Math.ceil(takeoverHeight / tileHeight);
  const rect = monitor.getBoundingClientRect();
  const sx = Math.max(0, Math.min(cols - 1, Math.floor((rect.left + rect.width / 2) / tileWidth)));
  const sy = Math.max(0, Math.min(rows - 1, Math.floor((rect.top + rect.height / 2) / tileHeight)));
  tiles = Array.from({length: cols * rows}, (_, i) => ({
    x: i % cols, y: Math.floor(i / cols), arrival: Infinity,
    resistance: .15 + Math.pow(Math.random(), 2) * 5,
    phase: Math.random() * Math.PI * 2
  }));
  // Weighted neighbour growth creates connected branches and delayed pockets.
  // No radial distance or straight wipe is used to decide activation times.
  const pending = [{index: sy * cols + sx, time: 0}];
  tiles[pending[0].index].arrival = 0;
  while (pending.length) {
    pending.sort((a, b) => b.time - a.time);
    const next = pending.pop();
    const cell = tiles[next.index];
    if (next.time !== cell.arrival) continue;
    for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
      const x = cell.x + dx, y = cell.y + dy;
      if (x < 0 || y < 0 || x >= cols || y >= rows) continue;
      const i = y * cols + x;
      const time = next.time + tiles[i].resistance;
      if (time < tiles[i].arrival) {
        tiles[i].arrival = time;
        pending.push({index:i, time});
      }
    }
  }
  const maxArrival = Math.max(...tiles.map(t => t.arrival), 1);
  for (const tile of tiles) tile.arrival = tile.arrival / maxArrival * (takeoverDuration - 180);
}

function paintTakeover(now) {
  takeoverFrame = 0;
  if (!entering || !takeoverContext) return;
  if (takeoverWidth !== innerWidth || takeoverHeight !== innerHeight) buildPatches();
  const elapsed = now - takeoverStart;
  const c = takeoverContext;
  c.clearRect(0, 0, takeoverWidth, takeoverHeight);
  c.font = '12px monospace';
  c.textAlign = 'left';
  c.textBaseline = 'top';
  for (const tile of tiles) {
    const age = elapsed - tile.arrival;
    if (age < 0) continue;
    const x = tile.x * tileWidth, y = tile.y * tileHeight;
    c.globalAlpha = Math.min(1, age / 150);
    c.fillStyle = '#010d14';
    c.fillRect(x, y, tileWidth + .5, tileHeight + .5);
    const pulse = .5 + .5 * Math.sin(elapsed / 400 + tile.phase);
    c.fillStyle = age < 250 ? '#8dffd3' : `rgba(64,239,150,${.35 + pulse * .5})`;
    // Complete eight-bit bytes, repeated in y-u-k-t-a order, rather than random digits.
    for (let row = 0; row < 2; row++) {
      const byte = words[(tile.y * 2 + row + tile.x * 2) % words.length];
      c.fillText(byte, x + 9, y + 5 + row * 18);
    }
    if (age < 220) {
      c.fillStyle = '#56ffd050';
      c.fillRect(x, y, tileWidth, 1);
    }
  }
  c.globalAlpha = 1;
  takeoverFrame = requestAnimationFrame(paintTakeover);
}
function startTakeover() {
  if (!takeoverContext) { location.assign(monitor.href); return; }
  buildPatches();
  takeoverStart = performance.now();
  takeoverFrame = requestAnimationFrame(paintTakeover);
}
function stopTakeover() {
  cancelAnimationFrame(takeoverFrame);
  takeoverFrame = 0;
  tiles = [];
  if (takeoverContext) takeoverContext.clearRect(0,0,takeoverWidth,takeoverHeight);
}

for (const link of [monitor]) {
 link.addEventListener('focus',updateHover);link.addEventListener('blur',updateHover);
 link.addEventListener('click',event=>{
 if(event.ctrlKey||event.metaKey||event.altKey||event.shiftKey||reduced.matches||paused)return;
 event.preventDefault();
 if(entering)return;
 entering=true;
 stopEffects();
 document.body.classList.add('entering');
 startTakeover();
 timers.push(setTimeout(()=>statusText.textContent='Entering CYBERHEAD-NEWS…',200));
 timers.push(setTimeout(()=>location.assign(link.href),2900));
 });
}
function reset(){stopTakeover();timers.forEach(clearTimeout);timers=[];entering=false;hover=false;pointerNear=false;stopEffects();landing.classList.remove('is-near');document.body.classList.remove('entering');statusText.textContent='';resize();start();}
addEventListener('pageshow',reset);addEventListener('pagehide',()=>{stopTakeover();timers.forEach(clearTimeout);cancelAnimationFrame(frame);frame=0;});
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else start();});
reduced.addEventListener('change',()=>{setPaused(reduced.matches);if(reduced.matches&&entering){stopTakeover();timers.forEach(clearTimeout);location.assign(monitor.href);}});new ResizeObserver(resize).observe(landing);resize();setPaused(paused);
