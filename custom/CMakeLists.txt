# ============================================================================
# 32Raven Custom QGroundControl Build
# ============================================================================

message(STATUS "QGC: Adding 32Raven custom plugin")

list(APPEND CUSTOM_RESOURCES ${CMAKE_CURRENT_SOURCE_DIR}/resources.qrc)
set(QGC_RESOURCES ${QGC_RESOURCES} ${CUSTOM_RESOURCES} CACHE STRING "Paths to .qrc Resources" FORCE)

set(CUSTOM_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/RavenPlugin.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/src/RavenPlugin.h
    ${CMAKE_CURRENT_SOURCE_DIR}/src/AutoPilotPlugin/RavenAutoPilotPlugin.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/src/AutoPilotPlugin/RavenAutoPilotPlugin.h
    ${CMAKE_CURRENT_SOURCE_DIR}/src/FirmwarePlugin/RavenFirmwarePlugin.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/src/FirmwarePlugin/RavenFirmwarePlugin.h
    ${CMAKE_CURRENT_SOURCE_DIR}/src/FirmwarePlugin/RavenFirmwarePluginFactory.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/src/FirmwarePlugin/RavenFirmwarePluginFactory.h
    CACHE INTERNAL "" FORCE
)

set(CUSTOM_INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/AutoPilotPlugin
    ${CMAKE_CURRENT_SOURCE_DIR}/src/FirmwarePlugin
    CACHE INTERNAL "" FORCE
)

set(CUSTOM_DEFINITIONS
    QGC_CUSTOM_BUILD
    CUSTOMHEADER="RavenPlugin.h"
    CUSTOMCLASS=RavenPlugin
    CACHE INTERNAL "" FORCE
)
