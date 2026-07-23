<p align="center">
  <img width="387" height="141" src="https://github.com/stangreg/Ignitron/blob/main/resources/Ignitron_logo_large.png">
</p>

An ESP32 based foot pedal to communicate with the Spark Amp and Spark App via Bluetooth LE (iOS) and Bluetooth Serial (Android). Also works as a control device for a Looper app on the mobile. Ignitron also supports the built-in looper and additional HW presets of Spark 2.

**Ignitron has been successfully tested with**

* Spark 2
* Spark 40
* Spark Mini
* Spark GO
* **Spark NEO**

**Ignitron** gives you full control over your Spark Amp:
* Switch between the four **hardware presets**
* Switch between **custom saved presets** organized in banks
* **Toggle effects** for the selected preset
* **Save new presets** to Ignitron via the Spark App
* **Delete** stored presets
* Control the **Spark 2 internal looper**. 
* Control **Looper apps** on a mobile (actually *all* apps which support bluetooth keyboard controls)
* Use the built-in **Tuner**
* Show **Input Volume**
* Multiple BT keyboard layouts configurable

Adding new presets to **Ignitron** can easily be done as it can also act like a Spark Amp. Simply connect to **Ignitron** with the Spark App and save new presets directly from ToneCloud (or your downloaded presets) to **Ignitron**.

One big advantage of **Ignitron** is that it communicates with the Spark Amp using the **Bluetooth LE** protocol.
This means it is possible to connect your mobile to your Spark Amp as an audio speaker and play along your favorite songs while you control your effects with Ignitron.

The current active preset and effects are indicated via LEDs.\
In addition, the **built-in display** provides information on
* selected bank and preset number
* selected preset name
* operation mode (Preset, Manual/FX, Looper)
* activated pedal types in the FX chain
* Bluetooth connection status to Spark Amp and Spark App

This work was inspired by the [Sparkpal project](https://github.com/jamesguitar3/sparkpal), and the [Python Spark Parser project](https://github.com/paulhamsh/Spark-Parser) helped me to understand the messages being sent to and from the Spark Amp.

The following sections show how to [build](https://github.com/stangreg/SparkBLE#Building-Ignitron) and [operate](https://github.com/stangreg/SparkBLE#Operating-Ignitron) Ignitron.

<p align="center">
  <img src="https://github.com/stangreg/Ignitron/blob/main/resources/Ignitron_with_Spark.JPG" width=200>
  <img src="https://github.com/stangreg/Ignitron/blob/main/resources/Ignitron_preset_mode.JPG" width=200>
  <img src="https://github.com/stangreg/Ignitron/blob/main/resources/Ingitron_FX_Mode2.jpg" width=200>
  <img src="https://github.com/stangreg/Ignitron/blob/main/resources/Ignitron_full_wiring.JPG" width=200>
</p>

# Building Ignitron
Software: [click here](https://github.com/stangreg/Ignitron/blob/main/src/)

Hardware: [click here](https://github.com/stangreg/Ignitron/blob/main/hardware/)

# Operating Ignitron

## Blocking an unwanted Spark amp

If Ignitron connects to another Spark amp, press and hold `Bank Up` and
`Bank Down` together for two seconds. The display shows `AMP BLOCKED`, saves
that amp's Bluetooth address, and restarts Ignitron. Future scans ignore the
blocked amp.

To clear the saved block, hold `Bank Up` and `Bank Down` while powering on or
resetting Ignitron. Keep holding until the display shows `AMP BLOCKLIST
CLEARED`, then release both switches. Ignitron can block one amp at a time.

## Table of contents
* [Operation modes](https://github.com/stangreg/SparkBLE#operation-modes)
* [APP mode](https://github.com/stangreg/SparkBLE#app-mode)
* [Keyboard mode](https://github.com/stangreg/SparkBLE#keyboard-mode)
* [AMP mode](https://github.com/stangreg/SparkBLE#amp-mode)
  * [Storing a new preset](https://github.com/stangreg/SparkBLE#storing-a-new-preset-a-preset-from-the-app-needs-to-be-loaded)
  * [Deleting an existing preset](https://github.com/stangreg/SparkBLE#deleting-a-preset-only-possible-with-no-preset-from-the-app-loaded)
  * [Manually creating presets](https://github.com/stangreg/SparkBLE#manually-creating-presets)
    * [Preset format](https://github.com/stangreg/SparkBLE#preset-format)
    * [FX parameter reference](https://github.com/stangreg/SparkBLE#fx-parameter-reference)
* [OTA Update](https://github.com/stangreg/SparkBLE#OTA-Update)


## Operation modes
**Ignitron** has two operation modes, **APP mode** and **AMP mode**.\
In **APP mode** (default mode on startup), **Ignitron** connects to a Spark Amp and behaves like the Spark App towards the Spark Amp. It can then be used to switch between saved presets, toggle FX pedals, and even connect it to a Looper app on a mobile (providing 6 buttons to control a (looper or tabs) app).

**AMP mode** can be used to manage the presets stored on **Ignitron**, presets can be saved via the app or be deleted from **Ignitron**. For Android, the Bluetooth mode has to be set to Serial (SRL), for iOS it has to be set to BLE.\

**Keyboard mode** is useful when Ignitron should act as a bluetooth keyboard control without controlling a Spark Amp. This provides 2x6=12 buttons to control any supporting app (e.g., a looper or a tabs app).

To enter **AMP mode**, hold the `Preset 1` button during startup.
To enter **Keyboard mode**, hold the `Preset 3` button during startup.

Amp mode and Keyboard mode can best be started by holding the respective button pressed while pressing and holding `Preset 2` button to reset.

A graphical overview of all modes with button mapping can be found [here](https://github.com/stangreg/Ignitron/blob/main/resources/ignitron-cheatsheet.pdf). (Thanks to [@itarozzi](https://www.github.com/itarozzi) for creating this.)

## APP mode
In APP mode, the foot switches can be used to either switch between pre-saved presets (**Preset mode**), control all single effects in the selected preset (**Manual/FX mode**), or switch between presets while controlling an app on your mobile, e.g. a Looper app (**Looper (keyboard) mode**). If connected to a Spark 2 amp, the **Looper (amp) mode** will control the internal looper of the amp. You can easily toggle between **Preset mode** and **Manual/FX mode** by long pressing the `Bank-Up` button. To toggle between **Preset mode** and **Looper mode**, simply long-press the `Preset 4` button.

When selecting **Preset mode**, four buttons are used to select presets, the other two buttons are used to navigate through the preset banks. This way the user has access to a huge number of saved presets. When pressing the foot switch of the current active preset, the effect configured in the DRIVE section can be toggled.\
In **Manual/FX mode**, the user has direct access to all effects of the selected preset. Pressing a switch will toggle the respective FX type.\
When the **Tuner** is switched on, the output is shown on the display and the LEDs, allowing for quick tuning while connected with the amp.\
When **Looper (Keyboard) mode** is activated, Ignitron acts partially like a bluetooth keyboard. You can use the buttons to control a looper app, e.g. Loopy HD, and also switch between stored presets by long pressing the `Bank down`/`Bank up` buttons. **Note:** When switching presets in Looper mode, it will do this across banks.  
When **Looper (Amp) mode** is activated, Ignitron will control the internal looper of the Spark 2 amp. The display will also show information on the looper settings and click. The amp looper settings can easily be changed using Ignitron.

### Button commands in APP mode:

#### Preset mode
|Button      | Press pattern | Function           |
|----------- | :-----------: | ------------------ |
|`Bank down` | Short         | Navigate bank up   |
|`Bank up`   | Short         | Navigate bank down |
|`Preset 1`  | Short         | Select preset 1 / Toggle Drive |
|`Preset 2`  | Short         | Select preset 2 / Toggle Drive |
|`Preset 3`  | Short         | Select preset 3 / Toggle Drive |
|`Preset 4`  | Short         | Select preset 4 / Toggle Drive |
|`Preset 4` | Long           | Switch to Looper mode |
|`Bank down`   | Long          | Switch to Tuner mode. Short press while in Tuner mode to switch back to Preset mode.  |
|`Bank up`   | Long          | Switch to FX mode  |
|`Preset 2`  | Long          | Restart **Ignitron**  |

#### Manual/FX mode
|Button      | Press pattern | Function              |
|----------- | :-----------: | --------------------- |
|`Bank down` | Short         | Toggle Noise Gate     |
|`Bank up`   | Short         | Toggle Compressor/Wah |
|`Preset 1`  | Short         | Toggle Drive          |
|`Preset 2`  | Short         | Toggle Modulation     |
|`Preset 3`  | Short         | Toggle Delay          |
|`Preset 4`  | Short         | Toggle Reverb         |
|`Bank up`   | Long          | Switch to Preset mode |
|`Preset 2`  | Long          | Restart **Ignitron**  |

#### Looper (keyboard) mode (combined with Preset functionality)
|Button      | Press pattern | Function           |
|----------- | :-----------: | ------------------ |
|`Preset 1`  | Short         | Sends character "1" (can be freely configured in app) |
|`Preset 2`  | Short         | Sends character "2" (can be freely configured in app) |
|`Preset 3`  | Short         | Sends character "3" (can be freely configured in app) |
|`Preset 4`  | Short         | Sends character "4" (can be freely configured in app) |
|`Bank down` | Short         | Sends character "5" (can be freely configured in app) |
|`Bank up`   | Short         | Sends character "6" (can be freely configured in app) |
|`Bank down` | Long          | Switch to previous preset (across banks)  |
|`Bank up` | Long          | Switch to next preset (across banks)  |
|`Preset 4` | Long          | Switch to Preset mode |
|`Preset 2`  | Long          | Restart **Ignitron**     |

***Note:*** *In Looper mode, Ignitron is connected to your mobile as a bluetooth keyboard. If supported by the respective app on the mobile, the buttons can be freely configured to any function offered by the respective App. You may need to manually connect to the Ignitron BLE keyboard in your Bluetooth settings after switching to Looper mode.*

Example Button setup (available commands depend on availability in the respective app):
|Button      | Function           |
|----------- | ------------------ |
|`Preset 1`  | Record/overdub current track |
|`Preset 2`  | Play/pause session |
|`Preset 3`  | Delete current track (press twice) |
|`Preset 4`  | Mute current track |
|`Bank down` | Switch to previous track |
|`Bank up`   | Switch to next track |

#### Looper (amp) mode (to control the Spark 2 looper)
The preset buttons 1-3 mimick the three looper buttons on the amp, the LED status should match the LEDs on the amp.
With long pressing the `Bank up` button, Ignitron will toggle between Looper control mode and Looper config mode. The current mode will be shown by a 'L' or 'C' in the display respectively.

**Looper control mode**
|Button      | Press pattern | Function           |
|----------- | :-----------: | ------------------ |
|`Preset 1`  | Short         | Record / Dub |
|`Preset 2`  | Short         | Play / Stop |
|`Preset 3`  | Short         | Undo / Redo |
|`Preset 4`  | Short         | Read current Record status from amp (only needed for analysis) |
|`Bank down` | Short         | Tap tempo (repeatedly press button to adjust the tempo) |
|`Bank up`   | Short         | Read current looper settings from amp (only needed for analysis) |
|`Preset 3` | Long          | Delete all loops (reset)  |
|`Bank up` | Long          | Change to **Looper Config** mode  |
|`Preset 4` | Long          | Switch to Preset mode |
|`Preset 2`  | Long          | Restart **Ignitron**     |

**Looper config mode**
|Button      | Press pattern | Function           |
|----------- | :-----------: | ------------------ |
|`Preset 1`  | Short         | Change number of bars to be recorded |
|`Preset 2`  | Short         | Change feel of loop (straight / shuffle) |
|`Preset 3`  | Short         | Enable / Disable click |
|`Preset 4`  | Short         | NO FUNCTION |
|`Bank down` | Short         | Tap tempo (repeatedly press button to adjust the tempo) |
|`Bank up`   | Short         | NO FUNCTION |
|`Bank up` | Long          | Change to **Looper Control** mode  |
|`Preset 4` | Long          | Switch to Preset mode |
|`Preset 2`  | Long          | Restart **Ignitron**     |


-----------------------------------------------

## Keyboard mode
This mode will turn the Ignitron into a Bluetooth LE keyboard. All buttons will act like keyboard presses, there is no functionality regarding Preset change or other Spark Amp related functions. Use this mode if you want to only use Ignitron as a looper control device (or any other supporting app like a tabs app) . If you want to use looper control in combination with Spark Amp control, use the Looper mode as part of the APP mode (see above).
In the code, multiple different keyboard layouts can be defined to support various apps. In operations, Ignitron can switch between these keyboard with the press of a button.

Every key needs be configured with the following parameters:
- *Key ID* (1-6 for short presses, 11-14 for long presses)
- *Key code*
- *Modifier key* (Shift, CTRL, etc.)
- Key press *repetitions* (0 for single press)
- *String representation* of key in display (should only be 1 character)

In operations, when a button is pressed, the corresponding key including modifiers will be sent to the connected device. The display will show the key representations of the currently active keyboard.
The standard defined keyboard layout will send characters `1` to `6` for short presses and characters `A` to `D`for long presses.

Example:
```
{
  1,
  0xD8, // KEY_LEFT_ARROW
  0x81, // KEY_LEFT_SHIFT
  2,
  "<"
}
```
   
If a key is configured like the above, a button press will send the combination of the `LEFT SHIFT` and `LEFT ARROW` keys with 2 repetitions. In the display the key will be shown as `<`.
Long pressing `Bank down` and `Bank up` are reserved for keyboard layout switching.

Key codes for special keys can be found here: [BLE Keyboard Library](https://github.com/T-vK/ESP32-BLE-Keyboard/blob/master/BleKeyboard.h)

In keyboard mode, the following keys will be sent to the connected device:

|Button      | Press pattern | Function           |
|----------- | :-----------: | ------------------ |
|`Preset 1`  | Short         | Sends defined character (function can be freely configured in app) |
|`Preset 2`  | Short         | Sends defined character (function can be freely configured in app) |
|`Preset 3`  | Short         | Sends defined character (function can be freely configured in app) |
|`Preset 4`  | Short         | Sends defined character (function can be freely configured in app) |
|`Bank down` | Short         | Sends defined character (function can be freely configured in app) |
|`Bank up`   | Short         | Sends defined character (function can be freely configured in app) |
|`Preset 1`  | Long          | Sends defined character (function can be freely configured in app) |
|`Preset 2`  | Long          | Sends defined character (function can be freely configured in app) |
|`Preset 3`  | Long          | Sends defined character (function can be freely configured in app) |
|`Preset 4`  | Long          | Sends defined character (function can be freely configured in app) |
|`Bank down` | Long          | Switch to previous keyboard layout (cycling) |
|`Bank up`   | Long          | Switch to next keyboard layoout (cycling) |


-----------------------------------------------

## AMP mode
In AMP mode, **Ignitron** acts like a Spark AMP and can communicate with the Spark app running on a mobile. New presets can be stored on **Ignitron** and existing presets can be deleted.

### Connecting the Spark app with **Ignitron**

***Note:*** By default, Ignitron is configured to use BLE which only works with iOS. In order to connect an Android device, you need to switch to Serial Bluetooth. To do so, press and hold the `Bank Up` button when in AMP mode (after step 1. below). This will toggle the Bluetooth mode and restart **Ignitron**. After toggling the Bluetooth mode, start with step 1. below again. Ignitron persists the Bluetooth mode over restarts.  

1. Start **Ignitron** in AMP mode (hold `Preset 1` button during startup).
2. Open the Spark App on the mobile
3. For the first connection, make sure to have your real Spark Amp powered off to avoid the app connecting to it.
4. Hit the connect button in the app (or the + button in the connection overview)
5. Once the connection is established, you can give the connection a name in the app so you can distinguish from your regular Spark Amp connection.

### Storing a new preset (a preset from the app needs to be loaded)
1. Start **Ignitron** in AMP mode (hold Preset 1 button during startup).
2. Connect the Spark App with **Ignitron** (see above)
3. Select a preset in the app (either saved in the app or from ToneCloud).
4. The preset name should appear in the bottom line of the display
5. The `Preset`/`Bank` buttons on **Ignitron** can be used to navigate to the desired preset position.
6. Press the `Preset` button to mark the position for storing *(the LED of the selected preset position should start blinking)*
7. Hit the same `Preset` button a second time to confirm storage
(Hitting any other `Preset`/`Bank` button will revert the state back to navigating)
8. The preset will be saved to the selected position, other presets will be pushed one position back

#### Button commands (case: preset has been received from Spark app)
| Button     | Press pattern | Function                        | Remark |
| ---------- | :-----------: | ------------------------------- | ------ |
|`Bank down` | Short         | Navigate bank up                |        |
|`Bank up`   | Short         | Navigate bank down              |        |
|`Preset 1`  | Short         | Select preset 1                 | *Press twice to store received preset* |
|`Preset 2`  | Short         | Select preset 2                 | *Press twice to store received preset* |
|`Preset 3`  | Short         | Select preset 3                 | *Press twice to store received preset* |
|`Preset 4`  | Short         | Select preset 4                 | *Press twice to store received preset* |
|`Bank down` | Long          | Unload preset                   | *Removes loaded preset if present*     |
|`Bank up`   | Long          | Toggle Bluetooth mode                   | *Toggle between BLE and BT Serial mode*  |
|`Preset 2`  | Long          | Restart **Ignitron**                  |        |


### Deleting a preset (only possible when no preset from the app is loaded)
1. Start **Ignitron** in AMP mode (hold `Preset 1` button during startup).
2. Use the `Preset`/`Bank` buttons on **Ignitron** to navigate to the desired preset position
3. **Long press** the `Bank Down` button to mark the selected preset for deletion
4. The LED of the selected preset should start blinking
5. In the display you should see a prompt if deletion should be executed
6. If you want to cancel the deletion, simply short press any other button
7. Otherwise, **long press** the `Bank Down` button again to confirm deletion.
(Hitting any other button will cancel the deletion and return back to navigation)

#### Button commands (case: no preset has been received, slot is empty)
| Button     | Press pattern | Function                 | Remark |
| ---------- | :-----------: | ------------------------ | ------ |
|`Bank down` | Short         | Navigate bank up         |        |
|`Bank up`   | Short         | Navigate bank down       |        |
|`Preset 1`  | Short         | Select preset 1          |        |
|`Preset 2`  | Short         | Select preset 2          |        |
|`Preset 3`  | Short         | Select preset 3          |        |
|`Preset 4`  | Short         | Select preset 4          |        |
|`Bank down` | Long          | Mark preset for deletion | *Pressing any other button in that state will cancel the deletion* |
|`Bank down` | Long          | Delete marked preset     | *Only if preset was first marked for deletion* |
|`Bank up` | Long          | Toggle Bluetooth mode                   | *Toggle between BLE and BT Serial mode*  |
|`Preset 2`  | Long          | Restart **Ignitron**           |        |

-------------------------------------------------------

### Manually creating presets
*This method is only recommended if a preset cannot be transferred via the Spark app or if the preset files have been received/generated in a different way.*
1. Create a **preset file** in JSON format as shown below
2. Make sure the **file name** does not exceed 31 characters (including the `.json` suffix)
3. Put the file name into the **data folder**
4. Insert the file name (including the `.json` suffix) to the desired prefix location in the `PresetList.txt` file
5. *Place the PresetList.txt file into the data folder (if not already there)*
6. **Upload the data folder** to **Ignitron** via the Arduino IDE (or other tools)

#### Preset format
**Ignitron** stores presets in a JSON format using the SPIFFS file system.
Each preset is stored in a separate file and presets are organized in a separate text file called 'PresetList.txt'. This list simply stores the file names of the presets, the order defines the way the banks are filled.
An example preset file would look like this:
```
{"PresetNumber": 127, "UUID":"DEFBB271-B3EE-4C7E-A623-2E5CA53B6DDA",
"Name":"Studio Session" , "Version":"0.7", "Description":"Description for Acoustic Preset 1", "Icon":"icon.png", "BPM": 120.0000,
"Pedals": [
  { "Name":"bias.noisegate",  "IsOn": false,  "Parameters":[0.5000,0.3467] },
  { "Name":"BBEOpticalComp",  "IsOn": true,   "Parameters":[0.7583,0.2585,0.0000] },
  { "Name":"DistortionTS9",   "IsOn": false,  "Parameters":[0.1396,0.4073,0.6898] },
  { "Name":"Acoustic",  "IsOn": true,   "Parameters":[0.6398,0.3851,0.3834,0.5994,0.5195] },
  { "Name":"ChorusAnalog",  "IsOn": true,   "Parameters":[0.8417,0.2275,0.9359,0.3513] },
  { "Name":"DelayMono",   "IsOn": false,  "Parameters":[0.2240,0.2112,0.4909,0.6000,1.0000] },
  { "Name":"bias.reverb",   "IsOn": true,   "Parameters":[0.7228,0.3262,0.2758,0.3607,0.3439,0.4860,0.4000] } ],
"Filler":"23"
}
```

As a guidance which effect and amp names can be used and in which order the parameters of each effect have to be given, please see below.

#### FX parameter reference
In order to know which effects are available with paramters, see below table.
This data can be used to build own presets in JSON format (see above).
Use the Technical Name information in the JSON files.
Parameters marked with `Switch` can only have values of 0 or 1, others can have any value between 0 and 1.

##### Standard Tones

| Type       | App&nbsp;Name           | Technical&nbsp;Name&nbsp;(JSON)    | Parameter&nbsp;0             | Parameter&nbsp;1             | Parameter&nbsp;2         | Parameter&nbsp;3    | Parameter&nbsp;4  | Parameter&nbsp;5 | Parameter&nbsp;6         | Extra&nbsp;Info                    |
|------------|--------------------|-------------------|-------------------------|-------------------------|---------------------|----------------|--------------|-------------|---------------------|-------------------------------|
| Noise Gate | Noise Gate         | bias.noisegate    | Threshold               | Decay                   |                     |                |              |             |                     |                               |
| Compressor | LA Comp            | LA2AComp          | Limit/Compress `Switch` | Gain                    | Peak Reduction      |                |              |             |                     |                               |
| Compressor | Sustain Comp       | BlueComp          | Level                   | Tone                    | Attack              | Sustain        |              |             |                     |                               |
| Compressor | Red Comp           | Compressor        | Output                  | Sensitivity             |                     |                |              |             |                     |                               |
| Compressor | Bass Comp          | BassComp          | Comp                    | Gain                    |                     |                |              |             |                     |                               |
| Compressor | Optical Comp       | BBEOpticalComp    | Volume                  | Comp                    | Pad `Switch`        |                |              |             |                     |                               |
| Drive      | Booster            | Booster           | Gain                    |                         |                     |                |              |             |                     |                               |
| Drive      | Clone Drive        | KlonCentaurSilver | Output                  | Treble                  | Gain                |                |              |             |                     |                               |
| Drive      | Tube Drive         | DistortionTS9     | Overdrive               | Tone                    | Level               |                |              |             |                     |                               |
| Drive      | Over Drive         | Overdrive         | Level                   | Tone                    | Drive               |                |              |             |                     |                               |
| Drive      | Fuzz Face          | Fuzz              | Volume                  | Fuzz                    |                     |                |              |             |                     |                               |
| Drive      | Black Op           | ProCoRat          | Distortion              | Filter                  | Volume              |                |              |             |                     |                               |
| Drive      | Bass Muff          | BassBigMuff       | Volume                  | Tone                    | Sustain             |                |              |             |                     |                               |
| Drive      | Guitar Muff        | GuitarMuff        | Volume                  | Tone                    | Sustain             |                |              |             |                     |                               |
| Drive      | Bassmaster         | MaestroBassmaster | Brass Volume            | Sensitivity             | Bass Volume         |                |              |             |                     |                               |
| Drive      | SAB Driver         | SABDriver         | Volume                  | Tone                    | Drive               | LP/HP `Switch` |              |             |                     |                               |
| Amp        | Silver 120         | RolandJC120       | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Black Duo          | Twin              | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | AD Clean           | ADClean           | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Match DC           | 94MatchDCV2       | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | ODS 50             | ODS50CN           | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Blues Boy          | BluesJrTweed      | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Tweed Bass         | Bassman           | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | AC Boost           | AC Boost          | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Checkmate          | Checkmate         | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Two Stone SP50     | TwoStoneSP50      | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | American Deluxe    | Deluxe65          | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Plexiglas          | Plexi             | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | JM45               | OverDrivenJM45    | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Lux Verb           | OverDrivenLuxVerb | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | RB 101             | Bogner            | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | British 30         | OrangeAD30        | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | American High Gain | AmericanHighGain  | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | SLO 100            | SLO100            | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | YJM100             | YJM100            | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Treadplate         | Rectifier         | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Insane             | EVH               | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Insane 6508        | 6505Plus          | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | SwitchAxe          | SwitchAxeLead     | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Rocker V           | Invader           | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | BE 101             | BE101             | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Pure Acoustic      | Acoustic          | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Fishboy            | AcousticAmpV2     | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Jumbo              | FatAcousticV2     | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Flat Acoustic      | FlatAcoustic      | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | RB-800             | GK800             | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Sunny 3000         | Sunny3000         | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | W600               | W600              | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Amp        | Hammer 500         | Hammer500         | Gain                    | Treble                  | Middle              | Bass           | Volume       |             |                     |                               |
| Modulation | Tremolo            | Tremolo           | Speed                   | Depth                   | Level               |                |              |             |                     |                               |
| Modulation | Chorus             | ChorusAnalog      | E.Level                 | Rate                    | Depth               | Tone           |              |             |                     |                               |
| Modulation | Flanger            | Flanger           | Rate                    | Mix                     | Depth               |                |              |             |                     |                               |
| Modulation | Phaser             | Phaser            | Speed                   | Intensity               |                     |                |              |             |                     |                               |
| Modulation | Vibrato            | Vibrato01         | Speed                   | Depth                   |                     |                |              |             |                     |                               |
| Modulation | UniVibe            | UniVibe           | Speed                   | Vibrato/Chorus `Switch` | Intensity           |                |              |             |                     |                               |
| Modulation | Cloner Chorus      | Cloner            | Rate                    | Depth `Switch`          |                     |                |              |             |                     |                               |
| Modulation | Classic Vibe       | MiniVibe          | Speed                   | Intensity               |                     |                |              |             |                     |                               |
| Modulation | Tremolator         | Tremolator        | Depth                   | Speed                   | BPM On/Off `Switch` |                |              |             |                     |                               |
| Modulation | Tremolo Square     | TremoloSquare     | Speed                   | Depth                   | Level               |                |              |             |                     |                               |
| Modulation | Guitar EQ          | GuitarEQ6         | Level                   | 100                     | 200                 | 400            | 800          | 1.6k        | 3.2k                |                               |
| Modulation | Bass EQ            | BassEQ6           | Level                   | 50                      | 120                 | 400            | 800          | 4.5k        | 10k                 |                               |
| Delay      | Digital Delay      | DelayMono         | E.Level                 | Feedback                | DelayTime           | Mode           | BPM `Switch` |             |                     | Modes: 0.3 (50ms) - 0.4 (200ms) - 0.6 (500ms) - 0.72 (1s) |
| Delay      | Echo Filt          | DelayEchoFilt     | Delay                   | Feedback                | Level               | Tone           | BPM `Switch` |             |                     |                               |
| Delay      | Vintage Delay      | VintageDelay      | Repeat Rate             | Intensity               | Echo                | BPM `Switch`   |              |             |                     |                               |
| Delay      | Reverse Delay      | DelayReverse      | Mix                     | Decay                   | Filter              | Time           | BPM `Switch` |             |                     |                               |
| Delay      | Multi Head         | DelayMultiHead    | Repeat Rate             | Intensity               | Echo Volume         | Mode Selector  | BPM `Switch` |             |                     | Modes: 0 (Head 1) - 0.35 (Head 2) - 0.65 (Head 3) - 0.95 (Head 4) |
| Delay      | Echo Tape          | DelayRe201        | Sustain                 | Volume                  | Tone                | Short/Long     |              |             |                     |                               |
| Reverb     | Room Studio A      | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.0                           |
| Reverb     | Room Studio B      | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.1                           |
| Reverb     | Chamber            | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.2                           |
| Reverb     | Hall Natural       | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.3                           |
| Reverb     | Hall Medium        | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.4                           |
| Reverb     | Hall Ambient       | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.5                           |
| Reverb     | Plate Short        | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.6                           |
| Reverb     | Plate Rich         | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.7                           |
| Reverb     | Plate Long         | bias.reverb       | Level                   | Damping                 | Dwell               | Time           | Low Cut      | High Cut    | Selects Reverb Type | 0.8                           |

##### Hendrix Tones
**Note:** You can simply store tones using Hendrix gear on Ignitron. As the effects are licensed and purchased In-App, you need to connect your mobile Spark App to the Spark Amp after switching on the Spark Amp. When you then disconnect the Spark App and connect Ignitron afterwards you should be able to use presets using below gear.

| Type       | App&nbsp;Name           | Technical&nbsp;Name    | Parameter&nbsp;0             | Parameter&nbsp;1             | Parameter&nbsp;2         | Parameter&nbsp;3    | Parameter&nbsp;4  | Parameter&nbsp;5 | Parameter&nbsp;6         | Extra&nbsp;Info                    |
|------------|--------------------|-------------------|-------------------------|-------------------------|---------------------|----------------|--------------|-------------|---------------------|-------------------------------|
| Compressor/Wah | J.H. Legendary Wah         | JH.Vox846    | Auto Wah Mode               | BPM Mode `Switch`                  |  ms (BPM Off)                   | Bar (BPM On)               | Sensitivity             |             |                     | Auto Wah Mode: 0.0, 0.2, 0.4, 0.6, 0.8, 1.0 - Bar: 0.0 (1/8), 0.25 (1/4), 0.5 (1/2), 0.75 (1/1)                              |
| Drive | J.H. Axle Fuzz           | JH.AxisFuzz          | Volume | Drive                    |             |                |              |             |                     |                               |
| Drive | J.H. Super Fuzz      | JH.SupaFuzz          | Volume                   | Filter                    |               |         |              |             |                     |                               |
| Drive | J.H. Octave Fuzz           | JH.Octavia        | Level                  | Fuzz             |                     |                |              |             |                     |                               |
| Drive | J.H. Fuzz Zone          | JH.FuzzTone          | Volume                    | Attack                    |                     |                |              |             |                     |                               |
| Modulation/EQ | J.H. Legendary Vibe      | JH.VoodooVibeJr    | Speed                  | Sweep                    | Intensity        | Mix (Vibrato/Chorus)               |              |             |                     |                               |








============================================================================


<img width="1024" height="1024" alt="IPT" src="https://github.com/user-attachments/assets/232fbc66-9883-433b-a46b-68cead18deec" />

# Ignitron Preset Tools

*Shoutout to stangreg for this great project https://github.com/stangreg/Ignitron *

this program was coded 100% with chatgpt. I wanted a way to backup presets with ignitron, and struggled with pulling data back from the esp32 and converting it.  i simply asked chatgpt if it could
convert extracted raw preset data into usable .json files .  Then I just kept asking for more.

it includes the 3 standalone .exe's(preset_picker.exe, and preset_puller.exe, app_scraper.exe) which are all integrated with Ignitron Preset Tools.exe.  
To use, run  Ignitron Preset Tools.exe, which should be located inside the Ignitron Preset Tools which can be placed in the root directory of your `ignitron` folder:

```
/ignitron/Ignitron Preset Tools/ignitron_preset_tools.exe
```

To enable the Ignitron pedal to pull current pedal presets(by responding to the calls: LISTPRESETS and LISTBANKS), as well as stream presets from the app, two firmware files must be modified:

- `ignitron.ino` (main Ignitron folder) → **3 edits**  
- `SparkPresetControl.cpp` (in `/src` folder) → **1 edit**

You can either manually edit these files as described below, or replace them entirely with provided versions and update pedal-specific bits (pins, LEDs, display, etc.).

---

## A. Preset Pulling Setup  
(edit `/ignitron/ignitron.ino`)

### 1. Add this include at the top with the other libraries:
```cpp
#include <LittleFS.h>
```

---

### 2. Add this line right below `void loop()`:
```cpp
handleSerialCommands();   // so it will react to LISTPRESETS
```

---

### 3. Add the following block at the **end of the file**:
```cpp
// === BEGIN: LISTPRESETS serial support =======================================

// Case-insensitive “.json” check
static bool hasJsonExt(const char *name) {
  if (!name) return false;
  size_t len = strlen(name);
  if (len < 5) return false;
  const char *ext = name + (len - 5);
  return ext[0] == '.' &&
         (ext[1] == 'j' || ext[1] == 'J') &&
         (ext[2] == 's' || ext[2] == 'S') &&
         (ext[3] == 'o' || ext[3] == 'O') &&
         (ext[4] == 'n' || ext[4] == 'N');
}

// Dump entire JSON file to a single line (removes CR/LF/TAB)
static void printJsonFileSingleLine(File &f) {
  Serial.print("JSON STRING: ");
  while (f.available()) {
    char c = (char)f.read();
    if (c == '\r' || c == '\n' || c == '\t') continue;
    Serial.write(c);
  }
  Serial.println();
}

// List every *.json at the LittleFS root
static void listAllPresets() {
  Serial.println("LISTPRESETS_START");

  File root = LittleFS.open("/");
  if (!root) {
    Serial.println("⚠️ Could not open LittleFS root");
    Serial.println("LISTPRESETS_DONE");
    return;
  }

  while (true) {
    File f = root.openNextFile();
    if (!f) break;

    if (!f.isDirectory()) {
      const char *name = f.name();
      if (name && hasJsonExt(name)) {
        Serial.print("Reading preset filename: ");
        Serial.println(name);
        printJsonFileSingleLine(f);
      }
    }
    f.close();
  }

  Serial.println("LISTPRESETS_DONE");
}

// Robust line-buffered serial command reader
static void handleSerialCommands() {
  static String buf;

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;

    if (c == '\n') {
      String cmd = buf;
      buf = "";
      cmd.trim();
      if (cmd.length() == 0) return;

      String u = cmd;
      u.toUpperCase();

      if (u == "LISTPRESETS") {
        listAllPresets();
      }
      if (u == "LISTBANKS") {
        File f = LittleFS.open("/PresetList.txt");
        if (f) {
          Serial.println("LISTBANKS_START");
          while (f.available()) {
            char c = f.read();
            if (c == '\r') continue;
            Serial.write(c);
          }
          Serial.println("LISTBANKS_DONE");
          f.close();
        } else {
          Serial.println("⚠️ PresetList.txt not found");
          Serial.println("LISTBANKS_DONE");
        }
      }
    } else {
      buf += c;
      if (buf.length() > 256) {
        buf.remove(0, buf.length() - 256);
      }
    }
  }
}

// === END: LISTPRESETS serial support =========================================
```

---

## B. Spark App Streaming Setup  
(edit `/ignitron/src/SparkPresetControl.cpp`)

Add the following lines **after** `DEBUG_PRINTLN(appReceivedPreset_.json.c_str());` inside  
`SparkPresetControl::updateFromSparkResponseAmpPreset`:

```cpp
// 🔧 Added for App Scraper
Serial.println("received from app:");
Serial.println(appReceivedPreset_.json.c_str());
```

### Final snippet should look like:
```cpp
void SparkPresetControl::updateFromSparkResponseAmpPreset(char *presetJson) {
    presetEditMode_ = PRESET_EDIT_STORE;
    appReceivedPreset_ = presetBuilder.getPresetFromJson(presetJson);

    DEBUG_PRINTLN("received from app:");
    DEBUG_PRINTLN(appReceivedPreset_.json.c_str());

    // 🔧 Added for App Scraper
    Serial.println("received from app:");
    Serial.println(appReceivedPreset_.json.c_str());

    presetNumToEdit_ = 0;
}
```

---

## Building
After edits, **compile and flash to pedal**.  
Enjoy!

---

# Ignitron Preset Tools Operation

## Overview
- Ensure your pedal connects to your device running the Spark app (BLE or SRL). I have only tested this over SRL. 

- Preset pulling only works when the pedal is connected via USB in **AMP mode** (hold switch 1 while booting). 

-before plugging in the usb, put the pedal in AMP mode(power it on while holding switch 1) 

- Keep switch 1 pressed while the tool starts its connection. The pedal will reboot, and you can release switch 1 after the screen cycles.  

---


### Main Menu
When you run `ignitron_preset_tools.exe`, you’ll see 4 options:

```
1. Preset Picker
2. Preset Puller
3. App Scraper
4. Exit
```

### 1. Preset Picker
**DESCRIPTION:**  
Load your `/data` folder of presets, organize them in the GUI, and export the 2 files needed to build your preset banks.
<img width="1914" height="1025" alt="Screenshot 2025-09-19 185020" src="https://github.com/user-attachments/assets/c4d7df5b-296b-4690-9aad-0d835d0a1afb" />

**OPERATION:**
it starts with asking for how many banks, select 1-30.

<img width="218" height="142" alt="Screenshot 2025-09-19 184915" src="https://github.com/user-attachments/assets/3f0d051a-cc6f-4793-a56b-81f4f25aa419" />

then asks for your data folder, point it to /ignitron/data/.

<img width="779" height="498" alt="Screenshot 2025-09-19 184957" src="https://github.com/user-attachments/assets/a641fc86-161d-4f8b-95d0-d70b108447b2" />

after it opens up, you can see all presets from that folder on the left. you can then drag each preset to where you want it, if you double click it will 
add that preset to the next available slot. you can add or delete banks.  a button to fill all empty slots with random presets, will fill with unused presets from 
the left , then fill the rest with all presets in random locations to fill the grid.

when you're happy with your setup, hit the export button to update the /data/presetlist.txt, and the /data/PresetListUUIDs.txt, ready to upload to the pedal.  
Recompile and upload to the pedal and all your banks are where you put them.

it makes a presetlist.txt file like:
<img width="361" height="722" alt="Screenshot 2025-09-19 211613" src="https://github.com/user-attachments/assets/eeb15bff-ed62-4fc0-a372-c4fce5920a67" />

and the PresetListUUIDs.txt file like:
<img width="690" height="684" alt="Screenshot 2025-09-19 211746" src="https://github.com/user-attachments/assets/d68d71a6-bfbc-4f44-9d12-d7c4d5dd2ffa" />

which are formatted correctly, and directly ready to upload to your pedal upon save.  this will automatically generate a preset list grid in pdf form:

<img width="924" height="806" alt="Screenshot 2025-10-01 023755" src="https://github.com/user-attachments/assets/9145e9dc-c03a-44ba-a0f9-ead371258f86" />


---

### 2. Preset Puller
**DESCRIPTION:**

use this tool to retrieve, convert, and save presets from your ignitron pedal to your computer.  It pulls your presets saved to preset banks on the pedal, or pull all presets in the entire system.

**OPERATION:**

preset puller starts and asks pull mode:

   1. Only presets in pedal's presetlist.txt

   2. All presets on the pedal


<img width="586" height="562" alt="Screenshot 2025-09-19 204658" src="https://github.com/user-attachments/assets/3024e33a-39b6-46ba-bebe-8c331e9ccfb9" />


 it then asks for your connection port, enter the corresponding number for that port

 
<img width="578" height="187" alt="Screenshot 2025-09-19 205323" src="https://github.com/user-attachments/assets/00ef57e0-18df-4fb8-9602-a4cd8bf34267" />


 at this point, hold down switch 1 on the pedal and hit enter, keep holding 1 until you see the screen reboot and be in AMP mode(shows BLE or SRL.
 it will display the results after.  


<img width="682" height="291" alt="Screenshot 2025-09-19 210222" src="https://github.com/user-attachments/assets/655a60e7-1a0f-451e-8e2d-8049cbae2f0b" />


it will then open the save folder which should be time stamped.


<img width="959" height="860" alt="Screenshot 2025-09-19 210209" src="https://github.com/user-attachments/assets/68e1246a-3708-424e-830d-f377f69218ba" />



all these can be moved to your data folder and used with preset picker to save them to the pedal.(although they were pulled from the pedal.




---

## 3. App Scraper
**Description:**  
this tool is my favourite.  you connect to the pedal over usb, connect the app to the pedal over bluetooth, it monitors for preset chitchat, converts 
and saves selected presets to your computer. click a preset in the app, it saves directly to your computer.

**OPERATION:**

!this has only been tested with SRL not BLE!

important- before you select option 3 and hit enter for app scraper, your pedal needs to be already connected and in AMP mode.
once again, this tool you have to be holding preset 1 as you hit enter so it will save presets properly.                        

start with the pedal booted in AMP mode and connect the usb cable.  
Press and hold switch 1, enter 3 in the main menu and then hit enter. it will connect over usb, restart and boot to AMP mode. you will see the screen reset, 
release switch 1 after it reboots. it is now streaming the usb connection, waiting to convert and save preset messages


<img width="1112" height="630" alt="Screenshot 2025-09-19 222040" src="https://github.com/user-attachments/assets/29be511e-2ec0-4d07-9bcc-ca0235bc36ca" />


now open the spark app on your device, and connect to ignitron pedal.

once connected, when you select any preset in the app, it reads the request, converts it and saves it as a proper .json file on your computer.  it will
save it to a timestamped preset folder inside /ignitron preset tools with all the saved presets of that session. in this instance i clicked on the preset 
bush machinehead in my saved presets in the app.  It will also save them as you are browsing the Tone cloud in the app!  heres what it reads and outputs 
when you select a preset in the app: 


<img width="1119" height="319" alt="Screenshot 2025-09-19 222249" src="https://github.com/user-attachments/assets/68a605e7-7b73-46e1-94e2-ff6ed4336e62" />
<img width="783" height="447" alt="Screenshot 2025-09-19 223034" src="https://github.com/user-attachments/assets/49df7074-5310-4780-bfda-4b8e1eb18db4" />
<img width="407" height="858" alt="Screenshot 2025-09-19 223217" src="https://github.com/user-attachments/assets/7ace1cac-c9b9-44fc-9554-700d7a142a5c" />






