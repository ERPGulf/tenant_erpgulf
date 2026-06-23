app_name = "tenant_erpgulf"
app_title = "tenant_erpgulf"
app_publisher = "ERPGulf"
app_description = "Managing Real Estate company with tenant apps"
app_email = "support@erpgulf.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tenant_erpgulf",
# 		"logo": "/assets/tenant_erpgulf/logo.png",
# 		"title": "tenant_erpgulf",
# 		"route": "/tenant_erpgulf",
# 		"has_permission": "tenant_erpgulf.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tenant_erpgulf/css/tenant_erpgulf.css"
# app_include_js = "/assets/tenant_erpgulf/js/tenant_erpgulf.js"

# include js, css files in header of web template
# web_include_css = "/assets/tenant_erpgulf/css/tenant_erpgulf.css"
# web_include_js = "/assets/tenant_erpgulf/js/tenant_erpgulf.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tenant_erpgulf/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tenant_erpgulf/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "tenant_erpgulf.utils.jinja_methods",
# 	"filters": "tenant_erpgulf.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tenant_erpgulf.install.before_install"
# after_install = "tenant_erpgulf.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "tenant_erpgulf.uninstall.before_uninstall"
# after_uninstall = "tenant_erpgulf.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tenant_erpgulf.utils.before_app_install"
# after_app_install = "tenant_erpgulf.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tenant_erpgulf.utils.before_app_uninstall"
# after_app_uninstall = "tenant_erpgulf.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "tenant_erpgulf.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tenant_erpgulf.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"tenant_erpgulf.tasks.all"
# 	],
# 	"daily": [
# 		"tenant_erpgulf.tasks.daily"
# 	],
# 	"hourly": [
# 		"tenant_erpgulf.tasks.hourly"
# 	],
# 	"weekly": [
# 		"tenant_erpgulf.tasks.weekly"
# 	],
# 	"monthly": [
# 		"tenant_erpgulf.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "tenant_erpgulf.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "tenant_erpgulf.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tenant_erpgulf.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tenant_erpgulf.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tenant_erpgulf.utils.before_request"]
# after_request = ["tenant_erpgulf.utils.after_request"]

# Job Events
# ----------
# before_job = ["tenant_erpgulf.utils.before_job"]
# after_job = ["tenant_erpgulf.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"tenant_erpgulf.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

doc_events = {
    "Customer": {
        "after_insert": "tenant_erpgulf.user_qr_code.create_qr_code",
        "on_update": "tenant_erpgulf.user_qr_code.create_qr_code",
    },
    "Asset": {
        "before_save": "tenant_erpgulf.asset.before_save",
    },
    "Asset Maintenance Log": {
        "on_submit": "tenant_erpgulf.asset.on_submit",
    },
    "Employee": {
        "on_update": "tenant_erpgulf.employee.create_qr_code",
    }
}
override_doctype_class = {
    "Asset Maintenance Log": "tenant_erpgulf.asset_maintenance_log.CustomAssetMaintenanceLog"
}
doctype_js = {
    "Asset": "public/js/asset.js",
    "Asset Maintenance Log":"public/js/asset_maintenance_log.js",
    "Stock Entry":"public/js/stock_entry.js",
    "Maintenance Request":"public/js/maintenance_request.js"

}