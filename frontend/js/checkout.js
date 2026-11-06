async function initCheckout(){
  if(!requireAuth())return;
  let l;
  try{l=await loadLines()}catch(error){$('#err').textContent=error.message;$('#place').disabled=true;return}
  const t=totals(l);
  $('#items').innerHTML=l.map(i=>`<div><span>${i.qty} × ${i.name}</span><span>${peso(i.price*i.qty)}</span></div>`).join('')||'<p>Your cart is empty.</p>';
  $('#place').disabled=!l.length;
  try{const user=await api.getProfile();if(user){$('#name').value=user.name||'';$('#email').value=user.email||'';$('#phone').value=user.phone||''}}
  catch(error){$('#err').textContent=error.message;return}
  const draw=pick=>{const fee=pick==='pickup'||t.sub>=FREE_OVER?0:FEE;$('#csub').textContent=peso(t.sub);$('#cfee').textContent=fee?peso(fee):'Free';$('#ctotal').textContent=peso(t.sub+fee)};
  draw('standard'); document.querySelectorAll('[name=delivery]').forEach(r=>r.onchange=()=>draw(r.value));
  $('#form').onsubmit=async e=>{
    e.preventDefault(); const f=e.target; $('#err').textContent='';
    if(!l.length){$('#err').textContent='Add items to your cart before placing an order.';return}
    if(!f.checkValidity()){$('#err').textContent='Please complete the highlighted fields.';f.reportValidity();return}
    const b=$('#place'); b.disabled=true; b.textContent='Placing order…';
    try{
      const r=await api.checkout(Object.fromEntries(new FormData(f)));
      try{await updateBadge()}catch(error){console.warn('Order was placed, but the cart badge could not be refreshed',error)}
      if(r.checkout_url){b.textContent='Redirecting to secure payment…';location.assign(r.checkout_url);return}
      toast('Order placed!');
      setTimeout(()=>location.href='order-details.html?id='+r.id,700)
    }
    catch(err){$('#err').textContent=err.message;b.disabled=false;b.textContent='Place Order'}
  };
}
