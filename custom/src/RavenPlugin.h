#pragma once

#include "QGCCorePlugin.h"
#include "QGCOptions.h"

class RavenOptions : public QGCOptions
{
    Q_OBJECT

public:
    explicit RavenOptions(QObject* parent = nullptr) : QGCOptions(parent) {}

    // The IMU's orientation is a property of the board and is built into the
    // firmware, so the sensor pages must not offer to rotate it.
    bool sensorsHaveFixedOrientation() const override { return true; }
};

class RavenPlugin : public QGCCorePlugin
{
    Q_OBJECT

public:
    explicit RavenPlugin(QObject* parent = nullptr);

    static QGCCorePlugin* instance();

    QGCOptions* options() override;

    // The firmware and vehicle type are not questions here (see
    // adjustSettingMetaData), so the first-run prompt keeps only the units.
    bool showInitialSetupVehiclePreferences() const override { return false; }

    void adjustSettingMetaData(const QString& settingsGroup, FactMetaData& metaData, bool& userVisible) override;

private:
    RavenOptions* _options = nullptr;
};
