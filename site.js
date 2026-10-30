/* =====================================================================
   עץ עברי — קוד משותף לכל הדפים
   ---------------------------------------------------------------------
   המוצרים נטענים מגיליון גוגל. כדי לחבר את הגיליון:
   1. פותחים את הגיליון בגוגל שיטס > שיתוף > "כל מי שיש לו את הקישור" > צופה.
   2. מעתיקים את הקישור לגיליון ומדביקים אותו כאן בין הגרשיים:            */
var SHEET_URL = 'https://docs.google.com/spreadsheets/d/1W2AN_NymPqZTCthyCG4XA9-nsCPbcoMKmjmskoeaeoI/edit';
/* 3. שם הלשונית במסמך (אם לא שיניתם — נשאר "מוצרים"):                    */
var SHEET_TAB = 'מוצרים';
/* אם הגיליון לא מחובר או לא נטען — האתר מציג את הרשימה הקבועה DEFAULT_PRODUCTS למטה.
   ===================================================================== */

var WHATSAPP = '972585240008';

var DEFAULT_PRODUCTS = [
  {id:'m1', cat:'מזוזות', name:'מזוזת עץ זית — לבן פנינה', desc:'עץ זית ואפוקסי בגוון לבן פנינה. חריץ לקלף באורך 12 ס״מ.', size:'15*4 ס״מ', tones:['לבן'], price:'150', img:'images/mezuzah-1.jpg', imgs:['images/mezuzah-3.jpg'], home:true},
  {id:'m2', cat:'מזוזות', name:'מזוזת עץ זית — לבן וכחול', desc:'זוג מזוזות מעץ זית ואפוקסי, לבן וכחול. חריץ לקלף באורך 12 ס״מ.', size:'15*4 ס״מ', tones:['לבן','כחול'], price:'150', img:'images/mezuzah-2.jpg', imgs:[], home:true},
  {id:'m3', cat:'מזוזות', name:'מזוזת עץ זית — לבן', desc:'עץ זית ואפוקסי לבן, על רקע מטע הזיתים. חריץ לקלף באורך 12 ס״מ.', size:'15*4 ס״מ', tones:['לבן'], price:'150', img:'images/mezuzah-3.jpg', imgs:[], home:true},
  {id:'m4', cat:'מזוזות', name:'מזוזת עץ זית — כחול ים', desc:'עץ זית ואפוקסי בגוון כחול. חריץ לקלף באורך 12 ס״מ.', size:'15*4 ס״מ', tones:['כחול'], price:'150', img:'images/mezuzah-4.jpg', imgs:[], home:true},
  {id:'m5', cat:'מזוזות', name:'מזוזת עץ זית — משולב', desc:'עץ זית ואפוקסי בגווני לבן וכחול. חריץ לקלף באורך 12 ס״מ.', size:'15*4 ס״מ', tones:['לבן','כחול','משולב'], price:'150', img:'images/mezuzah-5.jpg', imgs:['images/product-main.jpg'], home:true},
  {id:'m6', cat:'מזוזות', name:'מזוזת עץ זית — סדרת המטע', desc:'עץ זית ואפוקסי בגווני לבן וכחול. חריץ לקלף באורך 12 ס״מ.', size:'15*4 ס״מ', tones:['לבן','כחול','משולב'], price:'150', img:'images/mezuzah-6.jpg', imgs:['images/product-main.jpg'], home:true}
];

(function(){
  var PAGE = document.body.getAttribute('data-page') || 'home';

  /* ---------- helpers ---------- */
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function isNum(v){ return /^\s*\d+([.,]\d+)?\s*$/.test(String(v)); }
  function priceHtml(v){ v=String(v||'').trim(); if(!v) return ''; return isNum(v) ? esc(v)+' <small>₪</small>' : esc(v); }
  function img(src){
    src=String(src||'').trim(); if(!src) return '';
    var m=src.match(/drive\.google\.com\/(?:file\/d\/|open\?id=|uc\?(?:export=\w+&)?id=)([\w-]{20,})/);
    if(m) return 'https://drive.google.com/thumbnail?id='+m[1]+'&sz=w1400';
    if(/^https?:\/\//.test(src) || src.indexOf('/')>-1) return src;
    return 'images/'+src;
  }
  function productHref(p){ return 'product.html#'+encodeURIComponent(p.id); }
  function yes(v){ return /^(כן|v|✓|true|1|yes|x)$/i.test(String(v||'').trim()); }

  /* ---------- CSV from Google Sheets ---------- */
  function parseCSV(t){
    var rows=[],row=[],f='',q=false;
    for(var i=0;i<t.length;i++){
      var c=t[i];
      if(q){ if(c==='"'){ if(t[i+1]==='"'){f+='"';i++;} else q=false; } else f+=c; }
      else if(c==='"') q=true;
      else if(c===','){ row.push(f); f=''; }
      else if(c==='\n'){ row.push(f); rows.push(row); row=[]; f=''; }
      else if(c!=='\r') f+=c;
    }
    if(f!==''||row.length){ row.push(f); rows.push(row); }
    return rows;
  }
  var COLS = {id:'מזהה', cat:'קטגוריה', name:'שם', desc:'תיאור', size:'מידות', tones:'גוונים', price:'מחיר', img:'תמונה', imgs:'תמונות נוספות', home:'בדף הבית', show:'מוצג באתר'};
  function rowsToProducts(rows){
    if(!rows.length) return [];
    var head=rows[0].map(function(h){return h.trim()}), idx={};
    Object.keys(COLS).forEach(function(k){ idx[k]=head.indexOf(COLS[k]); });
    var out=[];
    rows.slice(1).forEach(function(r,n){
      function g(k){ return idx[k]>-1 ? (r[idx[k]]||'').trim() : ''; }
      if(!g('name')) return;
      if(idx.show>-1 && g('show') && !yes(g('show'))) return;
      out.push({
        id: g('id') || ('p'+(n+1)), cat: g('cat') || 'מזוזות', name: g('name'), desc: g('desc'), size: g('size'),
        tones: g('tones') ? g('tones').split(/[\/,،|]+/).map(function(s){return s.trim()}).filter(Boolean) : [],
        price: g('price'), img: g('img'),
        imgs: g('imgs') ? g('imgs').split(/[\s,]+/).filter(Boolean) : [],
        home: yes(g('home'))
      });
    });
    return out;
  }
  function sheetCsvUrl(u){
    var m=String(u).match(/\/spreadsheets\/d\/([\w-]{20,})/); if(!m) return '';
    return 'https://docs.google.com/spreadsheets/d/'+m[1]+'/gviz/tq?tqx=out:csv&headers=1&sheet='+encodeURIComponent(SHEET_TAB);
  }

  /* ---------- rendering ---------- */
  function card(p){
    return '<a class="card" href="'+productHref(p)+'" data-tones="'+esc(p.tones.join('|'))+'"><div class="ph">'+
      (p.img ? '<img src="'+esc(img(p.img))+'" alt="'+esc(p.name)+'" loading="lazy">' : '<div class="slot"><b>'+esc(p.name)+'</b>התמונה תעלה בהמשך</div>')+
      '</div><h3>'+esc(p.name)+'</h3>'+(p.size?'<div class="size">'+esc(p.size)+'</div>':'')+'<div class="price">'+priceHtml(p.price)+'</div></a>';
  }
  function fill(el, list){ if(el && list.length) el.innerHTML=list.map(card).join(''); }
  function byCat(all, cat){ return all.filter(function(p){ return p.cat.replace(/[׳']/g,'')===cat.replace(/[׳']/g,''); }); }

  function filters(list){
    var box=document.querySelector('[data-page="mezuzot"] .filters'); if(!box) return;
    var tones=[]; list.forEach(function(p){ p.tones.forEach(function(t){ if(tones.indexOf(t)<0) tones.push(t); }); });
    box.innerHTML='<button type="button" aria-pressed="true">הכל</button>'+tones.map(function(t){return '<button type="button" aria-pressed="false">'+esc(t)+'</button>'}).join('');
    box.hidden = tones.length<2;
    var bs=box.querySelectorAll('button');
    bs.forEach(function(b){ b.addEventListener('click',function(){
      bs.forEach(function(x){x.setAttribute('aria-pressed','false')}); b.setAttribute('aria-pressed','true');
      var t=b.textContent.trim();
      document.querySelectorAll('#catGrid .card').forEach(function(c){ c.hidden = !(t==='הכל' || c.getAttribute('data-tones').split('|').indexOf(t)>-1); });
    });});
  }

  function feature(id, p, full){
    var el=document.getElementById(id); if(!el || !p) return; var i=0;
    var GAL=[p.img].concat(p.imgs).filter(Boolean).map(img); if(!GAL.length) GAL=['images/product-main.jpg'];
    var tone=p.tones[0]||'';
    el.innerHTML =
      '<div class="gallery"><div class="main"><img alt="'+esc(p.name)+'" src="'+esc(GAL[0])+'"></div>'+
      (GAL.length>1 ? '<button class="nav prev" type="button" aria-label="התמונה הקודמת">›</button><button class="nav next" type="button" aria-label="התמונה הבאה">‹</button>'+
        '<div class="thumbs">'+GAL.map(function(s,k){return '<button type="button" aria-pressed="'+(k===0)+'" aria-label="תמונה '+(k+1)+'"><img src="'+esc(s)+'" alt=""></button>'}).join('')+'</div>' : '')+
      '</div><div class="info"><h2'+(full?' style="font-size:clamp(40px,4vw,54px);line-height:1.05"':'')+'>'+esc(full ? p.name : (p.cat==='מזוזות'?'מזוזה':p.name))+'</h2>'+
      '<div class="spec">'+esc(p.desc)+(p.size?'<br>'+esc(p.size):'')+'</div>'+
      (full && p.tones.length>1 ? '<div class="opts" role="group" aria-label="גוון">'+p.tones.map(function(t,k){return '<button type="button" aria-pressed="'+(k===0)+'">'+esc(t)+'</button>'}).join('')+'</div>' : '')+
      '<div class="price">'+priceHtml(p.price)+'</div>'+
      (full ? '<a class="btn order" href="#" target="_blank" rel="noopener" style="margin-top:8px">להזמנה בוואטסאפ</a>' : '<a class="btn ghost" href="'+productHref(p)+'" style="margin-top:8px">לפרטים</a>')+
      '<div class="note"><img src="images/t-note.png" alt="כל המוצרים הינם עבודת יד ויתכנו שינויים בין פריט לפריט"></div></div>';
    var main=el.querySelector('.main img'), th=el.querySelectorAll('.thumbs button');
    function show(n){ i=(n+GAL.length)%GAL.length; main.src=GAL[i]; th.forEach(function(b,k){b.setAttribute('aria-pressed', String(k===i))}); }
    var pv=el.querySelector('.prev'), nx=el.querySelector('.next');
    if(pv) pv.addEventListener('click',function(){show(i-1)});
    if(nx) nx.addEventListener('click',function(){show(i+1)});
    th.forEach(function(b,k){ b.addEventListener('click',function(){show(k)}) });
    var order=el.querySelector('.order');
    function setOrder(){ if(order) order.href='https://wa.me/'+WHATSAPP+'?text='+encodeURIComponent('שלום, אני מעוניין/ת ב'+p.name+(tone?' (גוון: '+tone+')':'')+' — '+p.price+(isNum(p.price)?' ₪':'')); }
    el.querySelectorAll('.opts button').forEach(function(b,_,all){ b.addEventListener('click',function(){ all.forEach(function(x){x.setAttribute('aria-pressed','false')}); b.setAttribute('aria-pressed','true'); tone=b.textContent; setOrder(); }); });
    setOrder();
  }

  function render(all){
    var mez=byCat(all,'מזוזות');
    var homeList=all.filter(function(p){return p.home}); if(!homeList.length) homeList=mez.slice(0,6);
    fill(document.getElementById('homeGrid'), homeList);
    fill(document.getElementById('catGrid'), mez); filters(mez);
    fill(document.querySelector('[data-prefix="table"]'), byCat(all,'שולחנות'));
    fill(document.querySelector('[data-prefix="butcher"]'), byCat(all,'בוצר'));
    var gifts=byCat(all,'מתנות'), gg=document.querySelector('.giftgrid');
    if(gg && gifts.length) gg.innerHTML=gifts.map(function(p){
      return '<a class="gift" href="'+productHref(p)+'"><div class="ph">'+(p.img?'<img src="'+esc(img(p.img))+'" alt="'+esc(p.name)+'">':'<div class="slot"><b>'+esc(p.name)+'</b>התמונה תעלה בהמשך</div>')+'</div><div class="b"><h3>'+esc(p.name)+'</h3><span>'+esc(p.desc)+'</span><span class="price">'+priceHtml(p.price)+'</span></div></a>';
    }).join('');
    feature('featureHome', homeList.filter(function(p){return p.imgs.length})[0] || homeList[0], false);
    if(PAGE==='product'){
      var id=decodeURIComponent((location.hash||'').slice(1));
      var p=all.filter(function(x){return x.id===id})[0] || mez[0] || all[0];
      if(p){
        feature('featureProduct', p, true);
        document.title=p.name+' | עץ עברי';
        var cr=document.querySelector('[data-page="product"] .crumbs'); if(cr) cr.textContent='ראשי / '+p.cat+' / '+p.name;
        var about=document.querySelector('[data-page="product"] .prose h2'); if(about) about.textContent= p.cat==='מזוזות' ? 'על המזוזה' : 'על המוצר';
        document.querySelectorAll('[data-page="product"] .prose p:not(.note)').forEach(function(x){ x.hidden = p.cat!=='מזוזות'; });
        var rel=byCat(all,p.cat).filter(function(x){return x.id!==p.id}).slice(0,4);
        var rg=document.getElementById('relGrid'); if(rg){ if(rel.length) fill(rg,rel); else rg.innerHTML=''; }
      }
    }
    // empty photo spots fill themselves once the file exists in images/
    document.querySelectorAll('.slot[data-img]').forEach(function(sl){
      var im=new Image(); im.alt=sl.querySelector('b')?sl.querySelector('b').textContent:''; im.loading='lazy';
      im.onload=function(){ im.style.width='100%'; im.style.height='100%'; im.style.objectFit='cover'; sl.replaceWith(im); };
      im.src=sl.getAttribute('data-img');
    });
  }

  // empty image slots for categories without products yet
  document.querySelectorAll('[data-slots]').forEach(function(el){
    var pre=el.getAttribute('data-prefix');
    el.innerHTML = el.getAttribute('data-slots').split('|').map(function(n,k){
      return '<a class="card" href="contact.html"><div class="ph"><div class="slot" data-img="images/'+pre+'-'+(k+1)+'.jpg"><b>'+esc(n)+'</b>התמונה תעלה בהמשך</div></div><h3>'+esc(n)+'</h3><div class="size">לפי מידה</div><div class="price">[מחיר] <small>₪</small></div></a>';
    }).join('');
  });

  render(DEFAULT_PRODUCTS);
  var csv=sheetCsvUrl(SHEET_URL);
  if(csv && window.fetch){
    fetch(csv,{cache:'no-store'}).then(function(r){ if(!r.ok) throw new Error(r.status); return r.text(); })
      .then(function(t){ var list=rowsToProducts(parseCSV(t)); if(list.length) render(list); })
      .catch(function(){ /* keeps the built-in list */ });
  }
  if(PAGE==='product') window.addEventListener('hashchange', function(){ location.reload(); });

  /* ---------- contact form → WhatsApp ---------- */
  var n=0;
  function contact(id, title, text){
    var el=document.getElementById(id); if(!el) return; n++;
    el.innerHTML = '<img class="bg" src="images/bg-olive-tree.jpg" alt=""><div class="in"><div class="say"><h2>'+title+'</h2><p>'+text+'</p></div>'+
      '<form class="f" novalidate>'+
      '<label for="fn'+n+'">שם<input id="fn'+n+'" name="name" autocomplete="given-name"></label>'+
      '<label for="ln'+n+'">שם משפחה<input id="ln'+n+'" name="family" autocomplete="family-name"></label>'+
      '<label for="ph'+n+'">טלפון<input id="ph'+n+'" name="phone" type="tel" autocomplete="tel"></label>'+
      '<fieldset><legend>מה מעניין אתכם?</legend>'+
      ['מזוזות','שולחנות','בוצ׳ר','מתנות'].map(function(x,k){return '<label class="chk" for="c'+n+'_'+k+'"><input type="checkbox" id="c'+n+'_'+k+'" name="topic" value="'+x+'">'+x+'</label>'}).join('')+
      '</fieldset><label for="msg'+n+'">הודעה<textarea id="msg'+n+'" name="message" rows="3"></textarea></label>'+
      '<button class="btn" type="submit">שליחה בוואטסאפ</button><div class="sent" aria-live="polite"></div></form></div>';
    el.querySelector('form').addEventListener('submit',function(e){
      e.preventDefault(); var f=e.target;
      var topics=[].slice.call(f.querySelectorAll('input[name=topic]:checked')).map(function(x){return x.value}).join(', ');
      var name=(f.elements['name'].value+' '+f.elements['family'].value).trim();
      if(!name || !f.elements['phone'].value.trim()){ el.querySelector('.sent').textContent='נא למלא שם וטלפון.'; return; }
      var text='שלום, אני '+name+' ('+f.elements['phone'].value.trim()+').'+(topics?' מתעניין/ת ב: '+topics+'.':'')+(f.elements['message'].value.trim()?'\n'+f.elements['message'].value.trim():'');
      var url='https://wa.me/'+WHATSAPP+'?text='+encodeURIComponent(text);
      el.querySelector('.sent').innerHTML='הפנייה מוכנה — <a href="'+url+'" target="_blank" rel="noopener" style="text-decoration:underline">לחצו כאן לשליחה בוואטסאפ</a>';
      var w=window.open(url,'_blank','noopener'); if(w) el.querySelector('.sent').textContent='נפתח וואטסאפ עם הפנייה שלכם — רק ללחוץ שליחה.';
    });
  }
  contact('contactHome','דברו איתנו','רוצים מזוזה, שולחן או מתנה? השאירו פרטים ונחזור אליכם.');
  contact('contactCustom','ספרו לנו מה בא לכם','צרפו רעיון ונחזור אליכם עם הצעה.');
  contact('contactPage','צור קשר','השאירו פרטים, או שלחו הודעה בוואטסאפ ל־058-5240008.');

  /* ---------- menu ---------- */
  var pages=document.querySelectorAll('.page'), links=document.querySelectorAll('.menu a'), menu=document.getElementById('menu'), burger=document.getElementById('burger');
  pages.forEach(function(p){ p.classList.toggle('on', p.getAttribute('data-page')===PAGE); });
  links.forEach(function(a){ a.classList.toggle('cur', a.getAttribute('href')===(PAGE==='home'?'index.html':PAGE+'.html')); });
  burger.addEventListener('click',function(){ var o=menu.classList.toggle('open'); burger.setAttribute('aria-expanded',String(o)); });
})();

/* ---------- תמונה בגדול בלחיצה (lightbox) ---------- */
(function(){
  var css = ''+
  '.lb{position:fixed;inset:0;z-index:100;background:rgba(20,18,12,.92);display:flex;align-items:center;justify-content:center;padding:calc(56px + env(safe-area-inset-top,0px)) 64px calc(70px + env(safe-area-inset-bottom,0px))}'+
  '.lb[hidden]{display:none}'+
  '.lb img{max-width:100%;max-height:100%;object-fit:contain;border-radius:10px;box-shadow:0 10px 40px rgba(0,0,0,.5);user-select:none}'+
  '.lb button{position:absolute;background:rgba(246,242,236,.92);color:#3E3C33;border:0;border-radius:50%;width:52px;height:52px;font-size:30px;line-height:52px;cursor:pointer;font-family:Arial,sans-serif}'+
  '.lb button:focus-visible{outline:3px solid #fff;outline-offset:2px}'+
  '.lb .x{top:calc(14px + env(safe-area-inset-top,0px));left:14px}'+
  '.lb .pv{right:10px;top:50%;margin-top:-26px}.lb .nx{left:10px;top:50%;margin-top:-26px}'+
  '.lb .ct{direction:ltr;unicode-bidi:isolate;position:absolute;bottom:calc(20px + env(safe-area-inset-bottom,0px));left:0;right:0;text-align:center;color:#EDE6D8;font-size:16px;font-family:Assistant,Arial,sans-serif}'+
  '.zoomable{cursor:zoom-in}'+
  '@media (max-width:600px){.lb{padding:60px 8px 64px}.lb .pv,.lb .nx{top:auto;bottom:calc(10px + env(safe-area-inset-bottom,0px));margin-top:0}.lb .pv{right:20px}.lb .nx{left:20px}}';
  var st=document.createElement('style'); st.textContent=css; document.head.appendChild(st);

  var box=document.createElement('div'); box.className='lb'; box.hidden=true;
  box.setAttribute('role','dialog'); box.setAttribute('aria-modal','true'); box.setAttribute('aria-label','תמונה בגדול');
  box.innerHTML='<img alt=""><button class="x" type="button" aria-label="סגירה">×</button>'+
    '<button class="pv" type="button" aria-label="התמונה הקודמת">›</button><button class="nx" type="button" aria-label="התמונה הבאה">‹</button><div class="ct"></div>';
  document.body.appendChild(box);
  var big=box.querySelector('img'), ct=box.querySelector('.ct'), pv=box.querySelector('.pv'), nx=box.querySelector('.nx');
  var list=[], i=0, last=null;

  function large(src){ return String(src).replace(/([?&]sz=)w\d+/,'$1w2400'); }
  function show(n){ i=(n+list.length)%list.length; big.src=large(list[i].src); big.alt=list[i].alt||'';
    ct.textContent= list.length>1 ? (i+1)+' / '+list.length : ''; pv.hidden=nx.hidden=list.length<2; }
  function open(items,n){ list=items; last=document.activeElement; box.hidden=false; document.body.style.overflow='hidden'; show(n); box.querySelector('.x').focus(); }
  function close(){ box.hidden=true; document.body.style.overflow=''; big.removeAttribute('src'); if(last&&last.focus) last.focus(); }

  box.querySelector('.x').addEventListener('click',close);
  pv.addEventListener('click',function(e){e.stopPropagation();show(i-1)});
  nx.addEventListener('click',function(e){e.stopPropagation();show(i+1)});
  box.addEventListener('click',function(e){ if(e.target===box) close(); });
  document.addEventListener('keydown',function(e){
    if(box.hidden) return;
    if(e.key==='Escape') close();
    else if(e.key==='ArrowRight') show(i-1);
    else if(e.key==='ArrowLeft') show(i+1);
  });
  var sx=null; // swipe on phones
  box.addEventListener('touchstart',function(e){ sx=e.touches[0].clientX; },{passive:true});
  box.addEventListener('touchend',function(e){ if(sx===null) return; var dx=e.changedTouches[0].clientX-sx; if(Math.abs(dx)>50) show(dx>0? i+1 : i-1); sx=null; });

  // product gallery: main photo opens the whole gallery
  document.addEventListener('click',function(e){
    var m=e.target.closest('.gallery .main img');
    if(m){
      var g=m.closest('.gallery'), th=[].slice.call(g.querySelectorAll('.thumbs img'));
      var items= th.length ? th.map(function(t){return {src:t.src,alt:m.alt}}) : [{src:m.src,alt:m.alt}];
      var n=0; items.forEach(function(it,k){ if(it.src===m.src) n=k; });
      open(items,n); return;
    }
    var w=e.target.closest('.works figure img, [data-page="about"] .ph img');
    if(w){
      var all=[].slice.call(document.querySelectorAll('.works figure img'));
      if(all.indexOf(w)<0) all=[w];
      open(all.map(function(x){return {src:x.src,alt:x.alt||(x.closest('figure')&&x.closest('figure').textContent.trim())||''}}), all.indexOf(w));
    }
  });
  // mark zoomable images (also ones added later from the sheet)
  function mark(){ document.querySelectorAll('.gallery .main img, .works figure img').forEach(function(x){ x.classList.add('zoomable'); x.title='לחצו להגדלה'; }); }
  mark(); new MutationObserver(mark).observe(document.body,{childList:true,subtree:true});
})();
