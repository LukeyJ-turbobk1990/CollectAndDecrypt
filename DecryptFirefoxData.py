import hmac
import os
import sys
import json
from base64 import b64decode
from pyasn1.codec.der import decoder
from os import path
from re import compile
from sqlite3 import connect
from hashlib import sha1, pbkdf2_hmac
from binascii import unhexlify
from io import BufferedReader, BytesIO
from tempfile import NamedTemporaryFile
from Crypto.Cipher import DES3, AES
from Crypto.Util.Padding import unpad
from Crypto.Util.number import long_to_bytes

url_clean = compile(r"https?://(www\.)?")

def decryptmoz3des(global_salt: bytes, master_password: bytes, entry_salt: bytes, encrypted_data: bytes) -> bytes:
    chp = sha1(global_salt + master_password).digest() + entry_salt
    pes = entry_salt.ljust(20, b'\x00')
    k1 = hmac.new(chp, pes + entry_salt, sha1).digest()
    k2 = hmac.new(chp, pes + hmac.new(chp, pes, sha1).digest(), sha1).digest()
    key_iv = k1 + k2
    return DES3.new(key_iv[:24], DES3.MODE_CBC, key_iv[-8:]).decrypt(encrypted_data)

def get_decoded_login_data(logins_file: str) -> list:
    def decode_login_data(data: bytes) -> tuple:
        asn1data = decoder.decode(b64decode(data))
        key_id = asn1data[0][0].asOctets()
        iv = asn1data[0][1][1].asOctets()
        ciphertext = asn1data[0][2].asOctets()
        return key_id, iv, ciphertext

    logins = []

    if isinstance(logins_file, str) and logins_file.endswith('logins.json'):
        with open(logins_file, 'r') as loginf:
            json_logins = json.load(loginf)

        if 'logins' in json_logins:
            for row in json_logins['logins']:
                enc_username = row['encryptedUsername']
                enc_password = row['encryptedPassword']
                logins.append((decode_login_data(enc_username), decode_login_data(enc_password), row['hostname']))

    return logins

CKA_ID = unhexlify('f8{}1'.format('0' * 29))

def extract_secret_key(master_password, key_data) -> bytes:
    def decode_data(data):
        return decoder.decode(data)[0]

    pwd_check, global_salt = key_data[b'password-check'], key_data[b'global-salt']
    entry_salt = pwd_check[3:3 + pwd_check[1]]
    encrypted_passwd = pwd_check[-16:]
    cleartext_data = decryptmoz3des(global_salt, master_password, entry_salt, encrypted_passwd)

    if cleartext_data != b'password-check\x02\x02': raise Exception(
        "password check error, Master Password is certainly used")
    if CKA_ID not in key_data: return b''

    priv_key_entry = key_data[CKA_ID]
    salt_len, name_len = priv_key_entry[1], priv_key_entry[2]
    data = priv_key_entry[3 + salt_len + name_len:]
    entry_salt, priv_key_data = decode_data(data)[0][0][1][0].as_octets(), decode_data(data)[0][1].as_octets()
    priv_key = decryptmoz3des(global_salt, master_password, entry_salt, priv_key_data)
    key = long_to_bytes(decode_data(decode_data(priv_key)[0][2].as_octets())[0][3])

    return key

def decryptPBE(decodedItem, masterPassword, globalSalt) -> tuple:
    pbeAlgo = str(decodedItem[0][0][0])
    if pbeAlgo == '1.2.840.113549.1.5.13':
        assert str(decodedItem[0][0][1][0][0]) == '1.2.840.113549.1.5.12'
        assert str(decodedItem[0][0][1][0][1][3][0]) == '1.2.840.113549.2.9'
        assert str(decodedItem[0][0][1][1][0]) == '2.16.840.1.101.3.4.1.42'
        entrySalt = decodedItem[0][0][1][0][1][0].asOctets()
        iterationCount = int(decodedItem[0][0][1][0][1][1])
        keyLength = int(decodedItem[0][0][1][0][1][2])
        assert keyLength == 32
        k = sha1(globalSalt + masterPassword).digest()
        key = pbkdf2_hmac('sha256', k, entrySalt, iterationCount, dklen=keyLength)
        iv = b'\x04\x0e' + decodedItem[0][0][1][1][1].asOctets()
        cipherT = decodedItem[0][1].asOctets()
        clearText = AES.new(key, AES.MODE_CBC, iv).decrypt(cipherT)

        return clearText, pbeAlgo

def getKey(masterPassword: bytes, keydb: str) -> tuple:
    if isinstance(keydb, (BufferedReader, BytesIO)):
        with NamedTemporaryFile(prefix="firefox_", suffix=".key4.db", delete=False) as tmp:
            keydb.seek(0)
            tmp.write(keydb.read())
            keydb = tmp.name

    if keydb.endswith('key4.db'):
        with connect(keydb) as conn:
            c = conn.cursor()
            c.execute("SELECT item1,item2 FROM metadata WHERE id='password';")
            globalSalt, item2 = c.fetchone()
            decodedItem2 = decoder.decode(item2)
            clearText, algo = decryptPBE(decodedItem2, masterPassword, globalSalt)

            if clearText == b'password-check\x02\x02':
                c.execute("SELECT a11,a102 FROM nssPrivate;")
                a11, a102 = next((row for row in c if row[0] is not None), (None, None))

                if a102 == CKA_ID:
                    decoded_a11 = decoder.decode(a11)
                    clearText, algo = decryptPBE(decoded_a11, masterPassword, globalSalt)

                    return clearText[:24], algo

    return None, None

def DecryptLogins(loginsFile: str, keydbFile: str, masterPassword="") -> list:
    def decrypt3DES(encryptedData: bytes, key: bytes, iv: bytes) -> str:
        decrypted = unpad(DES3.new(key, DES3.MODE_CBC, iv).decrypt(encryptedData), 8)
        return decrypted.decode(errors='ignore')

    if not path.exists(loginsFile) or not path.exists(keydbFile):
        raise FileNotFoundError("Either logins.json or key4.db file does not exist!")

    key, algo = getKey(masterPassword.encode(), keydbFile)
    if key is None:
        raise Exception("Unable to retrieve key")

    logins = get_decoded_login_data(loginsFile)
    credentials = []
    supported_algorithms = ['1.2.840.113549.1.12.5.1.3', '1.2.840.113549.1.5.13']

    if algo in supported_algorithms:
        for i in logins:
            assert i[0][0] == CKA_ID
            hostname = url_clean.sub('', i[2]).strip().strip('/')
            username = decrypt3DES(i[0][2], key, i[0][1])
            password = decrypt3DES(i[1][2], key, i[1][1])
            credentials.append({
                "hostname": hostname,
                "username": username,
                "password": password
            })

    return credentials

username = os.getlogin()
browser_backups_folder = os.path.join("C:/", "Users", username, "Desktop", "Browser Backups")
if not os.path.exists(browser_backups_folder):
    print(f"Browser Backups folder not found at {browser_backups_folder}. Please ensure it exists.")
    sys.exit()

savelocation = os.path.join(browser_backups_folder, "Firefox Backup")
login_data_path = os.path.join(savelocation, "logins.json")
local_state_path = os.path.join(savelocation, "key4.db")
a = DecryptLogins(login_data_path, local_state_path, '')
decrypted_location = savelocation
output_file_path = os.path.join(decrypted_location, "decrypted_passwordsFIREFOX.txt")

if os.path.exists(login_data_path) and os.path.exists(local_state_path):
    print('Attempting to decrypt the logins.json/key4.db files...')
    print(f"logins.json path: {login_data_path}")
    print(f"key4.db path: {local_state_path}")
    print('')

with open(output_file_path, "w") as f:
    for item in a:
        output = f"URL: {item['hostname']}\nUser Name: {item['username']}\nPassword: {item['password']}\n{'*' * 50}\n"
        print(output)
        f.write(output)

print(f"Decrypted passwords saved to {output_file_path}")