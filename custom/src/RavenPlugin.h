#pragma once

#include "QGCCorePlugin.h"

class RavenPlugin : public QGCCorePlugin
{
    Q_OBJECT

public:
    explicit RavenPlugin(QObject *parent = nullptr);

    static QGCCorePlugin *instance();
};
