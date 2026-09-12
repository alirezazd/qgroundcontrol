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
    // Replaces PX4's dictionary rather than adding to it: CompInfoParam picks
    // one or the other, so anything absent here reaches the user as a bare
    // name. generate_param_metadata.py in the firmware tree keeps the file
    // to the parameters the bridge actually serves.
    QString _internalParameterMetaDataFile(const Vehicle* vehicle) const override
    {
        Q_UNUSED(vehicle);
        return QStringLiteral(":/FirmwarePlugin/32Raven/32RavenParameterFactMetaData.json");
    }

    QString _getLatestVersionFileUrl(Vehicle* vehicle) const override;
    void _versionFileDownloadFinished(const QString& remoteFile, const QString& localFile,
                                      const Vehicle* vehicle) const override;

private:
    void _handleAutopilotVersion(Vehicle* vehicle, mavlink_message_t* message) const;
};
