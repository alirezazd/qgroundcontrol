#pragma once

#include "PX4FirmwarePlugin.h"

class RavenFirmwarePlugin : public PX4FirmwarePlugin
{
    Q_OBJECT

public:
    RavenFirmwarePlugin() = default;

    AutoPilotPlugin* autopilotPlugin(Vehicle* vehicle) const override;
    bool adjustIncomingMavlinkMessage(Vehicle* vehicle, mavlink_message_t* message) override;
    bool shouldIgnoreMissingParameter(const Vehicle* vehicle, int componentId, const QString& name) const override;

protected:
    QString _getLatestVersionFileUrl(Vehicle* vehicle) const override;
    void _versionFileDownloadFinished(const QString& remoteFile, const QString& localFile,
                                      const Vehicle* vehicle) const override;

private:
    void _handleAutopilotVersion(Vehicle* vehicle, mavlink_message_t* message) const;
};
