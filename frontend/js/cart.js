const FEE=50, FREE_OVER=500;
async function loadLines(){ return api.getCart(); }
function totals(l){ const sub=l.reduce((s,i)=>s+i.price*i.qty,0); const fee=!sub||sub>=FREE_OVER?0:FEE; return {sub,fee,total:sub+fee}; }
async function renderCart(){
  const box=$('#lines');
  if(!requireAuth())return;
  let l;
  try{l=await loadLines()}catch(error){box.innerHTML=`<div class="empty"><h3>Couldn't load your cart</h3><p>${error.message}</p><a class="btn btn-primary" href="login.html">Log in</a></div>`;return}
  const t=totals(l);
  $('#sub').textContent=peso(t.sub); $('#fee').textContent=t.fee?peso(t.fee):'Free'; $('#total').textContent=peso(t.total);
  if($('#bar-total')) $('#bar-total').textContent=peso(t.total);
  $('#go').setAttribute('aria-disabled',String(!l.length));
  $('#go').href=l.length?'checkout.html':'products.html';
  box.innerHTML=l.length?l.map(i=>`<div class="line"><div class="thumb">🧺</div><div><b>${i.name}</b><br><span class="price">${peso(i.price)}</span></div>
  <div class="qty"><button data-q="${i.itemId}" data-d="-1" aria-label="Decrease">−</button><span>${i.qty}</span><button data-q="${i.itemId}" data-d="1" aria-label="Increase">+</button></div>
  <div style="text-align:right"><b>${peso(i.price*i.qty)}</b><br><button class="rm" data-rm="${i.itemId}">Remove</button></div></div>`).join('')
  :'<div class="empty"><h3>Your cart is empty</h3><p>Fresh eggs and chicken are waiting.</p><a class="btn btn-primary" href="products.html">Start shopping</a></div>';
}
document.addEventListener('click',async e=>{
  const q=e.target.closest('[data-q]'),r=e.target.closest('[data-rm]');
  try{
    if(q){const c=await api.getCart(),item=c.find(x=>x.itemId==q.dataset.q);if(item)await api.updateCart(item.itemId,Math.max(1,item.qty+Number(q.dataset.d)))}
    if(r){await api.removeFromCart(r.dataset.rm);toast('Item removed')}
    if(q||r){await renderCart();await updateBadge()}
  }catch(error){toast(error.message)}
});
