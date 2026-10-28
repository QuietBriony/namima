// Cached, procedural scenery. No images, dependencies, audio, or extra timers.
(function(root){
  "use strict";
  const INFO = Object.freeze({
    water_day:{ title:"昼の水面", detail:"光がほどける、青い入り江。", top:"#103746", bottom:"#062830", light:"#8fddcf" },
    garden_morning:{ title:"朝の庭", detail:"葉のあいだから、木漏れ日と風。", top:"#253e32", bottom:"#071f24", light:"#d2dda0" },
    family_room:{ title:"灯りの部屋", detail:"窓辺の灯りと、あたたかな余白。", top:"#382c36", bottom:"#171d2c", light:"#e6b16c" },
    transparent_evening:{ title:"透きとおる夕方", detail:"夕陽が沈む、紫の水平線。", top:"#392b4f", bottom:"#152137", light:"#eead88" },
    soft_sleep:{ title:"月あかり", detail:"月と星を映す、静かな夜。", top:"#111f3b", bottom:"#071321", light:"#b9d4e7" },
  });
  const valid = id => Object.hasOwn(INFO,id) ? id : "water_day";
  const clamp = n => Math.max(0,Math.min(1,n));
  function oval(ctx,x,y,rx,ry,color){
    ctx.fillStyle=color; ctx.beginPath(); ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2); ctx.fill();
  }
  function glow(ctx,x,y,r,color){
    const g=ctx.createRadialGradient(x,y,0,x,y,r);
    g.addColorStop(0,color);g.addColorStop(1,"#00000000");ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);
  }
  function landscape(canvas,id,w,h){
    // Cap the long edge; two resident backdrops at most, even on a large display.
    const scale=Math.min(1,1600/Math.max(w,h));
    canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
    const c=canvas.getContext("2d"), W=canvas.width, H=canvas.height, p=INFO[id];
    const bg=c.createLinearGradient(0,0,0,H);bg.addColorStop(0,p.top);bg.addColorStop(1,p.bottom);
    c.fillStyle=bg;c.fillRect(0,0,W,H);
    if(id==="water_day"){
      glow(c,W*.73,H*.3,H*.43,"#8fdac15c");
      oval(c,W*.72,H*.32,H*.036,H*.036,"#ddf1d9b3");
      c.fillStyle="#0c3543";c.fillRect(0,H*.48,W,H*.52);
      for(let i=0;i<24;i++){
        const y=H*(.49+i*.018), span=W*(.035+i*.007);
        c.strokeStyle=`rgba(154,224,206,${.14-i*.004})`;c.lineWidth=1;
        c.beginPath();c.moveTo(W*.72-span,y);c.lineTo(W*.72+span,y);c.stroke();
      }
      c.strokeStyle="#83d3ce50";c.beginPath();c.moveTo(0,H*.48);c.lineTo(W,H*.48);c.stroke();
    }else if(id==="garden_morning"){
      glow(c,W*.7,H*.3,H*.55,"#d9d9a95c");
      for(let side=0;side<2;side++){
        c.strokeStyle=side ? "#123c35" : "#0c302b";c.lineWidth=W*.015;
        c.beginPath();c.moveTo(W*(side ? 1.04 : -.04),H*.78);
        c.quadraticCurveTo(W*(side ? .83 : .16),H*.42,W*(side ? .78 : .2),H*.17);c.stroke();
        for(let i=0;i<10;i++){
          const y=H*(.2+i*.054),x=W*(side ? .82+i*.012 : .18-i*.012);
          c.save();c.translate(x,y);c.rotate((side ? -1 : 1)*(.5+i*.07));
          oval(c,0,0,W*(.05+i*.002),H*.016,i%2 ? "#5b8c574d" : "#1d5744bf");
          c.restore();
        }
      }
      for(let i=0;i<26;i++){
        const x=W*(.15+((i*37)%97)/130),y=H*(.22+((i*29)%89)/160);
        oval(c,x,y,1+(i%3),1+(i%3),"#e8e4a43b");
      }
      oval(c,W*.5,H*.94,W*.72,H*.2,"#0a2925b3");
    }else if(id==="family_room"){
      glow(c,W*.69,H*.49,H*.42,"#e9b36d6b");
      const x=W*.5,y=H*.27,ww=W*.32,hh=H*.29;
      c.fillStyle="#bf915f3b";c.fillRect(x,y,ww,hh);
      c.strokeStyle="#e8c49a5c";c.lineWidth=2;c.strokeRect(x,y,ww,hh);
      c.beginPath();c.moveTo(x+ww/2,y);c.lineTo(x+ww/2,y+hh);
      c.moveTo(x,y+hh*.55);c.lineTo(x+ww,y+hh*.55);c.stroke();
      c.fillStyle="#121d29";c.fillRect(0,H*.7,W,H*.3);
      c.strokeStyle="#c6986e40";c.beginPath();c.moveTo(0,H*.7);c.lineTo(W,H*.7);c.stroke();
      oval(c,W*.66,H*.75,W*.27,H*.035,"#dba76724");
      c.fillStyle="#201c27";c.fillRect(W*.16,H*.57,W*.008,H*.15);
      c.beginPath();c.moveTo(W*.09,H*.57);c.lineTo(W*.23,H*.57);
      c.lineTo(W*.2,H*.5);c.lineTo(W*.12,H*.5);c.closePath();c.fill();
    }else if(id==="transparent_evening"){
      glow(c,W*.7,H*.45,H*.43,"#efae9766");
      oval(c,W*.7,H*.46,H*.075,H*.075,"#edb09bba");
      c.fillStyle="#252d4b";c.beginPath();c.moveTo(0,H*.57);
      c.bezierCurveTo(W*.2,H*.43,W*.3,H*.61,W*.52,H*.55);
      c.bezierCurveTo(W*.78,H*.46,W*.86,H*.58,W,H*.53);
      c.lineTo(W,H);c.lineTo(0,H);c.closePath();c.fill();
      c.fillStyle="#19283b";c.fillRect(0,H*.62,W,H*.38);
      for(let i=0;i<17;i++){
        c.strokeStyle=`rgba(231,170,159,${.15-i*.006})`;c.lineWidth=1;
        c.beginPath();c.moveTo(W*(.62-i*.008),H*(.64+i*.018));c.lineTo(W*(.77+i*.008),H*(.64+i*.018));c.stroke();
      }
    }else{
      glow(c,W*.74,H*.27,H*.28,"#aecbe226");
      oval(c,W*.74,H*.27,H*.033,H*.033,"#cbdce7cf");
      for(let i=0;i<48;i++){
        const x=W*((i*47+19)%101)/101,y=H*(.11+((i*31)%97)/210);
        oval(c,x,y,i%5===0 ? 1.3 : .7,i%5===0 ? 1.3 : .7,"#bfd8e370");
      }
      c.fillStyle="#0c2033";c.beginPath();c.moveTo(0,H*.65);
      c.quadraticCurveTo(W*.28,H*.56,W*.52,H*.66);c.quadraticCurveTo(W*.8,H*.6,W,H*.66);
      c.lineTo(W,H);c.lineTo(0,H);c.closePath();c.fill();
      oval(c,W*.74,H*.71,W*.06,H*.009,"#b9d4e72b");
    }
    // Readable foreground text and controls, without flattening the scenery.
    const shade=c.createLinearGradient(0,0,0,H);shade.addColorStop(0,"#031017a8");
    shade.addColorStop(.24,"#03101700");shade.addColorStop(.72,"#03101700");shade.addColorStop(1,"#0310179c");
    c.fillStyle=shade;c.fillRect(0,0,W,H);
    return canvas;
  }
  function create(makeCanvas=()=>document.createElement("canvas")){
    let from=null,to=null,id=null,w=0,h=0,changedAt=0,first=true;
    const release=c=>{if(c){c.width=1;c.height=1;}};
    const progress=(time,reduced)=>reduced ? 1 : clamp((time-changedAt)/1.8);
    function draw(ctx,mood,width,height,time,options={}){
      const requested=valid(mood);
      const resized=width!==w || height!==h;
      if(resized || !to){
        release(from);release(to);from=null;w=width;h=height;
        to=landscape(makeCanvas(),requested,w,h);id=requested;first=true;
      }else if(requested!==id){
        if(from){
          const blend=from.getContext("2d");blend.save();blend.globalAlpha=progress(time,options.reducedMotion);
          blend.drawImage(to,0,0);blend.restore();release(to);
        }else from=to;
        to=landscape(makeCanvas(),requested,w,h);id=requested;changedAt=time;
      }
      const mix=from ? progress(time,options.reducedMotion) : 1;
      const opacity=(first || (from && options.reducedMotion)) ? 1 : (options.opacity ?? 1);
      ctx.save();ctx.globalCompositeOperation="source-over";
      if(from){ctx.globalAlpha=opacity;ctx.drawImage(from,0,0,w,h);}
      ctx.globalAlpha=opacity*mix;ctx.drawImage(to,0,0,w,h);ctx.restore();first=false;
      if(from && mix>=1){release(from);from=null;}
    }
    return Object.freeze({draw,snapshot:()=>({scene:id,buffers:Number(Boolean(from))+Number(Boolean(to)),width:w,height:h})});
  }
  root.NamimaScenery=Object.freeze({create,info:id=>INFO[valid(id)]});
})(typeof window!=="undefined" ? window : globalThis);
