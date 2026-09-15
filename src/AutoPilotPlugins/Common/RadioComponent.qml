import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

import QGroundControl
import QGroundControl.FactControls
import QGroundControl.Controls
import QGroundControl.VehicleSetup

SetupPage {
    id: radioPage

    // 32Raven maps the four sticks and nothing else: every switch parameter it serves is pinned
    // at zero, so a combo for one would offer choices the vehicle refuses.
    readonly property var _switchMappingParams: {
        const activeVehicle = QGroundControl.multiVehicleManager.activeVehicle

        if (!activeVehicle || !activeVehicle.px4Firmware) {
            return 0
        }
        if (activeVehicle.ravenFirmware) {
            return []
        }

        const flaps = activeVehicle.multiRotor ? [] : [ "RC_MAP_FLAPS" ]

        return flaps.concat([ "RC_MAP_AUX1", "RC_MAP_AUX2", "RC_MAP_PARAM1", "RC_MAP_PARAM2", "RC_MAP_PARAM3", "RC_MAP_PAY_SW" ])
    }
    pageComponent: pageComponent

    Component {
        id: pageComponent

        RemoteControlCalibration {
            id: remoteControlCalibration

            useDeadband: false
            // CRSF fixes the channel range and the transmitter holds the
            // endpoints, so 32Raven has nothing to calibrate and no Spektrum
            // receiver to bind.
            calibrates: !_ravenFirmware

            readonly property bool _ravenFirmware: {
                const activeVehicle = QGroundControl.multiVehicleManager.activeVehicle
                return activeVehicle ? activeVehicle.ravenFirmware : false
            }

            controller: RadioComponentController {
                statusText: remoteControlCalibration.statusText
                cancelButton: remoteControlCalibration.cancelButton
                nextButton: remoteControlCalibration.nextButton
                joystickMode: false

                onThrottleReversedCalFailure: QGroundControl.showMessageDialog(radioPage, qsTr("Throttle channel reversed"), qsTr("Calibration failed. The throttle channel on your transmitter is reversed. You must correct this on your transmitter in order to complete calibration."))
            }

            Component.onCompleted: controller.start()

            additionalSetupComponent: ColumnLayout {
                spacing: ScreenTools.defaultFontPixelHeight / 2

                ColumnLayout {
                    id: switchSettings
                    Layout.fillWidth: true
                    visible: radioPage._switchMappingParams.length > 0

                    Repeater {
                        model: radioPage._switchMappingParams

                        LabelledFactComboBox {
                            label: fact.shortDescription
                            fact: controller.getParameterFact(-1, modelData)
                            indexModel: false
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: qgcPal.text
                    visible: switchSettings.visible
                }

                RowLayout {
                    spacing: ScreenTools.defaultFontPixelWidth

                    QGCButton {
                        id: bindButton
                        text: qsTr("Spektrum Bind")
                        visible: !remoteControlCalibration._ravenFirmware
                        onClicked: spektrumBindDialogFactory.open()
                    }

                    QGCButton {
                        text: qsTr("CRSF Bind")
                        onClicked: QGroundControl.showMessageDialog(radioPage, qsTr("CRSF Bind"),
                                                                qsTr("Click Ok to place your CRSF receiver in the bind mode."),
                                                                Dialog.Ok | Dialog.Cancel,
                                                                function() { controller.crsfBindMode() })
                    }

                    QGCButton {
                        text: qsTr("Copy Trims")
                        visible: !remoteControlCalibration._ravenFirmware
                        onClicked: QGroundControl.showMessageDialog(radioPage, qsTr("Copy Trims"),
                                                                qsTr("Center your sticks and move throttle all the way down, then press Ok to copy trims. After pressing Ok, reset the trims on your radio back to zero."),
                                                                Dialog.Ok | Dialog.Cancel,
                                                                function() { controller.copyTrims() })
                    }
                }

                QGCPopupDialogFactory {
                    id: spektrumBindDialogFactory

                    dialogComponent: spektrumBindDialogComponent
                }

                Component {
                    id: spektrumBindDialogComponent

                    QGCPopupDialog {
                        title: qsTr("Spektrum Bind")
                        buttons: Dialog.Ok | Dialog.Cancel

                        onAccepted: { controller.spektrumBindMode(radioGroup.checkedButton.bindMode) }

                        ButtonGroup { id: radioGroup }

                        ColumnLayout {
                            spacing: ScreenTools.defaultFontPixelHeight / 2

                            QGCLabel {
                                wrapMode: Text.WordWrap
                                text: qsTr("Click Ok to place your Spektrum receiver in the bind mode.")
                            }

                            QGCLabel {
                                wrapMode: Text.WordWrap
                                text: qsTr("Select the specific receiver type below:")
                            }

                            QGCRadioButton {
                                text: qsTr("DSM2 Mode")
                                ButtonGroup.group: radioGroup
                                property int bindMode: RadioComponentController.DSM2
                            }

                            QGCRadioButton {
                                text: qsTr("DSMX (7 channels or less)")
                                ButtonGroup.group: radioGroup
                                property int bindMode: RadioComponentController.DSMX7
                            }

                            QGCRadioButton {
                                checked: true
                                text: qsTr("DSMX (8 channels or more)")
                                ButtonGroup.group: radioGroup
                                property int bindMode: RadioComponentController.DSMX8
                            }
                        }
                    }
                }
            }
        }
    }
}
