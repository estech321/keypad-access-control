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
    "authorized_cards": [],
    "authorized_codes": []
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
    """Load configuration from JSON file, or create default empty config if missing."""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                raise ValueError
    except (OSError, ValueError):
        config = {}

    updated = False
    for key, default_value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = default_value
            updated = True

    if updated:
        save_config(config)

    return config


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


def unregister_card(card_id):
    """Remove an RFID card from authorized list."""
    cards = load_authorized_cards()
    if card_id in cards:
        cards.remove(card_id)
        save_authorized_cards(cards)
        return True
    return False


def load_authorized_codes():
    """Load authorized access codes from config."""
    config = load_config()
    return config.get("authorized_codes", [])


def save_authorized_codes(codes):
    """Save authorized access codes to config."""
    config = load_config()
    config["authorized_codes"] = codes
    save_config(config)


def register_new_code(code):
    """Register a new access code."""
    codes = load_authorized_codes()
    if code not in codes:
        codes.append(code)
        save_authorized_codes(codes)
        return True
    return False


def unregister_code(code):
    """Remove an access code from authorized list."""
    codes = load_authorized_codes()
    if code in codes:
        codes.remove(code)
        save_authorized_codes(codes)
        return True
    return False


def get_access_pin():
    """Get the access PIN from config."""
    config = load_config()
    return config.get("access_pin")


def get_master_pin():
    """Get the master PIN from config."""
    config = load_config()
    return config.get("master_pin")


def is_valid_access_pin(pin):
    """Return True when PIN matches the primary access PIN or any authorized code."""
    if not pin:
        return False
    config = load_config()
    access_pin = config.get("access_pin")
    authorized_codes = config.get("authorized_codes", [])
    return pin == access_pin or pin in authorized_codes


def is_config_complete(config):
    """Return True when required credentials are present in config."""
    return bool(config.get("authorized_cards")) and bool(config.get("access_pin")) and bool(config.get("master_pin"))


def enter_new_pin(prompt):
    """Prompt for a new PIN twice and confirm it."""
    while True:
        pin, terminator = enter_pin(prompt, allow_cancel=False)
        if terminator not in ("#", "*") or pin == "":
            print("PIN cannot be empty. Try again.")
            beep_invalid()
            continue

        confirm_pin, confirm_terminator = enter_pin("Confirm PIN:", allow_cancel=False)
        if pin != confirm_pin:
            print("PINs do not match. Try again.")
            beep_invalid()
            continue

        return pin


def perform_initial_setup():
    """Ensure config contains at least one card, an access PIN, and a master PIN."""
    config = load_config()

    if is_config_complete(config):
        return config

    print("Initial configuration required.")
    if not config.get("authorized_cards"):
        print("Please scan a card to register as the first authorized RFID tag.")
        while True:
            card_id = scan_rfid_card()
            if card_id is None:
                utime.sleep_ms(100)
                continue
            config["authorized_cards"] = [card_id]
            save_config(config)
            print("Registered initial RFID card:", card_id)
            beep_valid()
            blink_rgb(led_green, 2, 100)
            break

    if not config.get("access_pin"):
        config["access_pin"] = enter_new_pin("Enter new access PIN")
        save_config(config)
        print("Access PIN registered.")

    if not config.get("master_pin"):
        config["master_pin"] = enter_new_pin("Enter new master PIN")
        save_config(config)
        print("Master PIN registered.")

    return config

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
config = perform_initial_setup()
authorized_cards = config.get("authorized_cards", [])
access_pin = config.get("access_pin")
master_pin = config.get("master_pin")

print("Access control ready.")
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
                print("Master PIN accepted. Scan new RFID tag or enter code to register.")
                state = "register"
            elif terminator == "#" and pin == master_pin:
                print("Master PIN accepted. Scan RFID tag or enter code to unregister.")
                state = "unregister"
            elif terminator == "#" and is_valid_access_pin(pin):
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
        elif terminator == "#" and is_valid_access_pin(pin):
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

    elif state in ("register", "unregister"):
        action = "register" if state == "register" else "unregister"
        print("Awaiting RFID tag or code to {}...".format(action))

        while True:
            led_yellow()
            key = scan_keypad()
            new_card_id = scan_rfid_card()

            if new_card_id is not None:
                print("Card scanned:", new_card_id)
                if state == "register":
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
                else:
                    if new_card_id in authorized_cards:
                        if unregister_card(new_card_id):
                            authorized_cards = load_authorized_cards()
                            print("RFID tag unregistered:", new_card_id)
                            beep_valid()
                            blink_rgb(led_green, 2, 100)
                        else:
                            print("Failed to remove card.")
                            beep_invalid()
                    else:
                        print("This tag is not registered:", new_card_id)
                        beep_invalid()
                        blink_rgb(led_red, 2)
                break

            if key is not None:
                if key in "0123456789":
                    beep_keypress()
                    prompt = "Enter code to {} and press #:".format(action)
                    code, terminator = enter_pin(prompt, allow_cancel=True)
                    if terminator == "cancel":
                        print("{} cancelled.".format(action.capitalize()))
                        break
                    elif terminator == "#" and code != "":
                        if state == "register":
                            if register_new_code(code):
                                print("New access code registered:", code)
                                beep_valid()
                                blink_rgb(led_green, 3, 100)
                            else:
                                print("Code already registered:", code)
                                beep_invalid()
                                blink_rgb(led_red, 2)
                        else:
                            if unregister_code(code):
                                print("Access code unregistered:", code)
                                beep_valid()
                                blink_rgb(led_green, 2, 100)
                            else:
                                print("Code not found:", code)
                                beep_invalid()
                                blink_rgb(led_red, 2)
                        break
                    else:
                        print("No code entered. Returning to idle.")
                        break
                else:
                    # Ignore other non-digit key presses while waiting
                    pass

            utime.sleep_ms(100)

        state = "idle"

    else:
        state = "idle"
