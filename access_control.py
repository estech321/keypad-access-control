# keypad-access-control > access_control.py
# Access control system with RFID and keypad on Raspberry Pi Pico
# Eric Smith 2026-5-30 - AI Assisted Code Generation (Gemini and GitHub Copilot)

# Features:
# - RFID card detection and registration
# - Keypad PIN entry with master PIN for registration
# - RGB LED feedback for states (red=locked, yellow=awaiting PIN, green=access granted)
# - Buzzer feedback for keypresses, valid/invalid actions
# - JSON-based configuration storage for PINs and authorized cards

import machine
import utime
import json
from lib.mfrc522 import MFRC522

# --- Hardware configuration -------------------------------------------------
ROW_PINS = [9, 10, 11, 12]
COL_PINS = [13, 14, 15]

# RGB LED pins (adjust if needed)
RGB_RED_PIN = 16
RGB_GREEN_PIN = 17
RGB_BLUE_PIN = 18

# Buzzer pin with PWM capability
BUZZER_PIN = 19

# --- Access control settings ----------------------------------------------
CONFIG_FILE = "access_config.json"
DEFAULT_CONFIG = {
    "access_pin": "1234",
    "master_pin": "0000",
    "authorized_cards": [298552099]  # This will be added to the defaut config JSON file if if doesn't exist
}
MAX_PIN_LENGTH = 8

# --- Keypad layout ---------------------------------------------------------
KEY_MAP = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["*", "0", "#"]
]

# --- Setup hardware objects ------------------------------------------------
row_objects = []
for pin_number in ROW_PINS:
    pin = machine.Pin(pin_number, machine.Pin.OUT)
    pin.value(0)
    row_objects.append(pin)

col_objects = []
for pin_number in COL_PINS:
    pin = machine.Pin(pin_number, machine.Pin.IN, machine.Pin.PULL_DOWN)
    col_objects.append(pin)

# RGB LED setup with PWM
rgb_red = machine.PWM(machine.Pin(RGB_RED_PIN))
rgb_green = machine.PWM(machine.Pin(RGB_GREEN_PIN))
rgb_blue = machine.PWM(machine.Pin(RGB_BLUE_PIN))
for pwm in [rgb_red, rgb_green, rgb_blue]:
    pwm.freq(1000)
    pwm.duty_u16(0)  # Off by default

# Buzzer setup with PWM for tone generation
buzzer = machine.PWM(machine.Pin(BUZZER_PIN))
buzzer.freq(1000)
buzzer.duty_u16(0)  # Off by default

reader = MFRC522(spi_id=0, sck=2, miso=4, mosi=3, cs=1, rst=0)

# --- Storage helpers (JSON-based) ------------------------------------------

def load_config():
    """Load configuration from JSON file, or create default if not exists."""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return config
    except (OSError, ValueError):
        # File doesn't exist or is corrupted, create default
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG


def save_config(config):
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        return True
    except OSError:
        print("Error: could not write config file.")
        return False


def load_authorized_cards():
    """Load authorized RFID cards from config."""
    config = load_config()
    return config.get("authorized_cards", [])


def save_authorized_cards(cards):
    """Save authorized RFID cards to config."""
    config = load_config()
    config["authorized_cards"] = cards
    save_config(config)


def register_new_card(card_id):
    """Register a new RFID card."""
    cards = load_authorized_cards()
    if card_id not in cards:
        cards.append(card_id)
        save_authorized_cards(cards)
        return True
    return False


def get_access_pin():
    """Get the access PIN from config."""
    config = load_config()
    return config.get("access_pin", DEFAULT_CONFIG["access_pin"])


def get_master_pin():
    """Get the master PIN from config."""
    config = load_config()
    return config.get("master_pin", DEFAULT_CONFIG["master_pin"])

# --- RGB LED helpers -------------------------------------------------------

def set_rgb(red, green, blue):
    """Set RGB LED color. Values 0-255 for each channel."""
    # PWM duty is 0-65535, so scale from 0-255
    rgb_red.duty_u16(int(red * 257))
    rgb_green.duty_u16(int(green * 257))
    rgb_blue.duty_u16(int(blue * 257))


def led_red():
    """Set LED to red (locked state)."""
    set_rgb(255, 0, 0)


def led_yellow():
    """Set LED to yellow (awaiting PIN)."""
    set_rgb(255, 255, 0)


def led_green():
    """Set LED to green (access granted)."""
    set_rgb(0, 255, 0)


def led_off():
    """Turn off RGB LED."""
    set_rgb(0, 0, 0)


def blink_rgb(color_func, times=3, duration_ms=150):
    """Blink RGB LED with specified color."""
    for _ in range(times):
        color_func()
        utime.sleep_ms(duration_ms)
        led_off()
        utime.sleep_ms(duration_ms)


def rapid_blink_yellow(times=6):
    """Rapidly blink yellow LED (for registration mode)."""
    blink_rgb(led_yellow, times, 100)


# --- Buzzer helpers --------------------------------------------------------

def beep(frequency=1000, duration_ms=100):
    """Generate a beep at specified frequency."""
    buzzer.freq(frequency)
    buzzer.duty_u16(32768)  # 50% duty cycle
    utime.sleep_ms(duration_ms)
    buzzer.duty_u16(0)  # Off
    utime.sleep_ms(50)  # Brief silence


def beep_keypress():
    """High-pitched beep for keypress."""
    beep(2000, 50)


def beep_invalid():
    """Low-pitched beep for invalid PIN/card."""
    beep(500, 200)


def beep_valid():
    """Two high-pitched beeps for valid PIN/card."""
    beep(2000, 100)
    utime.sleep_ms(100)
    beep(2000, 500)


def beep_register_waiting():
    """Repetitive medium-pitched beep while waiting for card registration."""
    for _ in range(3):
        beep(1000, 150)
        utime.sleep_ms(200)

# --- Keypad helpers --------------------------------------------------------

def scan_keypad():
    for row_idx, row_pin in enumerate(row_objects):
        row_pin.value(1)
        for col_idx, col_pin in enumerate(col_objects):
            if col_pin.value() == 1:
                row_pin.value(0)
                return KEY_MAP[row_idx][col_idx]
        row_pin.value(0)
    return None


def get_key():
    last_key = None
    while True:
        key = scan_keypad()
        if key is not None and key != last_key:
            utime.sleep_ms(50)
            if scan_keypad() == key:
                while scan_keypad() == key:
                    utime.sleep_ms(20)
                return key
        last_key = key
        utime.sleep_ms(20)


def enter_pin(prompt, allow_cancel=False):
    """
    Prompt user to enter PIN.
    allow_cancel: If True, empty * or # can cancel
    Returns: (pin, terminator) where terminator is '#', '*', or 'cancel'
    """
    pin = ""
    print(prompt)
    if allow_cancel:
        print("Use digits, then # or * to submit, or empty # to cancel.")
    else:
        print("Use digits, then # to submit, or * to submit master PIN for registration.")
    
    while True:
        key = get_key()
        if key in "0123456789":
            if len(pin) < MAX_PIN_LENGTH:
                pin += key
                print("PIN:", "*" * len(pin))
                beep_keypress()
            else:
                print("PIN length limit reached.")
        elif key == "#":
            if allow_cancel and pin == "":
                print("Cancelled.")
                return "", "cancel"
            print("Submitted PIN.")
            return pin, key
        elif key == "*":
            if allow_cancel and pin == "":
                print("Cancelled.")
                return "", "cancel"
            print("Submitted PIN.")
            return pin, key

# --- RFID helpers ----------------------------------------------------------

def scan_rfid_card():
    reader.init()
    (stat, tag_type) = reader.request(reader.REQIDL)
    if stat != reader.OK:
        return None
    (stat, uid) = reader.SelectTagSN()
    if stat != reader.OK:
        return None
    return int.from_bytes(bytes(uid), "little")


# --- Main access control logic -------------------------------------------

print("Access control system starting...")
utime.sleep_ms(500)

led_red()  # Start in locked state
authorized_cards = load_authorized_cards()
access_pin = get_access_pin()
master_pin = get_master_pin()

print("Access control ready.")
print("Authorized cards:", authorized_cards)
print("")

last_detected_card = None
state = "idle"

while True:
    if state == "idle":
        led_red()  # Red when idle (locked)
        card_id = scan_rfid_card()
        key = scan_keypad()

        if key is not None:
            # User started entering a PIN - could be master or access
            beep_keypress()
            pin, terminator = enter_pin("Enter PIN:", allow_cancel=True)
            
            if terminator == "cancel":
                print("Returning to idle.")
                state = "idle"
            elif terminator == "*" and pin == master_pin:
                print("Master PIN accepted. Scan new RFID tag to register.")
                state = "register"
            elif terminator == "#" and pin == access_pin:
                print("Access PIN entered in idle. Please scan RFID card first.")
                blink_rgb(led_red, 2)
                state = "idle"
            else:
                print("Invalid PIN.")
                beep_invalid()
                blink_rgb(led_red, 4)
                state = "idle"

        elif card_id is not None and card_id != last_detected_card:
            last_detected_card = card_id
            print("RFID detected:", card_id)
            if card_id in authorized_cards:
                print("Card accepted. Please enter access PIN.")
                beep_valid()
                state = "verify_pin"
            else:
                print("Unauthorized card.")
                beep_invalid()
                blink_rgb(led_red, 4)
                state = "idle"

        elif card_id is None:
            last_detected_card = None
            utime.sleep_ms(100)

    elif state == "verify_pin":
        led_yellow()  # Yellow when waiting for PIN after valid card
        pin, terminator = enter_pin("Enter access PIN and press #:", allow_cancel=True)
        
        if terminator == "cancel":
            print("PIN entry cancelled.")
            state = "idle"
        elif terminator == "#" and pin == access_pin:
            print("Access granted. Unlocking door...")
            beep_valid()
            led_green()  # Green when access granted
            utime.sleep(5)
            blink_rgb(led_green, 2, 100)
            led_red()
            state = "idle"
        else:
            print("Access denied.")
            beep_invalid()
            blink_rgb(led_red, 4)
            state = "idle"

    elif state == "register":
        # Rapid yellow blinking to indicate registration mode
        print("Awaiting new RFID card for registration...")
        
        # Do rapid blinks while waiting
        blink_start = utime.time()
        while True:
            rapid_blink_yellow(3)
            beep_register_waiting()
            
            # Check for card during waiting
            new_card_id = scan_rfid_card()
            if new_card_id is not None:
                print("Card scanned:", new_card_id)
                break
            
            # Check for timeout or escape (optional - can add timeout here if desired)
            # For now, will continue waiting indefinitely
            utime.sleep_ms(100)
        
        # Card was scanned
        if new_card_id in authorized_cards:
            print("This tag is already registered:", new_card_id)
            beep_invalid()
            blink_rgb(led_red, 2)
        else:
            if register_new_card(new_card_id):
                authorized_cards = load_authorized_cards()
                print("New RFID tag registered:", new_card_id)
                beep_valid()
                blink_rgb(led_green, 3, 100)
            else:
                print("Failed to register card.")
                beep_invalid()
        
        state = "idle"

    else:
        state = "idle"
