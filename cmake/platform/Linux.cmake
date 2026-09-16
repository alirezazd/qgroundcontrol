# ----------------------------------------------------------------------------
# QGroundControl Linux Platform Configuration
# ----------------------------------------------------------------------------

if(NOT LINUX)
    message(FATAL_ERROR "QGC: Invalid Platform: Linux.cmake included but platform is not Linux")
endif()

# ----------------------------------------------------------------------------
# Linux-Specific Definitions
# ----------------------------------------------------------------------------
target_compile_definitions(${CMAKE_PROJECT_NAME}
    PRIVATE
        _GNU_SOURCE
)

# ----------------------------------------------------------------------------
# Linux Desktop Integration
# ----------------------------------------------------------------------------
# Desktop entry and icon files are handled by the install scripts
# See cmake/install/CreateAppImage.cmake for AppImage-specific configuration

set(CMAKE_BUILD_RPATH_USE_ORIGIN ON)

# ----------------------------------------------------------------------------
# Keep bundled static libraries out of the dynamic symbol table
# ----------------------------------------------------------------------------
# The executable links CPM-built static copies of zlib, liblzma, zstd and
# libarchive. GNU ld exports any of their symbols that a shared library on
# the link line also references, and at run time every shared library in the
# process -- libpng under Qt's image handler, libxml2, ffmpeg's swscale, Qt
# Svg -- then binds inflate()/crc32() to the bundled copy instead of the
# system one it was built against. Where the system zlib is zlib-ng (Fedora)
# that mismatch corrupts PNG decoding. Excluding the archives from export
# leaves the shared libraries bound to each other as their packager intended.
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE "LINKER:--exclude-libs,ALL")

if(NOT DEFINED QGC_LINUX_DISTRO)
    include(LinuxDistro)
endif()

message(STATUS "QGC: Linux platform configuration applied (distro: ${QGC_LINUX_DISTRO}, family: ${QGC_LINUX_DISTRO_FAMILY})")
