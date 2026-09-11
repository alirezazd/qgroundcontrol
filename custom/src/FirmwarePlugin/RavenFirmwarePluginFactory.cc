#include "RavenFirmwarePluginFactory.h"
#include "RavenFirmwarePlugin.h"

RavenFirmwarePluginFactory RavenFirmwarePluginFactoryImp;

RavenFirmwarePluginFactory::RavenFirmwarePluginFactory()
{
}

QList<QGCMAVLink::FirmwareClass_t> RavenFirmwarePluginFactory::supportedFirmwareClasses() const
{
    return { QGCMAVLink::FirmwareClass32Raven };
}

FirmwarePlugin *RavenFirmwarePluginFactory::firmwarePluginForAutopilot(MAV_AUTOPILOT autopilotType, MAV_TYPE /*vehicleType*/)
{
    if (autopilotType == QGCMAVLink::firmwareClassToAutopilot(QGCMAVLink::FirmwareClass32Raven)) {
        if (!_pluginInstance) {
            _pluginInstance = new RavenFirmwarePlugin();
        }

        return _pluginInstance;
    }

    return nullptr;
}
