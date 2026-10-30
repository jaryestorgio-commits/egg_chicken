const ROOT = document.body.dataset.root || '';
const API_BASE = window.EC_API_BASE_URL || 'http://127.0.0.1:5000/api/v1';
const TOKEN_KEY = 'ec_access_token';
const WISHLIST_KEY = 'ec_wishlist';
const getAuthToken = () => localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
const clearAuthToken = () => { localStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(TOKEN_KEY); };
const saveAuthToken = (token, remember = true) => {
  clearAuthToken();
  (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
};
const productImageFiles = {
  'free-range brown eggs (6-pack)': '842eab39-e19c-4b8e-9d00-653d7390d64e.jpg',
  'large white eggs (12-pack)': '413fc266-a996-4364-ae41-945ee649f82f.jpg',
  'farm-fresh brown eggs (12-pack)': '674a8180-defe-44c6-aec6-30eb9ecd498d.jpg',
  'organic duck eggs (6-pack)': 'oPeUTlCPxYHN8EEh3xkEY4uOtFkzmhQHGSehiYfifvChLdSFSgKUKI1GBPWSCzsqGCxMLGimD1yOLbRnT9moKwKXRf0qpzuzJcML7cct2ALKTMgXMk14rNUOwSCJHSVrbu8-do4Z5S3ctJ9S0yT4AkAeMib4JkDehemIL4nUfgTbAn1OGh1x7DutHNzPjxDD.jpg',
  'whole native chicken (1 kg)': 'b019f5a0-d29e-44ab-8905-12a1ad787e31.jpg',
  'whole broiler chicken (1.2 kg)': '30142feb-1c76-48e6-81ab-838b28002d1a.jpg',
  'free-range whole chicken (1.5 kg)': 'e3e0c3a8-10a4-466b-8dff-a4ba26d4d6ff.jpg',
  'frozen whole chicken (1 kg)': '158f3fdd-5b84-4d4a-99c1-0e8a1e27c3b2.jpg',
  'chicken breast fillet (500 g)': 'a02bbb37-09eb-4f2a-a94b-c8b530f789cf.jpg',
  'chicken thighs (500 g)': '1e69904f-65d6-4cfa-adef-04919bebc6aa.jpg',
  'chicken wings (500 g)': '201b8b8f-26e4-44e5-99fa-47024a3cd9ea.jpg',
  'chicken drumsticks (500 g)': 'c771b862-f35d-40c6-b2c6-613788e90b54.jpg',
  'chicken leg quarters (500 g)': 'b3e6ab6d-7256-49f5-a260-39e918b7d6f7.jpg',
  eggs: 'ejphTqEcqSzfJGUULFweyeo8ozbXWkwhvV1DZqgoS9eXdjyQRdOfY50UKPrzNqr3DX9UCnaEgDwh2rIfDHq3sAMP0Y-kKq-Z_s6BiNcoRBpKgy0tAB-KmsVScDFeUAujaURbEP54lL2W6xNvMwqFQruVONOMK5o5MKjRBXAxJaCsKIAZeIA2i1cKHuY6GeS2.jpg',
  whole: 'dQ4lxeApBk_Adllm_0utRh4e9_3IRTjp-j76JdJ0jwj8mrwmTtpvLsq2-lh2UZipwbt0_c05A3Co0sg10S63uPxA-givLyjl8MDMzvSMwvm4k2MDeVst8nX09CXo3sbA9UqA1hHulU_am6PdohDQZEwjke5eaVw1YKnL_s3E1fZa1rUsSsj6Usmbo1coHNfm.jpg',
  bundles: 'tq77HwjLAAu834gPgCyBIcyTerd5ywKD7-Hh1qqT7efvr7PxMKaelrvO_YlouFo38JMFGI8_pTsr7HHjTRq191WvInZTtblna4HW209iwE_ewETpBbW9sajM92Bj6FbwsscDRYr13YnRc5T2c2Sqcb8cFAv5bPMWioPQqRXhdgVfIbpMQibwukosDLud78qF.jpg'
};
const peso = n => '₱' + Number(n).toFixed(2);
const $ = (s, el = document) => el.querySelector(s);

let categoriesCache;
class ApiError extends Error {
  constructor(message, status, errors) { super(message); this.status = status; this.errors = errors; }
}
const request = async (method, path, body) => {
  const headers = { Accept: 'application/json' };
  const token = getAuthToken();
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body)
    });
  } catch {
    throw new ApiError('Could not reach the store. Check that the API is running and try again.', 0);
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    if (response.status === 401 && token) {
      clearAuthToken();
      const page = location.pathname.toLowerCase();
      if (!page.endsWith('/login.html') && !page.endsWith('/register.html')) {
        const login = `${ROOT}pages/login.html?next=${encodeURIComponent(location.href)}`;
        location.href = login;
      }
    }
    throw new ApiError(payload.message || `Request failed (${response.status})`, response.status, payload.errors);
  }
  return payload.data ?? payload;
};
const categorySlug = name => {
  const value = String(name || '').toLowerCase();
  if (value.includes('egg')) return 'eggs';
  if (value.includes('whole')) return 'whole';
  if (value.includes('cut')) return 'cuts';
  if (value.includes('bundle')) return 'bundles';
  return value.trim().replace(/\s+/g, '-');
};
const getCategories = async () => {
  if (!categoriesCache) {
    const data = await request('GET', '/categories');
    categoriesCache = [{ id: 'all', name: 'All', categoryId: null },
      ...(data.categories || []).map(category => ({ ...category, categoryId: category.id, id: categorySlug(category.name) }))];
  }
  return categoriesCache;
};
const normalizeProduct = async product => {
  const categories = await getCategories();
  const category = categories.find(item => item.categoryId === product.category_id);
  const slug = category?.id || '';
  const localImage = productImageFiles[String(product.name || '').trim().toLowerCase()]
    || productImageFiles[slug];
  return {
    ...product, category: slug, categoryId: product.category_id,
    image: product.image_url && !product.image_url.includes('placehold.co')
      ? product.image_url
      : localImage ? `${ROOT}assets/images/${localImage}` : '',
    emoji: slug === 'eggs' ? '🥚' : slug === 'whole' ? '🐔' : slug === 'cuts' ? '🍗' : '🧺',
    created: product.created_at ? Date.parse(product.created_at) : 0,
    rating: product.rating ?? '',
    stock: product.stock ?? product.stock_quantity ?? 0
  };
};
const normalizeOrder = order => {
  const status = String(order.status || '').toLowerCase();
  const step = ({ pending: 0, confirmed: 1, processing: 2, shipped: 3, out_for_delivery: 3, delivered: 4 })[status] ?? 0;
  return {
    ...order, date: order.created_at ? new Date(order.created_at).toLocaleDateString() : '',
    total: Number(order.total_amount || 0), address: order.shipping_address || '', statusStep: step,
    items: (order.items || []).map(item => ({ ...item, id: item.product_id, qty: item.quantity }))
  };
};

const api = {
  get: path => request('GET', path),
  post: (path, data) => request('POST', path, data),
  put: (path, data) => request('PUT', path, data),
  patch: (path, data) => request('PATCH', path, data),
  delete: path => request('DELETE', path),
  getCategories,
  getProducts: async ({ search = '', category = 'all' } = {}) => {
    const categories = await getCategories();
    const selected = categories.find(item => item.id === category);
    const params = new URLSearchParams({ limit: '100' });
    if (search.trim()) params.set('search', search.trim());
    if (selected?.categoryId) params.set('category_id', selected.categoryId);
    const data = await request('GET', `/products?${params}`);
    const pages = Number(data.pagination?.pages || 1);
    const remaining = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, async (_, index) => {
      const pageParams = new URLSearchParams(params);
      pageParams.set('page', String(index + 2));
      return (await request('GET', `/products?${pageParams}`)).products || [];
    }));
    return Promise.all([...(data.products || []), ...remaining.flat()].map(normalizeProduct));
  },
  getProduct: async id => {
    const data = await request('GET', `/products/${encodeURIComponent(id)}`);
    return data.product ? normalizeProduct(data.product) : null;
  },
  getCart: async () => {
    const data = await request('GET', '/cart');
    return (data.cart?.items || []).map(item => ({
      ...item, itemId: item.id, id: item.product_id, product_id: item.product_id,
      qty: item.quantity, price: Number(item.unit_price), stock: item.stock
    }));
  },
  addToCart: (id, qty = 1) => request('POST', '/cart/items', { product_id: Number(id), quantity: qty }),
  updateCart: (itemId, qty) => request('PATCH', `/cart/items/${encodeURIComponent(itemId)}`, { quantity: qty }),
  removeFromCart: itemId => request('DELETE', `/cart/items/${encodeURIComponent(itemId)}`),
  clearCart: () => request('DELETE', '/cart'),
  checkout: async data => {
    const shipping_address = [data.name, data.phone, data.address, data.barangay, data.city, data.province, data.zip]
      .filter(Boolean).join(', ');
    const payment_method = data.payment === 'cod' ? 'cash_on_delivery' : 'online_payment';
    const result = await request('POST', '/orders', {
      shipping_address,
      delivery_option: data.delivery || 'standard',
      payment_method
    });
    const order = normalizeOrder(result.order);
    order.payment = result.payment;
    order.checkout_url = result.checkout_url || result.payment?.checkout_url || '';
    if (payment_method === 'online_payment' && !order.checkout_url) {
      throw new ApiError('Xendit did not return a hosted invoice URL. Contact support before retrying this order.', 502);
    }
    return order;
  },
  getOrders: async () => {
    const data = await request('GET', '/orders');
    return (data.orders || []).map(normalizeOrder);
  },
  getOrder: async id => {
    const data = await request('GET', `/orders/${encodeURIComponent(id)}`);
    return data.order ? normalizeOrder(data.order) : null;
  },
  getPayment: async id => {
    const data = await request('GET', `/payments/${encodeURIComponent(id)}`);
    return data.payment || null;
  },
  cancelOrder: async id => {
    const data = await request('PATCH', `/orders/${encodeURIComponent(id)}/cancel`, {});
    return data.order ? normalizeOrder(data.order) : null;
  },
  login: async data => {
    const result = await request('POST', '/auth/login', data);
    saveAuthToken(result.access_token);
    return result.user;
  },
  register: async data => {
    const result = await request('POST', '/auth/register', data);
    saveAuthToken(result.access_token);
    return result.user;
  },
  logout: async () => {
    try { await request('POST', '/auth/logout'); }
    finally { clearAuthToken(); }
  },
  getProfile: async () => {
    const data = await request('GET', '/users/me');
    return data.user || null;
  },
  updateProfile: async data => {
    const result = await request('PATCH', '/users/me', data);
    return result.user;
  },
  getAddresses: async () => (await request('GET', '/users/me/addresses')).addresses || [],
  createAddress: async data => (await request('POST', '/users/me/addresses', data)).address,
  updateAddress: async (id, data) => (await request('PATCH', `/users/me/addresses/${encodeURIComponent(id)}`, data)).address,
  deleteAddress: id => request('DELETE', `/users/me/addresses/${encodeURIComponent(id)}`),
  updatePassword: data => request('PUT', '/users/me/password', data),
  getWishlistIds: () => {
    const saved = JSON.parse(localStorage.getItem(WISHLIST_KEY) || '[]');
    if (!Array.isArray(saved)) throw new Error('Saved wishlist data is invalid. Clear the wishlist and try again.');
    return saved.map(Number).filter(id => Number.isSafeInteger(id) && id > 0);
  },
  isWishlisted: id => api.getWishlistIds().includes(Number(id)),
  toggleWishlist: id => {
    const productId = Number(id);
    const ids = api.getWishlistIds();
    const next = ids.includes(productId) ? ids.filter(savedId => savedId !== productId) : [...ids, productId];
    localStorage.setItem(WISHLIST_KEY, JSON.stringify(next));
    return next.includes(productId);
  }
};

let toastT; function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');clearTimeout(toastT);toastT=setTimeout(()=>t.classList.remove('show'),2600)}
async function partial(name){ return (await (await fetch(`${ROOT}components/${name}.html`,{cache:'no-cache'})).text()).replaceAll('{{root}}',ROOT) }
async function updateBadge(){
  const badges=[...document.querySelectorAll('[data-cart-count],#cart-count')];
  if(!badges.length)return;
  const cart=getAuthToken()?await api.getCart():[];
  const count=cart.reduce((sum,item)=>sum+Number(item.qty||0),0);
  badges.forEach(badge=>{badge.textContent=String(count)});
  $('.mobile-nav-cart')?.setAttribute('aria-label',`Cart, ${count} ${count===1?'item':'items'}`);
}
function configureMobileNavigation(){
  const path=location.pathname.toLowerCase();
  const page=path.split('/').pop();
  const active=page==='index.html'||!page?'home'
    :page==='products.html'||page==='product-details.html'?'shop'
    :page==='cart.html'||page==='checkout.html'?'cart'
    :page==='orders.html'||page==='order-details.html'?'orders'
    :page==='profile.html'||page==='login.html'||page==='register.html'?'profile':'';
  const profile=$('[data-mobile-nav="profile"]');
  if(getAuthToken()&&profile)profile.href=`${ROOT}pages/profile.html`;
  if(active){
    const activeLink=$(`[data-mobile-nav="${active}"]`);
    activeLink?.classList.add('active');
    activeLink?.setAttribute('aria-current','page');
  }
  document.body.classList.add('has-mobile-bottom-nav');
}
function configureNavbarAuthentication(){
  const authenticated=Boolean(getAuthToken());
  document.querySelectorAll('#navbar .nav-auth').forEach(link=>{
    link.textContent=authenticated?'Logout':'Log In';
    link.href=authenticated?'#':`${ROOT}pages/login.html`;
    link.setAttribute('aria-label',authenticated?'Logout':'Log In');
    if(authenticated)link.dataset.logout='';
    else delete link.dataset.logout;
  });
  const menu=$('#navbar #menu');
  if(menu){
    menu.querySelector('.menu-auth')?.remove();
    const item=document.createElement('li');
    item.className='menu-auth';
    const link=document.createElement('a');
    link.href=authenticated?'#':`${ROOT}pages/login.html`;
    link.textContent=authenticated?'Logout':'Log In';
    if(authenticated)link.dataset.logout='';
    item.append(link);
    menu.append(item);
  }
}
function requireAuth(){
  if(getAuthToken())return true;
  location.href=`${ROOT}pages/login.html?next=${encodeURIComponent(location.href)}`;
  return false;
}

let cardTpl;
async function initializeCustomerChat() {
  if (!getAuthToken()) return;
  const customer = await api.getProfile();
  if (!customer || customer.role !== 'customer') return;
  const root = document.createElement('section');
  root.className = 'customer-chat';
  root.innerHTML = '<button class="customer-chat-toggle" type="button" aria-expanded="false" aria-controls="customer-chat-panel">Chat with the farm</button><section class="customer-chat-panel" id="customer-chat-panel" hidden aria-label="Customer support chat"><header><div><strong>Farm support</strong><small>Ask about products or an order</small></div><button type="button" aria-label="Close chat" data-chat-close>×</button></header><div class="customer-chat-messages" aria-live="polite"><p class="customer-chat-empty">Loading your messages…</p></div><p class="customer-chat-error" role="alert" hidden></p><form class="customer-chat-compose"><label class="sr-only" for="customer-chat-order">Related order</label><select id="customer-chat-order" name="order_id"><option value="">General question</option></select><label class="sr-only" for="customer-chat-input">Your message</label><textarea id="customer-chat-input" name="message" rows="2" maxlength="4000" required placeholder="Write a message…"></textarea><button type="submit" aria-label="Send message">Send</button></form></section>';
  document.body.append(root);
  const panel = $('.customer-chat-panel', root);
  const toggle = $('.customer-chat-toggle', root);
  const messagesTarget = $('.customer-chat-messages', root);
  const errorTarget = $('.customer-chat-error', root);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
  const loadMessages = async () => {
    try {
      const data = await api.get('/chat/messages');
      const messages = data.messages || [];
      messagesTarget.innerHTML = messages.length ? messages.map(message =>
        `<article class="customer-chat-message${message.sender_role === 'customer' ? ' is-customer' : ''}"><p>${escape(message.body)}</p>${message.order_id ? `<small>Order #${escape(message.order_id)}</small>` : ''}<time>${escape(new Date(message.created_at).toLocaleString())}</time></article>`
      ).join('') : '<p class="customer-chat-empty">No messages yet. Send us a question and our team will reply here.</p>';
      messagesTarget.scrollTop = messagesTarget.scrollHeight;
      errorTarget.hidden = true;
    } catch (error) {
      errorTarget.textContent = error.message;
      errorTarget.hidden = false;
    }
  };
  try {
    const orders = await api.getOrders();
    $('.customer-chat-compose select', root).innerHTML = '<option value="">General question</option>' + orders.map(order =>
      `<option value="${escape(order.id)}">Order #${escape(order.id)}</option>`
    ).join('');
  } catch (error) {
    console.error('Customer orders could not be loaded for chat', error);
  }
  toggle.addEventListener('click', async () => {
    const isOpen = !panel.hidden;
    panel.hidden = isOpen;
    toggle.setAttribute('aria-expanded', String(!isOpen));
    if (!isOpen) await loadMessages();
  });
  $('[data-chat-close]', root).addEventListener('click', () => {
    panel.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  });
  $('.customer-chat-compose', root).addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const message = form.elements.message.value.trim();
    if (!message) return;
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await api.post('/chat/messages', { message, order_id: form.elements.order_id.value || null });
      form.elements.message.value = '';
      errorTarget.hidden = true;
      await loadMessages();
    } catch (error) {
      errorTarget.textContent = error.message;
      errorTarget.hidden = false;
    } finally {
      button.disabled = false;
    }
  });
  window.setInterval(() => {
    if (!panel.hidden) loadMessages();
  }, 20000);
}

async function cardHTML(p){
  cardTpl ??= await partial('product-card');
  const favorite=api.isWishlisted(p.id);
  const v={...p,root:ROOT,visual:p.image?`<img src="${p.image}" alt="">`:p.emoji,category:(await getCategories()).find(c=>c.id===p.category)?.name||'Farm fresh',priceText:peso(p.price),stockText:p.stock?'In stock':'Out of stock',stockClass:p.stock?'':'out',disabled:p.stock?'':'disabled',favorite:favorite?'true':'false',favoriteIcon:favorite?'♥':'♡'};
  return cardTpl.replace(/\{\{(\w+)\}\}/g,(_,k)=>v[k]??'');
}
document.addEventListener('click', async e => {
  const logout=e.target.closest('[data-logout]');
  if(logout){
    e.preventDefault();
    try{await api.logout()}
    catch(error){console.error('Logout failed',error);toast(error.message||'Logout failed. Please try again.')}
    location.href=`${ROOT}pages/login.html`;
    return;
  }
  const add=e.target.closest('[data-add]'); if(add){ if(!requireAuth())return; try{await api.addToCart(add.dataset.add, +(add.dataset.qty||1)); await updateBadge(); toast('Added to your cart')}catch(error){toast(error.message)} }
  const fav=e.target.closest('[data-fav]'); if(fav){ try{const saved=api.toggleWishlist(fav.dataset.fav);fav.textContent=saved?'♥':'♡';fav.setAttribute('aria-pressed',String(saved));fav.setAttribute('aria-label',`${saved?'Remove':'Add'} ${fav.closest('.pcard')?.querySelector('h3')?.textContent||'product'} ${saved?'from':'to'} wishlist`);toast(saved?'Saved to wishlist':'Removed from wishlist');document.dispatchEvent(new Event('wishlist:changed'))}catch(error){toast(error.message)} }
  if(e.target.closest('#burger')){ const m=$('#menu'), o=m.classList.toggle('open'); $('#burger').setAttribute('aria-expanded',String(o));$('#burger').setAttribute('aria-label',o?'Close navigation menu':'Open navigation menu'); }
  if(e.target.closest('#menu a')){const m=$('#menu');m.classList.remove('open');$('#burger')?.setAttribute('aria-expanded','false');$('#burger')?.setAttribute('aria-label','Open navigation menu')}
});
(async()=>{ try{$('#navbar').innerHTML=await partial('navbar');$('#footer').innerHTML=await partial('footer');const nav=$('#navbar .nav');const updateNav=()=>nav?.classList.toggle('is-scrolled',window.scrollY>4);window.addEventListener('scroll',updateNav,{passive:true});updateNav();configureNavbarAuthentication();configureMobileNavigation();document.dispatchEvent(new Event('shell:ready'));updateBadge().catch(error=>console.error('Cart quantity could not be refreshed',error));initializeCustomerChat().catch(error=>console.error('Customer support chat could not be initialized',error))}catch(error){console.error('Page shell failed to load',error)} })();
