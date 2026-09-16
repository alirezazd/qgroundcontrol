#include "RavenPlugin.h"

#include <QtCore/QApplicationStatic>

#include "AppSettings.h"
#include "FactMetaData.h"
#include "QGCLoggingCategory.h"
#include "QGCMAVLink.h"

QGC_LOGGING_CATEGORY(RavenPluginLog, "Custom.RavenPlugin")

Q_APPLICATION_STATIC(RavenPlugin, _ravenPluginInstance);

RavenPlugin::RavenPlugin(QObject* parent) : QGCCorePlugin(parent)
{
    qCDebug(RavenPluginLog) << this;
}

QGCCorePlugin* RavenPlugin::instance()
{
    return _ravenPluginInstance();
}

QGCOptions* RavenPlugin::options()
{
    if (!_options) {
        _options = new RavenOptions(this);
    }
    return _options;
}

// 32Raven is the only firmware this ground station is for, and it flies
// quadrotors only, so the preferences that tailor the interface to a firmware
// and vehicle type have one answer. A hidden setting is held at its default
// whatever an earlier install saved, so the first-run prompt and the General
// page stop asking. The offline plan editor's own firmware and vehicle type
// default to the same answer but stay settable: a plan file or a connected
// vehicle may still be something else.
void RavenPlugin::adjustSettingMetaData(const QString& settingsGroup, FactMetaData& metaData, bool& userVisible)
{
    QGCCorePlugin::adjustSettingMetaData(settingsGroup, metaData, userVisible);

    if (settingsGroup != AppSettings::settingsGroup) {
        return;
    }

    const QString name = metaData.name();
    if (name == AppSettings::preferredFirmwareClassName) {
        metaData.setRawDefaultValue(QGCMAVLink::FirmwareClass32Raven);
        userVisible = false;
    } else if (name == AppSettings::preferredVehicleClassName) {
        metaData.setRawDefaultValue(QGCMAVLink::VehicleClassMultiRotor);
        userVisible = false;
    } else if (name == AppSettings::offlineEditingFirmwareClassName) {
        metaData.setRawDefaultValue(QGCMAVLink::FirmwareClass32Raven);
    } else if (name == AppSettings::offlineEditingVehicleClassName) {
        metaData.setRawDefaultValue(QGCMAVLink::VehicleClassMultiRotor);
    }
}
