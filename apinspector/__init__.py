"""Android Package Inspector.

A zero-dependency tool that inspects installed packages on an ADB-connected
Android device, scores each app for risk (adware / spyware / bloatware traits),
and exposes a local web UI to view, group, and manage apps in batch.

The package is organised by responsibility:

    paths       filesystem locations (project root, data, static assets)
    util        tiny shared helpers
    config      domain constants (permissions, weights, critical packages)
    adb         the ADB client
    wifi        wireless ADB (connect / Android 11+ pairing / mDNS)
    collectors  one-shot global device collectors
    parsing     per-package dumpsys parsing
    scoring     criticality, risk scoring, bloatware, report packing
    scanning    scan orchestration and streaming
    actions     freeze / unfreeze / uninstall with backend safety gates
    exporters   report.json and recommendations.txt writers
    report      console report rendering
    icons       app icon service (cache + Google Play + SVG fallback)
    web.server  local HTTP API + static UI server
    cli         argument parsing and entry-point orchestration
"""

__version__ = "2.0.0"
