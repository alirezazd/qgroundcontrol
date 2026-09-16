# ============================================================================
# 32Raven Custom Build Overrides
# ============================================================================

# Upstream pins the maximum to the exact Qt it builds CI against, which rejects
# any later patch release. Widened so a distro Qt one patch ahead still
# configures; the minimum is upstream's own.
set(QGC_QT_MINIMUM_VERSION "6.11.0" CACHE STRING "Minimum Supported Qt Version" FORCE)
set(QGC_QT_MAXIMUM_VERSION "6.12.0" CACHE STRING "Maximum Supported Qt Version" FORCE)

# Custom fork branding source of truth. QGC_APP_NAME is the display name as
# well: upstream only appends " Daily" when QGC_DAILY_BUILD is defined.
set(QGC_APP_NAME "32RavenQGC" CACHE STRING "App Name" FORCE)

# The dialect that declares MAV_AUTOPILOT_32RAVEN (src/MAVLink/mavlink-32raven-dialect.patch):
# it includes everything upstream's "all" does.
set(QGC_MAVLINK_DIALECT "32raven" CACHE STRING "MAVLink dialect" FORCE)
set(QGC_ORG_NAME "32Raven" CACHE STRING "Org Name" FORCE)
set(QGC_APP_DESCRIPTION "32Raven Ground Control App" CACHE STRING "Description" FORCE)
