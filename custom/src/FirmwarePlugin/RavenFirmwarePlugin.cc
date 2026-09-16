#include "RavenFirmwarePlugin.h"

#include <QtCore/QFile>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QRegularExpression>

#include "PX4FirmwarePlugin.h"
#include "QGCApplication.h"
#include "QGCLoggingCategory.h"
#include "RavenAutoPilotPlugin.h"
#include "Vehicle.h"

QGC_LOGGING_CATEGORY(RavenFirmwarePluginLog, "Custom.RavenFirmwarePlugin")

namespace {

constexpr int kMinimumSupportedRavenMajorVersion = 0;
constexpr int kMinimumSupportedRavenMinorVersion = 0;
constexpr int kMinimumSupportedRavenPatchVersion = 1;
// The releases API rather than the version badge: the badge follows master, so
// it names the newest commit and would report every released build as out of
// date the moment master moves. `releases/latest` is the newest published
// release and excludes drafts and prereleases on its own, which is also why
// nothing here has to recognise a marker word in the release title.
constexpr const char* kLatestRavenReleaseUrl = "https://api.github.com/repos/alirezazd/32raven/releases/latest";

QString _versionString(int major, int minor, int patch)
{
    return QStringLiteral("%1.%2.%3").arg(major).arg(minor).arg(patch);
}

bool _parseVersionString(const QString& versionString, int& major, int& minor, int& patch)
{
    const QRegularExpressionMatch match =
        QRegularExpression(QStringLiteral("^\\s*v?(\\d+)\\.(\\d+)\\.(\\d+)\\s*$")).match(versionString);
    if (!match.hasMatch()) {
        return false;
    }

    bool majorOk = false;
    bool minorOk = false;
    bool patchOk = false;

    major = match.captured(1).toInt(&majorOk);
    minor = match.captured(2).toInt(&minorOk);
    patch = match.captured(3).toInt(&patchOk);

    return majorOk && minorOk && patchOk && major <= 0xFF && minor <= 0xFF && patch <= 0xFF;
}

int _compareVersions(int leftMajor, int leftMinor, int leftPatch, int rightMajor, int rightMinor, int rightPatch)
{
    if (leftMajor != rightMajor) {
        return leftMajor < rightMajor ? -1 : 1;
    }

    if (leftMinor != rightMinor) {
        return leftMinor < rightMinor ? -1 : 1;
    }

    if (leftPatch != rightPatch) {
        return leftPatch < rightPatch ? -1 : 1;
    }

    return 0;
}

bool _isLegacyDateVersion(int major, int minor, int patch)
{
    return (major >= 20) && (major <= 99) && (minor >= 1) && (minor <= 12) && (patch >= 1) && (patch <= 31);
}

bool _isUnsupportedRavenParameter(const QString& name)
{
    return (name == QStringLiteral("RC_MAP_AUX1")) || (name == QStringLiteral("RC_MAP_AUX2"));
}

}  // namespace

AutoPilotPlugin* RavenFirmwarePlugin::autopilotPlugin(Vehicle* vehicle) const
{
    return new RavenAutoPilotPlugin(vehicle, vehicle);
}

bool RavenFirmwarePlugin::shouldIgnoreMissingParameter(const Vehicle* vehicle, int componentId,
                                                       const QString& name) const
{
    Q_UNUSED(vehicle);
    Q_UNUSED(componentId);

    return _isUnsupportedRavenParameter(name);
}

bool RavenFirmwarePlugin::adjustIncomingMavlinkMessage(Vehicle* vehicle, mavlink_message_t* message)
{
    if (message->msgid == MAVLINK_MSG_ID_AUTOPILOT_VERSION) {
        _handleAutopilotVersion(vehicle, message);
        return true;
    }

    return PX4FirmwarePlugin::adjustIncomingMavlinkMessage(vehicle, message);
}

QString RavenFirmwarePlugin::_getLatestVersionFileUrl(Vehicle* vehicle) const
{
    Q_UNUSED(vehicle);
    return QString::fromLatin1(kLatestRavenReleaseUrl);
}

void RavenFirmwarePlugin::_versionFileDownloadFinished(const QString& remoteFile, const QString& localFile,
                                                       const Vehicle* vehicle) const
{
    qCDebug(RavenFirmwarePluginLog) << "Download complete" << remoteFile << localFile;

    // Only a build cut from a release tag reports OFFICIAL; every other one
    // says DEV and has no published release to be behind. Checking anyway
    // would tell the author their bench build is out of date against the
    // release it is ahead of.
    if (vehicle->firmwareVersionType() != FIRMWARE_VERSION_TYPE_OFFICIAL) {
        qCDebug(RavenFirmwarePluginLog) << "Skipping release check for a" << vehicle->firmwareVersionTypeString()
                                        << "build";
        return;
    }

    QFile versionFile(localFile);
    if (!versionFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qCWarning(RavenFirmwarePluginLog) << "Error opening downloaded version file.";
        return;
    }

    const QJsonDocument versionDocument = QJsonDocument::fromJson(versionFile.readAll());
    if (!versionDocument.isObject()) {
        qCWarning(RavenFirmwarePluginLog) << "Unable to parse latest version payload from" << remoteFile;
        return;
    }

    const QString latestVersionString = versionDocument.object().value(QStringLiteral("tag_name")).toString().trimmed();
    if (latestVersionString.isEmpty()) {
        qCWarning(RavenFirmwarePluginLog) << "Latest release payload missing tag_name field in" << remoteFile;
        return;
    }

    int latestMajor = 0;
    int latestMinor = 0;
    int latestPatch = 0;
    if (!_parseVersionString(latestVersionString, latestMajor, latestMinor, latestPatch)) {
        qCWarning(RavenFirmwarePluginLog)
            << "Unable to parse latest version string" << latestVersionString << "from" << remoteFile;
        return;
    }

    const bool currentVersionKnown = vehicle->firmwareMajorVersion() >= 0 && vehicle->firmwareMinorVersion() >= 0 &&
                                     vehicle->firmwarePatchVersion() >= 0;
    const bool currentIsLegacyDateVersion =
        currentVersionKnown && _isLegacyDateVersion(vehicle->firmwareMajorVersion(), vehicle->firmwareMinorVersion(),
                                                    vehicle->firmwarePatchVersion());
    const bool currentIsOlder =
        currentVersionKnown ? vehicle->versionCompare(latestMajor, latestMinor, latestPatch) < 0 : true;

    if (currentIsLegacyDateVersion || currentIsOlder) {
        const QString currentVersion =
            currentVersionKnown ? _versionString(vehicle->firmwareMajorVersion(), vehicle->firmwareMinorVersion(),
                                                 vehicle->firmwarePatchVersion())
                                : QStringLiteral("unknown");
        qgcApp()->showAppMessage(tr("Vehicle is not running the latest 32Raven version. Running %1, latest is %2.")
                                     .arg(currentVersion, _versionString(latestMajor, latestMinor, latestPatch)));
    }
}

void RavenFirmwarePlugin::_handleAutopilotVersion(Vehicle* vehicle, mavlink_message_t* message) const
{
    auto* instanceData = qobject_cast<PX4FirmwarePluginInstanceData*>(vehicle->firmwarePluginInstanceData());
    if (!instanceData || instanceData->versionNotified) {
        return;
    }

    mavlink_autopilot_version_t version{};
    mavlink_msg_autopilot_version_decode(message, &version);

    bool notifyUser = false;
    int currentMajorVersion = 0;
    int currentMinorVersion = 0;
    int currentPatchVersion = 0;
    if (version.flight_sw_version != 0) {
        currentMajorVersion = static_cast<int>((version.flight_sw_version >> 24) & 0xFF);
        currentMinorVersion = static_cast<int>((version.flight_sw_version >> 16) & 0xFF);
        currentPatchVersion = static_cast<int>((version.flight_sw_version >> 8) & 0xFF);

        notifyUser = _isLegacyDateVersion(currentMajorVersion, currentMinorVersion, currentPatchVersion) ||
                     _compareVersions(currentMajorVersion, currentMinorVersion, currentPatchVersion,
                                      kMinimumSupportedRavenMajorVersion, kMinimumSupportedRavenMinorVersion,
                                      kMinimumSupportedRavenPatchVersion) < 0;
    } else {
        notifyUser = true;
    }

    if (notifyUser) {
        instanceData->versionNotified = true;
        qgcApp()->showAppMessage(
            tr("QGroundControl supports 32Raven firmware version %1 and above. You are using %2.")
                .arg(_versionString(kMinimumSupportedRavenMajorVersion, kMinimumSupportedRavenMinorVersion,
                                    kMinimumSupportedRavenPatchVersion),
                     _versionString(currentMajorVersion, currentMinorVersion, currentPatchVersion)));
    }
}
