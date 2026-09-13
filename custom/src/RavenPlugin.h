#pragma once

#include "QGCCorePlugin.h"
#include "QGCOptions.h"

class RavenOptions : public QGCOptions
{
    Q_OBJECT

public:
    explicit RavenOptions(QObject *parent = nullptr) : QGCOptions(parent) {}

    // The IMU's orientation is a property of the board and is built into the
    // firmware, so the sensor pages must not offer to rotate it.
    bool sensorsHaveFixedOrientation() const override { return true; }
};

class RavenPlugin : public QGCCorePlugin
{
    Q_OBJECT

public:
    explicit RavenPlugin(QObject *parent = nullptr);

    static QGCCorePlugin *instance();

    QGCOptions *options() override;

private:
    RavenOptions *_options = nullptr;
};
