const ADMIN_API_BASE = (window.EC_API_BASE_URL || (
	['localhost', '127.0.0.1'].includes(location.hostname)
		? 'http://127.0.0.1:5000/api/v1'
		: `${location.origin}/api/v1`
)).replace(/\/+$/, '');
const ADMIN_TOKEN_KEY = 'ec_access_token';
const ORDER_STATUSES = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'];
const LOW_STOCK_LIMIT = 10;
const PAGE_SIZE = 10;
const adminPage = document.body.dataset.adminPage;
const adminState = { products: [], categories: [], orders: [], users: [], inventory: [], profile: null, report: null, dashboard: null, discounts: [] };
const adminPages = { products: 1, orders: 1, inventory: 1, customers: 1 };
let activeConversationId = null;
let loadedOrderCustomerId = null;
let customersLoadSequence = 0;
const adminQuery = selector => document.querySelector(selector);
const adminQueryAll = selector => [...document.querySelectorAll(selector)];
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
const adminStoreToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Manila' }).format(new Date());
const adminStoreDateOffset = (value, days) => {
	const date = new Date(`${value}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() + days);
	return date.toISOString().slice(0, 10);
};

function adminIconSvg(name) {
	const paths = {
		search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
		'dashboard.html': '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
		'products.html': '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4.5 7.7 7.5 4.4 7.5-4.4M12 12v9"/>',
		'inventory.html': '<path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z"/><path d="m4 12 8 4.5 8-4.5M4 16.5 12 21l8-4.5"/>',
		'orders.html': '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
		'customers.html': '<path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
		'reports.html': '<path d="M4 19V5M4 19h17"/><path d="m7 15 4-4 3 2 6-7"/>',
		'messages.html': '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8A8.5 8.5 0 0 1 8.7 3.9a8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
		'deliveries.html': '<path d="M3 7h11v10H3zM14 10h4l3 3v4h-7z"/><circle cx="7.5" cy="19" r="1.5"/><circle cx="17.5" cy="19" r="1.5"/>',
		'discounts.html': '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3.4 13.4a2 2 0 0 1 0-2.8l7.2-7.2A2 2 0 0 1 12 3h7a2 2 0 0 1 2 2v7a2 2 0 0 1-.4 1.4Z"/><circle cx="16.5" cy="7.5" r="1"/>',
		'account.html': '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1-.1 2Z"/>',
		'notification': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
		egg: '<path d="M12 3c-3.5 0-7 6.1-7 11a7 7 0 0 0 14 0c0-4.9-3.5-11-7-11Z"/>',
		chicken: '<path d="M7 15c-2.2 0-4 1.3-4 3s1.8 3 4 3h8a6 6 0 0 0 0-12h-2"/><circle cx="16" cy="7" r="3"/><path d="m19 7 3 1-2 2M8 15c0-4 2-7 6-7"/>',
		delivered: '<path d="m5 12 4 4L19 6"/><circle cx="12" cy="12" r="9"/>'
	};
	return `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ''}</svg>`;
}

function setupAdminCommunication() {
	if (adminPage && ['deliveries', 'discounts', 'messages'].includes(adminPage)) {
		window.location.replace('dashboard.html');
		return;
	}
	const sidebar = adminQuery('.admin-nav');
	if (sidebar) {
		const links = [
			['dashboard.html', 'Overview'],
			['orders.html', 'Orders'],
			['products.html', 'Products'],
			['inventory.html', 'Inventory'],
			['customers.html', 'Customers'],
			['reports.html', 'Analytics'],
			['account.html', 'Settings']
		];
		sidebar.innerHTML = links.map(([href, label]) => {
			const selected = href === `${adminPage}.html` || (adminPage === 'reports' && href === 'reports.html');
			return `<a href="${href}"${selected ? ' class="active" aria-current="page"' : ''}><span class="admin-nav-icon" aria-hidden="true">${adminIconSvg(href)}</span><span>${label}</span></a>`;
		}).join('');
		if (!sidebar.parentElement.querySelector('.admin-store-switcher')) {
			sidebar.insertAdjacentHTML('beforebegin', '<div class="admin-store-switcher" title="Store switching is not available in this single-store account"><span class="admin-store-icon" aria-hidden="true">▣</span><span><strong>Egg &amp; Chicken</strong><small><i data-store-health></i><span data-store-status>Checking store API…</span></small></span><span aria-hidden="true">⌄</span></div>');
		}
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
	if (actions && !actions.querySelector('.admin-global-search')) {
		const search = document.createElement('div');
		const searchShortcut = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K';
		search.className = 'admin-global-search';
		search.innerHTML = `<span aria-hidden="true">${adminIconSvg('search')}</span><label class="sr-only" for="admin-global-search-input">Search orders, products, and customers</label><input id="admin-global-search-input" type="search" placeholder="Search orders, products, customers…" autocomplete="off"><kbd>${searchShortcut}</kbd><section class="admin-search-results" id="admin-search-results" hidden></section>`;
		actions.prepend(search);
	}
	if (actions && !actions.querySelector('.admin-profile-menu')) {
		const profileMenu = document.createElement('details');
		profileMenu.className = 'admin-profile-menu';
		profileMenu.innerHTML = `<summary><span class="admin-profile-avatar" data-admin-avatar>EC</span><span><strong data-admin-profile-name>Admin</strong><small>Store administrator</small></span><span aria-hidden="true">⌄</span></summary><div class="admin-profile-dropdown"><a href="account.html">Account settings</a><button type="button" data-admin-logout>Sign out</button></div>`;
		actions.append(profileMenu);
	}
	const searchInput = adminQuery('#admin-global-search-input');
	searchInput?.addEventListener('input', () => {
		window.clearTimeout(adminSearchTimer);
		adminSearchTimer = window.setTimeout(() => runAdminSearch(), 250);
	});
	searchInput?.addEventListener('keydown', event => {
		if (event.key === 'Escape') {
			adminQuery('#admin-search-results').hidden = true;
			searchInput.blur();
		}
	});
	document.addEventListener('keydown', event => {
		if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
			event.preventDefault();
			searchInput?.focus();
		}
	});
	document.addEventListener('click', event => {
		if (!event.target.closest('.admin-global-search')) {
			const results = adminQuery('#admin-search-results');
			if (results) results.hidden = true;
		}
	});
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
	} catch (error) {
		const reason = error instanceof Error ? ` ${error.message}` : '';
		throw new Error(`Could not connect to the store API at ${ADMIN_API_BASE}. Check the API URL, backend availability, and CORS configuration.${reason}`);
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

let adminSearchTimer;
async function runAdminSearch() {
	const input = adminQuery('#admin-global-search-input');
	const target = adminQuery('#admin-search-results');
	if (!input || !target) return;
	const query = input.value.trim();
	if (query.length < 2) {
		target.hidden = true;
		target.innerHTML = '';
		return;
	}
	target.hidden = false;
	target.innerHTML = '<p class="admin-search-empty">Searching store records…</p>';
	try {
		const data = await adminRequest(`/admin/search?q=${encodeURIComponent(query)}`);
		if (input.value.trim() !== query) return;
		target.innerHTML = data.results?.length
			? data.results.map(result => `<a href="${adminEscape(result.href)}"><small>${adminEscape(result.kind)}</small><strong>${adminEscape(result.label)}</strong><span>${adminEscape(result.detail)}</span></a>`).join('')
			: '<p class="admin-search-empty">No matching orders, products, or customers.</p>';
	} catch (error) {
		if (input.value.trim() === query) {
			target.innerHTML = `<p class="admin-search-empty">${adminEscape(error.message)}</p>`;
		}
	}
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

function applyPageSearch(selector) {
	const url = new URL(location.href);
	const search = url.searchParams.get('search');
	if (!search) return;
	const input = adminQuery(selector);
	if (input) input.value = search;
	url.searchParams.delete('search');
	history.replaceState(null, '', url);
}

function slicePage(records, page) {
	return records.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
}

async function loadDashboard() {
	const today = adminStoreToday();
	const period = Number(adminQuery('#dashboard-period')?.value || 7);
	const start = period === 30 ? adminStoreDateOffset(today, -29)
		: period === 1 ? today : adminStoreDateOffset(today, -6);
	const params = new URLSearchParams({
		start_date: start,
		end_date: today
	});
	const stats = await adminRequest(`/admin/dashboard?${params}`);
	adminState.dashboard = stats;
	renderDashboardOverview(stats, period);
}

function exportDashboardReport() {
	if (!adminState.dashboard) {
		showAdminError('Dashboard data is not available to export yet.');
		return;
	}
	const stats = adminState.dashboard;
	const rows = [
		['Report', 'Egg & Chicken store overview'],
		['Currency', 'PHP'],
		['Timezone', 'Asia/Manila'],
		['Selected period gross sales', Number(stats.sales_period?.gross_sales || 0).toFixed(2)],
		['Orders today', Number(stats.orders_today || 0)],
		['Eggs sold today', Number(stats.eggs_sold || 0)],
		['Egg sales today', Number(stats.eggs_sales || 0).toFixed(2)],
		['Chicken sold today', Number(stats.chicken_sold || 0)],
		['Chicken sales today', Number(stats.chicken_sales || 0).toFixed(2)],
		[],
		['Daily sales'],
		['Date', 'Gross sales (PHP)', 'Egg sales (PHP)', 'Chicken sales (PHP)'],
		...(stats.sales_by_day || []).map(day => [day.date, Number(day.gross_sales || 0).toFixed(2), Number(day.eggs_sales || 0).toFixed(2), Number(day.chicken_sales || 0).toFixed(2)]),
		[],
		['Recent orders'],
		['Order ID', 'Customer', 'Items', 'Total (PHP)', 'Payment status', 'Fulfillment status'],
		...(stats.recent_orders || []).map(order => [
			order.id,
			order.customer?.name || `Customer #${order.user_id}`,
			(order.items || []).map(item => `${item.quantity} ${item.product_name}`).join('; '),
			Number(order.total_amount || 0).toFixed(2),
			order.payments?.[0]?.payment_status || 'not recorded',
			order.status
		])
	];
	const csv = rows.map(row => row.map(value => {
		const text = String(value ?? '');
		return `"${text.replace(/"/g, '""')}"`;
	}).join(',')).join('\r\n');
	const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }));
	const link = document.createElement('a');
	link.href = url;
	link.download = `egg-and-chicken-report-${stats.store_today || adminStoreToday()}.csv`;
	document.body.append(link);
	link.click();
	link.remove();
	URL.revokeObjectURL(url);
	showAdminToast('Report exported as CSV.');
}

function renderDashboardOverview(stats, period) {
	const periodSales = stats.sales_period || {};
	const percentLabel = value => value === null || value === undefined
		? 'No previous-period comparison'
		: `${Number(value) >= 0 ? '↑' : '↓'} ${Math.abs(Number(value)).toFixed(1)}% vs previous period`;
	const salesChange = periodSales.gross_sales_change_percent;
	const ordersChange = periodSales.orders_change_percent;
	const dateLabel = new Intl.DateTimeFormat(undefined, {
		day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Manila'
	}).format(new Date(`${stats.store_today}T12:00:00+08:00`));
	adminQuery('#dashboard-welcome').textContent = `A fresh start, ${adminState.profile?.name?.split(/\s+/)[0] || 'there'}.`;
	adminQuery('#dashboard-date').textContent = `Today · ${dateLabel}`;
	adminQuery('#dashboard-comparison').textContent = `${percentLabel(salesChange)} · ${percentLabel(ordersChange)}`;
	adminQuery('#dashboard-chart-period').textContent = period === 1
		? 'Today'
		: period === 30 ? 'Last 30 days' : 'Last 7 days';
	adminQuery('.admin-updated').textContent = `↻ Updated ${new Intl.DateTimeFormat(undefined, {
		hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Manila'
	}).format(new Date())} · PHT`;
	const comparison = periodSales.gross_sales_change_percent;
	const comparisonText = comparison === null || comparison === undefined
		? 'First recorded period'
		: `${comparison >= 0 ? '↑' : '↓'} ${Math.abs(comparison).toFixed(1)}% vs previous period`;
	const metricItems = [
		{ label: 'Gross sales', value: adminMoney(periodSales.gross_sales), note: comparisonText, icon: '₱', tone: 'is-forest' },
		{ label: 'Orders today', value: stats.orders_today || 0, note: `Placed ${stats.store_today} · PHT`, icon: 'orders.html' },
		{ label: 'Eggs sold', value: `${Number(stats.eggs_sold || 0).toLocaleString()} eggs`, note: `${adminMoney(stats.eggs_sales)} in selected-period sales`, icon: 'egg' },
		{ label: 'Chicken sold', value: `${Number(stats.chicken_sold || 0).toLocaleString()} items`, note: `${adminMoney(stats.chicken_sales)} in selected-period sales`, icon: 'chicken' }
	];
	adminQuery('#admin-stats').innerHTML = metricItems.map(item =>
		`<article class="admin-stat${item.tone ? ` ${item.tone}` : ''}"><span class="admin-stat-icon" aria-hidden="true">${item.icon === '₱' ? item.icon : adminIconSvg(item.icon)}</span><span>${adminEscape(item.label)}</span><strong>${adminEscape(item.value)}</strong><small>${adminEscape(item.note)}</small></article>`
	).join('');
	const orders = stats.recent_orders || [];
	adminQuery('#recent-orders-count').textContent = `${orders.length} latest`;
	adminQuery('#dashboard-orders').innerHTML = orders.length ? orders.map(order =>
		`<tr><td><button class="admin-link-button" type="button" data-order-details="${adminEscape(order.id)}">#EC-${adminEscape(order.id)}</button></td><td>${adminEscape(order.customer?.name || `Customer #${order.user_id}`)}</td><td>${adminEscape((order.items || []).map(item => `${item.quantity} ${item.product_name}`).join(', ') || '—')}</td><td>${adminMoney(order.total_amount)}</td><td>${statusPill(order.payments?.[0]?.payment_status || 'not recorded')}</td><td>${statusPill(order.status)}</td></tr>`
	).join('') : adminEmptyRow(6, 'No orders yet.');
	adminQuery('#dashboard-order-caption').textContent = `Showing the latest ${orders.length} of ${Number(stats.total_orders || 0)} orders · merchandise totals include current order records`;
	adminQuery('#dashboard-revenue').textContent = adminMoney(periodSales.gross_sales);
	renderOverviewChart(adminQuery('#dashboard-sales-chart'), stats.sales_by_day || []);
	renderFulfillment(stats.fulfillment || {});
	renderLowStock(stats.low_stock_items || []);
}

function renderOverviewChart(target, sales) {
	if (!target) return;
	if (!sales.length || sales.every(row => !Number(row.gross_sales))) {
		target.innerHTML = '<p class="admin-empty">No sales data is available for this period.</p>';
		return;
	}
	const width = 720;
	const height = 220;
	const left = 46;
	const top = 14;
	const bottom = 35;
	const plotHeight = height - top - bottom;
	const maxValue = Math.max(...sales.map(row => Number(row.gross_sales) || 0), 1);
	const barWidth = Math.min(34, 560 / sales.length);
	const gap = (width - left - 12) / sales.length;
	const grid = Array.from({ length: 4 }, (_, index) => {
		const y = top + plotHeight - index * plotHeight / 3;
		return `<line class="admin-chart-grid" x1="${left}" y1="${y}" x2="${width - 10}" y2="${y}"/><text class="admin-chart-axis" x="${left - 7}" y="${y + 4}" text-anchor="end">${adminEscape(adminMoney(maxValue * index / 3))}</text>`;
	}).join('');
	const bars = sales.map((item, index) => {
		const eggs = Math.max(0, Number(item.eggs_sales) || 0);
		const chicken = Math.max(0, Number(item.chicken_sales) || 0);
		const other = Math.max(0, Number(item.gross_sales) - eggs - chicken);
		const x = left + index * gap + (gap - barWidth) / 2;
		const scale = plotHeight / maxValue;
		const eggsHeight = eggs * scale;
		const chickenHeight = chicken * scale;
		const otherHeight = other * scale;
		const yBase = top + plotHeight;
		const date = new Date(`${item.date}T12:00:00+08:00`);
		const label = sales.length <= 8
			? new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', timeZone: 'Asia/Manila' }).format(date)
			: (index === 0 || index === sales.length - 1 || index % 5 === 0
				? new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', timeZone: 'Asia/Manila' }).format(date)
				: '');
		return `<g><title>${adminEscape(item.date)} · Eggs ${adminEscape(adminMoney(eggs))} · Chicken ${adminEscape(adminMoney(chicken))} · Total ${adminEscape(adminMoney(item.gross_sales))}</title>${eggsHeight ? `<rect class="admin-overview-bar-egg" x="${x}" y="${yBase - eggsHeight}" width="${barWidth}" height="${eggsHeight}" rx="3"/>` : ''}${chickenHeight ? `<rect class="admin-overview-bar-chicken" x="${x}" y="${yBase - eggsHeight - chickenHeight}" width="${barWidth}" height="${chickenHeight}" rx="3"/>` : ''}${otherHeight ? `<rect class="admin-overview-bar-other" x="${x}" y="${yBase - eggsHeight - chickenHeight - otherHeight}" width="${barWidth}" height="${otherHeight}" rx="3"/>` : ''}<text class="admin-chart-axis" x="${x + barWidth / 2}" y="${height - 8}" text-anchor="middle">${adminEscape(label)}</text></g>`;
	}).join('');
	target.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Daily gross sales by product type">${grid}${bars}</svg>`;
}

function renderFulfillment(fulfillment) {
	const toPack = Number(fulfillment.to_pack || 0);
	const dispatch = Number(fulfillment.ready_for_dispatch || 0);
	const delivered = Number(fulfillment.delivered_today || 0);
	adminQuery('#fulfillment-total').textContent = `${toPack + dispatch} to do`;
	adminQuery('#dashboard-fulfillment').innerHTML = `
		<a class="admin-fulfillment-row" href="orders.html"><span class="admin-fulfillment-icon">${adminIconSvg('inventory.html')}</span><span><strong>${toPack}</strong> orders to pack<small>Pending, confirmed, or processing</small><b>Open order queue →</b></span></a>
		<a class="admin-fulfillment-row" href="deliveries.html?status=shipped"><span class="admin-fulfillment-icon is-dispatch">${adminIconSvg('deliveries.html')}</span><span><strong>${dispatch}</strong> ready for dispatch<small>Orders marked shipped</small><b>Prepare dispatch →</b></span></a>
		<div class="admin-fulfillment-delivered">${adminIconSvg('delivered')}<span>${delivered} orders delivered today</span></div>`;
}

function renderLowStock(products) {
	adminQuery('#low-stock-count').textContent = `${products.length} items`;
	adminQuery('#dashboard-low-stock').innerHTML = products.length ? products.map(product => {
		const threshold = Math.max(1, Number(product.reorder_threshold) || LOW_STOCK_LIMIT);
		const stock = Math.max(0, Number(product.stock) || 0);
		const percent = Math.min(100, stock / threshold * 100);
		const category = product.category || 'Product';
		return `<article class="admin-low-stock-item">${adminProductImage(product)}<span class="admin-low-stock-info"><strong>${adminEscape(product.name)}</strong><small>${adminEscape(category)} · Reorder at ${threshold}</small><span class="admin-stock-track"><i style="width:${percent}%"></i></span></span><b>${adminEscape(stock)} units</b></article>`;
	}).join('') : '<p class="admin-empty">No active products are below the reorder threshold.</p>';
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
	applyPageSearch('#product-search');
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
		const matchesStatus = status === 'all' || order.status === status;
		const isDeliveryOrder = adminPage !== 'deliveries' || order.status !== 'cancelled';
		return matchesQuery && matchesStatus && isDeliveryOrder;
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
	applyPageSearch('#order-search');
	const data = await adminRequest('/admin/orders');
	adminState.orders = data.orders || [];
	const params = new URLSearchParams(location.search);
	const requestedStatus = params.get('status');
	if (requestedStatus && ORDER_STATUSES.includes(requestedStatus)) adminQuery('#order-filter').value = requestedStatus;
	if (params.has('search')) adminQuery('#order-search').value = params.get('search');
	renderOrders();
}

function addCreateOrderItem() {
	const target = adminQuery('#create-order-items');
	if (target.children.length >= 50) return;
	const products = adminState.products.filter(product => product.is_active);
	const row = document.createElement('div');
	row.className = 'admin-create-order-item';
	row.innerHTML = `<select name="product_id" aria-label="Product" required><option value="">Select a product</option>${products.map(product => `<option value="${adminEscape(product.id)}">${adminEscape(product.name)} · ${adminMoney(product.price)} · ${adminEscape(product.stock)} in stock</option>`).join('')}</select><input name="quantity" type="number" min="1" step="1" value="1" aria-label="Quantity" required><button type="button" class="admin-link-button" aria-label="Remove item" data-remove-order-item>Remove</button>`;
	target.append(row);
	updateOrderItemControls();
	adminQuery('[data-add-order-item]').disabled = target.children.length >= 50;
}

function updateOrderItemControls() {
	const rows = adminQueryAll('#create-order-items .admin-create-order-item');
	rows.forEach(row => {
		const remove = row.querySelector('[data-remove-order-item]');
		remove.hidden = rows.length === 1;
	});
}

async function openCreateOrderDialog() {
	const dialog = adminQuery('#create-order-dialog');
	const form = adminQuery('#create-order-form');
	if (!dialog || !form) return;
	form.reset();
	adminQuery('#create-order-error').textContent = '';
	adminQuery('#create-order-items').innerHTML = '<div class="admin-loading" role="status">Loading customers and products…</div>';
	dialog.showModal();
	try {
		const [customerData, products] = await Promise.all([
			adminRequest('/admin/users?role=customer'),
			getAllProducts()
		]);
		adminState.products = products;
		const customers = customerData.users || [];
		adminQuery('#create-order-customer').innerHTML = '<option value="">Select a customer</option>' + customers.map(customer =>
			`<option value="${adminEscape(customer.id)}">${adminEscape(customer.name)} · ${adminEscape(customer.email)}</option>`
		).join('');
		adminQuery('#create-order-items').innerHTML = '';
		addCreateOrderItem();
		if (!customers.length) adminQuery('#create-order-error').textContent = 'Create a customer account before placing an order.';
		if (!products.some(product => product.is_active)) adminQuery('#create-order-error').textContent = 'There are no active products available to order.';
	} catch (error) {
		adminQuery('#create-order-items').innerHTML = '';
		adminQuery('#create-order-error').textContent = error.message;
	}
}

async function saveAdminOrder(event) {
	event.preventDefault();
	const form = event.currentTarget;
	if (!form.reportValidity()) return;
	const items = [...adminQuery('#create-order-items').querySelectorAll('.admin-create-order-item')].map(row => ({
		product_id: Number(row.querySelector('[name="product_id"]').value),
		quantity: Number(row.querySelector('[name="quantity"]').value)
	}));
	const submit = form.querySelector('[type="submit"]');
	submit.disabled = true;
	adminQuery('#create-order-error').textContent = '';
	try {
		const data = await adminRequest('/admin/orders', 'POST', {
			customer_id: Number(form.elements.customer_id.value),
			shipping_address: form.elements.shipping_address.value.trim(),
			items
		});
		adminQuery('#create-order-dialog').close();
		await loadOrders();
		showAdminToast(`Order #${data.order.id} created. Payment is pending cash on delivery.`);
	} catch (error) {
		adminQuery('#create-order-error').textContent = error.message;
	} finally {
		submit.disabled = false;
	}
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

function localDateTimeInput(value) {
	if (!value) return '';
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return '';
	const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
	return local.toISOString().slice(0, 16);
}

function openDiscountDialog(discount = null) {
	const form = adminQuery('#discount-form');
	form.reset();
	form.elements.id.value = discount?.id || '';
	form.elements.code.value = discount?.code || '';
	form.elements.name.value = discount?.name || '';
	form.elements.discount_type.value = discount?.discount_type || 'percentage';
	form.elements.value.value = discount?.value ?? '';
	form.elements.starts_at.value = localDateTimeInput(discount?.starts_at);
	form.elements.expires_at.value = localDateTimeInput(discount?.expires_at);
	form.elements.is_active.checked = discount ? Boolean(discount.is_active) : true;
	adminQuery('#discount-dialog-title').textContent = discount ? 'Edit discount' : 'Create discount';
	adminQuery('#discount-form-error').textContent = '';
	adminQuery('#discount-dialog').showModal();
}

function discountStatus(discount) {
	if (!discount.is_active) return 'inactive';
	const now = Date.now();
	if (discount.starts_at && new Date(discount.starts_at).getTime() > now) return 'scheduled';
	if (discount.expires_at && new Date(discount.expires_at).getTime() < now) return 'expired';
	return 'active';
}

function renderDiscounts() {
	const query = adminQuery('#discount-search').value.trim().toLowerCase();
	const filter = adminQuery('#discount-status-filter').value;
	const discounts = adminState.discounts.filter(discount => {
		const matchesQuery = `${discount.code} ${discount.name}`.toLowerCase().includes(query);
		const status = discountStatus(discount);
		return matchesQuery && (filter === 'all' || (filter === 'active' ? status === 'active' : status !== 'active'));
	});
	adminQuery('#discount-rows').innerHTML = discounts.length ? discounts.map(discount => {
		const schedule = [discount.starts_at ? `Starts ${adminDateTime(discount.starts_at)}` : 'Starts now', discount.expires_at ? `Ends ${adminDateTime(discount.expires_at)}` : 'No expiry'].join('<br>');
		const amount = discount.discount_type === 'percentage' ? `${Number(discount.value)}%` : adminMoney(discount.value);
		return `<tr><td><strong>${adminEscape(discount.code)}</strong></td><td>${adminEscape(discount.name)}</td><td>${adminEscape(amount)} ${discount.discount_type === 'percentage' ? 'off' : 'discount'}</td><td>${schedule}</td><td>${statusPill(discountStatus(discount))}</td><td><div class="admin-row-actions"><button class="btn btn-outline" type="button" data-discount-edit="${adminEscape(discount.id)}">Edit</button><button class="btn btn-outline" type="button" data-discount-toggle="${adminEscape(discount.id)}">${discount.is_active ? 'Deactivate' : 'Activate'}</button><button class="btn btn-outline" type="button" data-discount-delete="${adminEscape(discount.id)}">Delete</button></div></td></tr>`;
	}).join('') : adminEmptyRow(6, 'No matching discounts.');
}

async function loadDiscounts() {
	const data = await adminRequest('/admin/discounts');
	adminState.discounts = data.discounts || [];
	renderDiscounts();
}

async function saveDiscount(event) {
	event.preventDefault();
	const form = event.currentTarget;
	if (!form.reportValidity()) return;
	const id = form.elements.id.value;
	const payload = {
		code: form.elements.code.value.trim().toUpperCase(),
		name: form.elements.name.value.trim(),
		discount_type: form.elements.discount_type.value,
		value: Number(form.elements.value.value),
		starts_at: form.elements.starts_at.value || null,
		expires_at: form.elements.expires_at.value || null,
		is_active: form.elements.is_active.checked
	};
	const submit = form.querySelector('[type="submit"]');
	submit.disabled = true;
	adminQuery('#discount-form-error').textContent = '';
	try {
		await adminRequest(id ? `/admin/discounts/${id}` : '/admin/discounts', id ? 'PATCH' : 'POST', payload);
		adminQuery('#discount-dialog').close();
		await loadDiscounts();
		showAdminToast(id ? 'Discount updated.' : 'Discount created.');
	} catch (error) {
		adminQuery('#discount-form-error').textContent = error.message;
	} finally {
		submit.disabled = false;
	}
}

async function toggleDiscount(id) {
	const discount = adminState.discounts.find(item => item.id === Number(id));
	if (!discount) return;
	try {
		await adminRequest(`/admin/discounts/${id}`, 'PATCH', { is_active: !discount.is_active });
		await loadDiscounts();
		showAdminToast(`Discount ${discount.is_active ? 'deactivated' : 'activated'}.`);
	} catch (error) {
		showAdminError(error.message);
	}
}

async function deleteDiscount(id) {
	const discount = adminState.discounts.find(item => item.id === Number(id));
	if (!discount || !window.confirm(`Delete discount ${discount.code}?`)) return;
	try {
		await adminRequest(`/admin/discounts/${id}`, 'DELETE');
		await loadDiscounts();
		showAdminToast('Discount deleted.');
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
		return `<tr class="${quantity <= LOW_STOCK_LIMIT ? 'admin-low-stock-row' : ''}"><td><b>${adminEscape(item.product_name)}</b></td><td>#${adminEscape(item.product_id)}</td><td>${statusPill(quantity <= LOW_STOCK_LIMIT ? 'low stock' : 'in stock')}</td><td><strong>${adminEscape(quantity)}</strong></td><td><form class="admin-inline-form" data-inventory-form="${adminEscape(item.product_id)}"><select name="operation" data-inventory-operation aria-label="Stock action for ${adminEscape(item.product_name)}"><option value="set">Set stock to</option><option value="stock_in">Stock in</option><option value="stock_out">Stock out</option></select><input aria-label="Quantity for ${adminEscape(item.product_name)}" type="number" name="quantity" min="0" step="1" value="${adminEscape(quantity)}" required><button class="btn btn-outline" type="submit">Apply</button><button class="admin-link-button" type="button" data-inventory-history="${adminEscape(item.product_id)}">History</button></form></td></tr>`;
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

async function showInventoryHistory(productId) {
	const product = adminState.inventory.find(item => item.product_id === Number(productId));
	const dialog = adminQuery('#inventory-history-dialog');
	const content = adminQuery('#inventory-history-content');
	if (!dialog || !content || !product) return;
	content.innerHTML = `<p class="eyebrow">Inventory history</p><h2>${adminEscape(product.product_name)}</h2><p class="admin-muted">Recent administrator stock adjustments.</p><div class="admin-loading" role="status">Loading stock history…</div>`;
	dialog.showModal();
	try {
		const data = await adminRequest(`/inventory/${productId}/history`);
		const entries = data.history || [];
		const history = entries.length ? entries.map(entry =>
			`<div class="admin-detail-row"><span>${adminEscape(entry.description)}<small>Admin #${adminEscape(entry.admin_user_id || '—')}</small></span><time>${adminEscape(adminDateTime(entry.created_at))}</time></div>`
		).join('') : '<p class="admin-empty">No administrator stock adjustments have been recorded.</p>';
		content.innerHTML = `<p class="eyebrow">Inventory history</p><h2>${adminEscape(product.product_name)}</h2>${history}`;
	} catch (error) {
		content.innerHTML = `<div class="admin-alert" role="alert">${adminEscape(error.message)}</div>`;
	}
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
	applyPageSearch('#customer-search');
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
	const profileName = adminQuery('[data-admin-profile-name]');
	if (profileName) profileName.textContent = data.user.name;
	const avatar = adminQuery('[data-admin-avatar]');
	if (avatar) avatar.textContent = data.user.name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
	document.querySelectorAll('[data-store-status]').forEach(element => { element.textContent = 'Online'; });
	if (adminPage === 'account') {
		adminQuery('#admin-profile-name').value = data.user.name;
		adminQuery('#admin-profile-email').value = data.user.email;
	}
}

async function loadAdminPreferences() {
	const data = await adminRequest('/users/me/preferences');
	const form = adminQuery('#admin-notification-form');
	if (!form) return;
	for (const [field, enabled] of Object.entries(data.preferences || {})) {
		const input = form.elements.namedItem(field);
		if (input) input.checked = Boolean(enabled);
	}
}

async function saveAdminPreferences(event) {
	event.preventDefault();
	const form = event.currentTarget;
	const submit = form.querySelector('[type="submit"]');
	submit.disabled = true;
	adminQuery('#admin-notification-error').textContent = '';
	try {
		const fields = ['email_order_updates', 'email_promotions', 'sms_order_updates', 'sms_promotions'];
		const preferences = Object.fromEntries(fields.map(field => [field, form.elements.namedItem(field).checked]));
		await adminRequest('/users/me/preferences', 'PATCH', preferences);
		showAdminToast('Notification preferences saved.');
	} catch (error) {
		adminQuery('#admin-notification-error').textContent = error.message;
	} finally {
		submit.disabled = false;
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
		if (adminPage === 'orders' || adminPage === 'deliveries') await loadOrders();
		if (adminPage === 'orders') {
			const orderId = new URLSearchParams(location.search).get('order');
			if (orderId && /^\d+$/.test(orderId)) await showOrderDetails(orderId);
			if (new URLSearchParams(location.search).get('create') === '1') {
				openCreateOrderDialog().catch(error => showAdminError(error.message));
			}
		}
		if (adminPage === 'inventory') await loadInventory();
		if (adminPage === 'customers') await loadCustomers();
		if (adminPage === 'reports') await loadReports();
		if (adminPage === 'discounts') await loadDiscounts();
		if (adminPage === 'account') await loadAdminPreferences();
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
	const inventoryHistory = target.closest('[data-inventory-history]');
	const pageButton = target.closest('[data-page-kind]');
	if (edit) openProductDialog(adminState.products.find(product => product.id === Number(edit.dataset.productEdit)));
	if (toggle) toggleProduct(toggle.dataset.productToggle);
	if (remove) deleteProduct(remove.dataset.productDelete);
	if (saveOrder) saveOrderStatus(saveOrder.dataset.orderSave);
	if (orderDetails) showOrderDetails(orderDetails.dataset.orderDetails);
	if (customerHistory) showCustomerHistory(customerHistory.dataset.customerHistory);
	if (inventoryHistory) showInventoryHistory(inventoryHistory.dataset.inventoryHistory);
	if (pageButton && !pageButton.disabled) {
		const kind = pageButton.dataset.pageKind;
		adminPages[kind] = Number(pageButton.dataset.page);
		if (kind === 'products') renderProducts();
		if (kind === 'orders') renderOrders();
		if (kind === 'inventory') renderInventory();
		if (kind === 'customers') renderCustomers();
	}
	if (target.closest('[data-dialog-close]')) target.closest('dialog').close();
	if (target.closest('[data-create-order]')) openCreateOrderDialog().catch(error => showAdminError(error.message));
	if (target.closest('[data-create-order-close]')) adminQuery('#create-order-dialog')?.close();
	if (target.closest('[data-add-order-item]')) addCreateOrderItem();
	if (target.closest('[data-remove-order-item]')) {
		const rows = adminQueryAll('#create-order-items .admin-create-order-item');
		if (rows.length > 1) {
			target.closest('.admin-create-order-item').remove();
			updateOrderItemControls();
			adminQuery('[data-add-order-item]').disabled = false;
		}
	}
	if (target.closest('[data-discount-create]')) openDiscountDialog();
	if (target.closest('[data-discount-cancel]')) adminQuery('#discount-dialog')?.close();
	const discountEdit = target.closest('[data-discount-edit]');
	const discountToggle = target.closest('[data-discount-toggle]');
	const discountDelete = target.closest('[data-discount-delete]');
	if (discountEdit) openDiscountDialog(adminState.discounts.find(item => item.id === Number(discountEdit.dataset.discountEdit)));
	if (discountToggle) toggleDiscount(discountToggle.dataset.discountToggle);
	if (discountDelete) deleteDiscount(discountDelete.dataset.discountDelete);
	if (target.closest('[data-export-report]')) exportDashboardReport();
});

document.addEventListener('change', event => {
	if (!event.target.matches('[data-inventory-operation]')) return;
	const quantity = event.target.closest('form').elements.quantity;
	quantity.min = event.target.value === 'set' ? '0' : '1';
	if (Number(quantity.value) < Number(quantity.min)) quantity.value = quantity.min;
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
	if (event.target.id === 'admin-notification-form') {
		saveAdminPreferences(event);
		return;
	}
	if (event.target.id === 'create-order-form') {
		saveAdminOrder(event);
		return;
	}
	if (event.target.id === 'discount-form') {
		saveDiscount(event);
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
		const formData = new FormData(form);
		const quantity = Number(formData.get('quantity'));
		const operation = String(formData.get('operation'));
		if (!Number.isSafeInteger(quantity) || quantity < 0 || (operation !== 'set' && quantity === 0)) {
			showAdminError('Enter a whole number greater than zero for stock in/out, or zero when setting stock.');
			return;
		}
		const button = form.querySelector('button');
		button.disabled = true;
		try {
			await adminRequest(`/inventory/${productId}`, 'PATCH', { operation, quantity });
			await loadInventory();
			showAdminError('');
			showAdminToast(operation === 'stock_in' ? 'Stock received.' : operation === 'stock_out' ? 'Stock removed.' : 'Inventory updated.');
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
adminQuery('#dashboard-period')?.addEventListener('change', () => loadDashboard().catch(error => showAdminError(error.message)));
adminQuery('#discount-search')?.addEventListener('input', renderDiscounts);
adminQuery('#discount-status-filter')?.addEventListener('change', renderDiscounts);
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
