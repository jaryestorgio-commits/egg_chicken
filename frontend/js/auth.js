function bindAuth(kind){
  const form=$('#form');
  if(kind==='login'){
    const password=$('#pw');
    const toggle=$('#toggle-password');
    toggle?.addEventListener('click',()=>{
      const show=password.type==='password';
      password.type=show?'text':'password';
      toggle.setAttribute('aria-label',show?'Hide password':'Show password');
      toggle.setAttribute('aria-pressed',String(show));
    });
    $('#forgot-password')?.addEventListener('click',event=>{
      event.preventDefault();
      const help=$('#login-help');
      help.hidden=!help.hidden;
    });
  }
  form.onsubmit=async e=>{ e.preventDefault(); const f=e.target,err=$('#err'),success=$('#login-success'),button=f.querySelector('[type="submit"]'),buttonLabel=button.innerHTML; err.textContent=''; if(success)success.hidden=true;
    if(!f.checkValidity()){err.textContent=kind==='register'?'Enter a valid email and a password of at least 8 characters.':'Enter a valid email and password.';return}
    button.disabled=true;
    button.textContent=kind==='register'?'Creating account…':'Signing in…';
    try{
      const formData=Object.fromEntries(new FormData(f));
      const remember=f.elements.remember?.checked??true;
      delete formData.remember;
      const user=await api[kind](formData);
      let destination='profile.html';
      if(kind==='login'){
        const token=localStorage.getItem(TOKEN_KEY);
        if(token){
          localStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(TOKEN_KEY);
          (remember?localStorage:sessionStorage).setItem(TOKEN_KEY,token);
        }
        if(user?.role==='admin')destination=`${ROOT}admin/dashboard.html`;
        else if(user?.role==='customer')destination=`${ROOT}index.html`;
        else{
          localStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(TOKEN_KEY);
          throw new Error('This account does not have a supported role.');
        }
      }else{
        const next=new URLSearchParams(location.search).get('next');
        if(next){try{const target=new URL(next,location.href);if(target.origin===location.origin)destination=target.href}catch{}}
      }
      toast('Welcome to Egg & Chicken');
      if(success){success.textContent='Signed in successfully. Redirecting…';success.hidden=false}
      setTimeout(()=>{location.href=destination},700);
    }catch(x){err.textContent=accountErrorMessage(x)}
    finally{button.disabled=false;button.innerHTML=buttonLabel}
  };
}
const accountEscape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const accountErrorMessage = error => {
  const details = error.errors && typeof error.errors === 'object'
    ? Object.values(error.errors).flat().filter(value => typeof value === 'string')
    : [];
  return details.length ? `${error.message}: ${details.join(', ')}` : error.message;
};
let accountOrders = [];
let accountAddressesLoaded = false;

function showAccountMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle('error', isError);
}

function renderAccountOrders(target, orders, mode) {
  if (!orders.length) {
    target.innerHTML = `<div class="account-empty card"><span aria-hidden="true">🥚</span><h3>${mode === 'recent' ? 'No orders yet' : 'Your order list is empty'}</h3><p>Your orders will appear here after checkout.</p><a class="btn btn-primary btn-sm" href="${ROOT}pages/products.html">Browse the shop</a></div>`;
    return;
  }
  const displayedOrders = mode === 'recent' ? orders.slice(0, 3) : orders;
  target.innerHTML = displayedOrders.map(order => {
    const id = encodeURIComponent(order.id);
    const status = accountEscape(order.status || 'pending');
    const statusClass = String(order.status || 'pending').toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const itemCount = (order.items || []).reduce((count, item) => count + Number(item.qty || item.quantity || 0), 0);
    const action = mode === 'orders' ? 'View order' : 'Track order';
    return `<a class="account-order-card card" href="${ROOT}pages/order-details.html?id=${id}">
      <div class="account-order-main"><span class="account-order-number">Order #${accountEscape(order.id)}</span><span class="account-status status-${statusClass}">${status}</span></div>
      <div class="account-order-meta"><span>${accountEscape(order.date || 'Date unavailable')}</span><span>${itemCount} ${itemCount === 1 ? 'item' : 'items'}</span><strong>${peso(order.total)}</strong></div>
      <span class="account-order-link">${action} <span aria-hidden="true">→</span></span>
    </a>`;
  }).join('');
}

async function loadAccountOrders() {
  const targets = [
    ['#recent-orders', 'recent'],
    ['#all-orders', 'orders'],
    ['#tracking-orders', 'tracking']
  ];
  targets.forEach(([selector]) => { const target = $(selector); if (target) target.innerHTML = '<div class="account-loading" role="status">Loading your orders…</div>'; });
  try {
    accountOrders = await api.getOrders();
    targets.forEach(([selector, mode]) => { const target = $(selector); if (target) renderAccountOrders(target, accountOrders, mode); });
  } catch (error) {
    targets.forEach(([selector]) => {
      const target = $(selector);
      if (target) target.innerHTML = `<div class="account-empty card"><h3>Couldn't load orders</h3><p>${accountEscape(error.message)}</p><button class="btn btn-outline btn-sm" type="button" data-account-retry="orders">Try again</button></div>`;
    });
  }
}

async function loadAccountWishlist() {
  const target = $('#wishlist-items');
  target.innerHTML = '<div class="account-loading" role="status">Loading your saved products…</div>';
  try {
    const savedIds = api.getWishlistIds();
    if (!savedIds.length) {
      target.innerHTML = '<div class="account-empty card"><span aria-hidden="true">♡</span><h3>Your wishlist is waiting</h3><p>Save products from the shop and they will show up here.</p><a class="btn btn-primary btn-sm" href="../pages/products.html">Explore products</a></div>';
      return;
    }
    const products = await api.getProducts();
    const savedProducts = products.filter(product => savedIds.includes(Number(product.id)));
    target.innerHTML = savedProducts.length
      ? (await Promise.all(savedProducts.map(cardHTML))).join('')
      : '<div class="account-empty card"><h3>Saved products are no longer available</h3><p>Browse the shop to find something fresh to save.</p><a class="btn btn-primary btn-sm" href="../pages/products.html">Explore products</a></div>';
  } catch (error) {
    target.innerHTML = `<div class="account-empty card"><h3>Couldn't load your wishlist</h3><p>${accountEscape(error.message)}</p><button class="btn btn-outline btn-sm" type="button" data-account-retry="wishlist">Try again</button></div>`;
  }
}

function addressFields(address) {
  return `<div class="account-fields">
    <div><label>Full name<input name="full_name" required maxlength="150" value="${accountEscape(address.full_name)}"></label></div>
    <div><label>Phone number<input name="phone" required maxlength="40" value="${accountEscape(address.phone)}"></label></div>
    <div class="field-wide"><label>Street address<input name="address_line" required maxlength="300" value="${accountEscape(address.address_line)}"></label></div>
    <div><label>City<input name="city" required maxlength="120" value="${accountEscape(address.city)}"></label></div>
    <div><label>Province<input name="province" required maxlength="120" value="${accountEscape(address.province)}"></label></div>
    <div><label>Postal code<input name="postal_code" required maxlength="20" value="${accountEscape(address.postal_code)}"></label></div>
  </div>
  <label class="account-check"><input type="checkbox" name="is_default" value="true" ${address.is_default ? 'checked' : ''}> Set as my default address</label>`;
}

async function loadAccountAddresses() {
  const target = $('#addresses-list');
  target.innerHTML = '<div class="account-loading" role="status">Loading your addresses…</div>';
  try {
    const addresses = await api.getAddresses();
    accountAddressesLoaded = true;
    target.innerHTML = addresses.length ? addresses.map(address => `<article class="card address-card">
      <form class="address-edit-form" data-address-id="${accountEscape(address.id)}">
        <div class="address-heading"><h3>Saved address</h3>${address.is_default ? '<span class="account-status status-default">Default</span>' : ''}</div>
        ${addressFields(address)}
        <p class="account-message error" role="alert"></p>
        <div class="account-form-actions"><button class="btn btn-outline btn-sm" type="submit">Save address</button><button class="address-delete" type="button" data-delete-address="${accountEscape(address.id)}">Remove</button></div>
      </form>
    </article>`).join('') : '<div class="account-empty card"><h3>No saved addresses</h3><p>Add a delivery address to make checkout quicker.</p></div>';
  } catch (error) {
    accountAddressesLoaded = false;
    target.innerHTML = `<div class="account-empty card"><h3>Couldn't load your addresses</h3><p>${accountEscape(error.message)}</p><button class="btn btn-outline btn-sm" type="button" data-account-retry="addresses">Try again</button></div>`;
  }
}

async function initProfile(){
  if(!requireAuth())return;
  const nav = $('.account-nav');
  const navMedia = window.matchMedia('(min-width: 761px)');
  const syncAccountNav = () => { nav.open = navMedia.matches; };
  syncAccountNav();
  navMedia.addEventListener('change', syncAccountNav);

  document.querySelectorAll('[data-account-view]').forEach(button => {
    button.addEventListener('click', () => {
      const viewName = button.dataset.accountView;
      document.querySelectorAll('.account-view').forEach(view => { view.hidden = view.dataset.view !== viewName; });
      document.querySelectorAll('.side [data-account-view]').forEach(link => link.classList.toggle('on', link.dataset.accountView === viewName));
      if (!navMedia.matches) nav.open = false;
      if (viewName === 'addresses' && !accountAddressesLoaded) loadAccountAddresses();
      if (viewName === 'wishlist') loadAccountWishlist();
    });
  });

  const accountError = $('#account-error');
  try {
    const user = await api.getProfile();
    if (!user) { location.href = 'login.html'; return; }
    $('#account-name').textContent = user.name || 'Customer';
    $('#account-email').textContent = user.email || '';
    $('#profile-name').value = user.name || '';
    $('#profile-email').value = user.email || '';
  } catch (error) {
    accountError.hidden = false;
    accountError.innerHTML = `<strong>Couldn't load your account.</strong> ${accountEscape(error.message)} <button type="button" class="btn btn-outline btn-sm" id="retry-account">Try again</button>`;
    $('#retry-account').onclick = () => location.reload();
  }
  loadAccountOrders();

  $('#profile-form').onsubmit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const errorText = $('#profile-error');
    const status = $('#profile-status');
    const submit = form.querySelector('[type="submit"]');
    errorText.textContent = '';
    status.textContent = '';
    if (!form.reportValidity()) return;
    submit.disabled = true;
    submit.textContent = 'Saving…';
    try {
      const updated = await api.updateProfile(Object.fromEntries(new FormData(form)));
      $('#account-name').textContent = updated.name;
      $('#account-email').textContent = updated.email;
      showAccountMessage(status, 'Profile saved successfully.');
      toast('Profile updated');
    } catch (error) {
      showAccountMessage(errorText, accountErrorMessage(error), true);
    } finally {
      submit.disabled = false;
      submit.textContent = 'Save changes';
    }
  };

  $('#address-form').onsubmit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const errorText = $('#address-error');
    const submit = form.querySelector('[type="submit"]');
    errorText.textContent = '';
    if (!form.reportValidity()) return;
    const data = Object.fromEntries(new FormData(form));
    data.is_default = form.elements.is_default.checked;
    submit.disabled = true;
    submit.textContent = 'Adding…';
    try {
      await api.createAddress(data);
      form.reset();
      await loadAccountAddresses();
      toast('Address added');
    } catch (error) {
      showAccountMessage(errorText, accountErrorMessage(error), true);
    } finally {
      submit.disabled = false;
      submit.textContent = 'Add address';
    }
  };

  $('#password-form').onsubmit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const errorText = $('#password-error');
    const status = $('#password-status');
    const submit = form.querySelector('[type="submit"]');
    errorText.textContent = '';
    status.textContent = '';
    if (!form.reportValidity()) return;
    const data = Object.fromEntries(new FormData(form));
    if (data.new_password !== data.confirm_password) {
      showAccountMessage(errorText, 'The new passwords do not match.', true);
      return;
    }
    delete data.confirm_password;
    submit.disabled = true;
    submit.textContent = 'Updating…';
    try {
      await api.updatePassword(data);
      form.reset();
      showAccountMessage(status, 'Password updated successfully.');
      toast('Password updated');
    } catch (error) {
      showAccountMessage(errorText, accountErrorMessage(error), true);
    } finally {
      submit.disabled = false;
      submit.textContent = 'Update password';
    }
  };

  document.addEventListener('submit', async event => {
    const form = event.target.closest('.address-edit-form');
    if (!form) return;
    event.preventDefault();
    if (!form.reportValidity()) return;
    const errorText = form.querySelector('[role="alert"]');
    const submit = form.querySelector('[type="submit"]');
    const data = Object.fromEntries(new FormData(form));
    data.is_default = form.elements.is_default.checked;
    errorText.textContent = '';
    submit.disabled = true;
    submit.textContent = 'Saving…';
    try {
      await api.updateAddress(form.dataset.addressId, data);
      await loadAccountAddresses();
      toast('Address updated');
    } catch (error) {
      showAccountMessage(errorText, accountErrorMessage(error), true);
    } finally {
      if (submit.isConnected) {
        submit.disabled = false;
        submit.textContent = 'Save address';
      }
    }
  });

  document.addEventListener('click', async event => {
    const remove = event.target.closest('[data-delete-address]');
    if (remove) {
      remove.disabled = true;
      try {
        await api.deleteAddress(remove.dataset.deleteAddress);
        await loadAccountAddresses();
        toast('Address removed');
      } catch (error) {
        toast(error.message);
        remove.disabled = false;
      }
      return;
    }
    const retry = event.target.closest('[data-account-retry]');
    if (retry?.dataset.accountRetry === 'orders') loadAccountOrders();
    if (retry?.dataset.accountRetry === 'wishlist') loadAccountWishlist();
    if (retry?.dataset.accountRetry === 'addresses') loadAccountAddresses();
  });
  document.addEventListener('wishlist:changed', () => {
    if ($('[data-view="wishlist"]:not([hidden])')) loadAccountWishlist();
  });

  $('#logout').onclick = async () => {
    const button = $('#logout');
    button.disabled = true;
    try { await api.logout(); }
    catch (error) { toast(error.message); }
    finally { location.href = 'login.html'; }
  };
}
async function initOrders(){
  const box=$('#orders');if(!requireAuth())return;
  box.innerHTML='<div class="skeleton"></div>';
  try{const orders=await api.getOrders();box.innerHTML=orders.map(o=>`<a class="card hover" style="display:flex;justify-content:space-between;margin-top:12px" href="order-details.html?id=${o.id}"><b>Order #${o.id}</b><span>${o.date}</span><b>${peso(o.total)}</b></a>`).join('')||'<div class="empty"><p>No orders yet.</p></div>'}
  catch(error){box.innerHTML=`<div class="empty"><h3>Couldn't load orders</h3><p>${error.message}</p></div>`}
}
async function initOrder(){
  if(!requireAuth())return;
  const params=new URLSearchParams(location.search),id=params.get('id'),meta=$('#meta');
  if(!id){meta.innerHTML='<div class="empty"><p>Select an order from your order history.</p><a href="orders.html">My orders</a></div>';return}
  let o;try{o=await api.getOrder(id)}catch(error){meta.innerHTML=`<div class="empty"><h3>Couldn't load this order</h3><p>${error.message}</p></div>`;return}
  if(!o){meta.innerHTML='<div class="empty"><p>Order not found.</p></div>';return}
  let verificationMessage='';
  const onlinePayment=(o.payments||[]).find(payment=>['online_payment','gcash','card'].includes(payment.payment_method)&&['pending','failed'].includes(payment.payment_status));
  if(onlinePayment){
    try{
      await api.getPayment(onlinePayment.id);
      o=await api.getOrder(id);
    }catch(error){
      verificationMessage=`Payment status could not be refreshed: ${accountEscape(error.message)}. The order remains pending until Xendit verification completes.`;
    }
  }
  const pendingOnlinePayment=(o.payments||[]).find(payment=>['online_payment','gcash','card'].includes(payment.payment_method)&&['pending','failed'].includes(payment.payment_status));
  const canCancel=o.status==='pending'&&!(o.payments||[]).some(payment=>payment.payment_status==='paid');
  const steps=['Order Placed','Order Confirmed','Preparing','Out for Delivery','Delivered'];
  $('#tl').innerHTML=steps.map((s,i)=>`<li class="${i<o.statusStep?'done':i===o.statusStep?'now':''}"><i></i><b>${s}</b></li>`).join('');
  const returnState=params.get('payment');
  const paymentMessage=returnState==='cancelled'&&o.status==='pending'
    ? 'Returned from checkout. The payment is not confirmed; this order remains pending until the server verifies the invoice.'
    : returnState==='success'&&o.status==='pending'
      ? 'Payment is being verified by Xendit. This order will update after server verification.'
      : returnState==='failed'&&o.status==='pending'
        ? 'The payment was not completed. This order remains pending while the Xendit invoice is still active.'
        : '';
  const payments=(o.payments||[]).map(payment=>`<div><b>Payment</b> ${accountEscape(payment.payment_method.replaceAll('_',' '))} · ${accountEscape(payment.payment_status)}</div>`).join('');
  $('#meta').innerHTML=`<div><b>Order</b> #${o.id}</div><div><b>Date</b> ${accountEscape(o.date)}</div><div><b>Status</b> ${accountEscape(o.status)}</div><div><b>Address</b> ${accountEscape(o.address)}</div>${payments}${paymentMessage?`<p role="status">${accountEscape(paymentMessage)}</p>`:''}${verificationMessage?`<p role="alert">${verificationMessage}</p>`:''}`+(o.items||[]).map(i=>`<div>${accountEscape(i.qty)} × ${accountEscape(i.product_name)}</div>`).join('')+`<div class="price">Total ${peso(o.total)}</div>`+(pendingOnlinePayment?.checkout_url?`<a class="btn btn-primary" href="${accountEscape(pendingOnlinePayment.checkout_url)}">Continue online checkout</a>`:'')+(canCancel?'<button class="btn btn-outline" id="cancel-order" type="button">Cancel pending order</button>':'');
  $('#cancel-order')?.addEventListener('click',async event=>{
    const button=event.currentTarget;
    if(!window.confirm('Cancel this pending order? An online checkout will be closed before stock is released.'))return;
    button.disabled=true;
    try{await api.cancelOrder(id);toast('Order cancelled');await initOrder()}
    catch(error){toast(error.message);button.disabled=false}
  });
}
