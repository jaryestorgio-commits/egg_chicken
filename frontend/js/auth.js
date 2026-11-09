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
let accountOrders = null;
let accountWishlistProducts = [];
let accountAddressesLoaded = false;
let accountWishlistLoaded = false;
let accountNotificationPreferencesLoaded = false;

function showAccountMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle('error', isError);
}

function renderAccountOrders(target, orders, mode) {
  if (!orders.length) {
    const emptyTitle = mode === 'tracking' ? 'No orders to track yet' : 'No orders yet';
    target.innerHTML = `<div class="account-empty card"><span aria-hidden="true">🥚</span><h3>${emptyTitle}</h3><p>Your orders will appear here after checkout.</p><a class="btn btn-primary btn-sm" href="${ROOT}pages/products.html">Browse the shop</a></div>`;
    return;
  }
  const displayedOrders = mode === 'dashboard' || mode === 'tracking' ? orders.slice(0, 3) : orders;
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

function updateDashboardStats() {
  const total = $('#stat-total-orders');
  const pending = $('#stat-pending-orders');
  const completed = $('#stat-completed-orders');
  const wishlist = $('#stat-wishlist-items');
  if (total) total.textContent = accountOrders ? String(accountOrders.length) : '—';
  if (pending) pending.textContent = accountOrders
    ? String(accountOrders.filter(order => ['pending', 'confirmed', 'processing', 'shipped', 'out_for_delivery'].includes(String(order.status || '').toLowerCase())).length)
    : '—';
  if (completed) completed.textContent = accountOrders
    ? String(accountOrders.filter(order => ['delivered', 'completed'].includes(String(order.status || '').toLowerCase())).length)
    : '—';
  if (wishlist) wishlist.textContent = accountWishlistLoaded ? String(accountWishlistProducts.length) : '—';
}

async function loadAccountOrders() {
  const targets = [
    ['#dashboard-orders', 'dashboard'],
    ['#dashboard-tracking', 'tracking'],
    ['#all-orders', 'orders'],
    ['#tracking-orders', 'tracking']
  ];
  targets.forEach(([selector]) => { const target = $(selector); if (target) target.innerHTML = '<div class="account-loading" role="status">Loading your orders…</div>'; });
  try {
    accountOrders = await api.getOrders();
    targets.forEach(([selector, mode]) => { const target = $(selector); if (target) renderAccountOrders(target, accountOrders, mode); });
    updateDashboardStats();
  } catch (error) {
    targets.forEach(([selector]) => {
      const target = $(selector);
      if (target) target.innerHTML = `<div class="account-empty card"><h3>Couldn't load orders</h3><p>${accountEscape(error.message)}</p><button class="btn btn-outline btn-sm" type="button" data-account-retry="orders">Try again</button></div>`;
    });
    accountOrders = null;
    updateDashboardStats();
  }
}

async function loadAccountWishlist() {
  const target = $('#wishlist-items');
  if (target) target.innerHTML = '<div class="account-loading" role="status">Loading your saved products…</div>';
  const dashboardTarget = $('#dashboard-wishlist');
  if (dashboardTarget) dashboardTarget.innerHTML = '<div class="account-loading" role="status">Loading saved products…</div>';
  try {
    const savedIds = api.getWishlistIds();
    if (!savedIds.length) {
      accountWishlistProducts = [];
      accountWishlistLoaded = true;
      if (target) target.innerHTML = '<div class="account-empty card"><span aria-hidden="true">♡</span><h3>Your wishlist is waiting</h3><p>Save products from the shop and they will show up here.</p><a class="btn btn-primary btn-sm" href="../pages/products.html">Explore products</a></div>';
      if (dashboardTarget) dashboardTarget.innerHTML = '<div class="account-empty card"><h3>No saved products yet</h3><p>Save favorites from the shop to find them here.</p></div>';
      updateDashboardStats();
      return;
    }
    const products = await api.getProducts();
    const savedProducts = products.filter(product => savedIds.includes(Number(product.id)));
    accountWishlistProducts = savedProducts;
    accountWishlistLoaded = true;
    if (target) target.innerHTML = savedProducts.length
      ? (await Promise.all(savedProducts.map(cardHTML))).join('')
      : '<div class="account-empty card"><h3>Saved products are no longer available</h3><p>Browse the shop to find something fresh to save.</p><a class="btn btn-primary btn-sm" href="../pages/products.html">Explore products</a></div>';
    if (dashboardTarget) dashboardTarget.innerHTML = savedProducts.length
      ? (await Promise.all(savedProducts.slice(0, 2).map(cardHTML))).join('')
      : '<div class="account-empty card"><h3>Saved products are no longer available</h3><p>Browse the shop to find something fresh to save.</p></div>';
    updateDashboardStats();
  } catch (error) {
    accountWishlistLoaded = false;
    accountWishlistProducts = [];
    if (target) target.innerHTML = `<div class="account-empty card"><h3>Couldn't load your wishlist</h3><p>${accountEscape(error.message)}</p><button class="btn btn-outline btn-sm" type="button" data-account-retry="wishlist">Try again</button></div>`;
    if (dashboardTarget) dashboardTarget.innerHTML = `<div class="account-empty card"><h3>Couldn't load your wishlist</h3><p>${accountEscape(error.message)}</p></div>`;
    updateDashboardStats();
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
  const dashboardTarget = $('#dashboard-addresses');
  if (target) target.innerHTML = '<div class="account-loading" role="status">Loading your addresses…</div>';
  if (dashboardTarget) dashboardTarget.innerHTML = '<div class="account-loading" role="status">Loading your addresses…</div>';
  try {
    const addresses = await api.getAddresses();
    accountAddressesLoaded = true;
    if (target) target.innerHTML = addresses.length ? addresses.map(address => `<article class="card address-card">
      <form class="address-edit-form" data-address-id="${accountEscape(address.id)}">
        <div class="address-heading"><h3>Saved address</h3>${address.is_default ? '<span class="account-status status-default">Default</span>' : ''}</div>
        ${addressFields(address)}
        <p class="account-message error" role="alert"></p>
        <div class="account-form-actions"><button class="btn btn-outline btn-sm" type="submit">Save address</button><button class="address-delete" type="button" data-delete-address="${accountEscape(address.id)}">Remove</button></div>
      </form>
    </article>`).join('') : '<div class="account-empty card"><h3>No saved addresses</h3><p>Add a delivery address to make checkout quicker.</p></div>';
    if (dashboardTarget) dashboardTarget.innerHTML = addresses.length ? addresses.slice(0, 2).map(address => `<article class="card dashboard-address-card">
      <span class="dashboard-address-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0z"/><circle cx="12" cy="10" r="2.5"/></svg></span>
      <div><div class="address-heading"><h4>${accountEscape(address.full_name)}</h4>${address.is_default ? '<span class="account-status status-default">Default</span>' : ''}</div><p>${accountEscape(address.address_line)}, ${accountEscape(address.city)}, ${accountEscape(address.province)} ${accountEscape(address.postal_code)}</p><small>${accountEscape(address.phone)}</small></div>
    </article>`).join('') : '<div class="account-empty card"><h3>No saved addresses</h3><p>Add a delivery address to make checkout quicker.</p></div>';
  } catch (error) {
    accountAddressesLoaded = false;
    if (target) target.innerHTML = `<div class="account-empty card"><h3>Couldn't load your addresses</h3><p>${accountEscape(error.message)}</p><button class="btn btn-outline btn-sm" type="button" data-account-retry="addresses">Try again</button></div>`;
    if (dashboardTarget) dashboardTarget.innerHTML = `<div class="account-empty card"><h3>Couldn't load your addresses</h3><p>${accountEscape(error.message)}</p></div>`;
  }
}

async function loadNotificationPreferences() {
  const loading = $('#notification-loading');
  const loadError = $('#notification-load-error');
  const options = $('#notification-options');
  loading.hidden = false;
  loading.textContent = 'Loading your preferences…';
  loadError.hidden = true;
  options.hidden = true;
  try {
    const preferences = await api.getNotificationPreferences();
    Object.entries(preferences).forEach(([name, value]) => {
      const input = $('#notification-form').elements.namedItem(name);
      if (input) input.checked = value;
    });
    accountNotificationPreferencesLoaded = true;
    loading.hidden = true;
    options.hidden = false;
  } catch (error) {
    accountNotificationPreferencesLoaded = false;
    loading.hidden = true;
    loadError.innerHTML = `${accountEscape(error.message)} <button class="btn btn-outline btn-sm" type="button" data-account-retry="notifications">Try again</button>`;
    loadError.hidden = false;
  }
}

async function initProfile(){
  if(!requireAuth())return;
  const nav = $('.account-nav');
  const navMedia = window.matchMedia('(min-width: 761px)');
  const syncAccountNav = () => { nav.open = navMedia.matches; };
  syncAccountNav();
  navMedia.addEventListener('change', syncAccountNav);

  const requestedView = new URLSearchParams(location.search).get('view');
  const availableViews = new Set(['dashboard', 'profile-details', 'orders', 'tracking', 'wishlist', 'addresses', 'payment-methods', 'notifications', 'settings']);
  const initialView = availableViews.has(requestedView) ? requestedView : 'dashboard';
  const hideAccountPageHeading = () => { $('.account-heading').hidden = true; };
  hideAccountPageHeading();
  document.querySelectorAll('.account-view').forEach(view => { view.hidden = view.dataset.view !== initialView; });
  document.querySelectorAll('.side [data-account-view]').forEach(button => button.classList.toggle('on', button.dataset.accountView === initialView));

  const viewHeadings = {
    dashboard: ['Your Activity', 'Recent orders, delivery updates, and saved items from your account.'],
    'profile-details': ['Profile Details', 'Review and update the details connected to your account.'],
    orders: ['My Orders', 'Review your customer order history.'],
    tracking: ['Order Tracking', 'Follow the latest status of your orders.'],
    wishlist: ['Wishlist', 'Find the products you have saved for later.'],
    addresses: ['Delivery Addresses', 'Manage the delivery addresses saved to your account.'],
    'payment-methods': ['Payment Methods', 'Review how payment information is handled at checkout.'],
    notifications: ['Notification Preferences', 'Choose which email and SMS updates you receive.'],
    settings: ['Settings', 'Manage the account and app settings currently available to you.']
  };
  const initialHeading = viewHeadings[initialView];
  $('#account-page-title').textContent = initialHeading[0];
  $('#account-page-description').textContent = initialHeading[1];
  document.title = `${initialHeading[0]} | Egg & Chicken`;
  document.querySelectorAll('[data-account-view]').forEach(button => {
    button.addEventListener('click', () => {
      const viewName = button.dataset.accountView;
      hideAccountPageHeading();
      document.querySelectorAll('.account-view').forEach(view => { view.hidden = view.dataset.view !== viewName; });
      document.querySelectorAll('.side [data-account-view]').forEach(link => link.classList.toggle('on', link.dataset.accountView === viewName));
      const heading = viewHeadings[viewName];
      if (heading) {
        $('#account-page-title').textContent = heading[0];
        $('#account-page-description').textContent = heading[1];
        document.title = `${heading[0]} | Egg & Chicken`;
      }
      const viewQuery = viewName === 'dashboard' ? '' : `?view=${encodeURIComponent(viewName)}`;
      history.replaceState(null, '', `${location.pathname}${viewQuery}`);
      document.querySelectorAll('.mobile-nav-item').forEach(link => {
        link.classList.remove('active');
        link.removeAttribute('aria-current');
      });
      const mobileView = $(`[data-mobile-nav="${viewName === 'profile-details' ? 'profile' : 'dashboard'}"]`);
      mobileView?.classList.add('active');
      mobileView?.setAttribute('aria-current', 'page');
      if (!navMedia.matches) nav.open = false;
      if (viewName === 'addresses' && !accountAddressesLoaded) loadAccountAddresses();
      if (viewName === 'notifications' && !accountNotificationPreferencesLoaded) loadNotificationPreferences();
      if (viewName === 'wishlist' || viewName === 'dashboard') loadAccountWishlist();
      if (button.dataset.settingsFocus) {
        const target = $(`#${button.dataset.settingsFocus}`);
        target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        $('#current-password').focus({ preventScroll: true });
      }
    });
  });
  if (initialView === 'notifications') loadNotificationPreferences();

  const accountError = $('#account-error');
  const detailList = $('.profile-detail-list');
  const editProfileButton = $('#edit-profile');
  const profileForm = $('#profile-form');
  let accountUser = null;
  const setProfileEditing = editing => {
    profileForm.hidden = !editing;
    detailList.hidden = editing;
    editProfileButton.hidden = editing;
    if (editing) $('#profile-name').focus();
  };
  const displayProfile = user => {
    accountUser = user;
    const nameParts = String(user.name || '').trim().split(/\s+/).filter(Boolean);
    const initials = nameParts.slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'EC';
    $('#account-name').textContent = user.name || 'Customer';
    $('#account-email').textContent = user.email || '';
    $('#account-role').textContent = String(user.role || 'customer').replace(/^\w/, letter => letter.toUpperCase());
    $('#profile-name').value = user.name || '';
    $('#profile-email').value = user.email || '';
    $('#profile-phone').value = user.phone || '';
    $('#profile-birthday').value = user.birthday || '';
    $('#profile-first-name').textContent = nameParts[0] || '—';
    $('#profile-last-name').textContent = nameParts.slice(1).join(' ') || '—';
    $('#profile-email-value').textContent = user.email || '—';
    $('#profile-phone-value').textContent = user.phone || 'Not provided';
    const birthday = user.birthday ? new Date(`${user.birthday}T00:00:00`) : null;
    $('#profile-birthday-value').textContent = birthday && !Number.isNaN(birthday.getTime())
      ? new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'long', day: 'numeric' }).format(birthday)
      : 'Not provided';
    const age = birthday && !Number.isNaN(birthday.getTime())
      ? (() => {
        const today = new Date();
        let years = today.getFullYear() - birthday.getFullYear();
        if (today.getMonth() < birthday.getMonth() || (today.getMonth() === birthday.getMonth() && today.getDate() < birthday.getDate())) years--;
        return years;
      })()
      : null;
    $('#profile-age-value').textContent = age === null ? 'Not available' : String(age);
    $('#profile-gender-value').textContent = user.gender || 'Not provided';
    $('#profile-role-value').textContent = String(user.role || 'customer').replace(/^\w/, letter => letter.toUpperCase());
    const joined = user.created_at ? new Date(user.created_at) : null;
    $('#profile-joined-value').textContent = joined && !Number.isNaN(joined.getTime())
      ? new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'long', day: 'numeric' }).format(joined)
      : 'Not available';
    $('#account-avatar').textContent = initials;
    $('#profile-photo-input').dataset.userId = String(user.id);
    const photo = $('#account-avatar-image');
    try {
      const savedPhoto = localStorage.getItem(`ec_profile_avatar_${user.id}`);
      photo.hidden = !savedPhoto;
      if (savedPhoto) photo.src = savedPhoto;
    } catch (error) {
      console.error('Customer profile picture could not be loaded', error);
    }
  };
  try {
    const user = await api.getProfile();
    if (!user) { location.href = 'login.html'; return; }
    displayProfile(user);
    $('#profile-photo-error').hidden = true;
  } catch (error) {
    accountError.hidden = false;
    accountError.innerHTML = `<strong>Couldn't load your account.</strong> ${accountEscape(error.message)} <button type="button" class="btn btn-outline btn-sm" id="retry-account">Try again</button>`;
    $('#retry-account').onclick = () => location.reload();
  }
  loadAccountOrders();
  loadAccountWishlist();
  loadAccountAddresses();

  $('#change-profile-photo').addEventListener('click', () => $('#profile-photo-input').click());
  $('#profile-photo-input').addEventListener('change', event => {
    const photoInput = event.currentTarget;
    const file = photoInput.files[0];
    const errorText = $('#profile-photo-error');
    errorText.hidden = true;
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
      errorText.textContent = 'Choose a JPEG, PNG, WebP, or GIF image.';
      errorText.hidden = false;
      photoInput.value = '';
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      errorText.textContent = 'Choose an image smaller than 2 MB.';
      errorText.hidden = false;
      photoInput.value = '';
      return;
    }
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      try {
        const userId = photoInput.dataset.userId;
        if (!userId) throw new Error('Your account could not be identified.');
        localStorage.setItem(`ec_profile_avatar_${userId}`, reader.result);
        const photo = $('#account-avatar-image');
        photo.src = reader.result;
        photo.hidden = false;
      } catch (error) {
        errorText.textContent = `The profile picture could not be saved on this device. ${error.message}`;
        errorText.hidden = false;
      }
    });
    reader.addEventListener('error', () => {
      errorText.textContent = 'The selected image could not be read. Choose another image.';
      errorText.hidden = false;
    });
    reader.readAsDataURL(file);
  });
  editProfileButton.addEventListener('click', () => setProfileEditing(true));
  $('#cancel-profile-edit').addEventListener('click', () => {
    if (accountUser) displayProfile(accountUser);
    $('#profile-error').textContent = '';
    setProfileEditing(false);
  });

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
      displayProfile(updated);
      setProfileEditing(false);
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

  $('#notification-form').onsubmit = async event => {
    event.preventDefault();
    if (!accountNotificationPreferencesLoaded) return;
    const form = event.currentTarget;
    const errorText = $('#notification-error');
    const status = $('#notification-status');
    const submit = form.querySelector('[type="submit"]');
    errorText.textContent = '';
    status.textContent = '';
    const preferences = Object.fromEntries(
      [...form.querySelectorAll('input[type="checkbox"][name]')].map(input => [input.name, input.checked])
    );
    submit.disabled = true;
    submit.textContent = 'Saving…';
    try {
      await api.updateNotificationPreferences(preferences);
      showAccountMessage(status, 'Your notification preferences have been saved.');
      toast('Preferences saved');
    } catch (error) {
      showAccountMessage(errorText, accountErrorMessage(error), true);
    } finally {
      submit.disabled = false;
      submit.textContent = 'Save preferences';
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
    if (retry?.dataset.accountRetry === 'notifications') loadNotificationPreferences();
  });
  document.addEventListener('wishlist:changed', () => {
    loadAccountWishlist();
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
