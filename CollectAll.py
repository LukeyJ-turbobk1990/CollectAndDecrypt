import os
import shutil
import json

def get_firefox_profile_path():
    try:
        profile_path = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Firefox profile path not found: {profile_path}")
        return profile_path
    except Exception as e:
        print(f"Error getting Firefox profile path: {e}")
        return

def find_firefox_profile_folder(profile_path):
    try:
        profile_folders = [folder for folder in os.listdir(profile_path) if folder.endswith(".default-release")]

        if not profile_folders:
            raise FileNotFoundError(f"No '.default-release' folder found in: {profile_path}")

        return profile_folders[0]
    except FileNotFoundError as fnfe:
        print(f"Error finding Firefox profile folder: {fnfe}")
        return
    except Exception as e:
        print(f"Unexpected error finding Firefox profile folder: {e}")
        return

def get_chrome_profile_path():
    try:
        profile_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Google", "Chrome", "User Data")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Chrome profile path not found: {profile_path}")
        return profile_path
    except Exception as e:
        print(f"Error getting Chrome profile path: {e}")
        return

def find_chrome_login_data_profile_folder(profile_path):
    try:
        local_state_path = os.path.join(profile_path, "Local State")
        if not os.path.exists(local_state_path):
            raise FileNotFoundError(f"Local State file not found at: {local_state_path}")

        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        profile = local_state.get("profile", {}).get("last_used", "")
        if not profile:
            raise ValueError("Failed to determine the last used Chrome profile.")

        return os.path.join(profile_path, profile)
    except Exception as e:
        print(f"Error finding Chrome login data profile folder: {e}")
        return

def get_edge_profile_path():
    try:
        profile_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Microsoft", "Edge", "User Data")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Edge profile path not found: {profile_path}")
        return profile_path
    except Exception as e:
        print(f"Error getting Edge profile path: {e}")
        return

def find_edge_default_profile_folder(profile_path):
    try:
        profile_folders = [folder for folder in os.listdir(profile_path) if folder.lower() == "default"]

        if not profile_folders:
            raise FileNotFoundError(f"No 'Default' folder found in: {profile_path}")

        return profile_folders[0]
    except FileNotFoundError as fnfe:
        print(f"Error finding Edge default profile folder: {fnfe}")
        return
    except Exception as e:
        print(f"Unexpected error finding Edge default profile folder: {e}")
        return

def create_backup_folder(browser):
    try:
        main_backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "Browser Backups")
        os.makedirs(main_backup_folder, exist_ok=True)

        backup_folder = os.path.join(main_backup_folder, f"{browser} Backup")
        os.makedirs(backup_folder, exist_ok=True)

        if not os.path.exists(backup_folder):
            raise FileNotFoundError(f"Failed to create backup folder: {backup_folder}")

        return backup_folder
    except FileNotFoundError as fnfe:
        print(f"Error creating backup folder: {fnfe}")
        return
    except Exception as e:
        print(f"Unexpected error creating backup folder: {e}")
        return

def copy_file_to_backup(src_path, backup_folder, filename):
    try:
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"{filename} not found at: {src_path}")

        shutil.copy(src_path, backup_folder)

        dst_path = os.path.join(backup_folder, filename)
        if not os.path.exists(dst_path):
            raise IOError(f"Failed to copy {filename} to {backup_folder}")

    except FileNotFoundError as fnfe:
        print(f"Error copying {filename} file: {fnfe}")
        return
    except IOError as ioe:
        print(f"Error copying {filename} file: {ioe}")
        return
    except Exception as e:
        print(f"Unexpected error copying {filename} file: {e}")
        return

def backup_firefox():
    firefox_profile_path = get_firefox_profile_path()
    firefox_profile_folder = find_firefox_profile_folder(firefox_profile_path)

    files_to_backup = ["key4.db", "logins.json"]
    backup_folder = create_backup_folder("Firefox")

    for filename in files_to_backup:
        src_path = os.path.join(firefox_profile_path, firefox_profile_folder, filename)
        copy_file_to_backup(src_path, backup_folder, filename)

    print(f"Firefox {files_to_backup} successfully backed up to:", backup_folder)
    print(" ")

def backup_chrome():
    chrome_profile_path = get_chrome_profile_path()
    chrome_login_data_profile_folder = find_chrome_login_data_profile_folder(chrome_profile_path)

    files_to_backup = [
        (os.path.join(chrome_profile_path, "Local State"), "Local State"),
        (os.path.join(chrome_login_data_profile_folder, "Login Data"), "Login Data"),
    ]

    backup_folder = create_backup_folder("Chrome")

    for src_path, filename in files_to_backup:
        copy_file_to_backup(src_path, backup_folder, filename)

    print(f"Chrome {[filename for _, filename in files_to_backup]} successfully backed up to:", backup_folder)
    print(" ")

def backup_edge():
    edge_profile_path = get_edge_profile_path()
    edge_default_profile_folder = find_edge_default_profile_folder(edge_profile_path)

    files_to_backup = [
        (os.path.join(edge_profile_path, "Local State"), "Local State"),
        (os.path.join(edge_profile_path, edge_default_profile_folder, "Login Data"), "Login Data"),
    ]
    backup_folder = create_backup_folder("Edge")

    for src_path, filename in files_to_backup:
        copy_file_to_backup(src_path, backup_folder, filename)

    print(f"Edge {[filename for _, filename in files_to_backup]} successfully backed up to:", backup_folder)
    print(" ")

def main():
    firefox_profile_path = get_firefox_profile_path()
    if firefox_profile_path:
        try:
            backup_firefox()
        except Exception as e:
            print(f"Error backing up Firefox: {e}")
            print("Continuing to the next browser...")
            print(" ")
    else:
        print("Firefox not installed. Continuing to the next browser...")
        print(" ")

    chrome_profile_path = get_chrome_profile_path()
    if chrome_profile_path:
        try:
            backup_chrome()
        except Exception as e:
            print(f"Error backing up Chrome: {e}")
            print("Continuing to the next browser...")
            print(" ")
    else:
        print("Chrome not installed. Continuing to the next browser...")
        print(" ")

    edge_profile_path = get_edge_profile_path()
    if edge_profile_path:
        try:
            backup_edge()
        except Exception as e:
            print(f"Error backing up Edge: {e}")
            print("Continuing to the next browser...")
            print(" ")
    else:
        print("Edge not installed. Continuing to the next browser...")
        print(" ")

if __name__ == "__main__":
    main()