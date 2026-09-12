import QtQuick
import QtQuick.Controls
import QtLocation
import QtPositioning

import QGroundControl
import QGroundControl.Controls

/// Mission item map visual
Item {
    id: _root

    property var map        ///< Map control to place item in
    property var vehicle    ///< Vehicle associated with this item
    property bool interactive: true    ///< Vehicle associated with this item

    signal clicked(int sequenceNumber)

    Loader {
        id: mapVisualLoader

        asynchronous: true

        // This is a delegate, so the mission model changing takes it away --
        // at startup that happens while the visual is still incubating, and
        // Qt warns that the context went out from under an object it was
        // building. Clearing the source cancels the incubation; leaving it
        // set means the incubator is torn down mid-build instead.
        Component.onDestruction: mapVisualLoader.source = ""

        Component.onCompleted: {
            mapVisualLoader.setSource(object.mapVisualQML, {
                map: _root.map,
                vehicle: _root.vehicle,
                opacity: Qt.binding(() => _root.opacity),
                interactive: Qt.binding(() => _root.interactive)
            })
        }

        onLoaded: {
            if (!item) {
                return
            }

            item.parent = map

            if (item.clicked) {
                item.clicked.connect(_root.clicked)
            }
        }
    }
}
