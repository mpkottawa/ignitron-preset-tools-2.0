#define CONFIG_LITTLEFS_SPIFFS_COMPAT

#include <Arduino.h>
#include <NimBLEDevice.h>
#include <SPI.h>
#include <Wire.h>
#include <string>
#include <LittleFS.h>

#include "src/SparkButtonHandler.h"
#include "src/SparkDataControl.h"
#include "src/SparkDisplayControl.h"
#include "src/SparkLEDControl.h"
#include "src/SparkPresetControl.h"

#ifndef AMP_MODE_SWITCH_PIN
#define AMP_MODE_SWITCH_PIN 35 // External 10k pull-up to 3.3V; SPST switch to GND
#endif

using namespace std;

// Device Info Definitions
const string DEVICE_NAME = "Ignitron";

// Control classes
SparkDataControl spark_dc;
SparkButtonHandler spark_bh;
SparkLEDControl spark_led;
SparkDisplayControl sparkDisplay;
SparkPresetControl &presetControl = SparkPresetControl::getInstance();

unsigned long lastInitialPresetTimestamp = 0;
unsigned long currentTimestamp = 0;
int initialRequestInterval = 3000;

// Check for initial boot
bool isInitBoot;
OperationMode operationMode = SPARK_MODE_APP;

static void handleSerialCommands();

/////////////////////////////////////////////////////////
//
// INIT AND RUN
//
/////////////////////////////////////////////////////////

void setup() {

    Serial.begin(115200);
    while (!Serial)
        ;

    Serial.println("Initializing");
    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS Mount failed");
        return;
    }

    spark_bh.setDataControl(&spark_dc);
    operationMode = spark_bh.checkBootOperationMode();
    // Amp mode rocker on GPIO 35.
    pinMode(AMP_MODE_SWITCH_PIN, INPUT);
    int ampToggleState = digitalRead(AMP_MODE_SWITCH_PIN); // HIGH=open, LOW=closed
    if (ampToggleState == LOW) {
        operationMode = SPARK_MODE_AMP;
        Serial.println("Amp rocker ON - forcing AMP mode");
    } else {
        Serial.println("Amp rocker OFF - normal boot");
    }

    // Setting operation mode before initializing
    operationMode = spark_dc.init(operationMode);
    spark_bh.configureButtons();
    Serial.printf("Operation mode: %d\n", operationMode);

    switch (operationMode) {
    case SPARK_MODE_APP:
        Serial.println("======= Entering APP mode =======");
        break;
    case SPARK_MODE_AMP:
        Serial.println("======= Entering AMP mode =======");
        break;
    case SPARK_MODE_KEYBOARD:
        Serial.println("======= Entering Keyboard mode =======");
        break;
    }

    sparkDisplay.setDataControl(&spark_dc);
    spark_dc.setDisplayControl(&sparkDisplay);
    sparkDisplay.init(operationMode);
    spark_bh.setDataControl(&spark_dc);
    spark_led.setDataControl(&spark_dc);

    Serial.println("Initialization done.");
}

void loop() {
    handleSerialCommands();

    if (operationMode == SPARK_MODE_APP) {
        while (!(spark_dc.checkBLEConnection())) {
            handleSerialCommands();
            sparkDisplay.update(spark_dc.isInitBoot());
            spark_led.updateLEDs();
            spark_bh.readButtons();
        }

        if (spark_dc.isInitBoot()) {
            spark_dc.getSerialNumber();
            spark_dc.isInitBoot() = false;
        }
    }

    if (operationMode != SPARK_MODE_KEYBOARD) {
        spark_dc.checkForUpdates();
    }

    spark_bh.configureButtons();
    spark_bh.readButtons();
#ifdef ENABLE_BATTERY_STATUS_INDICATOR
    spark_dc.updateBatteryLevel();
#endif
    spark_led.updateLEDs();
    sparkDisplay.update();
}

// === BEGIN: Ignitron USB preset flasher serial support =======================
//
// Existing commands kept for compatibility:
//   LISTPRESETS, LISTBANKS
//
// New commands:
//   PING
//   FSINFO
//   LISTFILES
//   MIRROR ON|OFF
//   TUNERSTREAM ON|OFF
//   SELECTPRESET <bank> <preset>
//   PUTBEGIN <filename> <size> <additive-checksum-hex>
//   PUTB64 <base64 data chunk>
//   PUTEND
//   PUTABORT
//   DELETE <filename>
//   RESTART

static File uploadFile;
static String uploadPath = "";
static size_t uploadExpectedSize = 0;
static size_t uploadBytesWritten = 0;
static uint32_t uploadExpectedChecksum = 0;
static uint32_t uploadChecksum = 0;
static bool uploadActive = false;
static bool uploadError = false;

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

static void printJsonFileSingleLine(File &f) {
    Serial.print("JSON STRING: ");
    while (f.available()) {
        char c = (char)f.read();
        if (c == '\r' || c == '\n' || c == '\t') continue;
        Serial.write(c);
    }
    Serial.println();
}

static String normalizeFsPath(String name) {
    name.trim();
    name.replace("\\", "/");
    while (name.startsWith("/")) {
        name.remove(0, 1);
    }
    if (name.length() == 0 || name.indexOf("..") >= 0 || name.indexOf("/") >= 0) {
        return "";
    }
    return "/" + name;
}

static uint8_t decodeBase64Char(char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return 255;
}

static bool appendBase64Chunk(const String &encoded) {
    if (!uploadActive || uploadError || !uploadFile) {
        Serial.println("ERR NO_UPLOAD");
        return false;
    }

    uint8_t out[3];
    uint8_t values[4];
    int valueCount = 0;
    int padCount = 0;

    for (size_t i = 0; i < encoded.length(); i++) {
        char c = encoded.charAt(i);
        if (c == '=') {
            values[valueCount++] = 0;
            padCount++;
        } else {
            uint8_t decoded = decodeBase64Char(c);
            if (decoded == 255) {
                uploadError = true;
                Serial.println("ERR BAD_BASE64");
                return false;
            }
            values[valueCount++] = decoded;
        }

        if (valueCount == 4) {
            out[0] = (values[0] << 2) | (values[1] >> 4);
            out[1] = ((values[1] & 0x0f) << 4) | (values[2] >> 2);
            out[2] = ((values[2] & 0x03) << 6) | values[3];

            int bytesToWrite = 3 - padCount;
            if (uploadBytesWritten + bytesToWrite > uploadExpectedSize) {
                uploadError = true;
                Serial.println("ERR SIZE_OVERFLOW");
                return false;
            }

            size_t written = uploadFile.write(out, bytesToWrite);
            if (written != (size_t)bytesToWrite) {
                uploadError = true;
                Serial.println("ERR WRITE_FAILED");
                return false;
            }

            for (int j = 0; j < bytesToWrite; j++) {
                uploadChecksum = (uploadChecksum + out[j]) & 0xffffffff;
            }
            uploadBytesWritten += bytesToWrite;
            valueCount = 0;
            padCount = 0;
        }
    }

    if (valueCount != 0) {
        uploadError = true;
        Serial.println("ERR BAD_BASE64_LENGTH");
        return false;
    }

    Serial.printf("OK CHUNK %u\n", (unsigned int)uploadBytesWritten);
    return true;
}

static void abortUpload() {
    if (uploadFile) {
        uploadFile.close();
    }
    if (uploadPath.length() > 0) {
        LittleFS.remove(uploadPath.c_str());
    }
    uploadPath = "";
    uploadExpectedSize = 0;
    uploadBytesWritten = 0;
    uploadExpectedChecksum = 0;
    uploadChecksum = 0;
    uploadActive = false;
    uploadError = false;
    Serial.println("OK ABORT");
}

static void beginUpload(String cmd) {
    if (uploadActive) {
        Serial.println("ERR UPLOAD_ACTIVE");
        return;
    }

    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    int thirdSpace = cmd.indexOf(' ', secondSpace + 1);
    if (firstSpace < 0 || secondSpace < 0 || thirdSpace < 0) {
        Serial.println("ERR USAGE PUTBEGIN filename size checksum");
        return;
    }

    String filename = cmd.substring(firstSpace + 1, secondSpace);
    String sizeText = cmd.substring(secondSpace + 1, thirdSpace);
    String checksumText = cmd.substring(thirdSpace + 1);
    String path = normalizeFsPath(filename);
    if (path.length() == 0) {
        Serial.println("ERR BAD_FILENAME");
        return;
    }

    uploadExpectedSize = (size_t)strtoul(sizeText.c_str(), NULL, 10);
    uploadExpectedChecksum = (uint32_t)strtoul(checksumText.c_str(), NULL, 16);
    uploadBytesWritten = 0;
    uploadChecksum = 0;
    uploadError = false;
    uploadPath = path;

    if (LittleFS.exists(uploadPath.c_str())) {
        LittleFS.remove(uploadPath.c_str());
    }

    uploadFile = LittleFS.open(uploadPath.c_str(), FILE_WRITE);
    if (!uploadFile) {
        uploadPath = "";
        Serial.println("ERR OPEN_FAILED");
        return;
    }

    uploadActive = true;
    Serial.printf("OK BEGIN %s %u\n", uploadPath.c_str(), (unsigned int)uploadExpectedSize);
}

static void finishUpload() {
    if (!uploadActive) {
        Serial.println("ERR NO_UPLOAD");
        return;
    }
    if (uploadFile) {
        uploadFile.close();
    }

    if (uploadError) {
        LittleFS.remove(uploadPath.c_str());
        uploadActive = false;
        uploadPath = "";
        Serial.println("ERR UPLOAD_FAILED");
        return;
    }

    if (uploadBytesWritten != uploadExpectedSize) {
        LittleFS.remove(uploadPath.c_str());
        uploadActive = false;
        uploadPath = "";
        Serial.printf("ERR SIZE_MISMATCH %u %u\n", (unsigned int)uploadBytesWritten, (unsigned int)uploadExpectedSize);
        return;
    }

    if (uploadChecksum != uploadExpectedChecksum) {
        LittleFS.remove(uploadPath.c_str());
        uploadActive = false;
        uploadPath = "";
        Serial.printf("ERR CHECKSUM_MISMATCH %08lx %08lx\n", uploadChecksum, uploadExpectedChecksum);
        return;
    }

    Serial.printf("OK FILE %s %u %08lx\n", uploadPath.c_str(), (unsigned int)uploadBytesWritten, uploadChecksum);
    uploadActive = false;
    uploadPath = "";
}

static void listAllPresets() {
    Serial.println("LISTPRESETS_START");
    File root = LittleFS.open("/");
    if (!root) {
        Serial.println("ERR OPEN_ROOT");
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

static void listFiles() {
    Serial.println("LISTFILES_START");
    File root = LittleFS.open("/");
    if (!root) {
        Serial.println("ERR OPEN_ROOT");
        Serial.println("LISTFILES_DONE");
        return;
    }
    while (true) {
        File f = root.openNextFile();
        if (!f) break;
        if (!f.isDirectory()) {
            Serial.printf("FILE %s %u\n", f.name(), (unsigned int)f.size());
        }
        f.close();
    }
    Serial.println("LISTFILES_DONE");
}

static void printBankList() {
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
        Serial.println("ERR PresetList.txt not found");
        Serial.println("LISTBANKS_DONE");
    }
}

static void deleteFsFile(String filename) {
    String path = normalizeFsPath(filename);
    if (path.length() == 0) {
        Serial.println("ERR BAD_FILENAME");
        return;
    }
    if (LittleFS.remove(path.c_str())) {
        Serial.printf("OK DELETE %s\n", path.c_str());
    } else {
        Serial.printf("ERR DELETE_FAILED %s\n", path.c_str());
    }
}

static void printFsInfo() {
    Serial.printf("FSINFO total=%u used=%u\n", (unsigned int)LittleFS.totalBytes(), (unsigned int)LittleFS.usedBytes());
}

static void setDisplayMirror(String cmd) {
    cmd.trim();
    cmd.toUpperCase();
    bool enabled = cmd.endsWith(" ON") || cmd == "MIRROR";
    sparkDisplay.setSerialDisplayMirror(enabled);
    Serial.println(enabled ? "OK MIRROR ON" : "OK MIRROR OFF");
}

static void setTunerStream(String cmd) {
    cmd.trim();
    cmd.toUpperCase();
    bool enabled = cmd.endsWith(" ON") || cmd == "TUNERSTREAM";
    if (enabled) {
        if (spark_dc.operationMode() == SPARK_MODE_APP) {
            SparkDataControl::switchSubMode(SUB_MODE_TUNER);
        } else {
            Serial.println("ERR TUNER_REQUIRES_APP_MODE");
        }
    } else if (spark_dc.subMode() == SUB_MODE_TUNER) {
        SparkDataControl::switchSubMode(SUB_MODE_PRESET);
    }
    sparkDisplay.setSerialTunerStream(enabled);
    Serial.println(enabled ? "OK TUNERSTREAM ON" : "OK TUNERSTREAM OFF");
}

static void selectPresetFromUsb(String cmd) {
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    if (firstSpace < 0 || secondSpace < 0) {
        Serial.println("ERR USAGE SELECTPRESET bank preset");
        return;
    }

    int bank = cmd.substring(firstSpace + 1, secondSpace).toInt();
    int preset = cmd.substring(secondSpace + 1).toInt();
    if (bank < 1 || bank > presetControl.numberOfBanks() || preset < 1 || preset > PRESETS_PER_BANK) {
        Serial.println("ERR BAD_PRESET");
        return;
    }
    if (spark_dc.operationMode() != SPARK_MODE_APP) {
        Serial.println("ERR PRESET_REQUIRES_APP_MODE");
        return;
    }

    SparkDataControl::switchSubMode(SUB_MODE_PRESET);
    presetControl.setBank(bank);
    bool changed = presetControl.switchPreset(preset, false);
    Serial.printf("%s SELECTPRESET %d %d\n", changed ? "OK" : "ERR", bank, preset);
}

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

            if (u == "PING") {
                Serial.println("IGNITRON_FLASHER 1");
            } else if (u == "FSINFO") {
                printFsInfo();
            } else if (u == "LISTFILES") {
                listFiles();
            } else if (u == "LISTPRESETS") {
                listAllPresets();
            } else if (u == "LISTBANKS") {
                printBankList();
            } else if (u == "MIRROR" || u.startsWith("MIRROR ")) {
                setDisplayMirror(cmd);
            } else if (u == "TUNERSTREAM" || u.startsWith("TUNERSTREAM ")) {
                setTunerStream(cmd);
            } else if (u.startsWith("SELECTPRESET ")) {
                selectPresetFromUsb(cmd);
            } else if (u.startsWith("PUTBEGIN ")) {
                beginUpload(cmd);
            } else if (u.startsWith("PUTB64 ")) {
                appendBase64Chunk(cmd.substring(7));
            } else if (u == "PUTEND") {
                finishUpload();
            } else if (u == "PUTABORT") {
                abortUpload();
            } else if (u.startsWith("DELETE ")) {
                deleteFsFile(cmd.substring(7));
            } else if (u == "RESTART") {
                Serial.println("OK RESTART");
                delay(250);
                ESP.restart();
            }
        } else {
            buf += c;
            if (buf.length() > 1024) {
                buf = "";
                Serial.println("ERR LINE_TOO_LONG");
            }
        }
    }
}

// === END: Ignitron USB preset flasher serial support =========================
