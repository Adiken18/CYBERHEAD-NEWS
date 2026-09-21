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
function draw(now){frame=0;if(!ctx||paused||document.hidden||(!hover&&!entering))return;
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
function start(){if(!frame&&!paused&&ctx&&(hover||entering)){last=0;frame=requestAnimationFrame(draw);}}
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
for (const link of [monitor]) {
 link.addEventListener('focus',updateHover);link.addEventListener('blur',updateHover);
 link.addEventListener('click',event=>{
 if(event.ctrlKey||event.metaKey||event.altKey||event.shiftKey||reduced.matches||paused)return;
 event.preventDefault();if(entering)return;entering=true;start();
 const box=landing.getBoundingClientRect();scene.style.setProperty('--travel-x',`${innerWidth/2-(box.left+cx)}px`);scene.style.setProperty('--travel-y',`${innerHeight/2-(box.top+cy)}px`);
 document.body.classList.add('entering');
 timers.push(setTimeout(()=>statusText.textContent='ENTERING CYBERHEAD-NEWS…',900));
 timers.push(setTimeout(()=>location.assign(link.href),1500));
 });
}
function reset(){timers.forEach(clearTimeout);timers=[];entering=false;hover=false;pointerNear=false;stopEffects();landing.classList.remove('is-near');document.body.classList.remove('entering');statusText.textContent='';resize();start();}
addEventListener('pageshow',reset);addEventListener('pagehide',()=>{timers.forEach(clearTimeout);cancelAnimationFrame(frame);frame=0;});
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else start();});
reduced.addEventListener('change',()=>setPaused(reduced.matches));new ResizeObserver(resize).observe(landing);resize();setPaused(paused);
