const state={cat:new URLSearchParams(location.search).get('cat')||'all',q:'',sort:'featured'};
async function renderShop(){
  const grid=$('#grid'); grid.innerHTML='<div class="skeleton"></div>'.repeat(3);
  try{
    let list=await api.getProducts({search:state.q,category:state.cat});
    const s={low:(a,b)=>a.price-b.price,high:(a,b)=>b.price-a.price,newest:(a,b)=>b.created-a.created}[state.sort]; if(s) list.sort(s);
    grid.innerHTML=list.length?(await Promise.all(list.map(cardHTML))).join(''):'<div class="empty"><h3>No products found</h3><p>Try another category or clear your search.</p></div>';
  }catch(err){ grid.innerHTML=`<div class="empty"><h3>Couldn't load products</h3><p>${err.message}</p><button class="btn btn-outline" id="retry-products" type="button">Try again</button></div>`; $('#retry-products').onclick=renderShop; }
}
async function initShop(){
  try{$('#chips').innerHTML=(await api.getCategories()).map(c=>`<button class="chip ${c.id===state.cat?'on':''}" data-c="${c.id}">${c.name}</button>`).join('')}
  catch(error){$('#grid').innerHTML=`<div class="empty"><h3>Couldn't load categories</h3><p>${error.message}</p><button class="btn btn-outline" id="retry-categories" type="button">Try again</button></div>`;$('#retry-categories').onclick=initShop;return}
  $('#chips').onclick=e=>{const b=e.target.closest('[data-c]');if(!b)return;state.cat=b.dataset.c;document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x===b));renderShop()};
  $('#q').oninput=e=>{state.q=e.target.value.toLowerCase();renderShop()}; $('#sort').onchange=e=>{state.sort=e.target.value;renderShop()};
  renderShop();
}
async function initBest(){
  const best=$('#best');
  best.innerHTML='<div class="skeleton"></div>'.repeat(4);
  try{
    const products=await api.getProducts();
    best.innerHTML=products.length
      ? (await Promise.all(products.slice(0,4).map(cardHTML))).join('')
      : '<div class="empty"><h3>No products available</h3><p>Please check back soon.</p></div>';
  }catch(error){
    best.innerHTML=`<div class="empty"><h3>Couldn't load products</h3><p>${error.message}</p><button class="btn btn-outline" id="retry-best" type="button">Try again</button></div>`;
    $('#retry-best').onclick=initBest;
  }
}
async function initDetail(){
  const id=new URLSearchParams(location.search).get('id'), box=$('#detail');
  if(!id){box.innerHTML='<div class="empty"><h3>Product not found</h3><a class="btn btn-primary" href="products.html">Back to shop</a></div>';return}
  let p;
  try{p=await api.getProduct(id)}catch(error){box.innerHTML=`<div class="empty"><h3>Couldn't load product</h3><p>${error.message}</p></div>`;return}
  if(!p){box.innerHTML='<div class="empty"><h3>Product not found</h3><a class="btn btn-primary" href="products.html">Back to shop</a></div>';return}
  let q=1; document.title=p.name+' | Egg & Chicken';
  box.innerHTML=`<div><div class="art">${p.image?`<img src="${p.image}" alt="">`:p.emoji}</div><div class="thumbs"><span>${p.emoji}</span><span>🌾</span><span>📦</span></div></div>
  <div><small class="eyebrow">${p.category.toUpperCase()}</small><h1 style="font-size:2.4rem">${p.name}</h1><p class="stars">★★★★★ <span style="color:var(--brown)">${p.rating}</span></p>
  <p class="price" style="font-size:2rem;margin:8px 0">${peso(p.price)}</p><p>${p.description}</p>
  <p class="stock ${p.stock?'':'out'}" style="margin:10px 0">${p.stock?p.stock+' available':'Out of stock'}</p>
  <div class="btns" style="align-items:center"><div class="qty"><button id="m" aria-label="Decrease">−</button><span id="n">1</span><button id="p" aria-label="Increase">+</button></div>
  <button class="btn btn-primary" id="add" ${p.stock?'':'disabled'}>Add to Cart</button><button class="btn btn-gold" id="buy" ${p.stock?'':'disabled'}>Buy Now</button></div>
  <div class="info"><details open><summary>Product information</summary><p>Sourced from partner farms and quality checked.</p></details><details><summary>Freshness information</summary><p>Packed within 24 hours of collection.</p></details><details><summary>Storage instructions</summary><p>Keep chilled at 4°C or below. Eggs last up to 3 weeks refrigerated.</p></details><details><summary>Delivery information</summary><p>Chilled delivery or farm pickup. Free over ₱500.</p></details></div></div>`;
  $('#m').onclick=()=>$('#n').textContent=q=Math.max(1,q-1); $('#p').onclick=()=>$('#n').textContent=q=Math.min(p.stock,q+1);
  $('#add').onclick=async()=>{if(!requireAuth())return;try{await api.addToCart(p.id,q);await updateBadge();toast('Added to your cart')}catch(error){toast(error.message)}};
  $('#buy').onclick=async()=>{if(!requireAuth())return;try{await api.addToCart(p.id,q);location.href='checkout.html'}catch(error){toast(error.message)}};
  try{const rel=(await api.getProducts()).filter(x=>x.id!=p.id).slice(0,3);$('#related').innerHTML=(await Promise.all(rel.map(cardHTML))).join('')}catch(error){$('#related').innerHTML=`<div class="empty">${error.message}</div>`}
}
