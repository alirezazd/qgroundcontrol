#pragma once

#include "FirmwarePluginFactory.h"

class RavenFirmwarePlugin;

class RavenFirmwarePluginFactory : public FirmwarePluginFactory
{
    Q_OBJECT

public:
    RavenFirmwarePluginFactory();

    QList<QGCMAVLink::FirmwareClass_t> supportedFirmwareClasses() const final;
    FirmwarePlugin *firmwarePluginForAutopilot(MAV_AUTOPILOT autopilotType, MAV_TYPE vehicleType) final;

private:
    RavenFirmwarePlugin *_pluginInstance = nullptr;
};
