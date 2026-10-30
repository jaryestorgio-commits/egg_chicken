const ADMIN_API_BASE = window.EC_API_BASE_URL || 'http://127.0.0.1:5000/api/v1';
const ADMIN_TOKEN_KEY = 'ec_access_token';
const ORDER_STATUSES = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'];
const LOW_STOCK_LIMIT = 10;
const PAGE_SIZE = 10;
const adminPage = document.body.dataset.adminPage;
const adminState = { products: [], categories: [], orders: [], users: [], inventory: [], profile: null, report: null };
const adminPages = { products: 1, orders: 1, inventory: 1, customers: 1 };
let activeConversationId = null;
let loadedOrderCustomerId = null;
let notificationRefreshTimer;
let conversationRefreshTimer;
let customersLoadSequence = 0;
const adminQuery = selector => document.querySelector(selector);
const getAdminToken = () => localStorage.getItem(ADMIN_TOKEN_KEY) || sessionStorage.getItem(ADMIN_TOKEN_KEY);
const clearAdminToken = () => { localStorage.removeItem(ADMIN_TOKEN_KEY); sessionStorage.removeItem(ADMIN_TOKEN_KEY); };
const adminMoney = value => '₱' + Number(value || 0).toFixed(2);
const adminEscape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const adminDate = value => value ? new Date(value).toLocaleDateString() : '—';
const adminDateTime = value => value ? new Date(value).toLocaleString() : '';
const adminIsoDate = value => {
	const date = new Date(value);
	return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
};

function adminIconSvg(name) {
	const paths = {
		'dashboard.html': '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
		'products.html': '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4.5 7.7 7.5 4.4 7.5-4.4M12 12v9"/>',
		'inventory.html': '<path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z"/><path d="m4 12 8 4.5 8-4.5M4 16.5 12 21l8-4.5"/>',
		'orders.html': '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
		'customers.html': '<path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
		'reports.html': '<path d="M4 19V5M4 19h17"/><path d="m7 15 4-4 3 2 6-7"/>',
		'messages.html': '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8A8.5 8.5 0 0 1 8.7 3.9a8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
		'account.html': '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1-.1 2Z"/>',
		'notification': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>'
	};
	return `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ''}</svg>`;
}

function setupAdminCommunication() {
	const sidebar = adminQuery('.admin-nav');
	if (sidebar && !sidebar.querySelector('a[href="messages.html"]')) {
		const link = document.createElement('a');
		link.href = 'messages.html';
		link.textContent = 'Messages';
		if (adminPage === 'messages') link.classList.add('active');
		sidebar.append(link);
	}
	sidebar?.querySelectorAll('a[href]').forEach(link => {
		if (!link.querySelector('.admin-nav-icon')) {
			const icon = document.createElement('span');
			icon.className = 'admin-nav-icon';
			icon.setAttribute('aria-hidden', 'true');
			icon.innerHTML = adminIconSvg(link.getAttribute('href').split('?')[0]);
			link.prepend(icon);
		}
	});
	let actions = adminQuery('.admin-topbar .admin-actions');
	if (!actions) {
		actions = document.createElement('div');
		actions.className = 'admin-actions';
		const greeting = adminQuery('.admin-topbar [data-admin-greeting]');
		if (greeting) actions.append(greeting);
		adminQuery('.admin-topbar')?.append(actions);
	}
	const notifications = document.createElement('div');
	notifications.className = 'admin-notification-control';
	notifications.innerHTML = `<button class="admin-notification-toggle" type="button" aria-label="Notifications" aria-expanded="false" data-notification-toggle>${adminIconSvg('notification')}<span class="admin-notification-count" data-notification-count hidden></span></button><section class="admin-notification-panel" data-notification-panel hidden><header><strong>Notifications</strong><button type="button" class="admin-link-button" data-notifications-read-all>Mark all read</button></header><div data-notification-list><p class="admin-empty">Loading notifications…</p></div></section>`;
	actions?.prepend(notifications);
	loadAdminNotifications().catch(error => showAdminError(error.message));
	notificationRefreshTimer = window.setInterval(() => {
		loadAdminNotifications().catch(error => console.error('Admin notifications could not be refreshed', error));
	}, 30000);
	if (adminPage === 'messages') {
		loadAdminConversations().catch(error => showAdminError(error.message));
		const customerId = Number(new URLSearchParams(location.search).get('customer'));
		if (Number.isSafeInteger(customerId) && customerId > 0) {
			openAdminConversation(customerId).catch(error => showAdminError(error.message));
		}
		conversationRefreshTimer = window.setInterval(() => {
			loadAdminConversations().catch(error => console.error('Admin conversations could not be refreshed', error));
			if (activeConversationId) loadAdminConversation(activeConversationId).catch(error => console.error('Admin messages could not be refreshed', error));
		}, 20000);
	}
}

async function loadAdminNotifications() {
	const data = await adminRequest('/admin/notifications');
	const count = Number(data.unread_count || 0);
	const badge = adminQuery('[data-notification-count]');
	if (badge) {
		badge.textContent = count > 99 ? '99+' : String(count);
		badge.hidden = count === 0;
	}
	const list = adminQuery('[data-notification-list]');
	if (!list) return;
	const items = data.notifications || [];
	list.innerHTML = items.length ? items.map(item =>
		`<a class="admin-notification-item${item.is_read ? '' : ' is-unread'}" href="${adminEscape(item.href)}" data-notification-id="${adminEscape(item.id)}"><span class="admin-notification-dot" aria-hidden="true"></span><span><strong>${adminEscape(item.title)}</strong><small>${adminEscape(item.message)}</small><time>${adminEscape(adminDateTime(item.created_at))}</time></span></a>`
	).join('') : '<p class="admin-empty">No notifications yet.</p>';
}

async function loadAdminConversations() {
	const data = await adminRequest('/admin/chat/conversations');
	const target = adminQuery('#admin-conversation-list');
	if (!target) return;
	const conversations = data.conversations || [];
	if (!conversations.length) {
		target.innerHTML = '<p class="admin-empty">No customer messages yet.</p>';
		return;
	}
	target.innerHTML = conversations.map(item =>
		`<button class="admin-conversation${Number(activeConversationId) === item.customer_id ? ' is-active' : ''}" type="button" data-conversation-id="${adminEscape(item.customer_id)}"><span class="admin-conversation-name">${adminEscape(item.customer_name)}</span><small>${adminEscape(item.latest_message.body)}</small><span class="admin-conversation-meta"><time>${adminEscape(adminDateTime(item.latest_message.created_at))}</time>${item.unread_count ? `<b>${adminEscape(item.unread_count)}</b>` : ''}</span></button>`
	).join('');
}

async function openAdminConversation(customerId) {
	activeConversationId = customerId;
	const url = new URL(location.href);
	url.searchParams.set('customer', String(customerId));
	history.replaceState(null, '', url);
	await loadAdminConversation(customerId);
	await loadAdminConversations();
}

async function loadAdminConversation(customerId) {
	const data = await adminRequest(`/admin/chat/conversations/${customerId}/messages`);
	const heading = adminQuery('#admin-chat-heading');
	const target = adminQuery('#admin-chat-messages');
	const form = adminQuery('#admin-chat-form');
	if (!heading || !target || !form) return;
	heading.innerHTML = `<h2>${adminEscape(data.customer.name)}</h2><p>${adminEscape(data.customer.email)}</p>`;
	const messages = data.messages || [];
	target.innerHTML = messages.length ? messages.map(message =>
		`<article class="admin-chat-bubble${message.sender_role === 'admin' ? ' is-admin' : ''}"><p>${adminEscape(message.body)}</p>${message.order_id ? `<small>Order #${adminEscape(message.order_id)}</small>` : ''}<time>${adminEscape(adminDateTime(message.created_at))}</time></article>`
	).join('') : '<p class="admin-empty">Start the conversation by replying below.</p>';
	form.hidden = false;
	const orderSelect = adminQuery('#admin-chat-order');
	if (loadedOrderCustomerId !== customerId) {
		const orderData = await adminRequest(`/admin/users/${customerId}/orders`);
		orderSelect.innerHTML = '<option value="">No order attached</option>' + (orderData.orders || []).map(order =>
			`<option value="${adminEscape(order.id)}">Order #${adminEscape(order.id)} · ${adminEscape(order.status)}</option>`
		).join('');
		loadedOrderCustomerId = customerId;
	}
	target.scrollTop = target.scrollHeight;
}

async function sendAdminMessage(event) {
	event.preventDefault();
	if (!activeConversationId) return;
	const form = event.currentTarget;
	const message = form.elements.message.value.trim();
	if (!message) return;
	const button = form.querySelector('[type="submit"]');
	button.disabled = true;
	try {
		await adminRequest(`/admin/chat/conversations/${activeConversationId}/messages`, 'POST', {
			message,
			order_id: form.elements.order_id.value || null
		});
		form.elements.message.value = '';
		await loadAdminConversation(activeConversationId);
		await loadAdminConversations();
		await loadAdminNotifications();
	} catch (error) {
		showAdminError(error.message);
	} finally {
		button.disabled = false;
	}
}

async function adminRequest(path, method = 'GET', body) {
	const token = getAdminToken();
	const headers = { Accept: 'application/json' };
	if (token) headers.Authorization = `Bearer ${token}`;
	if (body !== undefined) headers['Content-Type'] = 'application/json';
	let response;
	try {
		response = await fetch(`${ADMIN_API_BASE}${path}`, {
			method,
			headers,
			body: body === undefined ? undefined : JSON.stringify(body)
		});
	} catch {
		throw new Error('Could not reach the store API. Check that the backend is running.');
	}
	const payload = await response.json().catch(() => ({}));
	if (!response.ok || payload.success === false) {
		const error = new Error(payload.message || `Request failed (${response.status})`);
		error.status = response.status;
		error.errors = payload.errors;
		throw error;
	}
	return payload.data ?? payload;
}

function showAdminError(message) {
	const alert = adminQuery('#admin-error');
	if (!alert) return;
	alert.textContent = message;
	alert.hidden = !message;
}

function showAdminToast(message) {
	const toast = adminQuery('#admin-toast');
	if (!toast) return;
	toast.textContent = message;
	toast.classList.add('visible');
	window.clearTimeout(showAdminToast.timeout);
	showAdminToast.timeout = window.setTimeout(() => {
		toast.classList.remove('visible');
	}, 3200);
}

function adminEmptyRow(columns, message) {
	return `<tr><td colspan="${columns}" class="admin-empty">${adminEscape(message)}</td></tr>`;
}

function statusPill(status) {
	const value = String(status || 'unknown').toLowerCase();
	const className = value.replace(/[^a-z0-9_-]/g, '-');
	return `<span class="admin-status ${adminEscape(className)}">${adminEscape(value.replaceAll('_', ' '))}</span>`;
}

function adminSafeImageUrl(value) {
	if (!value) return '';
	try {
		const url = new URL(value, location.href);
		return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
	} catch {
		return '';
	}
}

function adminProductImage(product) {
	const url = adminSafeImageUrl(product.image_url);
	return url
		? `<img class="admin-product-image" src="${adminEscape(url)}" alt="" loading="lazy">`
		: '<span class="admin-product-image admin-product-placeholder" aria-hidden="true">🥚</span>';
}

function renderPagination(target, page, total, kind) {
	if (!target) return;
	const pageCount = Math.ceil(total / PAGE_SIZE);
	if (pageCount <= 1) {
		target.innerHTML = `<span>${total} ${total === 1 ? 'record' : 'records'}</span>`;
		return;
	}
	target.innerHTML = `<span>${total} records</span><div class="admin-page-controls"><button class="btn btn-outline btn-sm" type="button" data-page-kind="${kind}" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>Previous</button><span>Page ${page} of ${pageCount}</span><button class="btn btn-outline btn-sm" type="button" data-page-kind="${kind}" data-page="${page + 1}" ${page >= pageCount ? 'disabled' : ''}>Next</button></div>`;
}

function slicePage(records, page) {
	return records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
}

async function loadDashboard() {
	const today = new Date();
	const weekStart = new Date(today);
	weekStart.setDate(today.getDate() - 6);
	const params = new URLSearchParams({
		start_date: adminIsoDate(weekStart),
		end_date: adminIsoDate(today)
	});
	const [stats, report] = await Promise.all([
		adminRequest('/admin/dashboard'),
		adminRequest(`/admin/reports?${params}`)
	]);
	const metricItems = [
		['Paid revenue', adminMoney(stats.total_sales), 'Collected payments'],
		['Total orders', stats.total_orders, 'All order records'],
		['Active customers', stats.active_customers, 'Ordered in the past 30 days'],
		['Products', stats.total_products, 'Catalog items'],
		['Low stock', stats.low_stock_products, `At or below ${LOW_STOCK_LIMIT} units`, 'inventory.html'],
		['Pending orders', stats.pending_orders, 'Awaiting confirmation', 'orders.html']
	];
	adminQuery('#admin-stats').innerHTML = metricItems.map(([label, value, caption, href]) =>
		`<article class="admin-stat"><span class="admin-stat-icon" aria-hidden="true">${adminIconSvg(label === 'Paid revenue' ? 'reports.html' : label === 'Total orders' || label === 'Pending orders' ? 'orders.html' : label === 'Customers' ? 'customers.html' : label === 'Products' ? 'products.html' : 'inventory.html')}</span><span>${adminEscape(label)}</span><strong>${adminEscape(value)}</strong><small>${href ? `<a href="${href}">${adminEscape(caption)} →</a>` : adminEscape(caption)}</small></article>`
	).join('');
	const statuses = stats.order_statuses || {};
	adminQuery('#dashboard-statuses').innerHTML = ORDER_STATUSES.map(status =>
		`<a class="admin-status-card" href="orders.html?status=${encodeURIComponent(status)}"><span>${statusPill(status)}</span><strong>${adminEscape(statuses[status] ?? 0)}</strong></a>`
	).join('');
	const orders = stats.recent_orders || [];
	adminQuery('#dashboard-orders').innerHTML = orders.length ? orders.map(order =>
		`<tr><td><button class="admin-link-button" type="button" data-order-details="${adminEscape(order.id)}">#${adminEscape(order.id)}</button></td><td>${adminEscape(order.customer?.name || `Customer #${order.user_id}`)}<small>${adminEscape(order.customer?.email || '')}</small></td><td>${adminEscape(adminDate(order.created_at))}</td><td>${statusPill(order.status)}</td><td>${adminMoney(order.total_amount)}</td><td>${adminEscape(order.payments?.map(payment => payment.payment_status).join(', ') || 'Not recorded')}</td></tr>`
	).join('') : adminEmptyRow(6, 'No orders yet.');
	adminQuery('#dashboard-revenue').textContent = adminMoney(report.summary.revenue);
	renderSalesChart(adminQuery('#dashboard-sales-chart'), report.sales_by_day || []);
	renderTopProducts(adminQuery('#dashboard-top-products'), report.top_products || []);
}

function renderSalesChart(target, sales) {
	if (!target) return;
	if (!sales.length) {
		target.innerHTML = '<p class="admin-empty">No sales data is available for this date range.</p>';
		return;
	}
	const width = 720;
	const height = 250;
	const left = 44;
	const right = 12;
	const top = 14;
	const bottom = 34;
	const plotWidth = width - left - right;
	const plotHeight = height - top - bottom;
	const values = sales.map(item => Math.max(0, Number(item.revenue) || 0));
	const maxValue = Math.max(...values, 1);
	const points = values.map((value, index) => {
		const x = left + index * plotWidth / Math.max(values.length - 1, 1);
		const y = top + plotHeight - value / maxValue * plotHeight;
		return { x, y, value, date: sales[index].date };
	});
	const line = points.map((point, index) => `${index ? 'L' : 'M'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');
	const area = `${line} L${points[points.length - 1].x.toFixed(1)} ${top + plotHeight} L${points[0].x.toFixed(1)} ${top + plotHeight} Z`;
	const grid = Array.from({ length: 5 }, (_, index) => {
		const y = top + plotHeight - index * plotHeight / 4;
		const label = maxValue * index / 4;
		return `<line class="admin-chart-grid" x1="${left}" y1="${y.toFixed(1)}" x2="${width - right}" y2="${y.toFixed(1)}"/><text class="admin-chart-axis" x="${left - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end">${adminEscape(adminMoney(label))}</text>`;
	}).join('');
	const labelCount = Math.min(5, points.length);
	const labels = Array.from({ length: labelCount }, (_, index) => {
		const point = points[Math.round(index * (points.length - 1) / Math.max(labelCount - 1, 1))];
		const labelDate = new Date(`${point.date}T00:00:00`);
		const label = labelDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
		return `<text class="admin-chart-axis" x="${point.x.toFixed(1)}" y="${height - 8}" text-anchor="middle">${adminEscape(label)}</text>`;
	}).join('');
	const markers = points.map(point =>
		`<circle class="admin-chart-point" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3"><title>${adminEscape(point.date)}: ${adminEscape(adminMoney(point.value))}</title></circle>`
	).join('');
	target.innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true"><defs><linearGradient id="admin-chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#0d9b68" stop-opacity=".2"/><stop offset="100%" stop-color="#0d9b68" stop-opacity="0"/></linearGradient></defs>${grid}<path class="admin-chart-area" d="${area}"/><path class="admin-chart-line" d="${line}"/>${markers}${labels}</svg>`;
}

function renderTopProducts(target, products) {
	if (!target) return;
	target.innerHTML = products.length ? products.map(product =>
		`<article class="admin-top-product">${adminProductImage(product)}<span><b>${adminEscape(product.name)}</b><small>${adminEscape(product.units_sold)} units sold</small></span><strong>${adminMoney(product.sales)}</strong></article>`
	).join('') : '<p class="admin-empty">No product sales in this period.</p>';
}

function renderReports(report) {
	adminState.report = report;
	const startInput = adminQuery('#reports-start');
	const endInput = adminQuery('#reports-end');
	if (startInput) startInput.value = report.start_date;
	if (endInput) endInput.value = report.end_date;
	adminQuery('#reports-range-caption').textContent = `Showing activity from ${adminDate(report.start_date)} to ${adminDate(report.end_date)}. Revenue includes paid payments only.`;
	const summaryItems = [
		['Paid revenue', adminMoney(report.summary.revenue), 'Payments recorded as paid'],
		['Orders', report.summary.orders, 'Orders placed in this period'],
		['Average paid order', adminMoney(report.summary.average_paid_order), `${report.summary.paid_orders} paid orders`],
		['Customers', report.summary.customers, 'Unique customers who ordered']
	];
	adminQuery('#reports-stats').innerHTML = summaryItems.map(([label, value, caption]) =>
		`<article class="admin-stat"><span>${adminEscape(label)}</span><strong>${adminEscape(value)}</strong><small>${adminEscape(caption)}</small></article>`
	).join('');
	renderSalesChart(adminQuery('#reports-sales-chart'), report.sales_by_day || []);
	const statuses = report.order_statuses || {};
	adminQuery('#reports-order-statuses').innerHTML = ORDER_STATUSES.map(status =>
		`<div class="admin-status-card"><span>${statusPill(status)}</span><strong>${adminEscape(statuses[status] ?? 0)}</strong></div>`
	).join('');
	const products = report.top_products || [];
	adminQuery('#reports-product-rows').innerHTML = products.length ? products.map(product =>
		`<tr><td><div class="admin-product-cell">${adminProductImage(product)}<span><b>${adminEscape(product.name)}</b><small>#${adminEscape(product.id)}</small></span></div></td><td>${adminEscape(product.units_sold)}</td><td>${adminMoney(product.sales)}</td></tr>`
	).join('') : adminEmptyRow(3, 'No product sales in this period.');
}

async function loadReports() {
	const startDate = adminQuery('#reports-start').value;
	const endDate = adminQuery('#reports-end').value;
	const params = new URLSearchParams();
	if (startDate) params.set('start_date', startDate);
	if (endDate) params.set('end_date', endDate);
	const data = await adminRequest(`/admin/reports?${params}`);
	renderReports(data);
}

async function getAllProducts() {
	const products = [];
	for (const active of [true, false]) {
		const params = new URLSearchParams({ limit: '100', is_active: String(active) });
		const first = await adminRequest(`/products?${params}`);
		products.push(...(first.products || []));
		const pages = Number(first.pagination?.pages || 1);
		for (let page = 2; page <= pages; page += 1) {
			params.set('page', String(page));
			const result = await adminRequest(`/products?${params}`);
			products.push(...(result.products || []));
		}
	}
	return products.sort((a, b) => a.name.localeCompare(b.name));
}

function renderProducts() {
	const query = adminQuery('#product-search').value.trim().toLowerCase();
	const filter = adminQuery('#product-filter').value;
	const categoryFilter = adminQuery('#product-category-filter').value;
	const products = adminState.products.filter(product => {
		const category = adminState.categories.find(item => item.id === product.category_id)?.name || '';
		const matchesQuery = `${product.name} ${category}`.toLowerCase().includes(query);
		const matchesStatus = filter === 'all' || (filter === 'active') === Boolean(product.is_active);
		const matchesCategory = categoryFilter === 'all' || String(product.category_id || '') === categoryFilter;
		return matchesQuery && matchesStatus && matchesCategory;
	});
	const visible = slicePage(products, adminPages.products);
	adminQuery('#product-rows').innerHTML = visible.length ? visible.map(product => {
		const category = adminState.categories.find(item => item.id === product.category_id)?.name || 'Uncategorized';
		const action = product.is_active
			? `<button class="btn btn-outline" type="button" data-product-delete="${adminEscape(product.id)}">Delete</button>`
			: `<button class="btn btn-outline" type="button" data-product-toggle="${adminEscape(product.id)}">Activate</button>`;
		const lowStock = Number(product.stock) <= LOW_STOCK_LIMIT;
		return `<tr><td><div class="admin-product-cell">${adminProductImage(product)}<span><b>${adminEscape(product.name)}</b><small>#${adminEscape(product.id)}</small></span></div></td><td>${adminEscape(category)}</td><td>${adminMoney(product.price)}</td><td>${lowStock ? statusPill('low stock') : ''} ${adminEscape(product.stock)}</td><td>${statusPill(product.is_active ? 'active' : 'inactive')}</td><td><div class="admin-row-actions"><button class="btn btn-outline" type="button" data-product-edit="${adminEscape(product.id)}">Edit</button>${action}</div></td></tr>`;
	}).join('') : adminEmptyRow(6, 'No matching products.');
	renderPagination(adminQuery('#product-pagination'), adminPages.products, products.length, 'products');
}

async function loadProducts() {
	const [products, categoryData] = await Promise.all([getAllProducts(), adminRequest('/categories')]);
	adminState.products = products;
	adminState.categories = categoryData.categories || [];
	adminQuery('#product-category').innerHTML = '<option value="">Uncategorized</option>' + adminState.categories.map(category =>
		`<option value="${adminEscape(category.id)}">${adminEscape(category.name)}</option>`
	).join('');
	adminQuery('#product-category-filter').innerHTML = '<option value="all">All categories</option>' + adminState.categories.map(category =>
		`<option value="${adminEscape(category.id)}">${adminEscape(category.name)}</option>`
	).join('');
	renderProducts();
}

function openProductDialog(product) {
	const dialog = adminQuery('#product-dialog');
	const form = adminQuery('#product-form');
	form.reset();
	form.elements.id.value = product?.id || '';
	form.elements.name.value = product?.name || '';
	form.elements.category_id.value = product?.category_id ?? '';
	form.elements.price.value = product?.price ?? '';
	form.elements.stock.value = product?.stock ?? 0;
	form.elements.image_url.value = product?.image_url || '';
	form.elements.description.value = product?.description || '';
	form.elements.is_active.checked = product ? Boolean(product.is_active) : true;
	adminQuery('#product-dialog-title').textContent = product ? 'Edit product' : 'Add product';
	adminQuery('#product-form-error').textContent = '';
	dialog.showModal();
}

async function saveProduct(event) {
	event.preventDefault();
	const form = event.currentTarget;
	if (!form.reportValidity()) return;
	const formData = new FormData(form);
	const productId = formData.get('id');
	const payload = {
		name: String(formData.get('name')).trim(),
		category_id: formData.get('category_id') ? Number(formData.get('category_id')) : null,
		price: Number(formData.get('price')),
		stock: Number(formData.get('stock')),
		image_url: String(formData.get('image_url') || '').trim() || null,
		description: String(formData.get('description') || '').trim() || null,
		is_active: form.elements.is_active.checked
	};
	const submit = form.querySelector('[type="submit"]');
	submit.disabled = true;
	try {
		await adminRequest(productId ? `/products/${productId}` : '/products', productId ? 'PATCH' : 'POST', payload);
		adminQuery('#product-dialog').close();
		await loadProducts();
		showAdminError('');
		showAdminToast(productId ? 'Product updated.' : 'Product added.');
	} catch (error) {
		adminQuery('#product-form-error').textContent = error.message;
	} finally {
		submit.disabled = false;
	}
}

async function toggleProduct(productId) {
	const product = adminState.products.find(item => item.id === Number(productId));
	if (!product) return;
	const action = product.is_active ? 'deactivate' : 'activate';
	if (!window.confirm(`Do you want to ${action} ${product.name}?`)) return;
	try {
		await adminRequest(`/products/${product.id}`, 'PATCH', { is_active: !product.is_active });
		await loadProducts();
		showAdminError('');
		showAdminToast(`Product ${action}d.`);
	} catch (error) {
		showAdminError(error.message);
	}
}

async function deleteProduct(productId) {
	const product = adminState.products.find(item => item.id === Number(productId));
	if (!product || !window.confirm(`Hide ${product.name} from the storefront? Existing order records will be preserved.`)) return;
	try {
		await adminRequest(`/products/${product.id}`, 'DELETE');
		await loadProducts();
		showAdminError('');
		showAdminToast('Product hidden from the storefront.');
	} catch (error) {
		showAdminError(error.message);
	}
}

function renderOrders() {
	const query = adminQuery('#order-search').value.trim().toLowerCase();
	const status = adminQuery('#order-filter').value;
	const orders = adminState.orders.filter(order => {
		const matchesQuery = `#${order.id} ${order.user_id} ${order.customer?.name || ''} ${order.customer?.email || ''}`.toLowerCase().includes(query);
		return matchesQuery && (status === 'all' || order.status === status);
	});
	const visible = slicePage(orders, adminPages.orders);
	adminQuery('#order-rows').innerHTML = visible.length ? visible.map(order => {
		const options = ORDER_STATUSES.map(option => `<option value="${option}" ${option === order.status ? 'selected' : ''}>${option.replaceAll('_', ' ')}</option>`).join('');
		const payment = order.payments?.[0];
		return `<tr><td><button class="admin-link-button" type="button" data-order-details="${adminEscape(order.id)}">#${adminEscape(order.id)} · Details</button></td><td>${adminEscape(order.customer?.name || `Customer #${order.user_id}`)}<small>${adminEscape(order.customer?.email || '')}</small></td><td>${adminEscape(adminDate(order.created_at))}</td><td>${adminEscape((order.items || []).reduce((sum, item) => sum + Number(item.quantity || 0), 0))} items</td><td>${adminMoney(order.total_amount)}</td><td>${payment ? `${adminEscape(payment.payment_method)}<small>${statusPill(payment.payment_status)}</small>` : 'Not recorded'}</td><td>${statusPill(order.status)}</td><td><div class="admin-inline-form"><select aria-label="Status for order ${adminEscape(order.id)}" data-order-status="${adminEscape(order.id)}">${options}</select><button class="btn btn-outline" type="button" data-order-save="${adminEscape(order.id)}">Save</button></div></td></tr>`;
	}).join('') : adminEmptyRow(8, 'No matching orders.');
	renderPagination(adminQuery('#order-pagination'), adminPages.orders, orders.length, 'orders');
}

async function loadOrders() {
	const data = await adminRequest('/admin/orders');
	adminState.orders = data.orders || [];
	const requestedStatus = new URLSearchParams(location.search).get('status');
	if (requestedStatus && ORDER_STATUSES.includes(requestedStatus)) adminQuery('#order-filter').value = requestedStatus;
	renderOrders();
}

async function saveOrderStatus(orderId) {
	const select = adminQuery(`[data-order-status="${CSS.escape(String(orderId))}"]`);
	if (!select) return;
	if (select.value === 'cancelled' && !window.confirm(`Cancel order #${orderId}? This will restore its items to inventory.`)) return;
	try {
		await adminRequest(`/admin/orders/${orderId}/status`, 'PATCH', { status: select.value });
		await loadOrders();
		showAdminError('');
		showAdminToast(`Order #${orderId} status updated.`);
	} catch (error) {
		showAdminError(error.message);
	}
}

async function showOrderDetails(orderId) {
	const dialog = adminQuery('#order-dialog');
	const content = adminQuery('#order-detail-content');
	content.innerHTML = '<div class="admin-loading" role="status">Loading order details…</div>';
	dialog.showModal();
	try {
		const [data, historyData] = await Promise.all([
			adminRequest(`/admin/orders/${orderId}`),
			adminRequest(`/admin/orders/${orderId}/history`)
		]);
		const order = data.order;
		const paymentRows = order.payments?.length ? order.payments.map(payment =>
			`<div class="admin-detail-row"><span>${adminEscape(payment.payment_method)} · ${statusPill(payment.payment_status)}</span><strong>${adminMoney(payment.amount)}</strong></div>`
		).join('') : '<p class="admin-muted">No payment record for this order.</p>';
		const items = order.items?.length ? order.items.map(item =>
			`<div class="admin-detail-row"><span>${adminEscape(item.product_name || `Product #${item.product_id}`)}<small>${adminEscape(item.quantity)} × ${adminMoney(item.unit_price)}</small></span><strong>${adminMoney(item.subtotal)}</strong></div>`
		).join('') : '<p class="admin-muted">No items recorded.</p>';
		const history = historyData.history?.length ? historyData.history.map(entry =>
			`<div class="admin-detail-row"><span>${adminEscape(entry.description)}</span><time>${adminEscape(adminDateTime(entry.created_at))}</time></div>`
		).join('') : '<p class="admin-muted">No status changes have been recorded.</p>';
		content.innerHTML = `<p class="eyebrow">Order details</p><h2>Order #${adminEscape(order.id)}</h2><div class="admin-detail-meta"><p><strong>Customer</strong><br>${adminEscape(order.customer?.name || `Customer #${order.user_id}`)}<br>${adminEscape(order.customer?.email || '')}</p><p><strong>Placed</strong><br>${adminEscape(adminDate(order.created_at))}<br>${statusPill(order.status)}</p></div><h3>Purchased items</h3>${items}<div class="admin-detail-row admin-detail-total"><span>Total</span><strong>${adminMoney(order.total_amount)}</strong></div><h3>Payment</h3>${paymentRows}<h3>Status history</h3>${history}<h3>Delivery address</h3><p class="admin-address">${adminEscape(order.shipping_address || 'No address recorded')}</p>`;
	} catch (error) {
		content.innerHTML = `<div class="admin-alert" role="alert">${adminEscape(error.message)}</div>`;
	}
}

function renderInventory() {
	const query = adminQuery('#inventory-search').value.trim().toLowerCase();
	const filter = adminQuery('#inventory-filter').value;
	const rows = adminState.inventory.filter(item => {
		const quantity = Number(item.quantity);
		return `${item.product_name || ''} ${item.product_id}`.toLowerCase().includes(query)
			&& (filter === 'all' || (filter === 'low' ? quantity <= LOW_STOCK_LIMIT : quantity > LOW_STOCK_LIMIT));
	});
	const visible = slicePage(rows, adminPages.inventory);
	adminQuery('#inventory-rows').innerHTML = visible.length ? visible.map(item => {
		const quantity = Number(item.quantity);
		return `<tr class="${quantity <= LOW_STOCK_LIMIT ? 'admin-low-stock-row' : ''}"><td><b>${adminEscape(item.product_name)}</b></td><td>#${adminEscape(item.product_id)}</td><td>${statusPill(quantity <= LOW_STOCK_LIMIT ? 'low stock' : 'in stock')}</td><td><strong>${adminEscape(quantity)}</strong></td><td><form class="admin-inline-form" data-inventory-form="${adminEscape(item.product_id)}"><input aria-label="New stock for ${adminEscape(item.product_name)}" type="number" name="quantity" min="0" step="1" value="${adminEscape(quantity)}" required><button class="btn btn-outline" type="submit">Save</button></form></td></tr>`;
	}).join('') : adminEmptyRow(5, 'No matching inventory records.');
	renderPagination(adminQuery('#inventory-pagination'), adminPages.inventory, rows.length, 'inventory');
}

async function loadInventory() {
	const data = await adminRequest('/inventory');
	adminState.inventory = data.inventory || [];
	const productId = new URLSearchParams(location.search).get('product');
	if (productId && /^\d+$/.test(productId)) adminQuery('#inventory-search').value = productId;
	renderInventory();
}

function renderCustomers() {
	const query = adminQuery('#customer-search').value.trim().toLowerCase();
	const users = adminState.users.filter(user => `${user.name} ${user.email}`.toLowerCase().includes(query));
	const visible = slicePage(users, adminPages.customers);
	adminQuery('#customer-rows').innerHTML = visible.length ? visible.map(user =>
		`<tr><td><b>${adminEscape(user.name)}</b><small>#${adminEscape(user.id)}</small></td><td>${adminEscape(user.email)}</td><td>${statusPill(user.role)}</td><td>${adminEscape(adminDate(user.created_at))}</td><td>${user.role === 'customer' ? `<button class="btn btn-outline" type="button" data-customer-history="${adminEscape(user.id)}">View history</button>` : '—'}</td></tr>`
	).join('') : adminEmptyRow(5, 'No matching accounts.');
	renderPagination(adminQuery('#customer-pagination'), adminPages.customers, users.length, 'customers');
}

async function loadCustomers() {
	const role = adminQuery('#customer-role-filter').value;
	const params = new URLSearchParams();
	if (role !== 'all') params.set('role', role);
	const search = adminQuery('#customer-search').value.trim();
	if (search) params.set('search', search);
	const query = params.toString();
	const requestSequence = ++customersLoadSequence;
	const data = await adminRequest(`/admin/users${query ? `?${query}` : ''}`);
	if (requestSequence !== customersLoadSequence) return;
	adminState.users = data.users || [];
	adminPages.customers = 1;
	renderCustomers();
}

async function showCustomerHistory(userId) {
	const dialog = adminQuery('#customer-dialog');
	const content = adminQuery('#customer-detail-content');
	const customer = adminState.users.find(user => user.id === Number(userId));
	if (!customer) return;
	content.innerHTML = `<p class="eyebrow">Customer order history</p><h2>${adminEscape(customer.name)}</h2><p class="admin-muted">${adminEscape(customer.email)}</p><div class="admin-loading" role="status">Loading order history…</div>`;
	dialog.showModal();
	try {
		const data = await adminRequest(`/admin/users/${userId}/orders`);
		const orders = data.orders || [];
		const rows = orders.length ? orders.map(order =>
			`<article class="admin-history-order"><div><strong>Order #${adminEscape(order.id)}</strong><small>${adminEscape(adminDate(order.created_at))} · ${adminEscape((order.items || []).reduce((count, item) => count + Number(item.quantity || 0), 0))} items</small></div><span>${statusPill(order.status)}</span><strong>${adminMoney(order.total_amount)}</strong></article>`
		).join('') : '<div class="admin-empty">No orders for this customer yet.</div>';
		content.innerHTML = `<p class="eyebrow">Customer order history</p><h2>${adminEscape(customer.name)}</h2><p class="admin-muted">${adminEscape(customer.email)}</p>${rows}`;
	} catch (error) {
		content.innerHTML = `<div class="admin-alert" role="alert">${adminEscape(error.message)}</div>`;
	}
}

async function loadProfile() {
	const data = await adminRequest('/auth/me');
	adminState.profile = data.user;
	document.querySelectorAll('[data-admin-greeting]').forEach(element => {
		element.textContent = `Signed in as ${data.user.name}`;
	});
	if (adminPage === 'account') {
		adminQuery('#admin-profile-name').value = data.user.name;
		adminQuery('#admin-profile-email').value = data.user.email;
	}
}

async function saveProfile(event) {
	event.preventDefault();
	const form = event.currentTarget;
	if (!form.reportValidity()) return;
	const button = form.querySelector('[type="submit"]');
	button.disabled = true;
	adminQuery('#admin-profile-error').textContent = '';
	try {
		const data = await adminRequest('/users/me', 'PATCH', {
			name: form.elements.name.value.trim(),
			email: form.elements.email.value.trim()
		});
		adminState.profile = data.user;
		document.querySelectorAll('[data-admin-greeting]').forEach(element => {
			element.textContent = `Signed in as ${data.user.name}`;
		});
		showAdminToast('Profile updated.');
	} catch (error) {
		adminQuery('#admin-profile-error').textContent = error.message;
	} finally {
		button.disabled = false;
	}
}

async function savePassword(event) {
	event.preventDefault();
	const form = event.currentTarget;
	if (!form.reportValidity()) return;
	const button = form.querySelector('[type="submit"]');
	button.disabled = true;
	adminQuery('#admin-password-error').textContent = '';
	try {
		await adminRequest('/users/me/password', 'PUT', {
			current_password: form.elements.current_password.value,
			new_password: form.elements.new_password.value
		});
		form.reset();
		showAdminToast('Password updated.');
	} catch (error) {
		adminQuery('#admin-password-error').textContent = error.message;
	} finally {
		button.disabled = false;
	}
}

async function adminLogout() {
	if (!window.confirm('Sign out of the admin account?')) return;
	try {
		await adminRequest('/auth/logout', 'POST', {});
		clearAdminToken();
		location.href = '../pages/login.html';
	} catch (error) {
		if (error.status === 401) {
			clearAdminToken();
			location.href = '../pages/login.html';
			return;
		}
		showAdminError(error.message);
	}
}

function closeAdminMenu() {
	document.body.classList.remove('admin-menu-open');
	adminQuery('[data-admin-menu-toggle]')?.setAttribute('aria-expanded', 'false');
}

function bindAdminNavigation() {
	const sidebar = adminQuery('#admin-sidebar');
	const toggle = adminQuery('[data-admin-menu-toggle]');
	const close = adminQuery('[data-admin-menu-close]');
	const mobile = window.matchMedia('(max-width: 760px)');
	const isCollapsed = localStorage.getItem('ec_admin_sidebar_collapsed') === 'true';
	document.body.classList.toggle('admin-sidebar-collapsed', isCollapsed);
	toggle?.addEventListener('click', () => {
		if (mobile.matches) {
			document.body.classList.toggle('admin-menu-open');
			toggle.setAttribute('aria-expanded', String(document.body.classList.contains('admin-menu-open')));
		} else {
			const collapsed = !document.body.classList.contains('admin-sidebar-collapsed');
			document.body.classList.toggle('admin-sidebar-collapsed', collapsed);
			localStorage.setItem('ec_admin_sidebar_collapsed', String(collapsed));
		}
	});
	close?.addEventListener('click', closeAdminMenu);
	sidebar?.querySelectorAll('.admin-nav a').forEach(link => {
		link.addEventListener('click', closeAdminMenu);
	});
	document.querySelectorAll('[data-admin-logout]').forEach(button => {
		button.addEventListener('click', adminLogout);
	});
	document.addEventListener('keydown', event => {
		if (event.key === 'Escape') closeAdminMenu();
	});
}

async function refreshAdminPage() {
	showAdminError('');
	const refresh = adminQuery('#admin-refresh');
	if (refresh) refresh.disabled = true;
	try {
		await adminRequest('/admin/dashboard');
		await loadProfile();
		if (adminPage === 'dashboard') await loadDashboard();
		if (adminPage === 'products') await loadProducts();
		if (adminPage === 'orders') await loadOrders();
		if (adminPage === 'orders') {
			const orderId = new URLSearchParams(location.search).get('order');
			if (orderId && /^\d+$/.test(orderId)) await showOrderDetails(orderId);
		}
		if (adminPage === 'inventory') await loadInventory();
		if (adminPage === 'customers') await loadCustomers();
		if (adminPage === 'reports') await loadReports();
		if (adminPage === 'messages') {
			await loadAdminConversations();
			if (activeConversationId) await loadAdminConversation(activeConversationId);
		}
	} catch (error) {
		if (error.status === 401) {
			location.href = `../pages/login.html?next=${encodeURIComponent(location.href)}`;
			return;
		}
		showAdminError(error.status === 403 ? 'This page is available to store administrators only.' : error.message);
	} finally {
		if (refresh) refresh.disabled = false;
	}
}

document.addEventListener('click', event => {
	const target = event.target;
	const conversation = target.closest('[data-conversation-id]');
	const notificationToggle = target.closest('[data-notification-toggle]');
	const notification = target.closest('[data-notification-id]');
	const notificationReadAll = target.closest('[data-notifications-read-all]');
	if (conversation) {
		openAdminConversation(Number(conversation.dataset.conversationId)).catch(error => showAdminError(error.message));
	}
	if (notificationToggle) {
		const panel = adminQuery('[data-notification-panel]');
		const expanded = notificationToggle.getAttribute('aria-expanded') !== 'true';
		notificationToggle.setAttribute('aria-expanded', String(expanded));
		panel.hidden = !expanded;
	}
	if (notification) {
		event.preventDefault();
		const href = notification.href;
		adminRequest(`/admin/notifications/${notification.dataset.notificationId}/read`, 'PATCH', {})
			.then(() => { location.href = href; })
			.catch(error => showAdminError(error.message));
	}
	if (notificationReadAll) {
		adminRequest('/admin/notifications/read-all', 'PATCH', {})
			.then(loadAdminNotifications)
			.catch(error => showAdminError(error.message));
	}
	if (!target.closest('.admin-notification-control')) {
		const panel = adminQuery('[data-notification-panel]');
		const toggleButton = adminQuery('[data-notification-toggle]');
		if (panel) panel.hidden = true;
		toggleButton?.setAttribute('aria-expanded', 'false');
	}
	const edit = target.closest('[data-product-edit]');
	const toggle = target.closest('[data-product-toggle]');
	const remove = target.closest('[data-product-delete]');
	const saveOrder = target.closest('[data-order-save]');
	const orderDetails = target.closest('[data-order-details]');
	const customerHistory = target.closest('[data-customer-history]');
	const pageButton = target.closest('[data-page-kind]');
	if (edit) openProductDialog(adminState.products.find(product => product.id === Number(edit.dataset.productEdit)));
	if (toggle) toggleProduct(toggle.dataset.productToggle);
	if (remove) deleteProduct(remove.dataset.productDelete);
	if (saveOrder) saveOrderStatus(saveOrder.dataset.orderSave);
	if (orderDetails) showOrderDetails(orderDetails.dataset.orderDetails);
	if (customerHistory) showCustomerHistory(customerHistory.dataset.customerHistory);
	if (pageButton && !pageButton.disabled) {
		const kind = pageButton.dataset.pageKind;
		adminPages[kind] = Number(pageButton.dataset.page);
		if (kind === 'products') renderProducts();
		if (kind === 'orders') renderOrders();
		if (kind === 'inventory') renderInventory();
		if (kind === 'customers') renderCustomers();
	}
	if (target.closest('[data-dialog-close]')) target.closest('dialog').close();
});

document.addEventListener('submit', async event => {
	if (event.target.id === 'admin-chat-form') {
		sendAdminMessage(event);
		return;
	}
	if (event.target.id === 'product-form') {
		saveProduct(event);
		return;
	}
	if (event.target.id === 'admin-profile-form') {
		saveProfile(event);
		return;
	}
	if (event.target.id === 'admin-password-form') {
		savePassword(event);
		return;
	}
	if (event.target.id === 'reports-filter') {
		event.preventDefault();
		const form = event.target;
		if (!form.reportValidity()) return;
		const button = form.querySelector('[type="submit"]');
		button.disabled = true;
		loadReports().then(() => {
			showAdminError('');
			showAdminToast('Report updated.');
		}).catch(error => showAdminError(error.message)).finally(() => {
			button.disabled = false;
		});
		return;
	}
	if (event.target.matches('[data-inventory-form]')) {
		event.preventDefault();
		const form = event.target;
		if (!form.reportValidity()) return;
		const productId = form.dataset.inventoryForm;
		const quantity = Number(new FormData(form).get('quantity'));
		if (!Number.isSafeInteger(quantity) || quantity < 0) {
			showAdminError('Stock must be a whole number zero or greater.');
			return;
		}
		const button = form.querySelector('button');
		button.disabled = true;
		try {
			await adminRequest(`/inventory/${productId}`, 'PATCH', { quantity });
			await loadInventory();
			showAdminError('');
			showAdminToast('Inventory updated.');
		} catch (error) {
			showAdminError(error.message);
		} finally {
			button.disabled = false;
		}
	}
});

adminQuery('#product-add')?.addEventListener('click', () => openProductDialog(null));
adminQuery('#product-cancel')?.addEventListener('click', () => adminQuery('#product-dialog').close());
adminQuery('#product-search')?.addEventListener('input', () => { adminPages.products = 1; renderProducts(); });
adminQuery('#product-filter')?.addEventListener('change', () => { adminPages.products = 1; renderProducts(); });
adminQuery('#product-category-filter')?.addEventListener('change', () => { adminPages.products = 1; renderProducts(); });
adminQuery('#order-search')?.addEventListener('input', () => { adminPages.orders = 1; renderOrders(); });
adminQuery('#order-filter')?.addEventListener('change', () => { adminPages.orders = 1; renderOrders(); });
adminQuery('#inventory-search')?.addEventListener('input', () => { adminPages.inventory = 1; renderInventory(); });
adminQuery('#inventory-filter')?.addEventListener('change', () => { adminPages.inventory = 1; renderInventory(); });
adminQuery('#customer-search')?.addEventListener('input', () => {
	adminPages.customers = 1;
	loadCustomers().catch(error => showAdminError(error.message));
});
adminQuery('#customer-role-filter')?.addEventListener('change', () => loadCustomers().catch(error => showAdminError(error.message)));
adminQuery('#admin-refresh')?.addEventListener('click', refreshAdminPage);

setupAdminCommunication();
bindAdminNavigation();
refreshAdminPage();
