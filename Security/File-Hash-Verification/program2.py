import os
import hashlib
import hmac
import sys

# Helper function to compute HMAC hash for a file
def compute_hmac(file_path, secret_key):
    hmac_hash = hmac.new(secret_key.encode(), digestmod=hashlib.sha256)
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            hmac_hash.update(chunk)
    return hmac_hash.hexdigest()

# Program 1: Generate hash values and save them to directory2
def generate_hashes(directory1, directory2, secret_key="my_secret_key"):
    if not os.path.exists(directory2):
        os.makedirs(directory2)

    for filename in os.listdir(directory1):
        file_path = os.path.join(directory1, filename)
        if os.path.isfile(file_path):
            hash_value = compute_hmac(file_path, secret_key)
            hash_file_path = os.path.join(directory2, f"{filename}-hash")
            
            with open(hash_file_path, 'w') as hash_file:
                hash_file.write(hash_value)
            print(f"Hash for {filename} saved to {hash_file_path}")

# Program 2: Verify the hashes

def verify_hashes(directory1, directory2, secret_key="my_secret_key"):
    for filename in os.listdir(directory1):
        file_path = os.path.join(directory1, filename)
        hash_file_path = os.path.join(directory2, f"{filename}-hash")

        if os.path.isfile(file_path) and os.path.isfile(hash_file_path):
            computed_hash = compute_hmac(file_path, secret_key)

            with open(hash_file_path, 'r') as hash_file:
                stored_hash = hash_file.read().strip()

            result = "YES" if computed_hash == stored_hash else "NO"
            print(f"{filename}: {result}")
        else:
            print(f"{filename}: Hash file or original file missing")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python program.py <directory1> <directory2>")
        print("Mode: verify")
        sys.exit(1)

    directory1 = sys.argv[1]
    directory2 = sys.argv[2]


    verify_hashes(directory1, directory2)