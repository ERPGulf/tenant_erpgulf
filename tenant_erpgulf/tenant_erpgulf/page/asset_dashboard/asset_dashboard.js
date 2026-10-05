const MD_API = "tenant_erpgulf.tenant_erpgulf.page.asset_dashboard.asset_dashboard";
const MD_LOG = "Asset Maintenance Log";

const MD_STATUSES = [
	{ key: "New", color: "var(--md-new)" },
	{ key: "In Progress", color: "var(--md-progress)" },
	{ key: "On Hold", color: "var(--md-hold)" },
	{ key: "Completed", color: "var(--md-completed)" },
	{ key: "Unassigned", color: "var(--md-unassigned)", hatch: true },
];

const MD_DATE_RANGES = [
	{ value: "last_month", label: __("Last month") },
	{ value: "last_6_months", label: __("Last 6 months") },
	{ value: "this_month", label: __("This month") },
	{ value: "this_quarter", label: __("This quarter") },
	{ value: "this_year", label: __("This year") },
	{ value: "all", label: __("All time") },
];

frappe.pages["asset-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Maintenance Dashboard"),
		single_column: true,
	});
	wrapper.maintenance_dashboard = new MaintenanceDashboard(page);
};

frappe.pages["asset-dashboard"].on_page_show = function (wrapper) {
	wrapper.maintenance_dashboard && wrapper.maintenance_dashboard.refresh();
};

class MaintenanceDashboard {
	constructor(page) {
		this.page = page;
		this.filters = { range: "last_month", building: "", type: "" };
		this.banner_dismissed = false;
		this.make();
		this.load_buildings();
		this.sync_timer = setInterval(() => this.update_synced_label(), 30 * 1000);
	}

	make() {
		const range_options = MD_DATE_RANGES.map(
			(r) => `<option value="${r.value}">${r.label}</option>`
		).join("");

		this.update_range_labels = () => {
			const suffix = {
				this_month: moment().format("MMM YYYY"),
				last_month: moment().subtract(1, "month").format("MMM YYYY"),
			};
			this.$root.find('select[data-filter="range"] option').each((_, opt) => {
				const range = MD_DATE_RANGES.find((r) => r.value === opt.value);
				opt.textContent = suffix[opt.value] ? `${range.label} · ${suffix[opt.value]}` : range.label;
			});
		};

		this.$root = $(`
			<div class="md-root" dir="${frappe.utils.is_rtl() ? "rtl" : "ltr"}">
				<div class="md-card md-toolbar">
					<label class="md-filter">
						${frappe.utils.icon("calendar", "sm")}
						<span>${__("Date")}</span>
						<select data-filter="range">${range_options}</select>
					</label>
					<label class="md-filter">
						<span>${__("Building")}</span>
						<select data-filter="building">
							<option value="">${__("All buildings")}</option>
						</select>
					</label>
					<div class="md-segmented">
						<button data-type="" class="active">${__("All")}</button>
						<button data-type="Planned">${__("Planned")}</button>
						<button data-type="Reactive">${__("Reactive")}</button>
					</div>
					<div class="md-toolbar-end">
						<span class="md-synced"></span>
						<button class="md-icon-btn md-refresh" title="${__("Refresh")}">
							${frappe.utils.icon("refresh", "sm")}
						</button>
					</div>
				</div>
				<div class="md-banner-slot"></div>
				<div class="md-kpis"></div>
				<div class="md-grid md-status-grid"></div>
				<div class="md-grid">
					<div class="md-card md-quotations"></div>
					<div class="md-card md-duration"></div>
				</div>
			</div>
		`).appendTo(this.page.main);

		this.update_range_labels();

		this.$root.on("change", "select[data-filter]", (e) => {
			this.filters[e.target.dataset.filter] = e.target.value;
			this.refresh();
		});
		this.$root.on("click", ".md-segmented button", (e) => {
			const $btn = $(e.currentTarget);
			$btn.addClass("active").siblings().removeClass("active");
			this.filters.type = $btn.attr("data-type");
			this.refresh();
		});
		this.$root.on("click", ".md-refresh", () => this.refresh());
		this.$root.on("click", ".md-dismiss", () => {
			this.banner_dismissed = true;
			this.$root.find(".md-banner-slot").empty();
		});
		this.$root.on("click", "[data-route-type]", (e) => {
			e.preventDefault();
			this.open_list($(e.currentTarget).attr("data-route-type"));
		});
		this.$root.on("click", ".md-review", (e) => {
			e.preventDefault();
			this.open_list(this.filters.type, {
				custom_employee_work_status: ["is", "not set"],
			});
		});
	}

	load_buildings() {
		frappe.xcall(`${MD_API}.get_buildings`).then((buildings) => {
			const $select = this.$root.find('select[data-filter="building"]');
			buildings.forEach((b) => {
				const label = frappe.utils.escape_html(b.building_name || b.name);
				$select.append(
					`<option value="${frappe.utils.escape_html(b.name)}">${label}</option>`
				);
			});
		});
	}

	refresh() {
		const [from_date, to_date] = this.get_date_range();
		this.$root.addClass("md-loading");
		return frappe
			.xcall(`${MD_API}.get_dashboard_data`, {
				from_date,
				to_date,
				building: this.filters.building || null,
				maintenance_type: this.filters.type || null,
			})
			.then((data) => {
				this.data = data;
				this.last_synced = moment();
				this.render();
			})
			.finally(() => this.$root.removeClass("md-loading"));
	}

	get_date_range() {
		const today = moment();
		const fmt = (d) => d.format("YYYY-MM-DD");
		switch (this.filters.range) {
			case "this_month":
				return [fmt(today.clone().startOf("month")), fmt(today)];
			case "last_month": {
				const last = today.clone().subtract(1, "month");
				return [fmt(last.clone().startOf("month")), fmt(last.endOf("month"))];
			}
			case "this_quarter":
				return [fmt(today.clone().startOf("quarter")), fmt(today)];
			case "this_year":
				return [fmt(today.clone().startOf("year")), fmt(today)];
			case "last_6_months":
				return [fmt(today.clone().subtract(6, "months").add(1, "day")), fmt(today)];
			default:
				return [null, null];
		}
	}

	render() {
		this.render_banner();
		this.render_kpis();
		this.render_status_cards();
		this.render_quotations();
		this.render_duration();
		this.update_synced_label();
	}

	render_banner() {
		const $slot = this.$root.find(".md-banner-slot").empty();
		const { work_orders, quotations } = this.data.unassigned;
		if (this.banner_dismissed || (!work_orders && !quotations)) return;

		$slot.html(`
			<div class="md-banner">
				<span class="md-banner-icon">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
						stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
						<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
					</svg>
				</span>
				<span class="md-banner-text">
					<b>${__("{0} work orders and {1} quotations have no status.", [
						work_orders,
						quotations,
					])}</b>
					${__("They appear as Unassigned in the charts below.")}
				</span>
				<a href="#" class="md-review">${__("Review records")}</a>
				<button class="md-dismiss" title="${__("Dismiss")}">&times;</button>
			</div>
		`);
	}

	render_kpis() {
		const { status, quotations, duration } = this.data;
		const p = status.Planned.counts;
		const r = status.Reactive.counts;
		const open = (c) => c["New"] + c["In Progress"] + c["On Hold"];

		const kpis = [
			{
				label: __("Open work orders"),
				value: open(p) + open(r),
				sub: this.split_label(open(p), open(r)),
			},
			{
				label: __("Completed"),
				value: p.Completed + r.Completed,
				sub: this.split_label(p.Completed, r.Completed),
			},
			{
				label: __("Average resolution time"),
				value: this.format_hours(duration.Overall),
				sub: __("All work orders this period"),
			},
			{
				label: __("Quotes awaiting approval"),
				value: quotations.awaiting_approval,
				sub: __("Issued, not yet approved"),
			},
		];

		this.$root.find(".md-kpis").html(
			kpis
				.map(
					(k) => `
				<div class="md-card">
					<div class="md-kpi-label">${k.label}</div>
					<div class="md-kpi-value">${k.value}</div>
					<div class="md-kpi-sub">${k.sub}</div>
				</div>`
				)
				.join("")
		);
	}

	split_label(planned, reactive) {
		return `${__("{0} planned", [planned])} · ${__("{0} reactive", [reactive])}`;
	}

	render_status_cards() {
		const types = this.filters.type ? [this.filters.type] : ["Planned", "Reactive"];
		const $grid = this.$root.find(".md-status-grid");
		$grid.toggleClass("single", types.length === 1);
		$grid.html(types.map((t) => this.status_card_html(t)).join(""));
	}

	status_card_html(type) {
		const { counts, total } = this.data.status[type];
		const share = (n) => (total ? Math.round((n / total) * 100) : 0);

		const segments = MD_STATUSES.filter((s) => counts[s.key])
			.map(
				(s) => `<span class="${s.hatch ? "md-hatch" : ""}"
					style="flex:${counts[s.key]};${s.hatch ? "" : `background:${s.color}`}"
					title="${__(s.key)}: ${counts[s.key]}"></span>`
			)
			.join("");

		const rows = MD_STATUSES.map(
			(s) => `
			<tr>
				<td><span class="md-dot ${s.hatch ? "md-hatch" : ""}" style="${s.hatch ? "" : `background:${s.color}`}"></span>${__(s.key)}</td>
				<td class="num count">${counts[s.key]}</td>
				<td class="num share">${share(counts[s.key])}%</td>
			</tr>`
		).join("");

		return `
			<div class="md-card">
				<div class="md-card-head">
					<span class="md-card-title">${__("{0} maintenance", [__(type)])}</span>
					<span class="md-card-meta">${__("{0} jobs", [total])}</span>
					<a href="#" data-route-type="${type}">${__("View all")}</a>
				</div>
				<div class="md-stack">${segments}</div>
				<table class="md-table">
					<thead>
						<tr>
							<th>${__("Status")}</th>
							<th class="num">${__("Count")}</th>
							<th class="num">${__("Share")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`;
	}

	render_quotations() {
		const q = this.data.quotations;
		const stages = [
			{ label: __("Requested"), value: q.requested, color: "#b9dcd8" },
			{ label: __("Issued"), value: q.issued, color: "#7fbfb8", step: __("issued") },
			{ label: __("Approved"), value: q.approved, color: "#3d968e", step: __("approved") },
			{ label: __("Paid"), value: q.paid, color: "#0d5c5c", step: __("paid") },
		];
		const width = (n) => (q.requested ? (n / q.requested) * 100 : 0);

		const html = stages
			.map((s, i) => {
				let step = "";
				if (i < stages.length - 1) {
					const next = stages[i + 1];
					const pct = s.value ? Math.round((next.value / s.value) * 100) : 0;
					step = `<div class="md-funnel-step">↓ ${pct}% ${next.step}</div>`;
				}
				return `
					<div class="md-funnel-row">
						<span>${s.label}</span>
						<div class="md-funnel-bar">
							<span style="width:${width(s.value)}%;background:${s.color}"></span>
						</div>
						<span class="md-funnel-value">${s.value}</span>
					</div>${step}`;
			})
			.join("");

		this.$root.find(".md-quotations").html(`
			<div class="md-card-head">
				<span class="md-card-title">${__("Quotation pipeline")}</span>
				<span class="md-card-meta">${__("{0} requested", [q.requested])}</span>
			</div>
			${html}
		`);
	}

	render_duration() {
		const d = this.data.duration;
		const tiles = [
			{ label: __("Planned"), value: d.Planned },
			{ label: __("Reactive"), value: d.Reactive },
			{ label: __("Overall"), value: d.Overall, cls: "overall" },
		];

		const $card = this.$root.find(".md-duration").html(`
			<div class="md-card-head">
				<span class="md-card-title">${__("Task duration")}</span>
				<span class="md-card-meta">${__("Average per job")}</span>
			</div>
			<div class="md-duration-tiles">
				${tiles
					.map(
						(t) => `
					<div class="md-duration-tile ${t.cls || ""}">
						<div class="md-kpi-label">${t.label}</div>
						<div class="value">${this.format_hours(t.value)}</div>
					</div>`
					)
					.join("")}
			</div>
			<div class="md-trend"></div>
		`);

		const trend = this.data.trend || [];
		const $trend = $card.find(".md-trend");
		if (trend.length < 3) {
			$trend.html(`
				<div class="md-trend-empty">
					${frappe.utils.icon("chart", "md")}
					<div>${__("Monthly trend available after 3 months of data")}</div>
				</div>`);
			return;
		}

		new frappe.Chart($trend[0], {
			type: "line",
			height: 180,
			colors: ["#0d5c5c"],
			data: {
				labels: trend.map((t) => moment(t.month, "YYYY-MM").format("MMM YY")),
				datasets: [
					{ name: __("Avg hours"), values: trend.map((t) => flt(t.hours, 1)) },
				],
			},
			axisOptions: { xIsSeries: 1 },
			lineOptions: { regionFill: 1, hideDots: 0 },
			tooltipOptions: { formatTooltipY: (v) => `${v} h` },
		});
	}

	format_hours(hours) {
		return hours == null ? "–" : `${hours} h`;
	}

	update_synced_label() {
		if (!this.last_synced) return;
		this.$root
			.find(".md-synced")
			.text(__("Last synced {0}", [this.last_synced.fromNow()]));
	}

	open_list(type, extra = {}) {
		const route_options = { ...extra };
		if (type) route_options.custom_asset_maintenance_type = type;
		frappe.route_options = route_options;
		frappe.set_route("List", MD_LOG);
	}
}
