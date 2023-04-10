import os
import json
import base64
import sqlite3
import win32crypt
from Cryptodome.Cipher import AES
import shutil
import sys

def get_master_key():
    with open(os.path.join(savelocation, "Local State"), "r") as f:
        local_state = f.read()
        local_state = json.loads(local_state)
    master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    master_key = master_key[5:]
    master_key = win32crypt.CryptUnprotectData(master_key, None, None, None, 0)[1]
    return master_key

def decrypt_payload(cipher, payload):
    return cipher.decrypt(payload)

def generate_cipher(aes_key, iv):
    return AES.new(aes_key, AES.MODE_GCM, iv)

def decrypt_password(buff, master_key):
    try:
        iv = buff[3:15]
        payload = buff[15:]
        cipher = generate_cipher(master_key, iv)
        decrypted_pass = decrypt_payload(cipher, payload)
        decrypted_pass = decrypted_pass[:-16].decode()  # remove suffix bytes
        return decrypted_pass
    except Exception as e:
        return f"Exception error: {e}"

username = os.getlogin()

browser_backups_folder = os.path.join("C:/", "Users", username, "Desktop", "Browser Backups")
if not os.path.exists(browser_backups_folder):
    print(f"Browser Backups folder not found at {browser_backups_folder}. Please ensure it exists.")
    sys.exit()

savelocation = os.path.join(browser_backups_folder, "Edge Backup")

login_data_path = os.path.join(savelocation, "Login Data")
local_state_path = os.path.join(savelocation, "Local State")

decrypted_location = savelocation

if os.path.exists(login_data_path) and os.path.exists(local_state_path):
    print('Attempting to decrypt the Login Data/Local State files...')
    print(f"Login Data path: {login_data_path}")
    print(f"Local State path: {local_state_path}")
    print('')
    try:
        master_key = get_master_key()
        shutil.copy2(login_data_path, os.path.join(decrypted_location, "Loginvault.db"))
        conn = sqlite3.connect(os.path.join(decrypted_location, "Loginvault.db"))
        cursor = conn.cursor()

        output_file_path = os.path.join(decrypted_location, "decrypted_passwordsEDGE.txt")
        with open(output_file_path, "w") as f:

            cursor.execute("SELECT action_url, username_value, password_value FROM logins")
            for r in cursor.fetchall():
                url = r[0]
                username = r[1]
                encrypted_password = r[2]
                decrypted_password = decrypt_password(encrypted_password, master_key)
                if len(username) > 0:
                    output = "URL: " + url + "\nUser Name: " + username + "\nPassword: " + decrypted_password + "\n" + "*" * 50 + "\n"
                    print(output)
                    f.write(output)

            cursor.close()
            conn.close()
            os.remove(os.path.join(decrypted_location, "Loginvault.db"))
            print('Successfully decrypted the Login Data file.')
            print('')

        print(f"Decrypted passwords saved to {output_file_path}")
    except Exception as e:
        print(f"Error decrypting passwords: {e}")
else:
    print("Login Data or Local State files not found in the specified folder.")