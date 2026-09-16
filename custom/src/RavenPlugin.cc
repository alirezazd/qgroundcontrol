#include "RavenPlugin.h"

#include <QtCore/QApplicationStatic>

#include "QGCLoggingCategory.h"

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
