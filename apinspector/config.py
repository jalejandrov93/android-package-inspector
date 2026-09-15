"""Domain constants: permissions, critical packages, score weights, templates."""

from __future__ import annotations

# Dangerous runtime permissions worth surfacing. Not exhaustive by design; these
# are the ones that matter for a quick risk read.
DANGEROUS_PERMS = {
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.READ_SMS",
    "android.permission.SEND_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.READ_PHONE_STATE",
    "android.permission.CALL_PHONE",
    "android.permission.READ_CALENDAR",
    "android.permission.WRITE_CALENDAR",
    "android.permission.BODY_SENSORS",
    "android.permission.GET_ACCOUNTS",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.REQUEST_INSTALL_PACKAGES",
    "android.permission.QUERY_ALL_PACKAGES",
}

# Curated critical packages: destructive actions on these get a hard warning.
CRITICAL_PACKAGES = {
    "com.whatsapp": "WhatsApp (messaging)",
    "com.whatsapp.w4b": "WhatsApp Business",
    "org.telegram.messenger": "Telegram (messaging)",
    "com.instagram.android": "Instagram (social)",
    "com.facebook.katana": "Facebook (social)",
    "com.facebook.orca": "Messenger (messaging)",
    "com.zhiliaoapp.musically": "TikTok (social)",
    "com.snapchat.android": "Snapchat (social)",
    "com.twitter.android": "X/Twitter (social)",
    "com.google.android.gms": "Google Play Services (core)",
    "com.google.android.gsf": "Google Services Framework (core)",
    "com.android.vending": "Google Play Store (core)",
    "com.google.android.apps.messaging": "Google Messages",
    "com.microsoft.office.outlook": "Outlook (mail)",
    "com.google.android.gm": "Gmail (mail)",
    "com.linkedin.android": "LinkedIn (social)",
}

# Heuristic keywords that mark a package as likely-critical (banking / finance).
CRITICAL_KEYWORDS = (
    "bank", "banco", "bancolombia", "davivienda", "bbva", "nequi", "daviplata",
    "pay", "payment", "wallet", "billetera", "finance", "finanzas", "card",
    "visa", "mastercard", "paypal", "mercadopago", "nubank", "revolut",
    "coinbase", "binance", "crypto",
)

# Score weights (raw, max = 21 -> normalised to /100).
WEIGHTS = {
    "overlay": 3,
    "accessibility": 5,
    "boot_completed": 3,
    "foreground_service": 2,
    "internet": 1,
    "unknown_installer": 2,
    "exports_services": 2,
    "user_app": 1,
    "untrusted_signature": 2,
}
MAX_RAW = sum(WEIGHTS.values())

INSTALLER_LABELS = {
    "com.android.vending": "Play Store",
    "com.google.android.packageinstaller": "Package Installer",
    "com.android.packageinstaller": "Package Installer",
    None: "Unknown",
    "null": "Unknown",
    "": "Unknown",
}

# Paths that indicate a package shipped with the system partition.
SYSTEM_PATH_PREFIXES = (
    "/system", "/product", "/vendor", "/apex", "/system_ext", "/oem",
)

# Shell templates for the destructive actions. System apps are never uninstalled;
# freeze (disable-user) is reversible and always the preferred option.
ACTION_TEMPLATES = {
    "freeze": "pm disable-user --user 0 {pkg}",
    "unfreeze": "pm enable {pkg}",
    "uninstall": "pm uninstall --user 0 {pkg}",
}
