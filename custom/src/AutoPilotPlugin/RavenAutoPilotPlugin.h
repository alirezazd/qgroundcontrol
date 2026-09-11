#pragma once

#include "PX4AutoPilotPlugin.h"

class RavenAutoPilotPlugin : public PX4AutoPilotPlugin
{
    Q_OBJECT

public:
    RavenAutoPilotPlugin(Vehicle *vehicle, QObject *parent);
};
